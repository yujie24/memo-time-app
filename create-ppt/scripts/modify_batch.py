import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

import httpx
from json_repair import repair_json

from ppt_client import call_coze_api, check_url_accessibility
from ppt_utils import OutputManager, GenerationLogger, get_storage_dir

# ================= 配置项 =================
CONCURRENCY_LIMIT = 10
GLOBAL_TIMEOUT = 120.0
# ================= 辅助函数 =================

def parse_input() -> Tuple[Dict, Optional[str]]:
    """
    解析输入参数。支持从命令行参数或 stdin 读取 JSON。
    
    Returns: 
        (解析后的数据字典, 错误信息)
    """
    input_str = ""
    # 优先读取 argv，其次读取 stdin (Heredoc 支持)
    if len(sys.argv) > 1:
        input_str = sys.argv[1]
    elif not sys.stdin.isatty():
        input_str = sys.stdin.read()

    if not input_str:
        return {}, "Missing input argument. Usage: python modify_batch.py '<JSON_STRING>'"

    try:
        repaired_str = repair_json(input_str)
        data = json.loads(repaired_str)
        
        # 校验 title 安全性
        if 'ppt_title' in data:
            title = data['ppt_title']
            invalid_chars = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}
            if any(c in invalid_chars for c in title):
                return {}, f"Invalid ppt_title: '{title}'. Title cannot contain: / \\ : * ? \" < > |"
                
        return data, None
    except Exception as e:
        return {}, f"Input parsing failed: {str(e)}"


def load_source_file(filepath: str) -> List[Dict]:
    """
    加载源 PPT 文件数据。
    
    Args:
        filepath: 文件路径（绝对路径或相对路径）
        
    Returns:
        页面列表。如果文件不存在则返回空列表。
    """
    if not filepath:
        return []

    # 路径解析策略：
    # 1. 尝试直接作为绝对路径
    # 2. 尝试在标准存储目录下查找
    if os.path.exists(filepath):
        final_path = filepath
    else:
        storage_dir = get_storage_dir()
        final_path = os.path.join(storage_dir, filepath)

    if not os.path.exists(final_path):
        return []

    try:
        with open(final_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试直接解析
        try:
            data = json.loads(content)
            return data.get("pages", [])
        except json.JSONDecodeError:
            # 解析失败，尝试用 json_repair 修复
            repaired = repair_json(content)
            data = json.loads(repaired)
            return data.get("pages", [])

    except Exception as e:
        print(f"[Warning] Failed to load source file {filepath}: {e}", file=sys.stderr)
        return []


# ================= 业务逻辑 =================

def get_ref_images_for_add(source_pages: List[Dict], insert_after_id: str) -> List[Dict]:
    """
    为新增页面寻找上下文参考图，以保持风格一致性。
    策略：尝试获取插入点“前一页”和“后一页”的图片。
    """
    refs = []

    target_idx = -1
    for i, p in enumerate(source_pages):
        if str(p.get("page_index")) == str(insert_after_id):
            target_idx = i
            break

    # 尝试获取前一页图片
    if target_idx >= 0:
        url = source_pages[target_idx].get("image_url")
        if url:
            refs.append({"url": url})

    # 尝试获取后一页图片
    if target_idx + 1 < len(source_pages):
        url = source_pages[target_idx + 1].get("image_url")
        if url:
            refs.append({"url": url})

    return refs


def apply_operations(source_pages: List[Dict], operations: List[Dict], global_style: str) -> List[Dict]:
    """
    核心逻辑：应用修改操作（Delete, Modify, Add）到源页面列表。
    
    Returns: 
        新的页面列表 (含 Pending 状态的新增/修改页)
    """
    # --- Step 1: 预处理操作指令 ---
    delete_ids = set()
    modify_map = {}
    add_map = {}  # Key: insert_after_id, Value: list of operations

    for op in operations:
        action = op.get("action")
        page_id_str = str(op.get("page_id") or op.get("page_number") or "")
        
        if action == "modify" and "suggestion" not in op:
            op["suggestion"] = op.get("content") or op.get("prompt") or ""

        if action == "delete":
            delete_ids.add(page_id_str)
        elif action == "modify":
            modify_map[page_id_str] = op
        elif action == "add":
            insert_after = str(op.get("insert_after", ""))
            if insert_after not in add_map:
                add_map[insert_after] = []
            add_map[insert_after].append(op)

    new_pages = []

    def create_pending_page(prompt_content: str, prompt_style: str = "", ref_urls: List[str] = None):
        """辅助函数：创建待生成的页面对象结构"""
        return {
            "prompt": prompt_content,
            "style": prompt_style,
            "image_url": "",
            "export_image_url": "",
            "status": "pending",
            "ref_images": [{"url": u} for u in (ref_urls or []) if u]
        }

    # --- Step 2: 处理前插 (Prepend) ---
    # 优先处理插在最前面的页面 (insert_after = "-1")
    processed_add_ids = set()
    if "-1" in add_map:
        processed_add_ids.add("-1")
        for op in add_map["-1"]:
            content = op.get("content", "")
            style = op.get("style", "") or global_style

            # 插在最前面，参考图只能找原文件的第一页
            ref_urls = []
            if source_pages:
                first_url = source_pages[0].get("image_url")
                if first_url:
                    ref_urls.append(first_url)
            
            new_pages.append(create_pending_page(content, style, ref_urls))

    # --- Step 3: 遍历源页面 (Iterate) ---
    for page in source_pages:
        pid = str(page.get("page_index"))

        if pid in delete_ids:
            # 命中 Delete：跳过，不加入新列表
            # 注意：即便删除了该页，该位置的 Add 操作仍需执行（挂载在被删页ID上的插入）
            pass
        else:
            if pid in modify_map:
                # 命中 Modify：标记为重绘 (Image-to-Image)
                op = modify_map[pid]
                suggestion = op.get("suggestion", "")

                # 确定参考图：用户指定的优先级 > 原图
                user_ref = op.get("ref_image_url")
                original_url = page.get("image_url")

                refs = []
                if user_ref:
                    refs.append(user_ref)
                elif original_url:
                    refs.append(original_url)

                original_prompt = page.get("prompt", "")

                page_obj = create_pending_page(
                    prompt_content=original_prompt,
                    prompt_style=global_style,
                    ref_urls=refs
                )
                # 注入特殊标记，供后续生成函数识别
                page_obj["_is_modify"] = True
                page_obj["_suggestion"] = suggestion
                page_obj["_original_prompt"] = original_prompt

                new_pages.append(page_obj)
            else:
                # 无操作：继承原页面 (Inherit)
                p_copy = page.copy()
                p_copy["status"] = "success"
                new_pages.append(p_copy)

        # 处理紧跟当前页的 Add 操作 (insert_after = 当前 pid)
        if pid in add_map:
            processed_add_ids.add(pid)
            for op in add_map[pid]:
                content = op.get("content", "")
                style = op.get("style", "") or global_style

                # 自动寻找上下文参考图
                refs_dicts = get_ref_images_for_add(source_pages, pid)
                ref_urls = [r["url"] for r in refs_dicts]

                new_pages.append(create_pending_page(content, style, ref_urls))
    
    # --- Step 4: 处理追加 (Append/Orphans) ---
    # 处理 insert_after 指向不存在 ID 的情况（通常意味着追加到末尾）
    for insert_after_id in add_map:
        if insert_after_id not in processed_add_ids:
            for op in add_map[insert_after_id]:
                content = op.get("content", "")
                style = op.get("style", "") or global_style

                # 尝试找最后一页作为参考图
                ref_urls = []
                if source_pages:
                    last_url = source_pages[-1].get("image_url")
                    if last_url:
                        ref_urls.append(last_url)

                new_pages.append(create_pending_page(content, style, ref_urls))

    # --- Step 5: 重置索引 ---
    # 重新生成连续的 page_index (0-based)
    for i, p in enumerate(new_pages):
        p["page_index"] = i

    return new_pages


def process_single_task(client: httpx.Client, page: Dict, global_style: str, output_manager: OutputManager,
                        logger: GenerationLogger) -> None:
    """
    执行单页生成任务（Modify 或 Add）。
    """
    idx = page["page_index"]

    # 如果是继承的成功页面，直接更新状态并返回
    if page.get("status") == "success":
        output_manager.update_page(idx, page.get("image_url", ""), "success")
        return

    prompt = ""
    style_for_log = global_style
    ref_images = []
    image_url = ""
    status = "failed"
    debug_info = {}

    try:
        # 构造 Prompt
        if page.get("_is_modify"):
            # 修改模式：基于原图 + 修改建议
            suggestion = page.get("_suggestion", "")
            prompt = f"基于用户需求修改如下的PPT图片 \n 修改要求：{suggestion}"
            if global_style:
                prompt = f"{prompt}\n\n视觉风格（以下内容仅用于指导风格，不要把文字本身写进画面）：{global_style}"
        else:
            # 新增模式：常规生成
            content = page.get("prompt", "")
            style = page.get("style", "") or global_style
            prompt = content
            if style:
                prompt = f"{prompt}\n\n视觉风格（以下内容仅用于指导风格，不要把文字本身写进画面）：{style}"
            style_for_log = style

        # 准备参考图
        ref_images = page.get("ref_images", [])
        valid_refs = []
        for img in ref_images:
            if isinstance(img, dict) and img.get("url"):
                if check_url_accessibility(client, img["url"]):
                    valid_refs.append(img)

        # 调用 API
        image_url, api_error_msg = call_coze_api(prompt, client, valid_refs)
        
        status = "success" if image_url else "failed"
        error_msg = api_error_msg if api_error_msg else ("API returned empty URL" if not image_url else "")
        
        output_manager.update_page(idx, image_url, status, error_msg)

    except Exception as e:
        output_manager.update_page(idx, "", "failed", str(e))
        status = "failed"
        debug_info = {"_local_exception": str(e)}

    finally:
        # 记录详细日志
        logger.record(
            page_index=idx,
            prompt=prompt,
            style=style_for_log,
            ref_images=ref_images,
            result_url=image_url,
            status=status,
            debug_info=debug_info
        )
        # 实时输出进度
        output_manager.print_json()


def main():
    # 1. 解析输入
    input_data, parse_error = parse_input()
    if parse_error:
        print(json.dumps({"error": parse_error}, ensure_ascii=False))
        return

    source_file = input_data.get("source_file")
    target_file = input_data.get("target_file")
    operations = input_data.get("operations", [])
    ppt_title = input_data.get("ppt_title", "Modified PPT")
    global_style = input_data.get("global_style", "")

    # 兼容旧格式输入 (Compatibility Layer)
    if not operations and "modification_suggestions" in input_data:
        suggestions = input_data.get("modification_suggestions", {})
        for page_id_str, suggestion in suggestions.items():
            operations.append({
                "action": "modify",
                "page_id": page_id_str,
                "suggestion": suggestion
            })
        
        # 旧格式可能直接包含 content
        ppt_content = input_data.get("ppt_content", [])
        source_pages = []
        for p in ppt_content:
            source_pages.append({
                "page_index": p.get("page_id"),
                "image_url": p.get("image_url", ""),
                "export_image_url": p.get("image_url", ""),
                "prompt": p.get("prompt", ""),
                "status": "success"
            })
    else:
        source_pages = load_source_file(source_file) if source_file else []

    # 自动生成目标文件名
    if not target_file:
        if any(c in ('/', '\\', ':', '*', '?', '"', '<', '>', '|') for c in ppt_title):
            print(json.dumps({"error": f"Invalid ppt_title: '{ppt_title}'. Title cannot contain illegal characters."},
                             ensure_ascii=False))
            return
        if not ppt_title.strip():
            ppt_title = "PPT"
        target_file = f"{ppt_title}.pptx.html"

    # 2. 构建目标页面列表
    target_pages = apply_operations(source_pages, operations, global_style)

    # 3. 初始化管理器
    output_manager = OutputManager(ppt_title=ppt_title)
    output_manager.output_file = target_file
    logger = GenerationLogger(ppt_title, target_file)

    init_data = [{"page_id": p["page_index"]} for p in target_pages]
    output_manager.initialize_pages(init_data)

    output_manager.print_start_marker()

    # 筛选待处理任务 (Pending)
    pending_tasks = [p for p in target_pages if p.get("status") != "success"]

    # 先更新所有已成功的页面状态 (Inherited pages)
    for p in target_pages:
        if p.get("status") == "success":
            output_manager.update_page(p["page_index"], p.get("image_url", ""), "success")

    output_manager.print_json(initial=True)

    # 4. 执行生成任务
    if not pending_tasks:
        # 无需修改，直接保存
        output_manager.print_completion_message()
        output_manager.print_json(filter_failed=False)
        output_manager.save_ppt_file()
        output_manager.print_file_saved_message()
        return

    try:
        with httpx.Client(timeout=GLOBAL_TIMEOUT) as client:
            with ThreadPoolExecutor(max_workers=CONCURRENCY_LIMIT) as executor:
                futures = []
                for page in pending_tasks:
                    futures.append(
                        executor.submit(process_single_task, client, page, global_style, output_manager, logger)
                    )

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"[Thread Error] {e}", file=sys.stderr)

        # 5. 完成流程
        output_manager.print_completion_message()
        output_manager.print_json(filter_failed=False)
        output_manager.save_ppt_file()
        output_manager.print_file_saved_message()

        # 保存调试日志
        log_path = logger.save_log_file()
        if log_path:
            print(f"[Logger] Log saved to: {log_path}", file=sys.stderr)

    except Exception as e:
        print(f"Runtime Error: {str(e)}", file=sys.stderr)


if __name__ == "__main__":
    main()
