"""
PDF关键词分析工具 v2.0 - 主程序
左侧功能区 + 右侧结果区布局
"""

import os
import sys
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Optional

from config import get_config
from keyword_loader import KeywordLoader
from cache_manager import CacheManager
from worker import TaskManager, MessageType
from utils import format_duration

# 导入消息类型常量
MSG_STATUS = MessageType.STATUS
MSG_PROGRESS = MessageType.PROGRESS
MSG_STATS = MessageType.STATS
MSG_RESULT = MessageType.RESULT
MSG_LOG = MessageType.LOG
MSG_COMPLETE = MessageType.COMPLETE
MSG_ERROR = MessageType.ERROR


class PDFKeywordAnalyzerApp:
    """PDF关键词分析工具主窗口"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Keyword Analyzer v2.0")
        
        # 加载配置
        self.config = get_config()
        
        # 设置窗口大小
        width = self.config.get("window", "width", default=1200)
        height = self.config.get("window", "height", default=800)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1000, 600)
        
        # 消息队列
        self.msg_queue = queue.Queue()
        
        # 任务管理器
        self.task_manager = TaskManager(self.msg_queue)
        
        # 缓存管理器
        self.cache_manager = CacheManager(
            max_age_days=self.config.get("cache", "max_age_days", default=30),
            max_size_mb=self.config.get("cache", "max_size_mb", default=500)
        )
        
        # 匹配结果
        self.match_result = None
        self.stats = None
        
        # 创建界面
        self.create_widgets()
        
        # 启动队列轮询
        self.poll_queue()
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """创建主界面布局"""
        # 主容器
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 左侧边栏
        self.create_sidebar(main_container)
        
        # 右侧内容区
        self.create_content_area(main_container)
    
    def create_sidebar(self, parent):
        """创建左侧功能区"""
        sidebar = ttk.Frame(parent, width=300)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # 固定顶部：Logo/标题
        title_frame = ttk.Frame(sidebar)
        title_frame.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Label(
            title_frame,
            text="PDF Keyword\nAnalyzer",
            font=('Arial', 16, 'bold'),
            foreground='#4CAF50'
        ).pack(anchor=tk.W)
        
        ttk.Label(title_frame, text="v2.0", foreground='#888888').pack(anchor=tk.W)
        
        # 分隔线
        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=5)
        
        # 可滚动中间区域：输入+设置
        canvas = tk.Canvas(sidebar, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(sidebar, orient=tk.VERTICAL, command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=280)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === 输入区域 ===
        self.create_input_section(self.scrollable_frame)
        
        # === 设置区域 ===
        self.create_settings_section(self.scrollable_frame)
        
        # 固定底部：操作按钮
        self.create_action_buttons(sidebar)
    
    def create_input_section(self, parent):
        """创建输入区域"""
        # 关键词库
        section = ttk.Frame(parent)
        section.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        ttk.Label(section, text="关键词库").pack(anchor=tk.W)
        
        input_frame = ttk.Frame(section)
        input_frame.pack(fill=tk.X, pady=(2, 0))
        
        self.keyword_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.keyword_var, width=25).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame, text="浏览", command=self.browse_keyword, width=6).pack(side=tk.LEFT, padx=(5, 0))
        
        # 格式提示
        self.keyword_format_label = ttk.Label(section, text="支持: TXT/CSV/Excel/JSON", foreground='#666666', font=('Arial', 8))
        self.keyword_format_label.pack(anchor=tk.W, pady=(2, 0))
        
        # PDF输入
        section2 = ttk.Frame(parent)
        section2.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        ttk.Label(section2, text="PDF文件").pack(anchor=tk.W)
        
        # PDF输入类型选择
        type_frame = ttk.Frame(section2)
        type_frame.pack(fill=tk.X, pady=(2, 5))
        
        self.pdf_type_var = tk.StringVar(value="single")
        ttk.Radiobutton(type_frame, text="单个文件", variable=self.pdf_type_var, value="single").pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text="多个文件", variable=self.pdf_type_var, value="multiple").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(type_frame, text="整个目录", variable=self.pdf_type_var, value="folder").pack(side=tk.LEFT, padx=(10, 0))
        
        # PDF路径
        input_frame2 = ttk.Frame(section2)
        input_frame2.pack(fill=tk.X)
        
        self.pdf_var = tk.StringVar()
        ttk.Entry(input_frame2, textvariable=self.pdf_var, width=25).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame2, text="浏览", command=self.browse_pdf, width=6).pack(side=tk.LEFT, padx=(5, 0))
        
        # 输出路径
        section3 = ttk.Frame(parent)
        section3.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        ttk.Label(section3, text="输出路径").pack(anchor=tk.W)
        
        input_frame3 = ttk.Frame(section3)
        input_frame3.pack(fill=tk.X, pady=(2, 0))
        
        self.output_var = tk.StringVar()
        ttk.Entry(input_frame3, textvariable=self.output_var, width=25).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame3, text="浏览", command=self.browse_output, width=6).pack(side=tk.LEFT, padx=(5, 0))
    
    def create_settings_section(self, parent):
        """创建设置区域"""
        section = ttk.Frame(parent)
        section.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ttk.Label(section, text="匹配设置").pack(anchor=tk.W)
        
        # 匹配模式
        mode_frame = ttk.Frame(section)
        mode_frame.pack(fill=tk.X, pady=(5, 5))
        
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT)
        self.match_mode_var = tk.StringVar(value="exact")
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.match_mode_var, values=["exact", "fuzzy", "regex"], width=10, state="readonly")
        mode_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # 区分大小写
        self.case_sensitive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(section, text="区分大小写", variable=self.case_sensitive_var).pack(anchor=tk.W, pady=(0, 5))
        
        # 上下文长度
        ctx_frame = ttk.Frame(section)
        ctx_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(ctx_frame, text="上下文长度:").pack(side=tk.LEFT)
        self.context_length_var = tk.IntVar(value=30)
        ttk.Spinbox(ctx_frame, from_=10, to=200, textvariable=self.context_length_var, width=5).pack(side=tk.LEFT, padx=(5, 0))
        
        # 导出格式
        ttk.Label(section, text="导出格式:").pack(anchor=tk.W, pady=(5, 0))
        
        self.export_excel_var = tk.BooleanVar(value=True)
        self.export_csv_var = tk.BooleanVar(value=False)
        self.export_json_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(section, text="Excel", variable=self.export_excel_var).pack(anchor=tk.W)
        ttk.Checkbutton(section, text="CSV", variable=self.export_csv_var).pack(anchor=tk.W)
        ttk.Checkbutton(section, text="JSON", variable=self.export_json_var).pack(anchor=tk.W)
        
        # 包含上下文
        self.include_context_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(section, text="包含上下文", variable=self.include_context_var).pack(anchor=tk.W, pady=(5, 0))
        
        # 缓存设置
        cache_frame = ttk.Frame(section)
        cache_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.use_cache_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cache_frame, text="使用缓存", variable=self.use_cache_var).pack(side=tk.LEFT)
        
        ttk.Button(cache_frame, text="清除缓存", command=self.clear_cache, width=8).pack(side=tk.RIGHT)
        
        # 缓存大小显示
        cache_size = self.cache_manager.get_total_size_str()
        self.cache_size_label = ttk.Label(section, text=f"缓存: {cache_size}", foreground='#666666', font=('Arial', 8))
        self.cache_size_label.pack(anchor=tk.W, pady=(2, 0))
        
        # OCR设置
        ttk.Separator(section, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(section, text="OCR设置:").pack(anchor=tk.W)
        
        ocr_frame = ttk.Frame(section)
        ocr_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.use_ocr_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ocr_frame, text="启用OCR（扫描PDF）", variable=self.use_ocr_var).pack(anchor=tk.W)
        
        self.auto_detect_ocr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ocr_frame, text="自动检测是否需要OCR", variable=self.auto_detect_ocr_var).pack(anchor=tk.W, pady=(2, 0))
        
        lang_frame = ttk.Frame(section)
        lang_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(lang_frame, text="OCR语言:").pack(side=tk.LEFT)
        self.ocr_lang_var = tk.StringVar(value="chi_sim+eng")
        ocr_lang_combo = ttk.Combobox(lang_frame, textvariable=self.ocr_lang_var, 
                                       values=["chi_sim+eng", "chi_sim", "eng", "jpn", "kor"], 
                                       width=12, state="readonly")
        ocr_lang_combo.pack(side=tk.LEFT, padx=(5, 0))
    
    def create_action_buttons(self, parent):
        """创建操作按钮"""
        section = ttk.Frame(parent)
        section.pack(fill=tk.X, padx=15, pady=(20, 10))
        
        # 开始分析按钮
        self.start_button = tk.Button(
            section,
            text="▶  开始分析",
            command=self.start_analysis,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 12, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        self.start_button.pack(fill=tk.X)
        
        # 停止按钮
        self.stop_button = tk.Button(
            section,
            text="■  停止",
            command=self.stop_analysis,
            bg='#f44336',
            fg='white',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=20,
            pady=5,
            state=tk.DISABLED,
            cursor='hand2'
        )
        self.stop_button.pack(fill=tk.X, pady=(5, 0))
    
    def create_content_area(self, parent):
        """创建右侧内容区"""
        content = ttk.Frame(parent)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 顶部：进度和状态
        self.create_progress_area(content)
        
        # 中间：选项卡（结果/统计/日志）
        self.create_notebook(content)
    
    def create_progress_area(self, parent):
        """创建进度区域"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.X)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        # 进度标签
        self.progress_label = ttk.Label(frame, text="就绪", width=50)
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def create_notebook(self, parent):
        """创建选项卡"""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 结果预览选项卡
        self.create_result_tab()
        
        # 统计信息选项卡
        self.create_stats_tab()
        
        # 日志选项卡
        self.create_log_tab()
    
    def create_result_tab(self):
        """创建结果预览选项卡"""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="结果预览")
        
        # 搜索框
        search_frame = ttk.Frame(tab)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_changed)
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT, padx=(5, 0))
        
        # 排序选项
        ttk.Label(search_frame, text="排序:").pack(side=tk.LEFT, padx=(20, 0))
        self.sort_by_var = tk.StringVar(value="count")
        ttk.Combobox(search_frame, textvariable=self.sort_by_var, values=["count", "name", "first_page"], width=10, state="readonly").pack(side=tk.LEFT, padx=(5, 0))
        
        self.sort_order_var = tk.StringVar(value="desc")
        ttk.Combobox(search_frame, textvariable=self.sort_order_var, values=["desc", "asc"], width=6, state="readonly").pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(search_frame, text="刷新", command=self.refresh_result_table).pack(side=tk.LEFT, padx=(10, 0))
        
        # 结果表格
        columns = ("keyword", "count", "pages", "first_page", "last_page", "pdf_count")
        self.result_tree = ttk.Treeview(tab, columns=columns, show="headings", height=15)
        
        # 设置列标题和宽度
        self.result_tree.heading("keyword", text="关键词", command=lambda: self.sort_table("name"))
        self.result_tree.heading("count", text="出现次数", command=lambda: self.sort_table("count"))
        self.result_tree.heading("pages", text="出现页码")
        self.result_tree.heading("first_page", text="首次出现", command=lambda: self.sort_table("first_page"))
        self.result_tree.heading("last_page", text="最后出现")
        self.result_tree.heading("pdf_count", text="PDF数量")
        
        self.result_tree.column("keyword", width=120, minwidth=80)
        self.result_tree.column("count", width=80, minwidth=60, anchor=tk.CENTER)
        self.result_tree.column("pages", width=250, minwidth=150)
        self.result_tree.column("first_page", width=80, minwidth=60, anchor=tk.CENTER)
        self.result_tree.column("last_page", width=80, minwidth=60, anchor=tk.CENTER)
        self.result_tree.column("pdf_count", width=80, minwidth=60, anchor=tk.CENTER)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 双击查看详情
        self.result_tree.bind('<Double-1>', self.on_result_double_click)
    
    def create_stats_tab(self):
        """创建统计信息选项卡"""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="统计信息")
        
        # 统计信息文本
        self.stats_text = tk.Text(tab, wrap=tk.WORD, font=('Consolas', 10))
        stats_scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=stats_scrollbar.set)
        
        self.stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 初始化内容
        self.stats_text.insert('1.0', "等待分析...")
        self.stats_text.config(state=tk.DISABLED)
    
    def create_log_tab(self):
        """创建日志选项卡"""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="日志")
        
        # 日志文本
        self.log_text = tk.Text(tab, wrap=tk.WORD, font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4')
        log_scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # ==================== 文件浏览 ====================
    
    def browse_keyword(self):
        """浏览关键词库文件"""
        filename = filedialog.askopenfilename(
            title="选择关键词库文件",
            filetypes=[
                ("所有支持格式", "*.txt *.csv *.xlsx *.xls *.json"),
                ("文本文件", "*.txt"),
                ("CSV文件", "*.csv"),
                ("Excel文件", "*.xlsx *.xls"),
                ("JSON文件", "*.json"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.keyword_var.set(filename)
            self.config.update_recent(keyword_dir=os.path.dirname(filename))
            
            # 显示格式信息
            fmt = KeywordLoader.get_format_description(filename)
            self.keyword_format_label.config(text=fmt)
    
    def browse_pdf(self):
        """浏览PDF文件"""
        pdf_type = self.pdf_type_var.get()
        
        if pdf_type == "single":
            filename = filedialog.askopenfilename(
                title="选择PDF文件",
                filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
            )
            if filename:
                self.pdf_var.set(filename)
                self.config.update_recent(pdf_dir=os.path.dirname(filename))
        
        elif pdf_type == "folder":
            dirname = filedialog.askdirectory(title="选择PDF文件夹")
            if dirname:
                self.pdf_var.set(dirname)
                self.config.update_recent(pdf_dir=dirname)
        
        else:  # multiple
            filenames = filedialog.askopenfilenames(
                title="选择多个PDF文件",
                filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
            )
            if filenames:
                self.pdf_var.set(';'.join(filenames))
                self.config.update_recent(pdf_dir=os.path.dirname(filenames[0]))
        
        # 自动生成输出路径
        if self.pdf_var.get() and not self.output_var.get():
            from exporter import Exporter
            output = Exporter.get_output_filename(self.pdf_var.get())
            self.output_var.set(output)
    
    def browse_output(self):
        """浏览输出路径"""
        filename = filedialog.asksaveasfilename(
            title="保存结果",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        if filename:
            base = os.path.splitext(filename)[0]
            self.output_var.set(base)
    
    # ==================== 操作 ====================
    
    def start_analysis(self):
        """开始分析"""
        if self.task_manager.is_running:
            return
        
        # 验证输入
        keyword_file = self.keyword_var.get()
        pdf_input = self.pdf_var.get()
        output_path = self.output_var.get()
        
        if not keyword_file:
            messagebox.showwarning("警告", "请选择关键词库文件")
            return
        
        if not pdf_input:
            messagebox.showwarning("警告", "请选择PDF文件")
            return
        
        if not output_path:
            messagebox.showwarning("警告", "请指定输出路径")
            return
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.progress_label.config(text="正在准备...")
        
        # 清空日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # 准备参数
        params = {
            'keyword_file': keyword_file,
            'pdf_input': pdf_input,
            'pdf_input_type': self.pdf_type_var.get(),
            'output_path': output_path,
            'match_mode': self.match_mode_var.get(),
            'case_sensitive': self.case_sensitive_var.get(),
            'context_length': self.context_length_var.get(),
            'export_formats': {
                'excel': self.export_excel_var.get(),
                'csv': self.export_csv_var.get(),
                'json': self.export_json_var.get()
            },
            'include_context': self.include_context_var.get(),
            'sort_by': self.sort_by_var.get(),
            'sort_order': self.sort_order_var.get(),
            'use_cache': self.use_cache_var.get(),
            'use_ocr': self.use_ocr_var.get(),
            'auto_detect_ocr': self.auto_detect_ocr_var.get(),
            'ocr_language': self.ocr_lang_var.get()
        }
        
        # 启动任务
        from worker import analysis_task
        self.task_manager.start_task(analysis_task, params)
        
        self.add_log("分析任务已启动...")
    
    def stop_analysis(self):
        """停止分析"""
        self.task_manager.stop_task()
        self.add_log("正在停止...")
    
    def clear_cache(self):
        """清除缓存"""
        count = self.cache_manager.clear_all()
        messagebox.showinfo("清除缓存", f"已清除 {count} 个缓存文件")
        
        cache_size = self.cache_manager.get_total_size_str()
        self.cache_size_label.config(text=f"缓存: {cache_size}")
    
    # ==================== 队列轮询 ====================
    
    def poll_queue(self):
        """轮询消息队列"""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.handle_message(msg)
        except queue.Empty:
            pass
        
        self.root.after(100, self.poll_queue)
    
    def handle_message(self, msg):
        """处理消息"""
        if msg.type == MSG_STATUS:
            self.progress_label.config(text=msg.data)
        
        elif msg.type == MSG_PROGRESS:
            if isinstance(msg.data, dict):
                self.progress_var.set(msg.data.get('progress', 0))
                detail = msg.data.get('detail', '')
                if detail:
                    self.progress_label.config(text=detail)
            else:
                self.progress_var.set(msg.data)
        
        elif msg.type == MSG_LOG:
            self.add_log(msg.data)
        
        elif msg.type == MSG_RESULT:
            self.match_result = msg.data.get('match_result')
            self.stats = msg.data.get('stats')
            self.update_result_table()
            self.update_stats_display()
        
        elif msg.type == MSG_COMPLETE:
            self.task_manager.on_task_complete()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
            total_time = msg.data.get('total_time', 0)
            files = msg.data.get('generated_files', [])
            
            self.progress_var.set(100)
            self.progress_label.config(text=f"完成! 耗时: {format_duration(total_time)}")
            
            self.add_log(f"分析完成! 耗时: {format_duration(total_time)}")
            for f in files:
                self.add_log(f"已导出: {f}")
            
            messagebox.showinfo("完成", f"分析完成!\n\n耗时: {format_duration(total_time)}\n\n已导出 {len(files)} 个文件")
        
        elif msg.type == MSG_ERROR:
            self.task_manager.on_task_complete()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_label.config(text=f"错误: {msg.data}")
            self.add_log(f"错误: {msg.data}")
            messagebox.showerror("错误", msg.data)
    
    def add_log(self, text: str):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    # ==================== 结果显示 ====================
    
    def update_result_table(self):
        """更新结果表格"""
        if not self.match_result:
            return
        
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        from stats import StatsCalculator
        table_data = StatsCalculator.get_keyword_table(
            self.match_result,
            self.sort_by_var.get(),
            self.sort_order_var.get()
        )
        
        search_text = self.search_var.get().strip()
        if search_text:
            table_data = [d for d in table_data if search_text.lower() in d['keyword'].lower()]
        
        for data in table_data:
            self.result_tree.insert("", tk.END, values=(
                data['keyword'],
                data['count'],
                data['pages'],
                data['first_page'] if data['first_page'] > 0 else '',
                data['last_page'] if data['last_page'] > 0 else '',
                data['pdf_count']
            ))
    
    def update_stats_display(self):
        """更新统计信息显示"""
        if not self.stats:
            return
        
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', self.stats.get_summary())
        self.stats_text.config(state=tk.DISABLED)
    
    def refresh_result_table(self):
        """刷新结果表格"""
        self.update_result_table()
    
    def sort_table(self, sort_by):
        """排序表格"""
        self.sort_by_var.set(sort_by)
        current = self.sort_order_var.get()
        self.sort_order_var.set("asc" if current == "desc" else "desc")
        self.update_result_table()
    
    def on_search_changed(self, *args):
        """搜索文本变化"""
        self.update_result_table()
    
    def on_result_double_click(self, event):
        """双击结果行"""
        selection = self.result_tree.selection()
        if not selection:
            return
        
        item = self.result_tree.item(selection[0])
        keyword = item['values'][0]
        self.show_context_detail(keyword)
    
    def show_context_detail(self, keyword: str):
        """显示上下文详情"""
        if not self.match_result or keyword not in self.match_result.keywords:
            return
        
        kw_result = self.match_result.keywords[keyword]
        
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"上下文详情 - {keyword}")
        detail_window.geometry("700x500")
        
        columns = ("pdf", "page", "context")
        tree = ttk.Treeview(detail_window, columns=columns, show="headings", height=15)
        
        tree.heading("pdf", text="PDF文件")
        tree.heading("page", text="页码")
        tree.heading("context", text="上下文")
        
        tree.column("pdf", width=150)
        tree.column("page", width=60, anchor=tk.CENTER)
        tree.column("context", width=450)
        
        scrollbar = ttk.Scrollbar(detail_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        from context_extractor import ContextExtractor
        contexts = ContextExtractor.get_all_contexts_for_keyword(kw_result.hits, 50)
        
        for ctx in contexts:
            tree.insert("", tk.END, values=(ctx.pdf_name, ctx.page_num, ctx.full_context))
    
    # ==================== 窗口事件 ====================
    
    def on_closing(self):
        """窗口关闭"""
        if self.task_manager.is_running:
            if messagebox.askokcancel("退出", "分析正在进行中，确定要退出吗？"):
                self.task_manager.stop_task()
                self.root.destroy()
        else:
            self.root.update_idletasks()
            self.config.update_window(
                width=self.root.winfo_width(),
                height=self.root.winfo_height(),
                x=self.root.winfo_x(),
                y=self.root.winfo_y()
            )
            self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    app = PDFKeywordAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
