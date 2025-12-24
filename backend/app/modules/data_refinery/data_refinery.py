# backend/app/modules/data_refinery/data_refinery.py
import asyncio
import json
import pandas as pd
import numpy as np
import io
import time
import random
import os
import aiohttp
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import List, Generator
from abc import ABC, abstractmethod

# 1. 引入代理池 (用于链接验证) - 相对导入
try:
    from ..proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

# 2. 🔥 引入 AI 中枢 (用于真实 AI 分析) - 相对导入
try:
    from ...core.ai_hub import call_ai_async
except ImportError:
    call_ai_async = None

router = APIRouter(prefix="/api/refinery", tags=["refinery"])


# ==================== 1. 基础抽象层 ====================

class DataContext:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.logs: List[str] = []


class BaseProcessor(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    async def process(self, ctx: DataContext) -> Generator[str, None, None]: pass


# ==================== 2. 功能单元 ====================

class StandardCleaner(BaseProcessor):
    @property
    def name(self): return "基础清洗工"

    async def process(self, ctx: DataContext):
        yield json.dumps({"step": "clean_start", "msg": "🧹 开始基础数据清洗..."}) + "\n"
        await asyncio.sleep(0.5)

        original = len(ctx.df)
        ctx.df.dropna(how='all', inplace=True)  # 去空行

        # 智能去重
        cols = ctx.df.columns.tolist()
        subset = [c for c in ['video_url', 'url', '链接', '标题', 'title'] if c in cols]
        if subset:
            ctx.df.drop_duplicates(subset=subset, keep='first', inplace=True)
            yield json.dumps({"step": "deduplicate", "msg": f"🗑️ 依据 {subset} 去除重复数据"}) + "\n"

        ctx.df.fillna("N/A", inplace=True)  # 填补空值

        removed = original - len(ctx.df)
        yield json.dumps({
            "step": "clean_done",
            "removed": removed,
            "remaining": len(ctx.df),
            "msg": f"✅ 清洗完成：移除 {removed} 条无效数据"
        }) + "\n"


class LinkValidator(BaseProcessor):
    @property
    def name(self):
        return "网络巡检员"

    async def process(self, ctx: DataContext):
        target_col = next((c for c in ['video_url', 'url', '链接'] if c in ctx.df.columns), None)
        if not target_col:
            yield json.dumps({"step": "skip", "msg": "⏩ 未找到 URL 列，跳过网络验证"}) + "\n"
            return

        yield json.dumps({"step": "net_init", "msg": f"🌐 启动代理池，并发验证 {len(ctx.df)} 个链接..."}) + "\n"

        chain = []
        if pool_manager: chain = pool_manager.get_standard_chain()
        chain.append((None, "Direct", 5))

        async def check_url(url, row_idx):
            if not str(url).startswith('http'): return row_idx, "Invalid"
            proxy_url, _, _ = random.choice(chain)
            try:
                conn = aiohttp.ProxyConnector.from_url(proxy_url) if proxy_url else None
                async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=8)) as sess:
                    async with sess.head(url, allow_redirects=True) as resp:
                        return row_idx, "Alive" if resp.status < 400 else f"Dead ({resp.status})"
            except:
                return row_idx, "Timeout"

        tasks = []
        results = []
        sem = asyncio.Semaphore(20)  # 限制并发

        async def worker(u, i):
            async with sem: return await check_url(u, i)

        for idx, row in ctx.df.iterrows():
            tasks.append(worker(row[target_col], idx))

        processed = 0
        total = len(tasks)

        for f in asyncio.as_completed(tasks):
            res = await f
            results.append(res)
            processed += 1
            if processed % 5 == 0:
                prog = int((processed / total) * 100)
                yield json.dumps(
                    {"step": "validating", "progress": prog, "msg": f"验证中... {processed}/{total}"}) + "\n"

        status_map = {r[0]: r[1] for r in results}
        ctx.df['Link_Status'] = ctx.df.index.map(status_map)
        yield json.dumps({"step": "validate_done", "msg": "✅ 网络验证结束"}) + "\n"


class AISentimentAnalyst(BaseProcessor):
    @property
    def name(self):
        return "AI 炼金术师 (Real)"

    async def process(self, ctx: DataContext):
        target_col = next((c for c in ['title', '标题', 'content', '内容', 'comment'] if c in ctx.df.columns), None)

        if not target_col:
            yield json.dumps({"step": "skip", "msg": "⏩ 未找到文本列，跳过 AI 分析"}) + "\n"
            return

        if not call_ai_async:
            yield json.dumps({"step": "error", "msg": "❌ AI 模块未加载，请检查配置"}) + "\n"
            return

        yield json.dumps({"step": "ai_init", "msg": "🧠 正在调用 LLM 进行深度内容分析..."}) + "\n"

        system_prompt = (
            "You are a Data Analyst. Analyze the content provided by the user.\n"
            "Return a JSON object with two keys:\n"
            "1. 'tag': A short category tag (e.g., 'Positive', 'Negative', 'Spam', 'HighQuality', 'News').\n"
            "2. 'score': A quality score from 0 to 100 (integer).\n"
            "JSON ONLY. No markdown."
        )

        tags = []
        scores = []
        total = len(ctx.df)
        process_limit = 20
        if total > process_limit:
            yield json.dumps({"step": "ai_warn", "msg": f"⚠️ 为节省 Token，仅分析前 {process_limit} 条数据"}) + "\n"

        sem = asyncio.Semaphore(5)

        async def analyze_row(row_idx, text):
            async with sem:
                try:
                    ai_resp = await call_ai_async(system_prompt, str(text)[:300])
                    clean_json = ai_resp.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    return row_idx, data.get("tag", "Unknown"), data.get("score", 0)
                except:
                    return row_idx, "Error", 0

        tasks = []
        for i, row in enumerate(ctx.df.itertuples()):
            if i >= process_limit:
                tags.append("Skipped"); scores.append(0)
                continue
            text_content = getattr(row, target_col, "")
            if not text_content or len(str(text_content)) < 2:
                tags.append("Empty"); scores.append(0)
                continue
            tags.append(None); scores.append(None)
            tasks.append(analyze_row(i, text_content))

        processed_count = 0
        total_tasks = len(tasks)
        
        for f in asyncio.as_completed(tasks):
            idx, tag, score = await f
            tags[idx] = tag; scores[idx] = score
            processed_count += 1
            yield json.dumps({"step": "ai_thinking", "progress": int((processed_count / total_tasks) * 100),
                                  "msg": f"AI 分析中: {tag} ({score})"}) + "\n"

        ctx.df['AI_Tag'] = tags
        ctx.df['AI_Score'] = scores
        yield json.dumps({"step": "ai_done", "msg": "✨ AI 智能分析任务完成"}) + "\n"


# ==================== 3. 核心引擎 ====================

class RefineryEngine:
    def __init__(self):
        self.processors: List[BaseProcessor] = []

    def add_processor(self, p: BaseProcessor):
        self.processors.append(p)
        return self

    async def run(self, df: pd.DataFrame):
        ctx = DataContext(df)
        yield json.dumps({"step": "init", "message": "🏭 流水线启动..."}) + "\n"

        total_steps = len(self.processors)
        for i, processor in enumerate(self.processors):
            yield json.dumps({"step": "phase_start", "phase": processor.name, "msg": f"➡️ 工序 [{i + 1}/{total_steps}]: {processor.name}"}) + "\n"
            async for log in processor.process(ctx): yield log
            try:
                preview_df = ctx.df.head(5).replace({np.nan: None})
                preview = preview_df.to_dict(orient='records')
                yield json.dumps({"step": "phase_preview", "columns": list(ctx.df.columns), "preview": preview, "msg": f"📊 {processor.name} 完成"}) + "\n"
            except:
                pass
            await asyncio.sleep(0.5)

        filename = f"refined_{int(time.time())}.csv"
        filepath = os.path.abspath(filename)
        ctx.df.to_csv(filepath, index=False, encoding="utf-8-sig")

        yield json.dumps({"step": "done", "download_url": f"http://127.0.0.1:8000/download/{filename}", "final_count": len(ctx.df), "msg": "🎉 处理完毕"}) + "\n"


# ==================== API ====================

@router.post("/process")
async def process_data(file: UploadFile = File(...), enable_ai: bool = Form(False), enable_network: bool = Form(False)):
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except:
        try:
            df = pd.read_excel(io.BytesIO(contents))
        except:
            return {"error": "无法读取文件"}

    engine = RefineryEngine()
    engine.add_processor(StandardCleaner())
    if enable_network: engine.add_processor(LinkValidator())
    if enable_ai: engine.add_processor(AISentimentAnalyst())

    return StreamingResponse(engine.run(df), media_type="application/x-ndjson")
