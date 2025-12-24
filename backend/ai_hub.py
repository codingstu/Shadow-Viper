# backend/ai_hub.py
import json
import os
import httpx  # 必须安装: pip install httpx
import requests
from dotenv import load_dotenv

try:
    from proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

load_dotenv()

# ==================== 🤖 硅基流动 (DeepSeek 官方加速版) ====================
AI_PROVIDERS = {
    "silicon": {
        "base_url": os.getenv("SILICON_BASE_URL", "https://api.siliconflow.cn/v1"),
        "api_key": os.getenv("SILICON_API_KEY", ""),
    }
}


def get_provider_config(model_name: str):
    return AI_PROVIDERS["silicon"], model_name.replace("silicon/", "")


# --- 🚀 核心：异步请求 (非阻塞) ---
async def _execute_request_async(client, url, headers, payload, timeout):
    try:
        if not url.endswith("/chat/completions"):
            url = f"{url.rstrip('/')}/chat/completions"

        resp = await client.post(url, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data['choices'][0]['message']['content'], None
            return None, f"Empty Resp: {resp.text[:100]}"
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


# --- 🚀 核心：异步流式生成 (非阻塞，支持打字机效果) ---
async def call_ai_stream_async(system_prompt: str, user_text: str, model: str = "deepseek-ai/DeepSeek-V3",
                               temperature: float = 0.7):
    """
    全异步流式调用，不会阻塞服务器主线程
    """
    config = AI_PROVIDERS["silicon"]
    api_key = config["api_key"]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    real_model = model
    if "r1" in model.lower(): real_model = "deepseek-ai/DeepSeek-R1"

    payload = {
        "model": real_model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        "temperature": temperature,
        "max_tokens": 8192,
        "stream": True
    }

    url = f"{config['base_url'].rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    yield f"Error {response.status_code}: {await response.aread()}"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        json_str = line[6:]
                        if json_str.strip() == "[DONE]": break
                        try:
                            chunk = json.loads(json_str)
                            content = chunk['choices'][0]['delta'].get('content', '')
                            if content: yield content
                        except:
                            pass
    except Exception as e:
        yield f"Stream Error: {str(e)}"


# --- 🚀 核心：异步普通调用 (非流式) ---
async def call_ai_async(system_prompt: str, user_text: str, model: str = "deepseek-ai/DeepSeek-V3",
                        temperature: float = 0.7):
    config = AI_PROVIDERS["silicon"]
    api_key = config["api_key"]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        "temperature": temperature,
        "max_tokens": 8192
    }

    async with httpx.AsyncClient() as client:
        content, error = await _execute_request_async(client, config["base_url"], headers, payload, 120)
        if error: raise Exception(error)
        return content


# ==================== 👇 保留旧版同步代码 (兼容旧模块) ====================
def _execute_request(session, url, headers, payload, proxies, timeout):
    try:
        if not url.endswith("/chat/completions"): url = f"{url.rstrip('/')}/chat/completions"
        resp = session.post(url, headers=headers, json=payload, timeout=timeout, proxies=proxies, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data['choices'][0]['message']['content'], None
            return None, f"Empty Resp: {resp.text[:100]}"
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def call_ai(system_prompt: str, user_text: str, model: str = "deepseek-ai/DeepSeek-V3", temperature: float = 0.7,
            return_model_name: bool = False):
    # 兼容旧代码的同步调用
    chain = []
    if pool_manager: chain = pool_manager.get_standard_chain()
    chain.append((None, "Direct", 60))

    config = AI_PROVIDERS["silicon"]
    api_key = config["api_key"]

    real_model = model
    if "gpt" in model or "smart" in model: real_model = "deepseek-ai/DeepSeek-V3"
    if "r1" in model.lower(): real_model = "deepseek-ai/DeepSeek-R1"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": real_model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
        "temperature": temperature,
        "max_tokens": 8192
    }

    last_error = None
    for proxy_url, _, timeout_sec in chain:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        session = requests.Session()
        content, error = _execute_request(session, config["base_url"], headers, payload, proxies, 60 + timeout_sec)

        if content:
            if return_model_name:
                return content, f"SiliconFlow-{real_model.split('/')[-1]}"
            return content

        last_error = error
        if "401" in error: break
        continue

    raise Exception(f"请求失败: {last_error}")