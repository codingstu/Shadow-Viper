# backend/app/modules/crawler/battle_analyzer.py
import json
import re
import random
import asyncio
from typing import Optional, List, Dict

# 🔥 恢复：只引入普通版 call_ai_async
from ...core.ai_hub import call_ai_async


def build_battle_prompt(post_title: str, comments_text: str) -> str:
    return f"""
    You are a "Battle Data Analyst" for a game called Cyber Colosseum.
    Your task is to analyze a list of user comments related to a central topic and convert them into game character stats.

    **Main Topic:** "{post_title}"

    **Rules:**
    1.  **Identify Factions:** Based on the Main Topic, identify the two primary opposing stances in the comments. For example, if the topic is "Rust vs C++", the stances are "Pro-Rust" and "Pro-C++". Assign the first stance you identify to "team_red" and the opposing one to "team_blue".
    2.  **Assign Warriors:** For each comment, create a "warrior" object and assign it to the correct team. If a comment is neutral or irrelevant, discard it.
    3.  **Calculate Stats:**
        * `id`: The user's name.
        * `attack`: (0-100) Based on the logical strength and evidence.
        * `poison`: (0-50) Based on toxicity or personal attacks.
        * `armor`: (0-1000) Based on likes.
        * `comment`: The original user comment (first 50 characters).
    4.  **JSON Format:** The final output MUST be a single, valid JSON object.

    **CRITICAL: YOUR ENTIRE RESPONSE MUST BE ONLY THE JSON OBJECT, WITH NO EXTRA TEXT OR MARKDOWN.**

    **Analyze the following comments related to the Main Topic:**
    ---
    {comments_text}
    ---
    """


def extract_json_from_string(text: str) -> Optional[dict]:
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)
    start_index = text.find('{')
    end_index = text.rfind('}')
    if start_index != -1 and end_index != -1 and end_index > start_index:
        json_str = text[start_index: end_index + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None


def generate_fallback_battle_data(post_title: str, comments: List[Dict]) -> dict:
    print("⚠️ [BattleAnalyzer] 启动本地降级生成模式 (AI Failed)...")
    team_red_name = "Red Faction"
    team_blue_name = "Blue Faction"
    team_red_warriors = []
    team_blue_warriors = []

    for i, row in enumerate(comments):
        content = row.get('内容', '')[:50]
        user_id = row.get('用户', f"Warrior_{i}").replace("User: ", "").strip()
        is_red = random.choice([True, False])
        warrior = {
            "id": f"@{user_id}", "attack": random.randint(30, 95),
            "poison": random.randint(0, 40), "armor": int(row.get('点赞数', random.randint(0, 100))),
            "comment": content
        }
        if is_red:
            team_red_warriors.append(warrior)
        else:
            team_blue_warriors.append(warrior)

    return {
        "team_red": {"name": team_red_name, "warriors": team_red_warriors},
        "team_blue": {"name": team_blue_name, "warriors": team_blue_warriors},
        "topic": post_title, "is_fallback": True
    }


async def analyze_comments_for_battle(post_title: str, comments: List[Dict]) -> dict:
    print(f"🔍 [BattleAnalyzer] 收到分析请求: {post_title}, 原始数据条数: {len(comments)}")

    valid_types = ['评论', 'comment', 'reply', 'P', 'LI', 'DIV', 'GENERAL COMMENT']
    comment_rows = [row for row in comments if
                    row.get('类型', '').upper() in [t.upper() for t in valid_types] or 'User:' in row.get('备注', '')]
    print(f"🔍 [BattleAnalyzer] 过滤后有效评论数: {len(comment_rows)}")

    if not comment_rows:
        print("⚠️ [BattleAnalyzer] 无有效评论，使用模拟数据填充")
        comment_rows = [{"用户": "System", "内容": "暂无评论", "点赞数": 10}]

    comments_for_ai = []
    for index, row in enumerate(comment_rows[:30]):
        content = row.get('内容', '')[:100]
        likes = row.get('点赞数', random.randint(5, 150))
        user_id = row.get('用户') or (
            row.get('备注', '').split('User:')[1].strip() if 'User:' in row.get('备注', '') else f"Warrior_{index}")
        comments_for_ai.append(f"- @{user_id} (Likes: {likes}): {content}")

    comments_text = "\n".join(comments_for_ai)
    prompt = build_battle_prompt(post_title, comments_text)

    print("⏳ [BattleAnalyzer] 正在请求 AI 分析 (超时设定 60s)...")

    try:
        ai_response_str = await asyncio.wait_for(
            call_ai_async("You are a battle data analyst. Output JSON only.", prompt),
            timeout=60.0
        )

        print(f"✅ [BattleAnalyzer] AI 响应成功 (长度: {len(ai_response_str)})")

        battle_data = extract_json_from_string(ai_response_str)
        if battle_data and "team_red" in battle_data:
            return battle_data
        else:
            print(f"❌ [BattleAnalyzer] JSON 解析失败或缺少字段")
            return generate_fallback_battle_data(post_title, comment_rows)

    except asyncio.TimeoutError:
        print("❌ [BattleAnalyzer] AI 响应超时 (60s)，切换到本地降级模式")
        return generate_fallback_battle_data(post_title, comment_rows)

    except Exception as e:
        print(f"❌ [BattleAnalyzer] AI 调用或处理出错: {e}，切换到本地降级模式")
        return generate_fallback_battle_data(post_title, comment_rows)