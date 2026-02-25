import json
import os
import sys
import threading
import time
from typing import List, Dict, Any, Optional


def get_storage_dir() -> str:
    """
    获取文件存储目录的统一入口。
    优先使用 /app/data/files/，如果不存在则回退到脚本所在目录的上级。
    """
    target_dir = "/app/data/files/"
    if not os.path.exists(target_dir):
        # 回退逻辑：scripts/../
        script_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.abspath(os.path.join(script_dir, "../../"))
    return target_dir


class OutputManager:
    """
    Output Manager: 管理 PPT 生成状态并生成标准化的实时 JSON 反馈。
    
    功能：
    1. 维护所有页面的生成状态（Success/Failed/Pending）。
    2. 实时打印 JSON 供前端/Agent 消费。
    3. 支持增量保存文件，防止数据丢失。
    """

    def __init__(self, ppt_id: Optional[str] = None, ppt_title: Optional[str] = None,
                 output_file: Optional[str] = None):
        self.ppt_id = ppt_id or ""
        self.ppt_title = ppt_title or ""
        self.output_file = output_file  # 显式指定的输出文件名
        self.template_url = ""          # 存储模板图 URL
        
        # 存储所有页面的状态：key 为页面索引 (int)，value 为页面数据字典
        self.pages_state: Dict[int, Dict[str, Any]] = {}
        # 线程锁，确保多线程并发更新时的状态一致性
        self.lock = threading.Lock()

    def initialize_pages(self, pages: List[Dict]):
        """
        初始化内部状态。
        
        Args:
            pages: 包含 'page_id' 的页面字典列表
        """
        with self.lock:
            for p in pages:
                try:
                    p_idx = int(p.get("page_id", 0))
                except (ValueError, TypeError):
                    p_idx = 0

                # 初始化状态：图片 URL 为空，status 为 None (Pending)
                self.pages_state[p_idx] = {
                    "page_index": p_idx,
                    "image_url": "",
                    "export_image_url": "",
                    "status": None,
                    "error_msg": "",
                    "prompt": p.get("prompt", "")
                }

    def update_page(self, page_index: int, image_url: str, status: str, error_msg: str = ""):
        """
        线程安全地更新单个页面的生成结果。
        """
        with self.lock:
            if page_index in self.pages_state:
                self.pages_state[page_index]["image_url"] = image_url
                self.pages_state[page_index]["export_image_url"] = image_url
                self.pages_state[page_index]["status"] = status
                self.pages_state[page_index]["error_msg"] = error_msg

    def print_start_marker(self):
        """打印开始生成的特殊标识，供流式解析使用。"""
        time.sleep(1)
        sys.stdout.flush()
        marker = "coze_image_ppt_skill_start"
        print(marker)
        sys.stdout.flush()
        time.sleep(1)

    def print_json(self, initial: bool = False, filter_failed: bool = False):
        """
        构建并打印标准化的 JSON 输出。
        
        Args:
            initial: 是否为初始消息（初始消息不包含 status 字段）
            filter_failed: 是否过滤掉生成失败的页面（通常用于最终交付）
        """
        with self.lock:
            # 按页面索引排序，保证输出顺序稳定
            sorted_indices = sorted(self.pages_state.keys())

            output_pages = []
            for idx in sorted_indices:
                data = self.pages_state[idx]

                # 过滤失败页面
                if filter_failed and data.get("status") == "failed":
                    continue

                page_obj = {
                    "page_index": str(data["page_index"]),
                    "image_url": data["image_url"],
                    "export_image_url": data["export_image_url"]
                }

                # 非初始消息时，包含 status 字段，告知前端当前进度
                if not initial:
                    if data.get("status"):
                        page_obj["status"] = data["status"]

                output_pages.append(page_obj)

            final_data = {
                "ppt_id": self.ppt_id,
                "ppt_title": self.ppt_title,
                "template_url": self.template_url,
                "pages": output_pages
            }

            # 打印 JSON 到标准输出，并强制刷新缓冲区
            print(json.dumps(final_data, ensure_ascii=False))
            sys.stdout.flush()

    def print_completion_message(self):
        """打印生成完成的标志性消息。"""
        time.sleep(1)
        sys.stdout.flush()
        marker = "coze_image_ppt_skill_end"
        print(marker)
        sys.stdout.flush()
        time.sleep(1)

    def save_ppt_file(self):
        """
        将生成的 PPT 内容保存为 JSON 文件（后缀为 .pptx.html）。
        支持增量合并：如果文件已存在，会合并现有内容和新生成的内容。
        """
        with self.lock:
            # 1. 确定文件名
            if self.output_file:
                filename = self.output_file
            else:
                title = self.ppt_title or "PPT"
                # 简单清洗非法字符
                if any(c in ('/', '\\', ':', '*', '?', '"', '<', '>', '|') for c in title):
                     sys.stderr.write(f"[Error] ppt_title '{title}' contains illegal characters. Save aborted.\n")
                     return
                filename = f"{title}.pptx.html"

            # 2. 确定保存路径
            target_dir = get_storage_dir()
            save_path = os.path.join(target_dir, filename)

            # 3. 读取现有文件内容（用于增量合并）
            existing_pages = {}
            existing_template_url = ""
            
            if os.path.exists(save_path):
                try:
                    with open(save_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        existing_template_url = old_data.get("template_url", "")
                        if isinstance(old_data, dict) and "pages" in old_data:
                            for p in old_data["pages"]:
                                p_idx = int(p.get("page_index", -1))
                                if p_idx >= 0:
                                    existing_pages[p_idx] = p
                except Exception as e:
                    sys.stderr.write(f"[Warning] Failed to read existing file: {e}\n")

            # 4. 合并数据
            # 策略：当前会话的数据覆盖旧数据，但保留旧数据中“已成功”而当前“失败”的部分
            final_pages_map = existing_pages.copy()
            
            # 优先使用新的 template_url，如果没有则保留旧的
            final_template_url = self.template_url if self.template_url else existing_template_url

            for idx, data in self.pages_state.items():
                if data.get("status") == "success":
                    # 成功：直接覆盖
                    page_obj = {
                        "page_index": data["page_index"],
                        "image_url": data["image_url"],
                        "export_image_url": data["export_image_url"],
                        "status": data["status"]
                    }
                    final_pages_map[idx] = page_obj
                elif data.get("status") == "failed":
                    # 失败：检查旧数据是否成功
                    if idx in existing_pages and existing_pages[idx].get("status") == "success":
                        # 保留旧的成功数据，不做覆盖
                        pass
                    else:
                        # 确实失败了，更新为失败状态
                        page_obj = {
                            "page_index": data["page_index"],
                            "image_url": data["image_url"],
                            "export_image_url": data["export_image_url"],
                            "status": data["status"]
                        }
                        final_pages_map[idx] = page_obj

            # 5. 构造并保存
            sorted_indices = sorted(final_pages_map.keys())
            output_pages = []
            for idx in sorted_indices:
                page = final_pages_map[idx]
                # 最终保存时，通常只保留非失败页面，或者全部保留由业务决定
                # 这里逻辑是保留所有，但在 print_json 时可以选择 filter
                if page.get("status") != "failed":
                    output_pages.append(page)

            final_data = {
                "ppt_id": self.ppt_id,
                "ppt_title": self.ppt_title,
                "template_url": final_template_url,
                "pages": output_pages
            }

            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False)

                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"\n[Error] Failed to save file to {save_path}: {e}\n")
                sys.stderr.flush()

    def print_file_saved_message(self):
        """
        打印文件已保存的提示消息，并附带失败页面的汇总报告。
        """
        time.sleep(0.5)
        sys.stdout.flush()
        
        # 统计失败页面
        failed_pages = []
        with self.lock:
            for idx, data in self.pages_state.items():
                if data.get("status") == "failed":
                    failed_pages.append({
                        "page_index": data["page_index"],
                        "prompt": data.get("prompt", ""),
                        "error_msg": data.get("error_msg", "Unknown error")
                    })
        
        if failed_pages:
            print("\n[Generation Errors Report]")
            print(json.dumps(failed_pages, ensure_ascii=False, indent=2))
            sys.stdout.flush()

        title = self.ppt_title or "PPT"
        
        # 打印关键的后续引导信息
        msg = (
            f"\n✅ {title}.pptx.html 文件已保存。\n"
            "请检查上方是否有失败页面报告 ([Generation Errors Report])。\n"
            "- 如有失败页面，参考 6.2 章节使用 generate_batch.py 重试（不要用 modify_batch.py）\n"
            "- 全部成功或达重试上限后，发送卡片展示给用户"
        )
        print(msg)
        sys.stdout.flush()


class GenerationLogger:
    """
    Generation Logger: 记录 PPT 生成过程中的详细参数与元数据。
    生成一个与 PPT 文件对应的 -log.json 文件，用于问题追溯。
    """

    def __init__(self, ppt_title: str, output_file: Optional[str] = None):
        """
        Args:
            ppt_title: PPT 标题
            output_file: 显式指定的输出文件名
        """
        self.ppt_title = ppt_title or "Untitled"
        self.output_file = output_file

        # 内存日志缓存：Key 为 page_index (int)
        self.logs: Dict[int, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _get_log_path(self) -> str:
        """计算日志文件的绝对路径。"""
        # 1. 确定基础文件名
        if self.output_file:
            base_name = os.path.splitext(self.output_file)[0]
            # 如果文件名本身包含 .pptx，再次去除
            if base_name.endswith(".pptx"):
                base_name = os.path.splitext(base_name)[0]
        else:
            # 从标题生成安全的文件名
            base_name = "".join([c for c in self.ppt_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            if not base_name:
                base_name = "PPT"

        filename = f"{base_name}-log.json"

        # 2. 获取目录
        target_dir = get_storage_dir()
        return os.path.join(target_dir, filename)

    def record(self, page_index: int, prompt: str, style: str, ref_images: List[Dict], result_url: str, status: str,
               debug_info: Optional[Dict] = None):
        """线程安全地记录单页生成详情。"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        entry = {
            "page_index": page_index,
            "status": status,
            "result_image_url": result_url,
            "params": {
                "prompt": prompt,
                "global_style": style,
                "ref_images": ref_images
            },
            "debug_info": debug_info or {},
            "timestamp": timestamp
        }

        with self.lock:
            self.logs[page_index] = entry

    def save_log_file(self) -> str:
        """保存日志到文件，支持增量合并。"""
        log_path = self._get_log_path()

        with self.lock:
            # 读取旧日志
            existing_logs = {}
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "records" in data:
                            for k, v in data["records"].items():
                                try:
                                    existing_logs[int(k)] = v
                                except ValueError:
                                    continue
                except Exception as e:
                    print(f"[Logger Warning] Failed to read existing log: {e}", file=sys.stderr)

            # 合并日志
            final_logs = existing_logs.copy()
            final_logs.update(self.logs)

            output_data = {
                "ppt_title": self.ppt_title,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "records": {str(k): v for k, v in sorted(final_logs.items())}
            }

            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                return log_path
            except Exception as e:
                print(f"[Logger Error] Failed to save log file: {e}", file=sys.stderr)
                return ""
