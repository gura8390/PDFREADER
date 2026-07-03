"""
工具函数模块
提供文件读取、文本标准化、缓存路径生成、日志配置等功能
"""

import os
import re
import hashlib
import logging
from typing import List, Optional


def setup_logger(name: str = "pdf_name_matcher", level: int = logging.INFO) -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def read_name_list(file_path: str) -> List[str]:
    """
    读取人名库文件，支持多种分隔符
    
    支持的格式：
    - 逗号分隔：张三,李四,王五
    - 分号分隔：张三;李四;王五
    - 换行分隔：
        张三
        李四
        王五
    - 空格分隔：张三 李四 王五
    - 混合分隔：张三,李四;王五
    
    Args:
        file_path: 人名库文件路径
    
    Returns:
        人名列表（已去除空白和空字符串）
    
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件内容为空
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"人名库文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    if not content:
        raise ValueError("人名库文件内容为空")
    
    # 先按换行符分割
    lines = content.split('\n')
    
    # 使用正则表达式按所有常见分隔符分割
    separators = re.compile(r'[,，;；\t ]+')
    
    names = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 按所有分隔符分割
        parts = separators.split(line)
        names.extend([n.strip() for n in parts if n.strip()])
    
    # 去重并保持顺序
    seen = set()
    unique_names = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)
    
    return unique_names


def normalize_text(text: str) -> str:
    """
    文本标准化：去除多余空白、统一编码
    
    Args:
        text: 原始文本
    
    Returns:
        标准化后的文本
    """
    if not text:
        return ""
    
    # 统一换行符
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 去除多余空白（保留单个空格和换行）
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 去除行首行尾空白
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text


def generate_cache_path(pdf_path: str, cache_dir: str = "cache") -> str:
    """
    生成PDF文本缓存文件路径
    
    使用PDF文件路径的MD5哈希作为缓存文件名，确保：
    - 同一PDF文件始终使用同一缓存
    - 不同PDF文件不会冲突
    
    Args:
        pdf_path: PDF文件路径
        cache_dir: 缓存目录路径
    
    Returns:
        缓存文件的完整路径
    """
    # 获取PDF文件的绝对路径
    abs_pdf_path = os.path.abspath(pdf_path)
    
    # 生成MD5哈希
    path_hash = hashlib.md5(abs_pdf_path.encode('utf-8')).hexdigest()
    
    # 确保缓存目录存在
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    return os.path.join(cache_dir, f"{path_hash}.json")


def format_duration(seconds: float) -> str:
    """
    格式化时间显示
    
    Args:
        seconds: 秒数
    
    Returns:
        格式化的时间字符串，如 "1分23秒" 或 "45秒"
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}分{remaining_seconds:.1f}秒"


def get_file_size_str(file_path: str) -> str:
    """
    获取文件大小的可读字符串
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件大小字符串，如 "12.5 MB"
    """
    size_bytes = os.path.getsize(file_path)
    
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def ensure_dir(dir_path: str) -> None:
    """
    确保目录存在，不存在则创建
    
    Args:
        dir_path: 目录路径
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def get_app_dir() -> str:
    """
    获取应用程序所在目录
    
    Returns:
        应用程序目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))


# 导入sys模块（用于get_app_dir）
import sys
