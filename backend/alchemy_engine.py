# backend/alchemy_engine.py
import json
import asyncio
import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 引入流式和普通调用
try:
    from ai_hub import call_ai, call_ai_stream_async
except ImportError:
    call_ai = None
    call_ai_stream_async = None

router = APIRouter(prefix="/api/alchemy", tags=["alchemy"])


class DeAIRequest(BaseModel):
    text: str


# ==================== ⚙️ 配置区域 ====================
# DeepSeek R1: 负责逻辑推理、特征分析 (思维链长，速度慢，但精准)
JUDGE_MODEL = "deepseek-ai/DeepSeek-R1"
# DeepSeek V3: 负责文本生成、润色 (速度快，效果好)
WRITER_MODEL = "deepseek-ai/DeepSeek-V3"


# ==================== 🛠 工具函数 ====================
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


# ==================== 🕵️‍♂️ 裁判系统 (流式增强版) ====================
async def stream_judge_logic(text: str):
    """
    流式执行裁判逻辑：
    1. 实时推送 R1 的思考过程 (解决卡顿焦虑)
    2. 最后返回完整的评分结果
    """
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

    full_response = ""
    in_think_block = False
    
    # 模拟一个初始的思考日志
    yield {"type": "log", "msg": f"🔗 连接模型: {JUDGE_MODEL}..."}
    
    try:
        # 使用 ai_hub 的异步流式接口
        async for chunk in call_ai_stream_async(prompt, f"TEXT TO ANALYZE:\n{text[:1500]}", model=JUDGE_MODEL, temperature=0):
            full_response += chunk
            
            # --- 实时解析思维链 ---
            # 简单的状态机处理 <think> 标签
            if "<think>" in chunk:
                in_think_block = True
                chunk = chunk.replace("<think>", "") # 移除标签展示内容
            
            if "</think>" in chunk:
                in_think_block = False
                # 截取 </think> 之前的部分作为最后一段思考
                parts = chunk.split("</think>")
                if parts[0]:
                    yield {"type": "think", "delta": parts[0]}
                continue

            if in_think_block:
                # 实时推送思考片段
                yield {"type": "think", "delta": chunk}
                
    except Exception as e:
        yield {"type": "error", "msg": str(e)}
        return

    # 流式结束后，解析最终结果
    think, json_text = extract_think_content(full_response)
    data = parse_json_safely(json_text)

    if data:
        yield {
            "type": "result", 
            "data": {
                "score": int(data.get("score", 50)),
                "detector": JUDGE_MODEL,
                "thinking": think
            }
        }
    else:
        # 🔥 失败回退机制：如果解析失败，尝试用正则暴力提取分数
        score_match = re.search(r'"score":\s*(\d+)', full_response)
        if score_match:
            fallback_score = int(score_match.group(1))
            yield {
                "type": "result", 
                "data": {
                    "score": fallback_score,
                    "detector": f"{JUDGE_MODEL} (Fallback)",
                    "thinking": think
                }
            }
        else:
            yield {"type": "result", "data": {"score": -1, "detector": "Parse Error", "thinking": think}}


# ==================== 🌪 核心流程 (Chaos Pipeline) ====================
async def chaos_pipeline(source_text: str):
    try:
        yield json.dumps({"step": "init", "msg": "🔌 启动 DeepSeek 透明化引擎 (CoT Streaming)..."}) + "\n"
        await asyncio.sleep(0.5)

        # --- Phase 1: 初始检测 (流式) ---
        yield json.dumps({"step": "thought", "msg": f"🕵️‍♂️ 裁判 ({JUDGE_MODEL}) 正在介入..."}) + "\n"
        
        current_score = 50
        check_data = {}
        
        # 消费裁判的流
        think_buffer = ""
        async for event in stream_judge_logic(source_text):
            if event["type"] == "log":
                yield json.dumps({"step": "process", "msg": event["msg"]}) + "\n"
            elif event["type"] == "think":
                # 累积思考内容，每隔一定长度推送一次，或者直接推送增量
                # 为了前端展示流畅，这里我们推送增量，前端需要支持追加，或者我们推送完整的 buffer
                think_buffer += event["delta"]
                # 限制推送频率或长度，这里简化为每收到一点就推一点，前端展示为“正在思考...”
                # 注意：前端如果不支持流式追加，这里可能需要优化。
                # 假设前端是覆盖式显示 msg，我们推送最新的 buffer 尾部
                yield json.dumps({"step": "process", "msg": f"🧠 [R1 深度思考中]:\n{think_buffer[-300:]}..."}) + "\n"
            elif event["type"] == "result":
                check_data = event["data"]
            elif event["type"] == "error":
                yield json.dumps({"step": "error", "msg": f"API Error: {event['msg']}"}) + "\n"
                return

        current_score = check_data.get("score", -1)
        
        # 展示完整的思考过程 (如果之前只展示了片段)
        if check_data.get("thinking"):
             yield json.dumps({"step": "process", "msg": f"🧠 [思考完成]:\n{check_data['thinking'][:500]}...\n(逻辑闭环)"}) + "\n"

        if current_score == -1:
            yield json.dumps({"step": "error", "msg": "❌ 检测失败: 无法解析裁判结果"}) + "\n"
            return

        yield json.dumps(
            {"step": "detected", "score": current_score, "msg": f"初始判定: {current_score}% (由 {check_data['detector']} 裁决)"}) + "\n"

        # --- Phase 2: 智能跳过 ---
        target_score = 10
        if current_score <= 15:
            yield json.dumps({"step": "process", "msg": "✅ 分数已达标，启动 V3 微调模式..."}) + "\n"
            
            # V3 微调也可以流式，但这里为了简单保持普通调用，因为它很快
            prompt = "Polish this text to make it flow naturally like a native speaker. Do not change the meaning."
            raw_res, model_name = call_ai(prompt, source_text, model=WRITER_MODEL, return_model_name=True)
            _, final_text = extract_think_content(raw_res)

            yield json.dumps({"step": "done", "result": final_text, "final_score": current_score,
                              "msg": f"已达标 | 润色模型: {model_name}"}) + "\n"
            return

        # --- Phase 3: 深度降重 ---
        current_text = source_text
        best_text = source_text
        best_score = current_score

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

            yield json.dumps({"step": "thought", "msg": f"🔄 [Round {attempt}] 执行策略: {strategy_name} (Model: {WRITER_MODEL})..."}) + "\n"

            # 执行生成 (使用 V3)
            # 这里使用普通调用，因为 V3 速度快，且通常不输出 <think>
            raw_res, model_name = call_ai(prompt_instruction, current_text, model=WRITER_MODEL, return_model_name=True)
            think, temp_text = extract_think_content(raw_res)

            if think:
                yield json.dumps({"step": "process", "msg": f"🧠 [写手思考]:\n{think[:200]}..."}) + "\n"

            yield json.dumps({"step": "update_view", "content": temp_text}) + "\n"

            # --- 复检 (同样使用流式 R1) ---
            yield json.dumps({"step": "thought", "msg": f"🔍 裁判 ({JUDGE_MODEL}) 复检中..."}) + "\n"
            
            new_check_data = {}
            think_buffer = ""
            async for event in stream_judge_logic(temp_text):
                if event["type"] == "think":
                    think_buffer += event["delta"]
                    yield json.dumps({"step": "process", "msg": f"🧠 [复检思考]:\n{think_buffer[-300:]}..."}) + "\n"
                elif event["type"] == "result":
                    new_check_data = event["data"]

            new_score = new_check_data.get("score", 100) # 默认高分防止误判

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
            "msg": f"最终: {best_score}% | 裁判: {JUDGE_MODEL}"
        }) + "\n"

    except Exception as e:
        yield json.dumps({"step": "error", "msg": f"Err: {str(e)}"}) + "\n"


@router.post("/de_ai")
async def de_ai_endpoint(req: DeAIRequest):
    return StreamingResponse(chaos_pipeline(req.text), media_type="application/x-ndjson")
