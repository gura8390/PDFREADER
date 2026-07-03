"""
人名匹配模块
基于正则表达式的精确匹配，避免子串误匹配
"""

import re
from typing import Dict, List, Optional, Callable, Set, Tuple
from collections import defaultdict

from utils import setup_logger

logger = setup_logger("name_matcher")


def build_pattern(name_list: List[str], case_sensitive: bool = True) -> Tuple[re.Pattern, Set[str]]:
    """
    构建正则表达式模式，用于匹配人名
    
    Args:
        name_list: 人名列表
        case_sensitive: 是否区分大小写
    
    Returns:
        元组：(编译后的正则表达式, 人名集合)
    """
    if not name_list:
        raise ValueError("人名列表为空")
    
    # 对人名按长度降序排序，优先匹配较长的名字
    sorted_names = sorted(name_list, key=len, reverse=True)
    
    # 转义每个人名中的特殊正则字符
    escaped_names = [re.escape(name) for name in sorted_names]
    
    # 组合所有模式
    combined_pattern = '|'.join(escaped_names)
    
    # 编译正则表达式
    flags = 0 if case_sensitive else re.IGNORECASE
    
    try:
        pattern = re.compile(combined_pattern, flags)
        name_set = set(name_list)
        logger.info(f"已编译正则表达式，匹配 {len(name_list)} 个人名")
        return pattern, name_set
    except re.error as e:
        logger.error(f"正则表达式编译失败: {e}")
        raise ValueError(f"无法编译正则表达式: {e}")


def is_valid_match(
    text: str,
    start: int,
    end: int,
    matched_name: str,
    name_set: Set[str],
    name_set_lower: Set[str],
    case_sensitive: bool = True
) -> bool:
    """
    检查匹配结果是否是有效的人名匹配（不是更长人名的子串）
    
    Args:
        text: 原始文本
        start: 匹配开始位置
        end: 匹配结束位置
        matched_name: 匹配到的名字
        name_set: 人名集合（原始大小写）
        name_set_lower: 人名集合（小写，用于不区分大小写比较）
        case_sensitive: 是否区分大小写
    
    Returns:
        是否是有效匹配
    """
    # 选择使用哪个集合进行比较
    check_set = name_set if case_sensitive else name_set_lower
    matched_check = matched_name if case_sensitive else matched_name.lower()
    
    # 检查前面的字符是否能构成更长的人名
    if start > 0:
        for prefix_len in [1, 2]:
            if start >= prefix_len:
                prefix = text[start - prefix_len:start]
                extended_name = prefix + matched_name
                extended_check = extended_name if case_sensitive else extended_name.lower()
                if extended_check in check_set and extended_check != matched_check:
                    return False
    
    # 检查后面的字符是否能构成更长的人名
    if end < len(text):
        for suffix_len in [1, 2]:
            if end + suffix_len <= len(text):
                suffix = text[end:end + suffix_len]
                extended_name = matched_name + suffix
                extended_check = extended_name if case_sensitive else extended_name.lower()
                if extended_check in check_set and extended_check != matched_check:
                    return False
    
    return True


def match_single_page(
    text: str,
    pattern: re.Pattern,
    name_set: Set[str],
    name_set_lower_to_original: Dict[str, str],
    page_num: int,
    case_sensitive: bool = True
) -> Dict[str, List[int]]:
    """
    在单页文本中匹配人名
    
    Args:
        text: 页面文本内容
        pattern: 编译后的正则表达式
        name_set: 人名集合（原始大小写）
        name_set_lower_to_original: 小写到原始大小写的映射
        page_num: 页码
        case_sensitive: 是否区分大小写
    
    Returns:
        字典，键为人名（原始大小写），值为包含该页码的列表
    """
    if not text:
        return {}
    
    name_set_lower = set(name_set_lower_to_original.keys())
    results = defaultdict(list)
    
    # 查找所有匹配
    for match in pattern.finditer(text):
        matched_text = match.group()
        start = match.start()
        end = match.end()
        
        # 将匹配结果转换为原始大小写形式
        if case_sensitive:
            canonical_name = matched_text
        else:
            canonical_name = name_set_lower_to_original.get(matched_text.lower(), matched_text)
        
        # 检查是否是有效匹配（不是更长人名的子串）
        if is_valid_match(text, start, end, matched_text, name_set, name_set_lower, case_sensitive):
            if page_num not in results[canonical_name]:
                results[canonical_name].append(page_num)
    
    return dict(results)


def match_all_pages(
    parsed_data: Dict[int, str],
    name_list: List[str],
    case_sensitive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Dict]:
    """
    在所有页面中匹配人名
    
    Args:
        parsed_data: 解析后的PDF数据，键为页码，值为文本
        name_list: 人名列表
        case_sensitive: 是否区分大小写
        progress_callback: 进度回调函数，参数为 (当前页数, 总页数)
    
    Returns:
        字典，键为人名，值为包含 count 和 pages 的字典
        例如：{"张三": {"count": 15, "pages": [1, 5, 23, 45, 67]}}
    """
    if not name_list:
        raise ValueError("人名列表为空")
    
    if not parsed_data:
        raise ValueError("PDF数据为空")
    
    # 构建正则表达式
    pattern, name_set = build_pattern(name_list, case_sensitive)
    # 创建小写到原始大小写的映射
    name_set_lower_to_original = {n.lower(): n for n in name_set}
    
    # 初始化结果字典
    results = {}
    for name in name_list:
        results[name] = {"count": 0, "pages": []}
    
    total_pages = len(parsed_data)
    logger.info(f"开始匹配，共 {total_pages} 页，{len(name_list)} 个人名")
    
    # 逐页匹配
    for i, (page_num, text) in enumerate(parsed_data.items()):
        page_results = match_single_page(text, pattern, name_set, name_set_lower_to_original, page_num, case_sensitive)
        
        # 合并结果
        for name, pages in page_results.items():
            if name in results:
                results[name]["count"] += len(pages)
                results[name]["pages"].extend(pages)
        
        # 回调进度
        if progress_callback:
            progress_callback(i + 1, total_pages)
        
        if (i + 1) % 50 == 0:
            logger.info(f"已匹配 {i + 1}/{total_pages} 页")
    
    # 对页码列表排序
    for name in results:
        results[name]["pages"] = sorted(set(results[name]["pages"]))
    
    # 统计信息
    matched_count = sum(1 for v in results.values() if v["count"] > 0)
    total_matches = sum(v["count"] for v in results.values())
    
    logger.info(f"匹配完成: {matched_count}/{len(name_list)} 个人名被匹配到，共 {total_matches} 次匹配")
    
    return results


def get_match_statistics(results: Dict[str, Dict]) -> Dict:
    """
    获取匹配结果的统计信息
    
    Args:
        results: 匹配结果字典
    
    Returns:
        统计信息字典
    """
    matched_names = {k: v for k, v in results.items() if v["count"] > 0}
    unmatched_names = {k: v for k, v in results.items() if v["count"] == 0}
    
    stats = {
        "total_names": len(results),
        "matched_count": len(matched_names),
        "unmatched_count": len(unmatched_names),
        "total_matches": sum(v["count"] for v in results.values()),
        "matched_names": list(matched_names.keys()),
        "unmatched_names": list(unmatched_names.keys())
    }
    
    return stats


def format_pages_string(pages: List[int], max_display: int = 10) -> str:
    """
    格式化页码列表为字符串
    
    Args:
        pages: 页码列表
        max_display: 最多显示的页码数量
    
    Returns:
        格式化的页码字符串
    """
    if not pages:
        return ""
    
    if len(pages) <= max_display:
        return ", ".join(str(p) for p in pages)
    else:
        displayed = ", ".join(str(p) for p in pages[:max_display])
        return f"{displayed} ... (共{len(pages)}页)"
