"""
PDF解析模块
使用pdfplumber解析PDF文件，支持文本缓存机制
"""

import json
import os
from typing import Dict, Optional, Callable, Any

import pdfplumber

from utils import normalize_text, generate_cache_path, setup_logger

logger = setup_logger("pdf_parser")


def parse_pdf(
    pdf_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    use_cache: bool = True
) -> Dict[int, str]:
    """
    解析PDF文件，提取每页的文本内容
    
    Args:
        pdf_path: PDF文件路径
        progress_callback: 进度回调函数，参数为 (当前页数, 总页数)
        use_cache: 是否使用缓存
    
    Returns:
        字典，键为页码（从1开始），值为该页的文本内容
    
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件不是有效的PDF
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 尝试从缓存加载
    if use_cache:
        cached_data = load_from_cache(pdf_path)
        if cached_data is not None:
            logger.info(f"从缓存加载PDF文本: {pdf_path}")
            # 转换键为整数
            return {int(k): v for k, v in cached_data.items()}
    
    # 解析PDF
    logger.info(f"开始解析PDF: {pdf_path}")
    parsed_data = {}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"PDF总页数: {total_pages}")
            
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                
                # 提取文本
                text = extract_page_text(page)
                parsed_data[page_num] = text
                
                # 回调进度
                if progress_callback:
                    progress_callback(page_num, total_pages)
                
                if page_num % 50 == 0:
                    logger.info(f"已解析 {page_num}/{total_pages} 页")
            
            logger.info(f"PDF解析完成，共 {total_pages} 页")
            
    except Exception as e:
        logger.error(f"PDF解析失败: {e}")
        raise ValueError(f"无法解析PDF文件: {e}")
    
    # 保存到缓存
    if use_cache and parsed_data:
        save_to_cache(pdf_path, parsed_data)
    
    return parsed_data


def extract_page_text(page: Any) -> str:
    """
    提取PDF页面的文本内容，包括普通文本和表格文本
    
    Args:
        page: pdfplumber的Page对象
    
    Returns:
        页面的完整文本内容
    """
    text_parts = []
    
    # 提取普通文本
    try:
        normal_text = page.extract_text()
        if normal_text:
            text_parts.append(normal_text)
    except Exception as e:
        logger.warning(f"提取页面文本时出错: {e}")
    
    # 提取表格文本
    try:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if row:
                    # 过滤None值并连接
                    row_text = ' '.join(
                        str(cell) for cell in row if cell is not None
                    )
                    if row_text.strip():
                        text_parts.append(row_text)
    except Exception as e:
        logger.warning(f"提取表格文本时出错: {e}")
    
    # 合并并标准化文本
    full_text = '\n'.join(text_parts)
    return normalize_text(full_text)


def load_from_cache(pdf_path: str) -> Optional[Dict[str, str]]:
    """
    从缓存加载PDF文本数据
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        缓存的数据，如果缓存不存在或无效则返回None
    """
    cache_path = generate_cache_path(pdf_path)
    
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 验证缓存数据格式
        if 'pdf_path' not in cache_data or 'data' not in cache_data:
            logger.warning("缓存格式无效，将重新解析")
            return None
        
        # 检查PDF文件是否被修改
        cached_mtime = cache_data.get('pdf_mtime', 0)
        current_mtime = os.path.getmtime(pdf_path)
        
        if abs(current_mtime - cached_mtime) > 1:  # 允许1秒误差
            logger.info("PDF文件已修改，将重新解析")
            return None
        
        return cache_data['data']
        
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"缓存文件损坏: {e}")
        return None


def save_to_cache(pdf_path: str, parsed_data: Dict[int, str]) -> None:
    """
    保存PDF文本数据到缓存
    
    Args:
        pdf_path: PDF文件路径
        parsed_data: 解析后的数据
    """
    cache_path = generate_cache_path(pdf_path)
    
    cache_data = {
        'pdf_path': os.path.abspath(pdf_path),
        'pdf_mtime': os.path.getmtime(pdf_path),
        'page_count': len(parsed_data),
        'data': {str(k): v for k, v in parsed_data.items()}
    }
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存缓存: {cache_path}")
    except Exception as e:
        logger.warning(f"保存缓存失败: {e}")


def clear_cache(cache_dir: str = "cache") -> int:
    """
    清除所有缓存文件
    
    Args:
        cache_dir: 缓存目录路径
    
    Returns:
        删除的缓存文件数量
    """
    if not os.path.exists(cache_dir):
        return 0
    
    count = 0
    for filename in os.listdir(cache_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(cache_dir, filename)
            try:
                os.remove(filepath)
                count += 1
            except Exception as e:
                logger.warning(f"删除缓存文件失败: {filepath}, {e}")
    
    logger.info(f"已清除 {count} 个缓存文件")
    return count


def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
    """
    获取PDF文件的基本信息
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        包含PDF信息的字典
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    info = {
        'path': pdf_path,
        'size': os.path.getsize(pdf_path),
        'page_count': 0,
        'title': '',
        'author': ''
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            info['page_count'] = len(pdf.pages)
            
            # 获取元数据
            metadata = pdf.metadata or {}
            info['title'] = metadata.get('Title', '')
            info['author'] = metadata.get('Author', '')
    except Exception as e:
        logger.warning(f"获取PDF信息时出错: {e}")
    
    return info
