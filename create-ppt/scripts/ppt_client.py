import os
import sys
import json
import time
from typing import List, Dict, Any, Optional, Tuple

import httpx

# ================= 配置项 =================
# 优先从环境变量获取，确保安全
COZE_API_TOKEN = os.getenv('identity_ticket')
WORKFLOW_ID = "7584118159226241076"
PROXY_HOST = "https://sd500jqlh74m0t5ldnsig.apigateway-cn-beijing-inner.volceapi.com"
API_URL = f"{PROXY_HOST}/v1/workflow/run"
MAX_RETRIES = 3


def check_url_accessibility(client: httpx.Client, url: str) -> bool:
    """
    验证 URL 可访问性。
    使用 stream=True 仅获取头部，避免下载整个文件体，节省带宽。
    
    Args:
        client: httpx 客户端实例
        url: 待检测的 URL
        
    Returns:
        bool: 是否可访问 (HTTP < 400)
    """
    try:
        # 设置较短的 timeout，避免阻塞太久
        with client.stream("GET", url, timeout=5.0) as resp:
            return resp.status_code < 400
    except Exception:
        return False


def call_coze_api(prompt: str, client: httpx.Client, ref_images: Optional[List[Dict[str, Any]]] = None,
                  size: str = "4096x2304", watermark: bool = False) -> Tuple[str, str]:
    """
    同步调用 Coze Workflow API，包含指数退避重试机制。
    
    Args:
        prompt: 提示词
        client: HTTP 客户端实例
        ref_images: 参考图列表，格式 [{"url": "..."}]
        size: 图片尺寸，默认 4096x2304

    Returns:
        (image_url, error_msg): 成功返回 (url, "")，失败返回 ("", 错误信息)
    """
    # 提取有效的参考图 URL，过滤空值
    image_url_list = [
        img["url"] for img in (ref_images or [])
        if isinstance(img, dict) and img.get("url")
    ]

    headers = {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "workflow_id": WORKFLOW_ID,
        "parameters": {
            "prompt": prompt,
            "images_url": image_url_list,
            "size": size,
            "watermark": watermark
        },
        "is_async": False
    }

    last_error_msg = ""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()

            res_json = response.json()
            if res_json.get("code") != 0:
                last_error_msg = f"API Error: {res_json.get('msg')}"
                print(f"[{last_error_msg}]", file=sys.stderr)
                # 业务级错误（如参数不对）通常重试无效，但为了稳健仍继续重试
                continue

            # 解析 data 字段，兼容 JSON 字符串和字典格式
            raw_data = res_json.get("data", "{}")

            try:
                if isinstance(raw_data, str):
                    parsed_data = json.loads(raw_data)
                else:
                    parsed_data = raw_data

                # 从路径 output -> data 提取 URL
                final_url = parsed_data.get("output", {}).get("data", "")
                
                # 检查 output 中的 msg 字段
                api_msg = parsed_data.get("output", {}).get("msg", "")
                
                # 特殊处理：如果 msg 不是 success，记录错误
                if api_msg != "success":
                     last_error_msg = f"Workflow Error: {api_msg}"
                     
                     # 严重错误：如果包含安全审核拦截，立即停止重试，避免账号风险或无效请求
                     if "Your prompt word did not pass our security review" in api_msg:
                         return "", last_error_msg

                if isinstance(final_url, str) and final_url.startswith("http"):
                    return final_url, ""
                
                if not last_error_msg:
                    last_error_msg = "Invalid data format: output.data is not a valid URL"

            except json.JSONDecodeError:
                last_error_msg = f"JSON Error: Invalid data field: {str(raw_data)[:50]}..."
                print(f"[{last_error_msg}]", file=sys.stderr)

        except Exception as e:
            last_error_msg = f"Request Error: {str(e)}"
            print(f"[Request Error] Attempt {attempt + 1}/{MAX_RETRIES}: {e}", file=sys.stderr)
            
            # 指数退避：1s, 2s, 4s...
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return "", last_error_msg
