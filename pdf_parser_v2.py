"""
PDF解析模块 v2.0
支持单个PDF、多个PDF、整个文件夹
支持文本缓存机制
"""

import json
import os
import glob
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

import pdfplumber

from utils import normalize_text, generate_cache_path, setup_logger

logger = setup_logger("pdf_parser_v2")


@dataclass
class PDFInfo:
    """PDF文件信息"""
    path: str
    name: str
    size: int
    page_count: int
    title: str = ""
    author: str = ""


@dataclass
class ParsedPage:
    """解析后的页面数据"""
    pdf_name: str       # 所属PDF文件名
    pdf_path: str       # 所属PDF文件路径
    page_num: int       # 页码（从1开始）
    text: str           # 页面文本内容
    has_text: bool      # 是否包含文字（用于OCR判断）


@dataclass
class ParsedResult:
    """解析结果"""
    pdf_list: List[PDFInfo]                    # PDF文件列表
    pages: List[ParsedPage]                    # 所有页面数据
    total_pages: int = 0                       # 总页数
    cached_count: int = 0                      # 从缓存加载的数量
    parsed_count: int = 0                      # 新解析的数量


class PDFParserV2:
    """PDF解析器 v2.0"""
    
    def __init__(self, use_cache: bool = True, cache_dir: str = "cache"):
        """
        初始化PDF解析器
        
        Args:
            use_cache: 是否使用缓存
            cache_dir: 缓存目录
        """
        self.use_cache = use_cache
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def collect_pdf_files(self, input_path: str, input_type: str = "auto") -> List[str]:
        """
        收集PDF文件列表
        
        Args:
            input_path: 输入路径（文件或目录）
            input_type: 输入类型 (auto/single/multiple/folder)
        
        Returns:
            PDF文件路径列表
        """
        if input_type == "auto":
            input_type = self._detect_input_type(input_path)
        
        if input_type == "single":
            # 单个文件
            if not os.path.isfile(input_path):
                raise FileNotFoundError(f"文件不存在: {input_path}")
            if not input_path.lower().endswith('.pdf'):
                raise ValueError(f"不是PDF文件: {input_path}")
            return [input_path]
        
        elif input_type == "folder":
            # 整个文件夹
            if not os.path.isdir(input_path):
                raise NotADirectoryError(f"目录不存在: {input_path}")
            pdf_files = []
            for root, dirs, files in os.walk(input_path):
                for f in files:
                    if f.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(root, f))
            pdf_files.sort()
            return pdf_files
        
        elif input_type == "multiple":
            # 多个文件（input_path应该是列表或分号分隔的字符串）
            if isinstance(input_path, str):
                pdf_files = [p.strip() for p in input_path.split(';') if p.strip()]
            elif isinstance(input_path, list):
                pdf_files = input_path
            else:
                raise ValueError("multiple类型需要文件路径列表或分号分隔的字符串")
            
            # 验证文件存在
            for pdf in pdf_files:
                if not os.path.isfile(pdf):
                    raise FileNotFoundError(f"文件不存在: {pdf}")
            
            return pdf_files
        
        else:
            raise ValueError(f"不支持的输入类型: {input_type}")
    
    def _detect_input_type(self, input_path: str) -> str:
        """自动检测输入类型"""
        if os.path.isdir(input_path):
            return "folder"
        elif os.path.isfile(input_path):
            return "single"
        else:
            # 可能是分号分隔的多个文件
            if ';' in input_path:
                return "multiple"
            raise FileNotFoundError(f"路径不存在: {input_path}")
    
    def get_pdf_info(self, pdf_path: str) -> PDFInfo:
        """获取PDF文件信息"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        info = PDFInfo(
            path=pdf_path,
            name=os.path.basename(pdf_path),
            size=os.path.getsize(pdf_path),
            page_count=0
        )
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                info.page_count = len(pdf.pages)
                metadata = pdf.metadata or {}
                info.title = metadata.get('Title', '')
                info.author = metadata.get('Author', '')
        except Exception as e:
            logger.warning(f"获取PDF信息失败: {e}")
        
        return info
    
    def parse_single_pdf(
        self,
        pdf_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ParsedPage]:
        """
        解析单个PDF文件
        
        Args:
            pdf_path: PDF文件路径
            progress_callback: 进度回调 (当前页, 总页数)
        
        Returns:
            解析后的页面列表
        """
        pdf_name = os.path.basename(pdf_path)
        
        # 尝试从缓存加载
        if self.use_cache:
            cached_pages = self._load_from_cache(pdf_path)
            if cached_pages is not None:
                logger.info(f"从缓存加载: {pdf_name}")
                return cached_pages
        
        # 解析PDF
        logger.info(f"开始解析: {pdf_name}")
        pages = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    
                    # 提取文本
                    text = self._extract_page_text(page)
                    has_text = bool(text.strip())
                    
                    parsed_page = ParsedPage(
                        pdf_name=pdf_name,
                        pdf_path=pdf_path,
                        page_num=page_num,
                        text=text,
                        has_text=has_text
                    )
                    pages.append(parsed_page)
                    
                    # 回调进度
                    if progress_callback:
                        progress_callback(page_num, total_pages)
                
        except Exception as e:
            logger.error(f"PDF解析失败: {pdf_path}, {e}")
            raise
        
        # 保存到缓存
        if self.use_cache and pages:
            self._save_to_cache(pdf_path, pages)
        
        return pages
    
    def parse_multiple_pdfs(
        self,
        pdf_files: List[str],
        progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None
    ) -> ParsedResult:
        """
        解析多个PDF文件
        
        Args:
            pdf_files: PDF文件路径列表
            progress_callback: 进度回调 (文件名, 当前文件页, 文件总页, 当前文件数, 总文件数)
        
        Returns:
            解析结果
        """
        result = ParsedResult(pdf_list=[], pages=[], total_pages=0)
        total_files = len(pdf_files)
        
        for file_idx, pdf_path in enumerate(pdf_files):
            try:
                # 获取PDF信息
                pdf_info = self.get_pdf_info(pdf_path)
                result.pdf_list.append(pdf_info)
                result.total_pages += pdf_info.page_count
                
                # 定义进度回调
                def file_progress(current_page, total_pages):
                    if progress_callback:
                        progress_callback(
                            pdf_info.name,
                            current_page,
                            total_pages,
                            file_idx + 1,
                            total_files
                        )
                
                # 解析单个PDF
                pages = self.parse_single_pdf(pdf_path, file_progress)
                result.pages.extend(pages)
                result.parsed_count += 1
                
            except Exception as e:
                logger.error(f"跳过文件 {pdf_path}: {e}")
                continue
        
        logger.info(f"解析完成: {len(result.pdf_list)} 个PDF, {result.total_pages} 页")
        return result
    
    def _extract_page_text(self, page: Any) -> str:
        """提取PDF页面的文本内容（避免表格内容重复提取）"""
        # 提取普通文本（pdfplumber会自动包含表格中的文字）
        try:
            normal_text = page.extract_text()
            if normal_text and normal_text.strip():
                return normalize_text(normal_text)
        except Exception as e:
            logger.warning(f"提取页面文本出错: {e}")
        
        # 如果普通文本为空，尝试从表格提取
        try:
            tables = page.extract_tables()
            text_parts = []
            for table in tables:
                for row in table:
                    if row:
                        row_text = ' '.join(str(cell) for cell in row if cell is not None)
                        if row_text.strip():
                            text_parts.append(row_text)
            if text_parts:
                return normalize_text('\n'.join(text_parts))
        except Exception as e:
            logger.warning(f"提取表格文本出错: {e}")
        
        return ""
    
    def _load_from_cache(self, pdf_path: str) -> Optional[List[ParsedPage]]:
        """从缓存加载"""
        cache_path = generate_cache_path(pdf_path, self.cache_dir)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 验证缓存
            if 'pdf_mtime' not in cache_data or 'pages' not in cache_data:
                return None
            
            # 检查文件是否被修改
            current_mtime = os.path.getmtime(pdf_path)
            if abs(current_mtime - cache_data['pdf_mtime']) > 1:
                return None
            
            # 转换为ParsedPage对象
            pages = []
            pdf_name = os.path.basename(pdf_path)
            for page_data in cache_data['pages']:
                pages.append(ParsedPage(
                    pdf_name=pdf_name,
                    pdf_path=pdf_path,
                    page_num=page_data['page_num'],
                    text=page_data['text'],
                    has_text=page_data['has_text']
                ))
            
            return pages
            
        except Exception as e:
            logger.warning(f"缓存加载失败: {e}")
            return None
    
    def _save_to_cache(self, pdf_path: str, pages: List[ParsedPage]) -> None:
        """保存到缓存"""
        cache_path = generate_cache_path(pdf_path, self.cache_dir)
        
        cache_data = {
            'pdf_path': os.path.abspath(pdf_path),
            'pdf_mtime': os.path.getmtime(pdf_path),
            'page_count': len(pages),
            'pages': [
                {
                    'page_num': p.page_num,
                    'text': p.text,
                    'has_text': p.has_text
                }
                for p in pages
            ]
        }
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def clear_cache(self) -> int:
        """清除所有缓存"""
        count = 0
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(filepath)
                        count += 1
                    except Exception as e:
                        logger.warning(f"删除缓存失败: {filepath}, {e}")
        
        logger.info(f"已清除 {count} 个缓存文件")
        return count
    
    def get_cache_size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
