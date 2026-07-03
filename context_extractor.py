"""
上下文提取模块 v2.0
提供上下文格式化和提取功能
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ContextInfo:
    """上下文信息"""
    keyword: str           # 关键词
    page_num: int          # 页码
    pdf_name: str          # PDF文件名
    context_before: str    # 前文
    keyword_text: str      # 关键词本身
    context_after: str     # 后文
    full_context: str      # 完整上下文（前文+关键词+后文）


class ContextExtractor:
    """上下文提取器"""
    
    @staticmethod
    def format_context(
        context_before: str,
        keyword: str,
        context_after: str,
        separator: str = "..."
    ) -> str:
        """
        格式化上下文显示
        
        Args:
            context_before: 前文
            keyword: 关键词
            context_after: 后文
            separator: 分隔符
        
        Returns:
            格式化的上下文字符串
        """
        parts = []
        if context_before:
            parts.append(context_before)
        parts.append(keyword)
        if context_after:
            parts.append(context_after)
        return separator.join(parts)
    
    @staticmethod
    def truncate_context(text: str, max_length: int = 30, position: str = "end") -> str:
        """
        截断上下文到指定长度
        
        Args:
            text: 原始文本
            max_length: 最大长度
            position: 截断位置 (start/end)
        
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        
        if position == "end":
            return text[:max_length] + "..."
        else:
            return "..." + text[-max_length:]
    
    @staticmethod
    def extract_page_context(
        text: str,
        keyword: str,
        keyword_position: int,
        context_length: int = 30
    ) -> ContextInfo:
        """
        提取指定位置的上下文
        
        Args:
            text: 页面文本
            keyword: 关键词
            keyword_position: 关键词在文本中的位置
            context_length: 上下文长度
        
        Returns:
            上下文信息
        """
        start = max(0, keyword_position - context_length)
        end = min(len(text), keyword_position + len(keyword) + context_length)
        
        context_before = text[start:keyword_position]
        context_after = text[keyword_position + len(keyword):end]
        
        return ContextInfo(
            keyword=keyword,
            page_num=0,
            pdf_name="",
            context_before=context_before,
            keyword_text=keyword,
            context_after=context_after,
            full_context=context_before + keyword + context_after
        )
    
    @staticmethod
    def get_all_contexts_for_keyword(
        hits: list,
        context_length: int = 30
    ) -> List[ContextInfo]:
        """
        获取某个关键词的所有上下文
        
        Args:
            hits: MatchHit列表
            context_length: 上下文长度
        
        Returns:
            上下文信息列表
        """
        contexts = []
        for hit in hits:
            ctx = ContextInfo(
                keyword=hit.keyword,
                page_num=hit.page_num,
                pdf_name=hit.pdf_name,
                context_before=ContextExtractor.truncate_context(
                    hit.context_before, context_length, "start"
                ),
                keyword_text=hit.matched_text,
                context_after=ContextExtractor.truncate_context(
                    hit.context_after, context_length, "end"
                ),
                full_context=ContextExtractor.format_context(
                    ContextExtractor.truncate_context(hit.context_before, context_length, "start"),
                    hit.matched_text,
                    ContextExtractor.truncate_context(hit.context_after, context_length, "end")
                )
            )
            contexts.append(ctx)
        
        return contexts
    
    @staticmethod
    def build_context_table(
        match_result,
        context_length: int = 30
    ) -> List[dict]:
        """
        构建上下文表格数据（用于导出）
        
        Args:
            match_result: MatchResult对象
            context_length: 上下文长度
        
        Returns:
            表格数据列表
        """
        table_data = []
        
        for kw, kw_result in match_result.keywords.items():
            for hit in kw_result.hits:
                ctx_before = ContextExtractor.truncate_context(
                    hit.context_before, context_length, "start"
                )
                ctx_after = ContextExtractor.truncate_context(
                    hit.context_after, context_length, "end"
                )
                
                table_data.append({
                    'keyword': kw,
                    'pdf_name': hit.pdf_name,
                    'page_num': hit.page_num,
                    'context': ctx_before + hit.matched_text + ctx_after
                })
        
        # 按页码排序
        table_data.sort(key=lambda x: (x['pdf_name'], x['page_num']))
        
        return table_data
