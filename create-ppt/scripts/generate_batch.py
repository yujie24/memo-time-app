import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Any, Optional

import httpx
from json_repair import repair_json

from ppt_client import call_coze_api, check_url_accessibility
from ppt_utils import OutputManager, get_storage_dir

# ================= 配置项 =================
CONCURRENCY_LIMIT = 10
GLOBAL_TIMEOUT = 120.0
URL_PATTERN = re.compile(r'^https?://', re.IGNORECASE)


# ================= 辅助函数 =================

def get_existing_template_url(ppt_title: str) -> str:
    """
    尝试从已存在的 PPT 文件中获取 template_url。
    用于保持增量生成时的风格一致性。
    """
    # 校验 title 是否包含非法字符
    if any(c in ('/', '\\', ':', '*', '?', '"', '<', '>', '|') for c in ppt_title):
         return ""
         
    filename = f"{ppt_title}.pptx.html"
    target_dir = get_storage_dir()
    file_path = os.path.join(target_dir, filename)

    if not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("template_url", "")
    except Exception:
        return ""


def parse_input() -> Tuple[str, str, str, List[Dict], Optional[str]]:
    """
    解析输入参数（支持命令行参数或标准输入）。
    
    Returns: 
        (title, global_style, template_prompt, content_list, error_message)
    """
    input_str = ""
    try:
        # 优先读取命令行参数，其次读取 stdin
        if len(sys.argv) > 1:
            input_str = sys.argv[1]
        elif not sys.stdin.isatty():
            input_str = sys.stdin.read()

        if not input_str:
            return "", "", "", [], "No input provided via argv or stdin."

        # 使用 json_repair 修复可能存在的格式问题
        repaired_str = repair_json(input_str)
        input_data = json.loads(repaired_str)

        title = input_data.get('ppt_title', 'Untitled PPT')
        
        # 校验 title 安全性
        invalid_chars = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}
        if any(c in invalid_chars for c in title):
             return "", "", "", [], f"Invalid ppt_title: '{title}'. Title cannot contain: / \\ : * ? \" < > |"

        global_style = input_data.get('global_style', '')
        template_prompt = input_data.get('template_prompt', '')
        content = input_data.get('ppt_content', [])

        if not isinstance(content, list):
            return title, global_style, template_prompt, [], "Invalid format: 'ppt_content' must be a list."

        return title, global_style, template_prompt, content, None

    except Exception as e:
        return "", "", "", [], f"Input parsing failed: {str(e)}"


def validate_ref_images(client: httpx.Client, ref_images: Any) -> List[Dict]:
    """
    校验参考图：检查格式并验证网络可达性。
    """
    valid_refs = []
    if not isinstance(ref_images, list):
        return []

    for img in ref_images:
        if not isinstance(img, dict):
            continue

        url = img.get('url', '')
        if not isinstance(url, str) or not url:
            continue

        if not URL_PATTERN.match(url.strip()):
            continue

        if check_url_accessibility(client, url):
            valid_refs.append(img)

    return valid_refs


# ================= 核心逻辑 =================

def process_single_page(client: httpx.Client, page_data: dict, global_style: str, template_image_url: str, index: int,
                        output_manager: OutputManager) -> None:
    """
    处理单页 PPT 生成任务。
    
    Args:
        client: HTTP 客户端
        page_data: 页面数据
        global_style: 全局风格 prompt
        template_image_url: 模板图 URL (作为参考图)
        index: 页面在列表中的索引
        output_manager: 输出管理器
    """
    # 确定 page_index：优先使用 JSON 中的 page_id，否则使用 index (0-based)
    page_id = page_data.get('page_id') if page_data.get('page_id') is not None else index
    try:
        page_index = int(page_id)
    except (ValueError, TypeError):
        page_index = index

    prompt = page_data.get('prompt', '')

    # 判断是否为封面页（封面页有特殊处理逻辑）
    is_cover = '封面页' in prompt

    # 注意：global_style 不再自动拼接，由 Agent 在每页 prompt 中完整写入视觉风格
    # 保留 global_style 参数是为了向后兼容，但实际不使用

    try:
        # 2. 准备参考图
        raw_refs = page_data.get('ref_images', [])
        valid_refs = validate_ref_images(client, raw_refs)

        # 3. 注入模板图
        # 封面页不使用通用背景底图
        if template_image_url and not is_cover:
            valid_refs.insert(0, {"url": template_image_url})

        # 4. 调用 API
        image_url, api_error_msg = call_coze_api(prompt, client, valid_refs)
        
        # 5. 更新状态
        status = "success" if image_url else "failed"
        # 优先使用 API 返回的明确错误信息
        error_msg = api_error_msg if api_error_msg else ("API returned empty URL" if not image_url else "")

        output_manager.update_page(page_index, image_url, status, error_msg)
        
        # 实时输出进度
        output_manager.print_json()

    except Exception as e:
        # 捕获线程内的未知异常
        output_manager.update_page(page_index, "", "failed", str(e))
        output_manager.print_json()


def main():
    # 1. 解析输入
    ppt_title, global_style, template_prompt, ppt_content, parse_error = parse_input()

    if parse_error:
        print(json.dumps({"error": parse_error}, ensure_ascii=False))
        return

    # 2. 初始化输出管理器
    output_manager = OutputManager(ppt_title=ppt_title)
    output_manager.initialize_pages(ppt_content)

    output_manager.print_start_marker()
    output_manager.print_json(initial=True)

    if not ppt_content:
        output_manager.print_completion_message()
        output_manager.print_json(filter_failed=True)
        output_manager.save_ppt_file()
        output_manager.print_file_saved_message()
        return

    try:
        with httpx.Client(timeout=GLOBAL_TIMEOUT) as client:
            
            # --- Phase 1: 模板生成/复用 (串行) ---
            template_image_url = ""
            
            if template_prompt:
                # 策略：优先复用已存在的模板图，确保增量生成时风格一致
                existing_url = get_existing_template_url(ppt_title)
                if existing_url:
                    template_image_url = existing_url
                    output_manager.template_url = template_image_url
                else:
                    # 生成新的模板图
                    # 模板图生成不带参考图，使用 2560x1440 尺寸
                    full_template_prompt = f"请生成一张PPT background image。只生成纯视觉背景和装饰元素，不要生成任何文字，页面中心保持大面积留白。\n视觉风格（以下内容仅用于指导风格，不要把文字本身写进画面）：{template_prompt}"
                    template_image_url, _ = call_coze_api(full_template_prompt, client, [], size="2560x1440")
                    if template_image_url:
                        output_manager.template_url = template_image_url

            # --- Phase 2: 内容页批量生成 (并发) ---
            with ThreadPoolExecutor(max_workers=CONCURRENCY_LIMIT) as executor:
                futures = []
                for i, page in enumerate(ppt_content):
                    futures.append(
                        executor.submit(
                            process_single_page, client, page, global_style, template_image_url, i, output_manager
                        )
                    )

                # 等待所有任务完成
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        pass

        # 3. 完成与保存
        output_manager.print_completion_message()
        output_manager.print_json(filter_failed=True)
        output_manager.save_ppt_file()
        output_manager.print_file_saved_message()

    except Exception as e:
        print(f"Runtime Error: {str(e)}", file=sys.stderr)


if __name__ == "__main__":
    main()
