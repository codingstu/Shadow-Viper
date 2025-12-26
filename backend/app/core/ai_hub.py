# backend/app/core/ai_hub.py
import json
import os
import requests
import httpx
from pathlib import Path

# 延迟导入，避免循环依赖
pool_manager = None


def set_pool_manager(manager):
    global pool_manager
    pool_manager = manager


# ==================== 🛠️ 核心修复：手写物理读取器 ====================
def _manual_read_env_key(target_key: str):
    """
    不依赖 load_dotenv，不依赖系统变量，直接暴力读取文件。
    使用相对路径，自动定位 .env (backend/.env)
    """
    try:
        # 1. 获取 ai_hub.py 所在的目录
        current_dir = Path(__file__).resolve().parent
        # 2. 往上找 2 层 (app -> backend)，找到 .env 所在目录
        # current: backend/app/core
        # parent:  backend/app
        # parent.parent: backend
        project_root = current_dir.parent.parent
        env_file = project_root / ".env"

        print(f"[DEBUG] 正在尝试从文件读取 Key: {env_file}")

        if not env_file.exists():
            print(f"[ERROR] .env 文件未找到! 路径: {env_file}")
            return None

        # 3. 逐行扫描
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 忽略注释和空行
                if not line or line.startswith("#"):
                    continue
                # 查找目标 Key
                if line.startswith(f"{target_key}="):
                    # 分割并清理空格、引号
                    key_value = line.split("=", 1)[1].strip().strip("'").strip('"')
                    if key_value:
                        print(f"[DEBUG] 成功从文件读取到 {target_key} (长度: {len(key_value)})")
                        return key_value
    except Exception as e:
        print(f"[ERROR] 读取 .env 发生异常: {e}")

    return None


# ==================== 🤖 配置定义 ====================
AI_PROVIDERS = {
    "silicon": {
        # Base URL 也可以尝试读取，这里给默认值
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",  # 占位符，下面动态获取
    }
}


def get_provider_config(model_name: str):
    return AI_PROVIDERS["silicon"], model_name.replace("silicon/", "")


def _get_dynamic_api_key():
    """
    三级火箭获取 Key：
    1. 系统环境变量 (最高级)
    2. 手动读取 .env 文件 (保底级)
    3. 硬编码兜底 (最后防线)
    """
    # 1. 尝试系统变量
    key = os.getenv("SILICON_API_KEY")
    if key and len(key) > 10:
        return key

    # 2. 尝试手动读取文件
    key = _manual_read_env_key("SILICON_API_KEY")
    if key and len(key) > 10:
        return key

    # 3. 如果实在读不到，为了防止服务崩溃，这里保留一个硬编码的“安全网”
    # 如果你觉得不安全，可以删掉这行，但这是解决“怎么都读不到”的最后办法
    # 你的 Key: sk-pbnkxfexbhsaxwbfrupdjpokwzkxsiwuqeysarxnnkuesdfn
    print("[WARNING] 使用硬编码 Key 作为最后兜底")
    return "sk-pbnkxfexbhsaxwbfrupdjpokwzkxsiwuqeysarxnnkuesdfn"


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
    """
    全异步流式调用
    """
    config = AI_PROVIDERS["silicon"]

    # 🔥 动态获取 Key
    api_key = _get_dynamic_api_key()

    if not api_key:
        yield "Stream Error: Critical - API Key not found in env or file."
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