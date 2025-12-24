# backend/alchemy_engine.py
import json
import asyncio
import random
import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from ai_hub import call_ai
except ImportError:
    call_ai = None

router = APIRouter(prefix="/api/alchemy", tags=["alchemy"])


class DeAIRequest(BaseModel):
    text: str


WRITER_MODEL = "deepseek-ai/DeepSeek-V3"
JUDGE_MODEL = "deepseek-ai/DeepSeek-R1"


# ==================== 1. 工具函数：提取思维链 ====================
def extract_think_content(text):
    """分离 <think> 内容和正文"""
    if not text: return None, None
    think_content = None
    clean_text = text

    # 提取 <think>...</think>
    match = re.search(r'<think>(.*?)</think>', text, flags=re.DOTALL)
    if match:
        think_content = match.group(1).strip()
        clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    # 清洗 Markdown JSON 包裹
    clean_text = clean_text.replace("```json", "").replace("```", "").strip()
    return think_content, clean_text

# ==================== 2. 裁判系统 (带思维链返回) ====================
# 2. 裁判系统：温度设为 0 以保证结果绝对一致
async def detect_ai_probability(text: str) -> dict:
    # 更加严谨的 Prompt，要求先思考特征，再打分，防止瞎猜
    prompt = (
        "Role: Professional AI Text Forensic Analyst.\n"
        "Task: Analyze the following text and determine the probability (0-100%) that it was written by an AI.\n"
        "Method: \n"
        "1. First, inside <think> tags, analyze the Sentence Length Variance (Burstiness) and Perplexity.\n"
        "2. Look for AI patterns: robotic transitions ('Moreover', 'In conclusion'), repetitive structure, lack of idioms.\n"
        "3. Finally, output the JSON.\n"
        "Output Format: <think>...analysis...</think>\n"
        "JSON ONLY: {\"score\": <int 0-100>, \"reason\": \"<short summary>\"}\n"
        "Constraint: Be consistent. If text is casual and irregular, score low (<10). If text is rigid and textbook-like, score high (>80)."
    )

    try:
        # 🔥 关键：temperature=0 确保每次检测结果一致，不会出现一次12一次95的情况
        raw_text, model_name = call_ai(
            prompt,
            f"TEXT TO ANALYZE:\n{text[:1500]}",
            model=JUDGE_MODEL,
            temperature=0,
            return_model_name=True
        )

        # 提取思考和结果
        think, json_text = extract_think_content(raw_text)
        data = parse_json_safely(json_text)

        if data:
            return {
                "score": int(data.get("score", 50)),
                "detector": model_name,
                "thinking": think  # 将思考过程返回给前端
            }

    except Exception as e:
        return {"score": -1, "detector": f"Error: {str(e)}", "thinking": None}

    return {"score": -1, "detector": "Failed", "thinking": None}

# ==================== 3. 核心流程 (完全透明化) ====================
# backend/alchemy_engine.py (新增工具函数 + 替换主流程)

def parse_json_safely(text):
    try:
        # 尝试寻找最外层的 {}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        return json.loads(text)
    except:
        return None

# 2. 替换：带透明化展示的主流程
# 3. 核心流程：实时推送思维链
async def chaos_pipeline(source_text: str):
    try:
        yield json.dumps({"step": "init", "msg": "🔌 启动 DeepSeek 透明化引擎 (CoT Visible)..."}) + "\n"
        await asyncio.sleep(0.5)

        # --- Phase 1: 初始检测 ---
        yield json.dumps({"step": "thought", "msg": "🕵️‍♂️ 裁判 (DeepSeek R1) 正在深度审视 (Temp=0)..."}) + "\n"
        check = await detect_ai_probability(source_text)

        # 🔥 实时展示裁判的思考过程
        if check.get("thinking"):
            yield json.dumps(
                {"step": "process", "msg": f"🧠 [裁判思考]:\n{check['thinking'][:300]}...\n(分析完毕)"}) + "\n"

        current_score = check["score"]
        if current_score == -1:
            yield json.dumps({"step": "error", "msg": "❌ 检测失败: 请检查 SILICON_API_KEY"}) + "\n"
            return

        yield json.dumps(
            {"step": "detected", "score": current_score, "msg": f"初始: {current_score}% ({check['detector']})"}) + "\n"

        # --- Phase 2: 智能跳过 ---
        target_score = 10
        if current_score <= 15:
            yield json.dumps({"step": "process", "msg": "✅ 分数已达标，正在进行微调润色..."}) + "\n"

            prompt = "Polish this text to make it flow naturally like a native speaker. Do not change the meaning."
            # 调用 V3 微调
            raw_res, model_name = call_ai(prompt, source_text, model=WRITER_MODEL, return_model_name=True)
            think, final_text = extract_think_content(raw_res)

            if think:
                yield json.dumps({"step": "process", "msg": f"🧠 [润色思考]:\n{think[:150]}..."}) + "\n"

            yield json.dumps({"step": "done", "result": final_text, "final_score": current_score,
                              "msg": f"已达标 | 微调模型: {model_name}"}) + "\n"
            return

        # --- Phase 3: 深度降重 ---
        current_text = source_text
        best_text = source_text
        best_score = current_score

        # 确保 strategies 格式正确 (2元素元组)
        strategies = [
            ("深度拟人", "Rewrite to sound like a human expert. Use variable sentence lengths. **NO LISTS**."),
            ("结构打散", "Completely change sentence structure. Combine short sentences. **NO LISTS**."),
            ("暴力口语", "Explain this casually. Use idioms. **NO FORMATTING**.")
        ]

        MAX_ATTEMPTS = 3
        attempt = 0

        while current_score > target_score and attempt < MAX_ATTEMPTS:
            attempt += 1
            if attempt > len(strategies): break

            strategy_name, prompt_instruction = strategies[attempt - 1]

            yield json.dumps({"step": "thought", "msg": f"🔄 [Round {attempt}] 执行策略: {strategy_name}..."}) + "\n"

            # 执行生成
            raw_res, model_name = call_ai(prompt_instruction, current_text, model=WRITER_MODEL, return_model_name=True)
            think, temp_text = extract_think_content(raw_res)

            # 🔥 展示写手的思考
            if think:
                yield json.dumps({"step": "process", "msg": f"🧠 [写手思考]:\n{think[:200]}..."}) + "\n"

            yield json.dumps({"step": "update_view", "content": temp_text}) + "\n"

            # 复检
            yield json.dumps({"step": "thought", "msg": "🔍 裁判复检中..."}) + "\n"
            new_check = await detect_ai_probability(temp_text)

            if new_check.get("thinking"):
                yield json.dumps({"step": "process", "msg": f"🧠 [复检思考]:\n{new_check['thinking'][:150]}..."}) + "\n"

            new_score = new_check["score"]

            # 止损逻辑
            if new_score > current_score + 10:
                yield json.dumps(
                    {"step": "ai_warn", "msg": f"⚠️ 警告: 分数恶化 ({current_score}% -> {new_score}%)，回滚..."}) + "\n"
                current_text = best_text
            elif new_score <= current_score:
                yield json.dumps({"step": "process", "msg": f"📉 优化成功: {current_score}% -> {new_score}%"}) + "\n"
                current_text = temp_text
                current_score = new_score
                best_text = temp_text
                best_score = new_score
            else:
                current_text = temp_text
                current_score = new_score

            if current_score <= target_score:
                break

        yield json.dumps({
            "step": "done",
            "result": best_text,
            "final_score": best_score,
            "msg": f"最终: {best_score}% | 裁判: {new_check['detector']}"
        }) + "\n"

    except Exception as e:
        yield json.dumps({"step": "error", "msg": f"Err: {str(e)}"}) + "\n"


@router.post("/de_ai")
async def de_ai_endpoint(req: DeAIRequest):
    return StreamingResponse(chaos_pipeline(req.text), media_type="application/x-ndjson")