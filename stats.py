"""
统计模块 v2.0
提供详细的匹配统计信息
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from utils import format_duration


@dataclass
class PerformanceStats:
    """性能统计"""
    total_time: float = 0.0           # 总耗时（秒）
    parse_time: float = 0.0           # PDF解析耗时
    match_time: float = 0.0           # 匹配耗时
    export_time: float = 0.0          # 导出耗时
    pages_per_second: float = 0.0     # 每秒处理页数
    keywords_per_second: float = 0.0  # 每秒匹配关键词数


@dataclass
class PDFStats:
    """PDF统计"""
    total_pdfs: int = 0               # PDF总数
    total_pages: int = 0              # 总页数
    pages_with_text: int = 0          # 包含文字的页数
    pages_needing_ocr: int = 0        # 需要OCR的页数
    pdf_names: List[str] = field(default_factory=list)  # PDF文件名列表


@dataclass
class KeywordStats:
    """关键词统计"""
    total_keywords: int = 0           # 关键词总数
    matched_keywords: int = 0         # 匹配到的关键词数
    unmatched_keywords: int = 0       # 未匹配的关键词数
    total_hits: int = 0               # 总命中次数
    avg_hits_per_keyword: float = 0.0 # 平均每个关键词命中次数
    top_keywords: List[dict] = field(default_factory=list)  # 命中最多的关键词
    unmatched_list: List[str] = field(default_factory=list)  # 未匹配的关键词列表


@dataclass
class AnalysisStats:
    """完整分析统计"""
    performance: PerformanceStats = field(default_factory=PerformanceStats)
    pdf: PDFStats = field(default_factory=PDFStats)
    keyword: KeywordStats = field(default_factory=KeywordStats)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'performance': {
                'total_time': self.performance.total_time,
                'total_time_str': format_duration(self.performance.total_time),
                'parse_time': self.performance.parse_time,
                'match_time': self.performance.match_time,
                'export_time': self.performance.export_time,
                'pages_per_second': self.performance.pages_per_second,
            },
            'pdf': {
                'total_pdfs': self.pdf.total_pdfs,
                'total_pages': self.pdf.total_pages,
                'pages_with_text': self.pdf.pages_with_text,
                'pages_needing_ocr': self.pdf.pages_needing_ocr,
                'pdf_names': self.pdf.pdf_names,
            },
            'keyword': {
                'total_keywords': self.keyword.total_keywords,
                'matched_keywords': self.keyword.matched_keywords,
                'unmatched_keywords': self.keyword.unmatched_keywords,
                'total_hits': self.keyword.total_hits,
                'avg_hits_per_keyword': self.keyword.avg_hits_per_keyword,
                'top_keywords': self.keyword.top_keywords,
                'unmatched_list': self.keyword.unmatched_list,
            }
        }
    
    def get_summary(self) -> str:
        """获取统计摘要"""
        lines = [
            "═══ 分析统计 ═══",
            "",
            "【PDF统计】",
            f"  PDF数量: {self.pdf.total_pdfs}",
            f"  总页数: {self.pdf.total_pages}",
        ]
        
        if self.pdf.pages_needing_ocr > 0:
            lines.append(f"  需要OCR: {self.pdf.pages_needing_ocr} 页")
        
        lines.extend([
            "",
            "【关键词统计】",
            f"  关键词总数: {self.keyword.total_keywords}",
            f"  匹配到: {self.keyword.matched_keywords}",
            f"  未匹配: {self.keyword.unmatched_keywords}",
            f"  总命中次数: {self.keyword.total_hits}",
        ])
        
        if self.keyword.total_keywords > 0:
            avg = self.keyword.total_hits / self.keyword.total_keywords
            lines.append(f"  平均命中: {avg:.1f} 次/关键词")
        
        lines.extend([
            "",
            "【性能统计】",
            f"  总耗时: {format_duration(self.performance.total_time)}",
        ])
        
        if self.performance.pages_per_second > 0:
            lines.append(f"  处理速度: {self.performance.pages_per_second:.1f} 页/秒")
        
        if self.keyword.top_keywords:
            lines.extend([
                "",
                "【命中最多的关键词】",
            ])
            for i, kw in enumerate(self.keyword.top_keywords[:5], 1):
                lines.append(f"  {i}. {kw['name']}: {kw['count']} 次")
        
        if self.keyword.unmatched_list:
            lines.extend([
                "",
                "【未匹配的关键词】",
            ])
            # 最多显示10个
            display = self.keyword.unmatched_list[:10]
            lines.append(f"  {', '.join(display)}")
            if len(self.keyword.unmatched_list) > 10:
                lines.append(f"  ... 共 {len(self.keyword.unmatched_list)} 个")
        
        return '\n'.join(lines)


class StatsCalculator:
    """统计计算器"""
    
    @staticmethod
    def calculate(
        match_result,
        parsed_result=None,
        total_time: float = 0.0,
        parse_time: float = 0.0,
        match_time: float = 0.0,
        export_time: float = 0.0
    ) -> AnalysisStats:
        """
        计算完整统计信息
        
        Args:
            match_result: MatchResult对象
            parsed_result: ParsedResult对象（可选）
            total_time: 总耗时
            parse_time: 解析耗时
            match_time: 匹配耗时
            export_time: 导出耗时
        
        Returns:
            统计信息对象
        """
        stats = AnalysisStats()
        
        # 性能统计
        stats.performance.total_time = total_time
        stats.performance.parse_time = parse_time
        stats.performance.match_time = match_time
        stats.performance.export_time = export_time
        
        if total_time > 0 and match_result.total_pages > 0:
            stats.performance.pages_per_second = match_result.total_pages / total_time
        
        # PDF统计
        if parsed_result:
            stats.pdf.total_pdfs = len(parsed_result.pdf_list)
            stats.pdf.total_pages = parsed_result.total_pages
            stats.pdf.pdf_names = [p.name for p in parsed_result.pdf_list]
            
            # 统计有文字的页数
            stats.pdf.pages_with_text = sum(1 for p in parsed_result.pages if p.has_text)
            stats.pdf.pages_needing_ocr = sum(1 for p in parsed_result.pages if not p.has_text)
        else:
            stats.pdf.total_pdfs = match_result.total_pdfs
            stats.pdf.total_pages = match_result.total_pages
        
        # 关键词统计
        stats.keyword.total_keywords = match_result.total_keywords
        stats.keyword.total_hits = match_result.total_hits
        stats.keyword.matched_keywords = match_result.matched_keywords
        stats.keyword.unmatched_keywords = match_result.total_keywords - match_result.matched_keywords
        
        if stats.keyword.total_keywords > 0:
            stats.keyword.avg_hits_per_keyword = stats.keyword.total_hits / stats.keyword.total_keywords
        
        # 命中最多的关键词
        sorted_keywords = sorted(
            match_result.keywords.values(),
            key=lambda x: x.count,
            reverse=True
        )
        stats.keyword.top_keywords = [
            {'name': kw.keyword, 'count': kw.count, 'pages': len(kw.pages)}
            for kw in sorted_keywords if kw.count > 0
        ]
        
        # 未匹配的关键词
        stats.keyword.unmatched_list = [
            kw.keyword for kw in sorted_keywords if kw.count == 0
        ]
        
        return stats
    
    @staticmethod
    def get_keyword_table(match_result, sort_by: str = "count", sort_order: str = "desc") -> List[dict]:
        """
        获取关键词结果表格数据
        
        Args:
            match_result: MatchResult对象
            sort_by: 排序字段 (count/name/first_page)
            sort_order: 排序方式 (asc/desc)
        
        Returns:
            表格数据列表
        """
        table_data = []
        
        for kw in match_result.keywords.values():
            table_data.append({
                'keyword': kw.keyword,
                'count': kw.count,
                'pages': ', '.join(str(p) for p in kw.pages),
                'first_page': kw.first_page,
                'last_page': kw.last_page,
                'pdf_count': len(kw.pdfs),
                'pdfs': ', '.join(kw.pdfs)
            })
        
        # 排序
        reverse = (sort_order == "desc")
        
        if sort_by == "count":
            table_data.sort(key=lambda x: x['count'], reverse=reverse)
        elif sort_by == "name":
            table_data.sort(key=lambda x: x['keyword'], reverse=reverse)
        elif sort_by == "first_page":
            table_data.sort(key=lambda x: x['first_page'] if x['first_page'] > 0 else 999999, reverse=reverse)
        
        return table_data
