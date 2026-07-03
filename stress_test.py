"""
v2.0 压力测试 - 测试边界情况和潜在问题
"""

import sys
import os
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 60)
print('v2.0 压力测试 - 开始')
print('=' * 60)

errors = []
test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_stress_temp')


def test(name, func):
    try:
        func()
        print(f'  ✓ {name}')
    except Exception as e:
        print(f'  ✗ {name}: {type(e).__name__}: {e}')
        errors.append((name, f'{type(e).__name__}: {e}'))


if os.path.exists(test_dir):
    shutil.rmtree(test_dir)
os.makedirs(test_dir, exist_ok=True)

# ==================== 关键词库边界测试 ====================
print('\n[1/6] 关键词库边界测试')

from keyword_loader import KeywordLoader


def test_empty_keywords():
    f = os.path.join(test_dir, 'empty.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('')
    try:
        KeywordLoader.load(f)
        assert False, '应该抛出ValueError'
    except ValueError:
        pass


def test_whitespace_only():
    f = os.path.join(test_dir, 'space.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('   \n  \n  ')
    try:
        KeywordLoader.load(f)
        assert False, '应该抛出ValueError'
    except ValueError:
        pass


def test_single_keyword():
    f = os.path.join(test_dir, 'single.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('张三')
    result = KeywordLoader.load(f)
    assert result == ['张三']


def test_special_chars():
    f = os.path.join(test_dir, 'special.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('张三(Jr.),李四[博士],王五&赵六')
    result = KeywordLoader.load(f)
    assert len(result) >= 3


def test_unicode_keywords():
    f = os.path.join(test_dir, 'unicode.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('田中太郎,John Smith,Müller,김철수')
    result = KeywordLoader.load(f)
    assert len(result) == 4


def test_very_long_keyword():
    f = os.path.join(test_dir, 'long.txt')
    long_kw = 'A' * 500
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(long_kw)
    result = KeywordLoader.load(f)
    assert result[0] == long_kw


test('空文件', test_empty_keywords)
test('纯空白', test_whitespace_only)
test('单个关键词', test_single_keyword)
test('特殊字符', test_special_chars)
test('Unicode关键词', test_unicode_keywords)
test('超长关键词', test_very_long_keyword)

# ==================== 匹配引擎边界测试 ====================
print('\n[2/6] 匹配引擎边界测试')

from match_engine import MatchEngine, MatchMode


def test_empty_text():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三'])
    result = engine.match_text('', 1, 'test.pdf', ['张三'])
    assert len(result) == 0


def test_no_keywords():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare([])
    result = engine.match_text('张三来了', 1, 'test.pdf', [])
    assert len(result) == 0


def test_keyword_at_start():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三'])
    result = engine.match_text('张三来了', 1, 'test.pdf', ['张三'])
    assert '张三' in result


def test_keyword_at_end():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三'])
    result = engine.match_text('看到张三', 1, 'test.pdf', ['张三'])
    assert '张三' in result


def test_keyword_only():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三'])
    result = engine.match_text('张三', 1, 'test.pdf', ['张三'])
    assert '张三' in result


def test_repeated_keyword():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三'])
    result = engine.match_text('张三说张三很厉害，张三是好人', 1, 'test.pdf', ['张三'])
    assert '张三' in result
    # 同一页只记录一次页码
    assert result['张三'][0].page_num == 1


def test_fuzzy_variations():
    engine = MatchEngine(MatchMode.FUZZY)
    engine.prepare(['张三'])
    variations = ['张 三', '张　三', '张-三', '张•三']
    for text in variations:
        result = engine.match_text(f'{text}来了', 1, 'test.pdf', ['张三'])
        assert '张三' in result, f'模糊匹配失败: "{text}"'


def test_regex_complex():
    engine = MatchEngine(MatchMode.REGEX)
    engine.prepare(['张.{1,2}三'])
    result = engine.match_text('张大三来了', 1, 'test.pdf', ['张.{1,2}三'])
    assert '张.{1,2}三' in result


def test_invalid_regex():
    engine = MatchEngine(MatchMode.REGEX)
    try:
        engine.prepare(['[invalid'])
        assert False, '应该抛出异常'
    except Exception:
        pass


test('空文本', test_empty_text)
test('无关键词', test_no_keywords)
test('关键词在开头', test_keyword_at_start)
test('关键词在结尾', test_keyword_at_end)
test('只有关键词', test_keyword_only)
test('重复关键词同页', test_repeated_keyword)
test('模糊匹配变体', test_fuzzy_variations)
test('正则复杂模式', test_regex_complex)
test('无效正则表达式', test_invalid_regex)

# ==================== PDF解析边界测试 ====================
print('\n[3/6] PDF解析边界测试')

from pdf_parser_v2 import PDFParserV2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def test_single_page_pdf():
    pdf_path = os.path.join(test_dir, 'single_page.pdf')
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 700, 'Hello World')
    c.showPage()
    c.save()
    
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_path)
    assert len(pages) == 1
    assert 'Hello' in pages[0].text


def test_empty_pdf():
    pdf_path = os.path.join(test_dir, 'empty.pdf')
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.showPage()
    c.save()
    
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_path)
    assert len(pages) == 1


def test_many_pages_pdf():
    pdf_path = os.path.join(test_dir, 'many_pages.pdf')
    c = canvas.Canvas(pdf_path, pagesize=letter)
    for i in range(20):
        c.drawString(100, 700, f'Page {i+1}')
        c.showPage()
    c.save()
    
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_path)
    assert len(pages) == 20


def test_collect_empty_folder():
    empty_dir = os.path.join(test_dir, 'empty_folder')
    os.makedirs(empty_dir, exist_ok=True)
    
    parser = PDFParserV2()
    files = parser.collect_pdf_files(empty_dir, 'folder')
    assert len(files) == 0


def test_nonexistent_pdf():
    parser = PDFParserV2()
    try:
        parser.parse_single_pdf('不存在.pdf')
        assert False, '应该抛出异常'
    except FileNotFoundError:
        pass


test('单页PDF', test_single_page_pdf)
test('空PDF', test_empty_pdf)
test('多页PDF', test_many_pages_pdf)
test('空文件夹', test_collect_empty_folder)
test('不存在的PDF', test_nonexistent_pdf)

# ==================== 导出边界测试 ====================
print('\n[4/6] 导出边界测试')

from exporter import Exporter
from match_engine import MatchResult, KeywordResult


def test_export_empty_result():
    result = MatchResult(keywords={}, total_hits=0, matched_keywords=0, total_keywords=0)
    output = os.path.join(test_dir, 'empty_export')
    files = Exporter.export(result, output, formats={'excel': True})
    assert len(files) == 1


def test_export_single_keyword():
    result = MatchResult(
        keywords={'A': KeywordResult(keyword='A', count=1, pages=[1], pdfs=['a.pdf'], first_page=1, last_page=1)},
        total_hits=1, matched_keywords=1, total_keywords=1
    )
    output = os.path.join(test_dir, 'single_export')
    files = Exporter.export(result, output, formats={'excel': True, 'csv': True})
    assert len(files) >= 2


def test_export_no_format():
    result = MatchResult(keywords={}, total_hits=0, matched_keywords=0, total_keywords=0)
    output = os.path.join(test_dir, 'no_format')
    files = Exporter.export(result, output, formats={})
    assert len(files) == 0


test('空结果导出', test_export_empty_result)
test('单关键词导出', test_export_single_keyword)
test('无格式导出', test_export_no_format)

# ==================== 统计模块边界测试 ====================
print('\n[5/6] 统计模块边界测试')

from stats import StatsCalculator, AnalysisStats


def test_stats_empty():
    result = MatchResult(keywords={}, total_hits=0, matched_keywords=0, total_keywords=0)
    stats = StatsCalculator.calculate(result)
    assert stats.keyword.total_keywords == 0
    assert stats.keyword.total_hits == 0


def test_stats_summary_empty():
    stats = AnalysisStats()
    summary = stats.get_summary()
    assert '统计' in summary


def test_keyword_table_empty():
    result = MatchResult(keywords={}, total_hits=0, matched_keywords=0, total_keywords=0)
    table = StatsCalculator.get_keyword_table(result)
    assert len(table) == 0


test('空统计', test_stats_empty)
test('空摘要', test_stats_summary_empty)
test('空表格', test_keyword_table_empty)

# ==================== 缓存管理边界测试 ====================
print('\n[6/6] 缓存管理边界测试')

from cache_manager import CacheManager


def test_cache_empty_dir():
    empty_cache = os.path.join(test_dir, 'empty_cache')
    cm = CacheManager(cache_dir=empty_cache)
    assert cm.get_cache_count() == 0
    assert cm.get_total_size() == 0


def test_cache_clear_empty():
    empty_cache = os.path.join(test_dir, 'empty_cache2')
    cm = CacheManager(cache_dir=empty_cache)
    count = cm.clear_all()
    assert count == 0


def test_cache_status_empty():
    empty_cache = os.path.join(test_dir, 'empty_cache3')
    cm = CacheManager(cache_dir=empty_cache)
    status = cm.get_status()
    assert status['file_count'] == 0


test('空缓存目录', test_cache_empty_dir)
test('清除空缓存', test_cache_clear_empty)
test('空缓存状态', test_cache_status_empty)

# ==================== 清理 ====================
print('\n清理临时文件...')
shutil.rmtree(test_dir, ignore_errors=True)

# ==================== 结果 ====================
print('\n' + '=' * 60)
if errors:
    print(f'压力测试完成: {len(errors)} 个错误')
    for name, err in errors:
        print(f'  ✗ {name}: {err}')
    sys.exit(1)
else:
    print('压力测试完成: 全部通过 ✓')
print('=' * 60)
