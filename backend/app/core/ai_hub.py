# backend/app/core/ai_hub.py
import json
import os
import requests
from dotenv import load_dotenv
import httpx
from pathlib import Path
import re  # 引入正则，用于物理读取

# 延迟导入，避免循环依赖
pool_manager = None


def set_pool_manager(manager):
    global pool_manager
    pool_manager = manager


# 1. 尝试标准加载 (不强制覆盖，避免把系统里的好值覆盖成空的)
try:
    env_path = Path("/home/azureuser/spiderflow/backend/.env")
    load_dotenv(dotenv_path=env_path)
except Exception:
    pass

# ==================== 🤖 硅基流动 (DeepSeek 官方加速版) ====================
AI_PROVIDERS = {
    "silicon": {
        "base_url": os.getenv("SILICON_BASE_URL", "https://api.siliconflow.cn/v1"),
        # 注意：这里先给个空值，全靠下面动态获取
        "api_key": "",
    }
}


def get_provider_config(model_name: str):
    return AI_PROVIDERS["silicon"], model_name.replace("silicon/", "")


# --- 🛠 核心修复：物理读取 .env 文件 ---
def _force_read_env_file(key_name):
    """
    当 os.getenv 失效时，直接打开文件去读。
    这是最底层的读取方式，只要文件里有字，就能读出来。
    """
    try:
        env_path = Path("/home/azureuser/spiderflow/backend/.env")
        if not env_path.exists():
            return None

        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 查找以 key_name 开头的行，并且忽略注释
                if line.startswith(f"{key_name}=") and not line.startswith("#"):
                    # 获取等号后面的部分，并去除引号和空格
                    value = line.split("=", 1)[1].strip()
                    return value.strip("'").strip('"')
    except Exception as e:
        print(f"物理读取 .env 失败: {e}")
    return None


def _get_dynamic_api_key():
    """
    三级火箭获取 Key
    """
    # 1. 第一级：查系统环境变量 (最高优先级，比如命令行注入的)
    key = os.getenv("SILICON_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if key and len(key) > 5:
        return key

    # 2. 第二级：物理读取 .env 文件 (专治 load_dotenv 不生效)
    key = _force_read_env_file("SILICON_API_KEY")
    if key and len(key) > 5:
        return key

    # 3. 第三级：硬编码兜底 (最后一道防线，防止报错 b'Bearer')
    # 这里填入你之前提供的 Key，确保万无一失
    fallback_key = "sk-pbnkxfexbhsaxwbfrupdjpokwzkxsiwuqeysarxnnkuesdfn"
    return fallback_key


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


# --- 🚀 核心：异步流式生成 ---
async def call_ai_stream_async(system_prompt: str, user_text: str, model: str = "deepseek-ai/DeepSeek-V3",
                               temperature: float = 0.7):
    config = AI_PROVIDERS["silicon"]

    # 🔥 动态获取 Key
    api_key = _get_dynamic_api_key()

    if not api_key:
        yield "Stream Error: API Key not found in env or file."
        return

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


# --- 🚀 核心：异步普通调用 ---
async def call_ai_async(system_prompt: str, user_text: str, model: str = "deepseek-ai/DeepSeek-V3",
                        temperature: float = 0.7):
    config = AI_PROVIDERS["silicon"]
    api_key = _get_dynamic_api_key()

    if not api_key:
        raise Exception("API Key Missing")

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


# ==================== 👇 兼容旧代码 ====================
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
    chain = []
    if pool_manager: chain = pool_manager.get_standard_chain()
    chain.append((None, "Direct", 60))

    config = AI_PROVIDERS["silicon"]
    api_key = _get_dynamic_api_key()

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