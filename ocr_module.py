"""
OCR模块 v2.0
支持扫描PDF的文字识别
需要安装: pip install pytesseract pillow pdf2image
"""

import os
from typing import Optional, Callable
from utils import setup_logger

logger = setup_logger("ocr_module")


class OCRModule:
    """OCR识别模块"""
    
    def __init__(self, language: str = "chi_sim+eng", dpi: int = 300):
        """
        初始化OCR模块
        
        Args:
            language: OCR语言（chi_sim=简体中文, eng=英文）
            dpi: 图像分辨率
        """
        self.language = language
        self.dpi = dpi
        self._available = None
    
    def is_available(self) -> bool:
        """检查OCR是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import pytesseract
            from pdf2image import convert_from_path
            from PIL import Image
            
            # 尝试获取tesseract版本
            pytesseract.get_tesseract_version()
            self._available = True
            logger.info("OCR模块可用")
        except ImportError as e:
            self._available = False
            logger.warning(f"OCR依赖未安装: {e}")
        except Exception as e:
            self._available = False
            logger.warning(f"OCR不可用: {e}")
        
        return self._available
    
    def ocr_pdf_page(
        self,
        pdf_path: str,
        page_num: int
    ) -> str:
        """
        对PDF单页进行OCR识别
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页码（从1开始）
        
        Returns:
            识别出的文字
        """
        if not self.is_available():
            raise RuntimeError("OCR模块不可用，请安装: pip install pytesseract pillow pdf2image")
        
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            # 将PDF页面转换为图像
            images = convert_from_path(
                pdf_path,
                first_page=page_num,
                last_page=page_num,
                dpi=self.dpi
            )
            
            if not images:
                return ""
            
            # OCR识别
            text = pytesseract.image_to_string(images[0], lang=self.language)
            return text.strip()
            
        except Exception as e:
            logger.error(f"OCR识别失败: {pdf_path} 第{page_num}页, {e}")
            return ""
    
    def ocr_pdf(
        self,
        pdf_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> dict:
        """
        对整个PDF进行OCR识别
        
        Args:
            pdf_path: PDF文件路径
            progress_callback: 进度回调
        
        Returns:
            字典，键为页码，值为识别文字
        """
        if not self.is_available():
            raise RuntimeError("OCR模块不可用")
        
        try:
            from pdf2image import convert_from_path
            import pytesseract
            import pdfplumber
            
            # 获取总页数
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
            
            results = {}
            
            # 逐页转换和识别
            for page_num in range(1, total_pages + 1):
                try:
                    images = convert_from_path(
                        pdf_path,
                        first_page=page_num,
                        last_page=page_num,
                        dpi=self.dpi
                    )
                    
                    if images:
                        text = pytesseract.image_to_string(images[0], lang=self.language)
                        results[page_num] = text.strip()
                    else:
                        results[page_num] = ""
                    
                except Exception as e:
                    logger.warning(f"OCR第{page_num}页失败: {e}")
                    results[page_num] = ""
                
                if progress_callback:
                    progress_callback(page_num, total_pages)
            
            logger.info(f"OCR完成: {pdf_path}, {total_pages} 页")
            return results
            
        except Exception as e:
            logger.error(f"OCR处理失败: {e}")
            raise
    
    def get_install_instructions(self) -> str:
        """获取安装说明"""
        return """
OCR功能需要安装以下依赖：

1. Tesseract OCR引擎:
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
   - 安装时选择中文语言包

2. Python依赖:
   pip install pytesseract pillow pdf2image

3. Poppler (pdf2image依赖):
   - Windows: https://github.com/osber/poppler-windows/releases
   - 解压后将bin目录添加到PATH环境变量

安装完成后重启程序即可使用OCR功能。
"""
