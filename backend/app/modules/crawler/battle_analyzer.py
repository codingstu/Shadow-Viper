# backend/app/modules/crawler/battle_analyzer.py
import json
import re
import random
import asyncio
from typing import Optional, List, Dict, AsyncGenerator

# 引入核心 AI 模块
from ...core.ai_hub import call_ai_stream_async


def build_battle_prompt(post_title: str, comments_text: str) -> str:
    return f"""
    You are a "Battle Data Analyst" for a game called Cyber Colosseum.
    Your task is to analyze a list of user comments related to a central topic and convert them into game character stats.

    **Main Topic:** "{post_title}"

    **Rules:**
    1.  **Think Step-by-Step:** First, inside `<think>` tags, identify the two main opposing viewpoints. Assign the first to "team_red" and the second to "team_blue". Briefly explain your reasoning.
    2.  **Assign Warriors:** For each comment, create a "warrior" object and assign it to the correct team. If a comment is neutral, discard it.
    3.  **Calculate Stats:**
        * `id`: The user's name.
        * `attack`: (0-100) Based on logical strength.
        * `poison`: (0-50) Based on toxicity.
        * `armor`: (0-1000) Based on likes.
        * `comment`: The original comment.
    4.  **Final Output:** After the closing `</think>` tag, output the complete JSON object.

    **CRITICAL: YOUR ENTIRE RESPONSE MUST FOLLOW THE <think>...</think> THEN JSON FORMAT.**

    **Analyze the following comments related to the Main Topic:**
    ---
    {comments_text}
    ---
    """


def extract_json_from_string(text: str) -> Optional[dict]:
    # 强力清洗：移除 Markdown 标记
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)

    # 寻找 JSON 的 {} 边界
    start_index = text.find('{')
    end_index = text.rfind('}')

    if start_index != -1 and end_index != -1 and end_index > start_index:
        json_str = text[start_index: end_index + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return None


def generate_fallback_battle_data(post_title: str, comments: List[Dict]) -> dict:
    """
    🔥 兜底方案：当 AI 挂掉时，使用本地算法生成数据
    确保演示永远流畅，绝不卡死！
    """
    team_red_warriors = []
    team_blue_warriors = []

    for i, row in enumerate(comments):
        content = row.get('内容', '')[:50]
        # 获取用户名
        user_str = row.get('备注', '') or row.get('用户', '') or f"User_{i}"
        user_id = str(user_str).replace("User: ", "").strip()

        # 模拟属性
        warrior = {
            "id": f"@{user_id}",
            "attack": random.randint(30, 95),
            "poison": random.randint(0, 60),
            "armor": int(row.get('点赞数', random.randint(10, 200))),
            "comment": content
        }

        # 随机分组 (50% 概率)
        if random.random() > 0.5:
            team_red_warriors.append(warrior)
        else:
            team_blue_warriors.append(warrior)

    return {
        "team_red": {
            "name": "Red Faction (Local)",
            "warriors": team_red_warriors
        },
        "team_blue": {
            "name": "Blue Faction (Local)",
            "warriors": team_blue_warriors
        },
        "topic": post_title,
        "is_fallback": True
    }


async def analyze_comments_for_battle_stream(post_title: str, comments: List[Dict]) -> AsyncGenerator[Dict, None]:
    """
    流式分析器，带超时熔断和本地降级
    """
    # 1. 准备数据
    comment_rows = [row for row in comments if row.get('类型') == '评论']
    if not comment_rows:
        # 如果没抓到评论，用正文或所有内容凑数，防止报错
        comment_rows = comments[:5]

    comments_for_ai = []
    for index, row in enumerate(comment_rows[:30]):  # 限制数量
        content = row.get('内容', '')[:100]
        likes = row.get('点赞数', random.randint(5, 150))
        user_str = row.get('备注', '') or row.get('用户', '') or f"User_{index}"
        user_id = str(user_str).replace("User: ", "").strip()
        comments_for_ai.append(f"- @{user_id} (Likes: {likes}): {content}")

    comments_text = "\n".join(comments_for_ai)
    prompt = build_battle_prompt(post_title, comments_text)

    full_response = ""
    is_thinking = False
    ai_failed = False

    yield {"type": "thought", "content": "正在连接 AI 神经中枢..."}

    # 2. 尝试调用 AI (带手动超时控制)
    try:
        # 获取迭代器
        ai_generator = call_ai_stream_async("You are a battle data analyst.", prompt)
        iterator = ai_generator.__aiter__()

        while True:
            try:
                # 🔥 核心：每 15 秒必须收到一个 token，否则视为卡死
                chunk = await asyncio.wait_for(iterator.__anext__(), timeout=15.0)

                full_response += chunk

                # 处理 <think> 标签流
                if "<think>" in chunk:
                    is_thinking = True
                    chunk = chunk.replace("<think>", "")

                if "</think>" in chunk:
                    is_thinking = False
                    part = chunk.split("</think>")[0]
                    if part: yield {"type": "thought", "content": part}
                    continue

                if is_thinking:
                    yield {"type": "thought", "content": chunk}

            except StopAsyncIteration:
                break  # 正常结束
            except asyncio.TimeoutError:
                print("❌ [BattleAnalyzer] AI 响应流中断 (超时)")
                yield {"type": "thought", "content": "\n⚠️ AI 响应超时，启动本地应急协议..."}
                ai_failed = True
                break
    except Exception as e:
        print(f"❌ [BattleAnalyzer] AI 系统故障: {e}")
        yield {"type": "thought", "content": f"\n⚠️ AI 连接失败: {str(e)}"}
        ai_failed = True

    # 3. 结果解析与降级
    battle_data = None

    if not ai_failed:
        # 尝试解析 AI 返回的 JSON
        final_json_str = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL)
        battle_data = extract_json_from_string(final_json_str)

    # 4. 如果 AI 失败或解析失败，使用本地兜底
    if not battle_data:
        print("⚠️ [BattleAnalyzer] 启用本地降级生成...")
        yield {"type": "thought", "content": "\n✅ 已切换至本地战术分析引擎。"}
        # 模拟一点延迟，让用户看清提示
        await asyncio.sleep(1)
        battle_data = generate_fallback_battle_data(post_title, comment_rows)

    yield {"type": "result", "data": battle_data}