"""
关键词库加载模块 v2.0
支持 TXT/CSV/Excel/JSON 格式自动识别
统一转换为 Python List
"""

import os
import re
import json
from typing import List, Optional
from utils import setup_logger

logger = setup_logger("keyword_loader")


class KeywordLoader:
    """关键词库加载器"""
    
    # 支持的文件格式
    SUPPORTED_FORMATS = {'.txt', '.csv', '.xlsx', '.xls', '.json'}
    
    @staticmethod
    def load(file_path: str) -> List[str]:
        """
        加载关键词库，自动识别格式
        
        Args:
            file_path: 关键词库文件路径
        
        Returns:
            关键词列表（已去重、去空白）
        
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持或内容为空
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"关键词库文件不存在: {file_path}")
        
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext not in KeywordLoader.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的文件格式: {ext}，支持: {KeywordLoader.SUPPORTED_FORMATS}")
        
        # 根据扩展名选择加载方式
        if ext == '.txt':
            keywords = KeywordLoader._load_txt(file_path)
        elif ext == '.csv':
            keywords = KeywordLoader._load_csv(file_path)
        elif ext in ('.xlsx', '.xls'):
            keywords = KeywordLoader._load_excel(file_path)
        elif ext == '.json':
            keywords = KeywordLoader._load_json(file_path)
        else:
            raise ValueError(f"未处理的格式: {ext}")
        
        # 清理和去重
        keywords = KeywordLoader._clean_keywords(keywords)
        
        if not keywords:
            raise ValueError("关键词库为空")
        
        logger.info(f"加载关键词库: {file_path}，共 {len(keywords)} 个关键词")
        return keywords
    
    @staticmethod
    def _load_txt(file_path: str) -> List[str]:
        """加载TXT格式"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return KeywordLoader._split_by_separators(content)
    
    @staticmethod
    def _load_csv(file_path: str) -> List[str]:
        """加载CSV格式"""
        import csv
        
        keywords = []
        with open(file_path, 'r', encoding='utf-8') as f:
            # 尝试检测分隔符
            sample = f.read(1024)
            f.seek(0)
            
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
            except csv.Error:
                dialect = csv.excel
            
            reader = csv.reader(f, dialect)
            for row in reader:
                for cell in row:
                    cell = cell.strip()
                    if cell:
                        # 单元格内可能还有分隔符
                        keywords.extend(KeywordLoader._split_by_separators(cell))
        
        return keywords
    
    @staticmethod
    def _load_excel(file_path: str) -> List[str]:
        """加载Excel格式"""
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("需要安装 openpyxl: pip install openpyxl")
        
        keywords = []
        wb = load_workbook(file_path, read_only=True, data_only=True)
        
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None:
                        cell_str = str(cell).strip()
                        if cell_str:
                            keywords.extend(KeywordLoader._split_by_separators(cell_str))
        
        wb.close()
        return keywords
    
    @staticmethod
    def _load_json(file_path: str) -> List[str]:
        """加载JSON格式"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 支持多种JSON结构
        if isinstance(data, list):
            # 直接是列表: ["张三", "李四"]
            return [str(item) for item in data]
        elif isinstance(data, dict):
            # 可能是 {"keywords": ["张三", "李四"]} 或 {"names": [...]}
            for key in ['keywords', 'names', 'items', 'data', 'list']:
                if key in data and isinstance(data[key], list):
                    return [str(item) for item in data[key]]
            # 或者取所有值
            return [str(v) for v in data.values() if isinstance(v, str)]
        else:
            raise ValueError("JSON格式无法识别")
    
    @staticmethod
    def _split_by_separators(text: str) -> List[str]:
        """按多种分隔符分割文本"""
        # 使用正则表达式按所有常见分隔符分割
        separators = re.compile(r'[,，;；\t\n\r|｜、]+')
        parts = separators.split(text)
        return [p.strip() for p in parts if p.strip()]
    
    @staticmethod
    def _clean_keywords(keywords: List[str]) -> List[str]:
        """清理关键词：去空白、去重、保持顺序"""
        seen = set()
        result = []
        for kw in keywords:
            kw = kw.strip()
            if kw and kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result
    
    @staticmethod
    def get_format_description(file_path: str) -> str:
        """获取文件格式描述"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        format_map = {
            '.txt': '文本文件 (TXT)',
            '.csv': '逗号分隔值 (CSV)',
            '.xlsx': 'Excel工作簿 (XLSX)',
            '.xls': 'Excel工作簿 (XLS)',
            '.json': 'JSON文件'
        }
        
        return format_map.get(ext, f'未知格式 ({ext})')
