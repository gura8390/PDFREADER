"""
任务调度模块 v2.0
多线程 + 消息队列实现
"""

import threading
import queue
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from utils import setup_logger

logger = setup_logger("worker")


class MessageType(Enum):
    """消息类型"""
    STATUS = "status"              # 状态更新
    PROGRESS = "progress"          # 进度更新
    STATS = "stats"                # 统计信息
    RESULT = "result"              # 结果数据
    LOG = "log"                    # 日志消息
    COMPLETE = "complete"          # 任务完成
    ERROR = "error"                # 任务出错


@dataclass
class WorkerMessage:
    """工作线程消息"""
    type: MessageType
    data: Any = None


class Worker(threading.Thread):
    """工作线程"""
    
    def __init__(self, task_func: Callable, params: Dict, msg_queue: queue.Queue):
        """
        初始化工作线程
        
        Args:
            task_func: 任务函数
            params: 任务参数
            msg_queue: 消息队列
        """
        super().__init__(daemon=True)
        self.task_func = task_func
        self.params = params
        self.msg_queue = msg_queue
        self._stop_event = threading.Event()
    
    def run(self):
        """执行任务"""
        try:
            self.task_func(self.params, self.send_message, self._stop_event)
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            self.send_message(MessageType.ERROR, str(e))
    
    def stop(self):
        """请求停止任务"""
        self._stop_event.set()
    
    def send_message(self, msg_type: MessageType, data: Any = None):
        """发送消息到主线程"""
        msg = WorkerMessage(type=msg_type, data=data)
        self.msg_queue.put(msg)


class TaskManager:
    """任务管理器"""
    
    def __init__(self, msg_queue: queue.Queue):
        """
        初始化任务管理器
        
        Args:
            msg_queue: 消息队列
        """
        self.msg_queue = msg_queue
        self._worker: Optional[Worker] = None
        self._is_running = False
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def start_task(self, task_func: Callable, params: Dict) -> None:
        """
        启动任务
        
        Args:
            task_func: 任务函数
            params: 任务参数
        """
        if self._is_running:
            raise RuntimeError("已有任务在运行")
        
        self._is_running = True
        self._worker = Worker(task_func, params, self.msg_queue)
        self._worker.start()
        
        logger.info("任务已启动")
    
    def stop_task(self) -> None:
        """停止当前任务"""
        if self._worker and self._is_running:
            self._worker.stop()
            logger.info("正在停止任务...")
    
    def on_task_complete(self) -> None:
        """任务完成回调（由主线程调用）"""
        self._is_running = False
        self._worker = None


def analysis_task(params: Dict, send_message: Callable, stop_event: threading.Event) -> None:
    """
    分析任务主函数
    
    Args:
        params: 任务参数
        send_message: 消息发送函数
        stop_event: 停止事件
    """
    from keyword_loader import KeywordLoader
    from pdf_parser_v2 import PDFParserV2
    from match_engine import MatchEngine, MatchMode
    from exporter import Exporter
    from stats import StatsCalculator
    
    start_time = time.time()
    
    # 解析参数
    keyword_file = params['keyword_file']
    pdf_input = params['pdf_input']
    pdf_input_type = params.get('pdf_input_type', 'auto')
    output_path = params['output_path']
    
    match_mode = params.get('match_mode', 'exact')
    case_sensitive = params.get('case_sensitive', True)
    context_length = params.get('context_length', 30)
    
    export_formats = params.get('export_formats', {'excel': True})
    include_context = params.get('include_context', True)
    sort_by = params.get('sort_by', 'count')
    sort_order = params.get('sort_order', 'desc')
    
    use_cache = params.get('use_cache', True)
    use_ocr = params.get('use_ocr', False)
    
    # 步骤1: 加载关键词库
    send_message(MessageType.STATUS, "正在加载关键词库...")
    
    try:
        keywords = KeywordLoader.load(keyword_file)
        send_message(MessageType.LOG, f"加载关键词: {len(keywords)} 个")
    except Exception as e:
        send_message(MessageType.ERROR, f"关键词库加载失败: {e}")
        return
    
    if stop_event.is_set():
        return
    
    # 步骤2: 收集PDF文件
    send_message(MessageType.STATUS, "正在收集PDF文件...")
    
    try:
        parser = PDFParserV2(use_cache=use_cache)
        pdf_files = parser.collect_pdf_files(pdf_input, pdf_input_type)
        send_message(MessageType.LOG, f"找到PDF: {len(pdf_files)} 个")
    except Exception as e:
        send_message(MessageType.ERROR, f"PDF文件收集失败: {e}")
        return
    
    if stop_event.is_set():
        return
    
    # 步骤3: 解析PDF
    send_message(MessageType.STATUS, "正在解析PDF...")
    parse_start = time.time()
    
    def parse_progress(pdf_name, current_page, total_pages, current_file, total_files):
        # 计算总进度
        overall_progress = ((current_file - 1) * total_pages + current_page) / (total_files * total_pages) * 50
        send_message(MessageType.PROGRESS, {
            'phase': 'parse',
            'progress': overall_progress,
            'detail': f"{pdf_name} ({current_file}/{total_files}) {current_page}/{total_pages}"
        })
    
    try:
        parsed_result = parser.parse_multiple_pdfs(pdf_files, parse_progress)
        parse_time = time.time() - parse_start
        send_message(MessageType.LOG, f"PDF解析完成: {parsed_result.total_pages} 页, 耗时 {parse_time:.1f}秒")
    except Exception as e:
        send_message(MessageType.ERROR, f"PDF解析失败: {e}")
        return
    
    if stop_event.is_set():
        return
    
    # 步骤4: OCR处理（如果需要）
    auto_detect_ocr = params.get('auto_detect_ocr', True)
    ocr_language = params.get('ocr_language', 'chi_sim+eng')
    
    if use_ocr:
        from ocr_module import OCRModule
        ocr = OCRModule(language=ocr_language)
        
        if ocr.is_available():
            send_message(MessageType.STATUS, "正在OCR识别...")
            send_message(MessageType.LOG, f"OCR语言: {ocr_language}")
            
            # 检查哪些页面需要OCR
            pages_needing_ocr = [p for p in parsed_result.pages if not p.has_text]
            
            if pages_needing_ocr:
                send_message(MessageType.LOG, f"发现 {len(pages_needing_ocr)} 页需要OCR识别")
                
                for i, page in enumerate(pages_needing_ocr):
                    try:
                        ocr_text = ocr.ocr_pdf_page(page.pdf_path, page.page_num)
                        if ocr_text:
                            page.text = ocr_text
                            page.has_text = True
                            send_message(MessageType.LOG, f"OCR完成: {page.pdf_name} 第{page.page_num}页")
                    except Exception as e:
                        send_message(MessageType.LOG, f"OCR失败: {page.pdf_name} 第{page.page_num}页 - {e}")
                    
                    # 更新进度
                    progress = 50 + (i / len(pages_needing_ocr)) * 10
                    send_message(MessageType.PROGRESS, {
                        'phase': 'ocr',
                        'progress': progress,
                        'detail': f"OCR {i+1}/{len(pages_needing_ocr)} 页"
                    })
            else:
                send_message(MessageType.LOG, "所有页面都包含文字，无需OCR")
        else:
            send_message(MessageType.LOG, "OCR模块不可用，请安装: pip install pytesseract pillow pdf2image")
            send_message(MessageType.LOG, ocr.get_install_instructions())
    
    if stop_event.is_set():
        return
    
    # 步骤5: 匹配关键词
    send_message(MessageType.STATUS, "正在匹配关键词...")
    match_start = time.time()
    
    mode_map = {
        'exact': MatchMode.EXACT,
        'fuzzy': MatchMode.FUZZY,
        'regex': MatchMode.REGEX
    }
    
    def match_progress(current, total):
        progress = 50 + (current / total) * 40
        send_message(MessageType.PROGRESS, {
            'phase': 'match',
            'progress': progress,
            'detail': f"匹配 {current}/{total} 页"
        })
    
    try:
        engine = MatchEngine(
            mode=mode_map.get(match_mode, MatchMode.EXACT),
            case_sensitive=case_sensitive,
            context_length=context_length
        )
        
        match_result = engine.match_all(parsed_result.pages, keywords, match_progress)
        match_time = time.time() - match_start
        send_message(MessageType.LOG, f"匹配完成: {match_result.total_hits} 次命中, 耗时 {match_time:.1f}秒")
    except Exception as e:
        send_message(MessageType.ERROR, f"匹配失败: {e}")
        return
    
    if stop_event.is_set():
        return
    
    # 步骤6: 导出结果
    send_message(MessageType.STATUS, "正在导出结果...")
    export_start = time.time()
    
    try:
        stats = StatsCalculator.calculate(
            match_result,
            parsed_result,
            total_time=time.time() - start_time,
            parse_time=parse_time,
            match_time=match_time
        )
        
        generated_files = Exporter.export(
            match_result,
            output_path,
            formats=export_formats,
            stats=stats,
            include_context=include_context,
            context_length=context_length,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        export_time = time.time() - export_start
        send_message(MessageType.LOG, f"导出完成: {len(generated_files)} 个文件, 耗时 {export_time:.1f}秒")
    except Exception as e:
        send_message(MessageType.ERROR, f"导出失败: {e}")
        return
    
    # 完成
    total_time = time.time() - start_time
    
    send_message(MessageType.PROGRESS, {'phase': 'complete', 'progress': 100, 'detail': '完成'})
    send_message(MessageType.RESULT, {
        'match_result': match_result,
        'stats': stats,
        'generated_files': generated_files
    })
    send_message(MessageType.COMPLETE, {
        'total_time': total_time,
        'generated_files': generated_files
    })
