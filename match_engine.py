"""
匹配引擎模块 v2.0
支持精确匹配、模糊匹配、正则表达式三种模式
"""

import re
from typing import Dict, List, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from utils import setup_logger

logger = setup_logger("match_engine")


class MatchMode(Enum):
    """匹配模式"""
    EXACT = "exact"      # 精确匹配
    FUZZY = "fuzzy"      # 模糊匹配
    REGEX = "regex"      # 正则表达式


@dataclass
class MatchHit:
    """单次匹配命中"""
    keyword: str         # 关键词（原始形式）
    page_num: int        # 页码
    pdf_name: str        # PDF文件名
    position: int        # 在文本中的位置
    context_before: str  # 前文上下文
    context_after: str   # 后文上下文
    matched_text: str    # 实际匹配的文本


@dataclass
class KeywordResult:
    """单个关键词的匹配结果"""
    keyword: str                              # 关键词
    count: int = 0                            # 出现次数
    pages: List[int] = field(default_factory=list)           # 出现的页码列表
    pdfs: List[str] = field(default_factory=list)            # 出现的PDF列表
    first_page: int = 0                       # 首次出现页码
    last_page: int = 0                        # 最后出现页码
    hits: List[MatchHit] = field(default_factory=list)       # 所有命中记录


@dataclass
class MatchResult:
    """整体匹配结果"""
    keywords: Dict[str, KeywordResult]        # 关键词结果字典
    total_hits: int = 0                       # 总命中次数
    matched_keywords: int = 0                 # 匹配到的关键词数
    total_keywords: int = 0                   # 总关键词数
    total_pages: int = 0                      # 总页数
    total_pdfs: int = 0                       # 总PDF数


class MatchEngine:
    """匹配引擎"""
    
    def __init__(
        self,
        mode: MatchMode = MatchMode.EXACT,
        case_sensitive: bool = True,
        context_length: int = 30
    ):
        """
        初始化匹配引擎
        
        Args:
            mode: 匹配模式
            case_sensitive: 是否区分大小写
            context_length: 上下文长度
        """
        self.mode = mode
        self.case_sensitive = case_sensitive
        self.context_length = context_length
        self._pattern = None
        self._keyword_set = set()
        self._keyword_lower_to_original = {}
    
    def prepare(self, keywords: List[str]) -> None:
        """
        准备匹配引擎（预编译正则表达式）
        
        Args:
            keywords: 关键词列表
        """
        self._keyword_set = set(keywords)
        self._keyword_lower_to_original = {k.lower(): k for k in keywords}
        
        if self.mode == MatchMode.EXACT:
            self._pattern = self._build_exact_pattern(keywords)
        elif self.mode == MatchMode.FUZZY:
            self._pattern = self._build_fuzzy_pattern(keywords)
        elif self.mode == MatchMode.REGEX:
            self._pattern = self._build_regex_pattern(keywords)
        
        logger.info(f"匹配引擎准备完成: 模式={self.mode.value}, 关键词数={len(keywords)}")
    
    def _build_exact_pattern(self, keywords: List[str]) -> re.Pattern:
        """构建精确匹配正则表达式"""
        # 按长度降序排序，优先匹配较长的关键词
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        escaped = [re.escape(kw) for kw in sorted_keywords]
        
        # 组合模式
        combined = '|'.join(escaped)
        
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(combined, flags)
    
    def _build_fuzzy_pattern(self, keywords: List[str]) -> re.Pattern:
        """构建模糊匹配正则表达式"""
        patterns = []
        
        for kw in sorted(keywords, key=len, reverse=True):
            # 在每个字符之间插入可选的分隔符
            # 支持: 张 三, 张　三, 张-三, 张•三
            chars = list(kw)
            fuzzy_pattern = r'[\s\-•·。,，;；]*'.join(re.escape(c) for c in chars)
            patterns.append(f'({fuzzy_pattern})')
        
        combined = '|'.join(patterns)
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(combined, flags)
    
    def _build_regex_pattern(self, keywords: List[str]) -> re.Pattern:
        """构建正则表达式模式（关键词本身就是正则）"""
        patterns = []
        for kw in keywords:
            try:
                # 验证正则表达式是否有效
                re.compile(kw)
                patterns.append(f'({kw})')
            except re.error as e:
                logger.warning(f"无效的正则表达式 '{kw}': {e}")
        
        if not patterns:
            raise ValueError("没有有效的正则表达式")
        
        combined = '|'.join(patterns)
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(combined, flags)
    
    def match_text(
        self,
        text: str,
        page_num: int,
        pdf_name: str,
        keywords: List[str]
    ) -> Dict[str, List[MatchHit]]:
        """
        在文本中匹配关键词
        
        Args:
            text: 文本内容
            page_num: 页码
            pdf_name: PDF文件名
            keywords: 关键词列表
        
        Returns:
            字典，键为关键词，值为命中列表
        """
        if not text or not self._pattern:
            return {}
        
        results = {}
        
        for regex_match in self._pattern.finditer(text):
            matched_text = regex_match.group()
            start = regex_match.start()
            end = regex_match.end()
            
            # 确定是哪个关键词
            keyword = self._identify_keyword(matched_text, keywords, regex_match)
            if keyword is None:
                continue
            
            # 精确模式下检查是否是子串
            if self.mode == MatchMode.EXACT:
                if not self._is_valid_match(text, start, end, matched_text):
                    continue
            
            # 提取上下文
            context_before = self._extract_context(text, start, before=True)
            context_after = self._extract_context(text, end, before=False)
            
            # 创建命中记录
            hit = MatchHit(
                keyword=keyword,
                page_num=page_num,
                pdf_name=pdf_name,
                position=start,
                context_before=context_before,
                context_after=context_after,
                matched_text=matched_text
            )
            
            if keyword not in results:
                results[keyword] = []
            results[keyword].append(hit)
        
        return results
    
    def _identify_keyword(self, matched_text: str, keywords: List[str], regex_match=None) -> Optional[str]:
        """识别匹配到的是哪个关键词"""
        if self.mode == MatchMode.EXACT:
            # 精确模式：直接查找
            if self.case_sensitive:
                return matched_text if matched_text in self._keyword_set else None
            else:
                return self._keyword_lower_to_original.get(matched_text.lower())
        
        elif self.mode == MatchMode.FUZZY:
            # 模糊模式：需要检查匹配的是哪个关键词组
            normalized = re.sub(r'[\s\-•·。,，;；]+', '', matched_text)
            for kw in keywords:
                kw_normalized = re.sub(r'[\s\-•·。,，;；]+', '', kw)
                if self.case_sensitive:
                    if normalized == kw_normalized:
                        return kw
                else:
                    if normalized.lower() == kw_normalized.lower():
                        return kw
        
        elif self.mode == MatchMode.REGEX and regex_match:
            # 正则模式：返回第一个非空的捕获组对应的关键词
            for i, kw in enumerate(keywords):
                try:
                    group = regex_match.group(i + 1)
                    if group:
                        return kw
                except IndexError:
                    pass
            # 如果没有捕获组，返回整个匹配
            if keywords:
                return keywords[0]
        
        return None
    
    def _is_valid_match(self, text: str, start: int, end: int, matched: str) -> bool:
        """检查是否是有效匹配（不是更长词的子串）"""
        # 检查前面
        if start > 0:
            for prefix_len in [1, 2]:
                if start >= prefix_len:
                    prefix = text[start - prefix_len:start]
                    extended = prefix + matched
                    if self.case_sensitive:
                        if extended in self._keyword_set:
                            return False
                    else:
                        if extended.lower() in self._keyword_lower_to_original:
                            return False
        
        # 检查后面
        if end < len(text):
            for suffix_len in [1, 2]:
                if end + suffix_len <= len(text):
                    suffix = text[end:end + suffix_len]
                    extended = matched + suffix
                    if self.case_sensitive:
                        if extended in self._keyword_set:
                            return False
                    else:
                        if extended.lower() in self._keyword_lower_to_original:
                            return False
        
        return True
    
    def _extract_context(self, text: str, position: int, before: bool = True) -> str:
        """提取上下文"""
        if before:
            start = max(0, position - self.context_length)
            return text[start:position]
        else:
            end = min(len(text), position + self.context_length)
            return text[position:end]
    
    def match_all(
        self,
        pages: List,
        keywords: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> MatchResult:
        """
        匹配所有页面
        
        Args:
            pages: ParsedPage列表
            keywords: 关键词列表
            progress_callback: 进度回调
        
        Returns:
            匹配结果
        """
        # 准备引擎
        self.prepare(keywords)
        
        # 初始化结果
        result = MatchResult(
            keywords={kw: KeywordResult(keyword=kw) for kw in keywords},
            total_keywords=len(keywords),
            total_pages=len(pages)
        )
        
        pdfs_seen = set()
        
        # 逐页匹配
        for i, page in enumerate(pages):
            pdfs_seen.add(page.pdf_name)
            
            hits = self.match_text(page.text, page.page_num, page.pdf_name, keywords)
            
            # 合并结果
            for kw, hit_list in hits.items():
                if kw in result.keywords:
                    kw_result = result.keywords[kw]
                    kw_result.count += len(hit_list)
                    kw_result.hits.extend(hit_list)
                    
                    if page.page_num not in kw_result.pages:
                        kw_result.pages.append(page.page_num)
                    
                    if page.pdf_name not in kw_result.pdfs:
                        kw_result.pdfs.append(page.pdf_name)
                    
                    # 更新首次/最后出现
                    if kw_result.first_page == 0 or page.page_num < kw_result.first_page:
                        kw_result.first_page = page.page_num
                    if page.page_num > kw_result.last_page:
                        kw_result.last_page = page.page_num
            
            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(pages))
        
        # 统计
        result.total_pdfs = len(pdfs_seen)
        result.total_hits = sum(kw.count for kw in result.keywords.values())
        result.matched_keywords = sum(1 for kw in result.keywords.values() if kw.count > 0)
        
        # 排序页码
        for kw in result.keywords.values():
            kw.pages.sort()
        
        logger.info(
            f"匹配完成: {result.matched_keywords}/{result.total_keywords} 关键词, "
            f"{result.total_hits} 次命中"
        )
        
        return result
