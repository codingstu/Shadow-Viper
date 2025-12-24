# backend/app/modules/crawler/proxy.py
import asyncio
import requests
from urllib.parse import quote, unquote, urlparse, urljoin
from fastapi import APIRouter, Response, Request
from fastapi.responses import StreamingResponse

try:
    from ..proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

# Use a specific, common user agent for media fetching
MEDIA_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
# This should be populated by the crawler logic, but we define it here for clarity
GLOBAL_COOKIE_JAR = {} 

router = APIRouter()

async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

@router.get("/api/proxy")
async def proxy_stream(url: str, request: Request):
    target_url = unquote(url)
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()
    
    # Default headers
    headers = {
        "User-Agent": MEDIA_USER_AGENT,
        "Range": request.headers.get("range", "bytes=0-"),
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive"
    }

    # 🔥 Bilibili-specific header overrides
    if "bilivideo.com" in domain or "bilibili.com" in domain:
        headers["Referer"] = "https://www.bilibili.com/"
        # Bilibili's CDN can be sensitive to the Origin header, so we remove it.
        if "Origin" in headers:
            del headers["Origin"]

    req_cookies = GLOBAL_COOKIE_JAR.get(domain)
    if not req_cookies and ("bilivideo.com" in domain or "bilibili" in domain):
        req_cookies = GLOBAL_COOKIE_JAR.get("www.bilibili.com") or GLOBAL_COOKIE_JAR.get("bilibili.com")

    chain = []
    if "bilivideo.com" in domain or "bilibili" in domain:
        chain.append((None, "Direct", 20))
    
    if pool_manager:
        chain.extend(pool_manager.get_standard_chain())
    
    if not chain:
        chain.append((None, "Direct", 20))

    for proxy_url, name, timeout_sec in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = await async_request(
                'get', target_url, headers=headers, cookies=req_cookies,
                stream=True, timeout=(5, timeout_sec), verify=False, proxies=proxies
            )

            if resp.status_code >= 400:
                continue

            content_type = resp.headers.get("content-type", "application/octet-stream")

            if "mpegurl" in content_type or ".m3u8" in target_url:
                text = resp.text
                new_lines = [
                    f"http://127.0.0.1:8000/api/proxy?url={quote(urljoin(target_url, line.strip()))}"
                    if line and not line.startswith("#") else line
                    for line in text.splitlines()
                ]
                return Response(content="\n".join(new_lines), media_type=content_type)

            def iter_content():
                for chunk in resp.iter_content(chunk_size=128 * 1024): # Increased chunk size
                    yield chunk

            return StreamingResponse(
                iter_content(),
                status_code=resp.status_code,
                headers={k: v for k, v in resp.headers.items() if k.lower() in ["content-type", "content-range", "content-length", "accept-ranges"]},
                media_type=content_type
            )
        except Exception:
            continue

    return Response(status_code=502, content="Stream Failed")
