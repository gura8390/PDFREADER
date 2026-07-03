"""
v2.0 集成测试 - 端到端完整流程测试
"""

import sys
import os
import shutil
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 60)
print('v2.0 集成测试 - 端到端流程')
print('=' * 60)

errors = []
test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_integration_temp')


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


# ==================== 准备测试数据 ====================
print('\n准备测试数据...')

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# 创建关键词库
keyword_file = os.path.join(test_dir, 'keywords.txt')
with open(keyword_file, 'w', encoding='utf-8') as f:
    f.write('John,Mary,Bob,Alice,Johnson')

# 创建PDF文件
pdf1 = os.path.join(test_dir, 'report1.pdf')
c = canvas.Canvas(pdf1, pagesize=letter)
c.drawString(100, 700, 'John and Mary went to the meeting')
c.showPage()
c.drawString(100, 700, 'Bob and Alice joined later')
c.showPage()
c.drawString(100, 700, 'John presented the results')
c.showPage()
c.save()

pdf2 = os.path.join(test_dir, 'report2.pdf')
c = canvas.Canvas(pdf2, pagesize=letter)
c.drawString(100, 700, 'Alice and Johnson discussed the plan')
c.showPage()
c.drawString(100, 700, 'Mary was not present')
c.showPage()
c.save()

print(f'  创建了关键词库: {keyword_file}')
print(f'  创建了PDF: {pdf1}, {pdf2}')


# ==================== 测试1: 单PDF + Excel导出 ====================
print('\n[1/8] 单PDF + 精确匹配 + Excel导出')

from keyword_loader import KeywordLoader
from pdf_parser_v2 import PDFParserV2
from match_engine import MatchEngine, MatchMode
from exporter import Exporter
from stats import StatsCalculator


def test_single_pdf_excel():
    keywords = KeywordLoader.load(keyword_file)
    assert len(keywords) == 5
    
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf1)
    assert len(pages) == 3
    
    engine = MatchEngine(MatchMode.EXACT, case_sensitive=True, context_length=30)
    result = engine.match_all(pages, keywords)
    
    assert result.keywords['John'].count == 2
    assert result.keywords['Mary'].count == 1
    assert result.keywords['Bob'].count == 1
    assert result.keywords['Alice'].count == 1
    assert result.keywords['Johnson'].count == 0
    
    output = os.path.join(test_dir, 'single_excel')
    files = Exporter.export(result, output, formats={'excel': True}, include_context=True)
    assert len(files) == 1
    assert os.path.exists(files[0])


test('单PDF + Excel', test_single_pdf_excel)


# ==================== 测试2: 多PDF + CSV导出 ====================
print('\n[2/8] 多PDF + CSV导出')


def test_multi_pdf_csv():
    parser = PDFParserV2(use_cache=False)
    result = parser.parse_multiple_pdfs([pdf1, pdf2])
    assert result.total_pages == 5
    assert len(result.pdf_list) == 2
    
    keywords = KeywordLoader.load(keyword_file)
    engine = MatchEngine(MatchMode.EXACT)
    match_result = engine.match_all(result.pages, keywords)
    
    assert match_result.keywords['John'].count == 2
    assert match_result.keywords['Alice'].count == 2
    assert match_result.total_pdfs == 2
    
    output = os.path.join(test_dir, 'multi_csv')
    files = Exporter.export(match_result, output, formats={'csv': True}, include_context=True)
    assert len(files) >= 1


test('多PDF + CSV', test_multi_pdf_csv)


# ==================== 测试3: 文件夹模式 + JSON导出 ====================
print('\n[3/8] 文件夹模式 + JSON导出')


def test_folder_json():
    parser = PDFParserV2(use_cache=False)
    pdf_files = parser.collect_pdf_files(test_dir, 'folder')
    assert len(pdf_files) >= 2
    
    result = parser.parse_multiple_pdfs(pdf_files)
    assert result.total_pages >= 5
    
    keywords = KeywordLoader.load(keyword_file)
    engine = MatchEngine(MatchMode.EXACT)
    match_result = engine.match_all(result.pages, keywords)
    
    output = os.path.join(test_dir, 'folder_json')
    files = Exporter.export(match_result, output, formats={'json': True})
    assert len(files) == 1
    
    # 验证JSON内容
    with open(files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert 'keywords' in data
    assert len(data['keywords']) > 0


test('文件夹 + JSON', test_folder_json)


# ==================== 测试4: 模糊匹配 ====================
print('\n[4/8] 模糊匹配')

from reportlab.pdfgen import canvas as c2


def test_fuzzy_match():
    # 创建包含变体的PDF
    pdf_fuzzy = os.path.join(test_dir, 'fuzzy.pdf')
    c_obj = c2.Canvas(pdf_fuzzy, pagesize=letter)
    c_obj.drawString(100, 700, 'J o h n came here')  # 带空格
    c_obj.showPage()
    c_obj.drawString(100, 700, 'Mary-Jane was here')  # 带连字符
    c_obj.showPage()
    c_obj.save()
    
    keywords = ['John', 'Mary']
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_fuzzy)
    
    engine = MatchEngine(MatchMode.FUZZY, context_length=20)
    result = engine.match_all(pages, keywords)
    
    assert result.keywords['John'].count >= 1, f'John应该匹配到，实际: {result.keywords["John"].count}'


test('模糊匹配', test_fuzzy_match)


# ==================== 测试5: 不区分大小写 ====================
print('\n[5/8] 不区分大小写')


def test_case_insensitive():
    pdf_case = os.path.join(test_dir, 'case.pdf')
    c_obj = c2.Canvas(pdf_case, pagesize=letter)
    c_obj.drawString(100, 700, 'john and MARY are here')
    c_obj.showPage()
    c_obj.drawString(100, 700, 'JOHN and mary left')
    c_obj.showPage()
    c_obj.save()
    
    keywords = ['John', 'Mary']
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_case)
    
    engine = MatchEngine(MatchMode.EXACT, case_sensitive=False, context_length=20)
    result = engine.match_all(pages, keywords)
    
    assert result.keywords['John'].count == 2, f'John应该匹配2次，实际: {result.keywords["John"].count}'
    assert result.keywords['Mary'].count == 2, f'Mary应该匹配2次，实际: {result.keywords["Mary"].count}'


test('不区分大小写', test_case_insensitive)


# ==================== 测试6: 统计信息 ====================
print('\n[6/8] 统计信息')


def test_stats_integration():
    keywords = KeywordLoader.load(keyword_file)
    parser = PDFParserV2(use_cache=False)
    parsed_result = parser.parse_multiple_pdfs([pdf1, pdf2])
    
    engine = MatchEngine(MatchMode.EXACT)
    match_result = engine.match_all(parsed_result.pages, keywords)
    
    stats = StatsCalculator.calculate(
        match_result, parsed_result,
        total_time=1.5, parse_time=0.5, match_time=0.8, export_time=0.2
    )
    
    assert stats.pdf.total_pdfs == 2
    assert stats.pdf.total_pages == 5
    assert stats.keyword.total_keywords == 5
    assert stats.keyword.matched_keywords >= 3
    assert stats.performance.total_time == 1.5
    
    summary = stats.get_summary()
    assert '统计' in summary
    assert '2' in summary  # PDF数量


test('统计信息', test_stats_integration)


# ==================== 测试7: 缓存机制 ====================
print('\n[7/8] 缓存机制')


def test_cache_integration():
    cache_dir = os.path.join(test_dir, 'cache')
    parser = PDFParserV2(use_cache=True, cache_dir=cache_dir)
    
    # 第一次解析
    pages1 = parser.parse_single_pdf(pdf1)
    assert len(pages1) == 3
    
    # 验证缓存文件存在
    cache_files = os.listdir(cache_dir)
    assert len(cache_files) >= 1
    
    # 第二次解析（从缓存加载）
    pages2 = parser.parse_single_pdf(pdf1)
    assert len(pages2) == len(pages1)
    
    # 验证内容一致
    for p1, p2 in zip(pages1, pages2):
        assert p1.text == p2.text


test('缓存机制', test_cache_integration)


# ==================== 测试8: 配置管理 ====================
print('\n[8/8] 配置管理')


def test_config_integration():
    from config import Config
    
    config_path = os.path.join(test_dir, 'config.json')
    config = Config(config_path)
    
    # 修改配置
    config.set("match", "mode", "fuzzy")
    config.set("match", "context_length", 50)
    config.update_recent(keyword_dir=test_dir)
    
    # 重新加载
    config2 = Config(config_path)
    assert config2.get("match", "mode") == "fuzzy"
    assert config2.get("match", "context_length") == 50
    assert config2.get("recent", "keyword_dir") == test_dir


test('配置管理', test_config_integration)


# ==================== 清理 ====================
print('\n清理临时文件...')
shutil.rmtree(test_dir, ignore_errors=True)

# ==================== 结果 ====================
print('\n' + '=' * 60)
if errors:
    print(f'集成测试完成: {len(errors)} 个错误')
    for name, err in errors:
        print(f'  ✗ {name}: {err}')
    sys.exit(1)
else:
    print('集成测试完成: 全部通过 ✓')
print('=' * 60)
