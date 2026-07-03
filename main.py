"""
PDF人名匹配工具 - 主程序
带GUI界面的人名匹配应用程序
多线程设计：避免GUI在处理大PDF时卡死
"""

import os
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Optional

from utils import read_name_list, setup_logger, format_duration, get_file_size_str
from pdf_parser import parse_pdf, clear_cache, get_pdf_info
from name_matcher import match_all_pages, get_match_statistics
from excel_exporter import export_to_excel, get_output_filename

logger = setup_logger("main")

# 消息类型常量
MSG_PROGRESS = "progress"      # 进度更新
MSG_STATUS = "status"          # 状态更新
MSG_STATS = "stats"            # 统计信息更新
MSG_RESULT = "result"          # 结果预览更新
MSG_COMPLETE = "complete"      # 任务完成
MSG_ERROR = "error"            # 任务出错


class Message:
    """线程间通信的消息对象"""
    def __init__(self, msg_type: str, data: any = None):
        self.type = msg_type
        self.data = data


class PDFNameMatcherApp:
    """PDF人名匹配工具主窗口"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF人名匹配工具 v1.0")
        self.root.geometry("800x700")
        self.root.minsize(700, 600)
        
        # 线程通信队列
        self.msg_queue = queue.Queue()
        
        # 状态变量
        self.is_running = False
        self.worker_thread = None
        self.match_result = None
        self.stats = None
        self.duration = 0
        
        # 创建界面
        self.create_widgets()
        
        # 居中窗口
        self.center_window()
        
        # 启动队列轮询
        self.poll_queue()
    
    def center_window(self):
        """窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        """创建所有界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 文件选择区域
        self.create_file_selection(main_frame)
        
        # 选项区域
        self.create_options(main_frame)
        
        # 按钮区域
        self.create_buttons(main_frame)
        
        # 进度条
        self.create_progress(main_frame)
        
        # 统计信息区域
        self.create_stats_panel(main_frame)
        
        # 结果预览区域
        self.create_result_preview(main_frame)
        
        # 状态栏
        self.create_status_bar()
    
    def create_file_selection(self, parent):
        """创建文件选择组件"""
        file_frame = ttk.LabelFrame(parent, text="文件选择", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 人名库文件
        row1 = ttk.Frame(file_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="人名库文件:", width=12).pack(side=tk.LEFT)
        self.name_file_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.name_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row1, text="浏览...", command=self.browse_name_file, width=8).pack(side=tk.LEFT)
        
        # PDF文件
        row2 = ttk.Frame(file_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="PDF文件:", width=12).pack(side=tk.LEFT)
        self.pdf_file_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.pdf_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row2, text="浏览...", command=self.browse_pdf_file, width=8).pack(side=tk.LEFT)
        
        # 输出文件
        row3 = ttk.Frame(file_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="输出文件:", width=12).pack(side=tk.LEFT)
        self.output_file_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.output_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row3, text="浏览...", command=self.browse_output_file, width=8).pack(side=tk.LEFT)
    
    def create_options(self, parent):
        """创建选项组件"""
        options_frame = ttk.LabelFrame(parent, text="匹配选项", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 选项行
        options_row = ttk.Frame(options_frame)
        options_row.pack(fill=tk.X)
        
        # 使用缓存
        self.use_cache_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_row, text="使用缓存（加速重复解析）", 
                        variable=self.use_cache_var).pack(side=tk.LEFT, padx=(0, 20))
        
        # 区分大小写
        self.case_sensitive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_row, text="区分大小写", 
                        variable=self.case_sensitive_var).pack(side=tk.LEFT)
    
    def create_buttons(self, parent):
        """创建按钮组件"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 开始匹配按钮
        self.start_button = ttk.Button(button_frame, text="开始匹配", command=self.start_matching)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 停止按钮
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_matching, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 清除缓存按钮
        ttk.Button(button_frame, text="清除缓存", command=self.clear_cache).pack(side=tk.LEFT, padx=(0, 10))
        
        # 打开输出目录按钮
        ttk.Button(button_frame, text="打开输出目录", command=self.open_output_dir).pack(side=tk.LEFT)
    
    def create_progress(self, parent):
        """创建进度条"""
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        # 进度标签
        self.progress_label = ttk.Label(progress_frame, text="0%", width=8)
        self.progress_label.pack(side=tk.LEFT, padx=(5, 0))
    
    def create_stats_panel(self, parent):
        """创建统计信息面板"""
        stats_frame = ttk.LabelFrame(parent, text="统计信息", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 统计信息文本
        self.stats_text = tk.Text(stats_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.stats_text.pack(fill=tk.X)
        
        # 初始化统计信息
        self.update_stats_text("等待开始匹配...")
    
    def create_result_preview(self, parent):
        """创建结果预览表格"""
        result_frame = ttk.LabelFrame(parent, text="结果预览", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格
        columns = ("name", "count", "pages")
        self.result_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=10)
        
        # 设置列标题
        self.result_tree.heading("name", text="名称")
        self.result_tree.heading("count", text="出现次数")
        self.result_tree.heading("pages", text="出现页码")
        
        # 设置列宽
        self.result_tree.column("name", width=100, minwidth=80)
        self.result_tree.column("count", width=80, minwidth=60, anchor=tk.CENTER)
        self.result_tree.column("pages", width=400, minwidth=200)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # ==================== 文件浏览 ====================
    
    def browse_name_file(self):
        """浏览人名库文件"""
        filename = filedialog.askopenfilename(
            title="选择人名库文件",
            filetypes=[("文本文件", "*.txt *.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.name_file_var.set(filename)
            self.update_status(f"已选择人名库: {os.path.basename(filename)}")
    
    def browse_pdf_file(self):
        """浏览PDF文件"""
        filename = filedialog.askopenfilename(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        if filename:
            self.pdf_file_var.set(filename)
            # 自动生成输出文件名
            output_file = get_output_filename(filename)
            self.output_file_var.set(output_file)
            
            # 显示PDF信息
            try:
                pdf_info = get_pdf_info(filename)
                self.update_stats_text(f"PDF文件: {os.path.basename(filename)}\n"
                                       f"页数: {pdf_info['page_count']} 页\n"
                                       f"大小: {get_file_size_str(filename)}")
            except Exception as e:
                self.update_stats_text(f"PDF文件: {os.path.basename(filename)}")
            
            self.update_status(f"已选择PDF: {os.path.basename(filename)}")
    
    def browse_output_file(self):
        """浏览输出文件"""
        filename = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        if filename:
            self.output_file_var.set(filename)
    
    # ==================== 按钮操作 ====================
    
    def clear_cache(self):
        """清除缓存"""
        try:
            count = clear_cache()
            messagebox.showinfo("清除缓存", f"已清除 {count} 个缓存文件")
            self.update_status(f"已清除 {count} 个缓存文件")
        except Exception as e:
            messagebox.showerror("错误", f"清除缓存失败: {e}")
    
    def open_output_dir(self):
        """打开输出目录"""
        output_file = self.output_file_var.get()
        if output_file and os.path.exists(os.path.dirname(output_file)):
            os.startfile(os.path.dirname(output_file))
        else:
            # 打开当前目录
            os.startfile(os.getcwd())
    
    # ==================== GUI更新方法 ====================
    
    def update_stats_text(self, text: str):
        """更新统计信息显示"""
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, text)
        self.stats_text.config(state=tk.DISABLED)
    
    def update_progress(self, current: int, total: int):
        """更新进度条"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            self.progress_label.config(text=f"{progress:.0f}%")
    
    def update_status(self, text: str):
        """更新状态栏"""
        self.status_var.set(text)
    
    def clear_result_preview(self):
        """清空结果预览表格"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
    
    def update_result_preview(self, match_result: Dict):
        """更新结果预览表格"""
        self.clear_result_preview()
        
        if not match_result:
            return
        
        # 按出现次数降序排序
        sorted_results = sorted(
            match_result.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        # 插入数据（最多显示100条）
        for name, data in sorted_results[:100]:
            pages_str = ", ".join(str(p) for p in data['pages'][:10])
            if len(data['pages']) > 10:
                pages_str += f" ... (共{len(data['pages'])}页)"
            
            self.result_tree.insert("", tk.END, values=(name, data['count'], pages_str))
    
    def validate_inputs(self) -> bool:
        """验证输入"""
        name_file = self.name_file_var.get()
        pdf_file = self.pdf_file_var.get()
        output_file = self.output_file_var.get()
        
        if not name_file:
            messagebox.showwarning("警告", "请选择人名库文件")
            return False
        
        if not os.path.exists(name_file):
            messagebox.showwarning("警告", "人名库文件不存在")
            return False
        
        if not pdf_file:
            messagebox.showwarning("警告", "请选择PDF文件")
            return False
        
        if not os.path.exists(pdf_file):
            messagebox.showwarning("警告", "PDF文件不存在")
            return False
        
        if not output_file:
            messagebox.showwarning("警告", "请指定输出文件路径")
            return False
        
        return True
    
    # ==================== 多线程核心逻辑 ====================
    
    def poll_queue(self):
        """
        定期轮询消息队列，处理后台线程发送的消息
        每100ms检查一次队列
        """
        try:
            while True:
                # 非阻塞方式获取消息
                msg = self.msg_queue.get_nowait()
                self.handle_message(msg)
        except queue.Empty:
            pass
        
        # 继续轮询
        self.root.after(100, self.poll_queue)
    
    def handle_message(self, msg: Message):
        """处理来自后台线程的消息"""
        if msg.type == MSG_PROGRESS:
            # 进度更新: data = (current, total)
            current, total = msg.data
            self.update_progress(current, total)
        
        elif msg.type == MSG_STATUS:
            # 状态更新: data = status_text
            self.update_status(msg.data)
        
        elif msg.type == MSG_STATS:
            # 统计信息更新: data = stats_text
            self.update_stats_text(msg.data)
        
        elif msg.type == MSG_RESULT:
            # 结果预览更新: data = match_result
            self.update_result_preview(msg.data)
        
        elif msg.type == MSG_COMPLETE:
            # 任务完成: data = (output_file, stats, duration)
            output_file, stats, duration = msg.data
            self.matching_complete(output_file, stats, duration)
        
        elif msg.type == MSG_ERROR:
            # 任务出错: data = error_message
            self.matching_failed(msg.data)
    
    def start_matching(self):
        """开始匹配（启动后台线程）"""
        if self.is_running:
            return
        
        if not self.validate_inputs():
            return
        
        # 更新UI状态
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 清空结果
        self.clear_result_preview()
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        
        # 获取参数
        params = {
            'name_file': self.name_file_var.get(),
            'pdf_file': self.pdf_file_var.get(),
            'output_file': self.output_file_var.get(),
            'use_cache': self.use_cache_var.get(),
            'case_sensitive': self.case_sensitive_var.get(),
        }
        
        # 启动后台工作线程
        self.worker_thread = threading.Thread(
            target=self.worker_task,
            args=(params,),
            daemon=True
        )
        self.worker_thread.start()
        
        self.update_status("正在匹配...")
    
    def stop_matching(self):
        """停止匹配"""
        # 注意：由于Python的GIL和线程机制，无法强制停止线程
        # 这里只是更新状态，实际的停止需要在线程中检查标志
        self.is_running = False
        self.update_status("正在停止...")
        self.stop_button.config(state=tk.DISABLED)
    
    def worker_task(self, params: Dict):
        """
        后台工作线程任务
        执行所有耗时操作：PDF解析、人名匹配、Excel导出
        
        Args:
            params: 包含所有参数的字典
        """
        start_time = time.time()
        
        try:
            # 步骤1: 读取人名库
            self.send_message(MSG_STATUS, "正在读取人名库...")
            self.send_message(MSG_STATS, "正在读取人名库...")
            
            name_list = read_name_list(params['name_file'])
            logger.info(f"读取人名库: {len(name_list)} 个人名")
            
            if not self.is_running:
                return
            
            # 步骤2: 解析PDF
            self.send_message(MSG_STATUS, "正在解析PDF...")
            self.send_message(MSG_STATS, 
                            f"人名库: {len(name_list)} 个\n正在解析PDF...")
            
            total_pages_est = 400  # 估算值，用于进度计算
            
            def pdf_progress_callback(current, total):
                nonlocal total_pages_est
                total_pages_est = total
                # PDF解析占总进度的50%
                progress_current = current
                progress_total = total * 2
                self.send_message(MSG_PROGRESS, (progress_current, progress_total))
                
                if current % 20 == 0:
                    self.send_message(MSG_STATUS, f"正在解析PDF... ({current}/{total})")
            
            parsed_data = parse_pdf(
                params['pdf_file'],
                progress_callback=pdf_progress_callback,
                use_cache=params['use_cache']
            )
            
            if not self.is_running:
                return
            
            # 步骤3: 匹配人名
            self.send_message(MSG_STATUS, "正在匹配人名...")
            self.send_message(MSG_STATS, 
                            f"人名库: {len(name_list)} 个\n"
                            f"PDF页数: {len(parsed_data)} 页\n"
                            f"正在匹配人名...")
            
            def match_progress_callback(current, total):
                # 人名匹配占总进度的后50%
                progress_current = total + current
                progress_total = total * 2
                self.send_message(MSG_PROGRESS, (progress_current, progress_total))
                
                if current % 20 == 0:
                    self.send_message(MSG_STATUS, f"正在匹配人名... ({current}/{total})")
            
            match_result = match_all_pages(
                parsed_data,
                name_list,
                case_sensitive=params['case_sensitive'],
                progress_callback=match_progress_callback
            )
            
            if not self.is_running:
                return
            
            # 步骤4: 获取统计信息
            stats = get_match_statistics(match_result)
            duration = time.time() - start_time
            
            # 步骤5: 导出Excel
            self.send_message(MSG_STATUS, "正在导出Excel...")
            self.send_message(MSG_STATS, 
                            f"人名库: {len(name_list)} 个\n"
                            f"PDF页数: {len(parsed_data)} 页\n"
                            f"匹配到: {stats['matched_count']} 个\n"
                            f"正在导出Excel...")
            
            export_to_excel(
                match_result,
                params['output_file'],
                pdf_name=os.path.basename(params['pdf_file']),
                stats=stats,
                duration=duration
            )
            
            # 发送结果预览
            self.send_message(MSG_RESULT, match_result)
            
            # 发送完成消息
            self.send_message(MSG_COMPLETE, (params['output_file'], stats, duration))
            
        except Exception as e:
            logger.error(f"匹配失败: {e}")
            self.send_message(MSG_ERROR, str(e))
        
        finally:
            # 重置运行状态（在主线程中处理）
            self.root.after(0, self.reset_running_state)
    
    def send_message(self, msg_type: str, data: any = None):
        """向主线程发送消息"""
        msg = Message(msg_type, data)
        self.msg_queue.put(msg)
    
    def reset_running_state(self):
        """重置运行状态"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def matching_complete(self, output_file: str, stats: Dict, duration: float):
        """匹配完成回调"""
        self.stats = stats
        self.duration = duration
        
        # 更新进度为100%
        self.progress_var.set(100)
        self.progress_label.config(text="100%")
        
        # 更新统计信息
        stats_text = (
            f"人名库数量: {stats['total_names']} 个\n"
            f"匹配到的人名: {stats['matched_count']} 个\n"
            f"未匹配到的人名: {stats['unmatched_count']} 个\n"
            f"总匹配次数: {stats['total_matches']} 次\n"
            f"耗时: {format_duration(duration)}"
        )
        self.update_stats_text(stats_text)
        
        # 更新状态栏
        self.update_status(f"匹配完成 ✓ 已导出: {os.path.basename(output_file)}")
        
        # 提示用户
        messagebox.showinfo("完成", f"匹配完成！\n\n已导出到:\n{output_file}")
    
    def matching_failed(self, error_msg: str):
        """匹配失败回调"""
        self.update_status(f"匹配失败: {error_msg}")
        self.update_stats_text(f"匹配失败:\n{error_msg}")
        messagebox.showerror("错误", f"匹配失败:\n{error_msg}")
    
    def on_closing(self):
        """窗口关闭事件"""
        if self.is_running:
            if messagebox.askokcancel("退出", "匹配正在进行中，确定要退出吗？"):
                self.is_running = False
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    app = PDFNameMatcherApp(root)
    
    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()


if __name__ == "__main__":
    main()
