"""
PDF关键词分析工具 v2.0 - 基准测试
测试所有模块的功能和边界情况
"""

import sys
import os
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 60)
print('v2.0 基准测试 - 开始')
print('=' * 60)

errors = []
test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_bench_temp')


def test(name, func):
    try:
        func()
        print(f'  ✓ {name}')
    except Exception as e:
        print(f'  ✗ {name}: {e}')
        errors.append((name, str(e)))


# 准备测试目录
if os.path.exists(test_dir):
    shutil.rmtree(test_dir)
os.makedirs(test_dir, exist_ok=True)

# ==================== M1: config.py ====================
print('\n[1/10] config.py - 配置管理')

from config import Config


def test_config_default():
    config = Config(os.path.join(test_dir, 'test_config.json'))
    assert config.get("window", "width") == 1200
    assert config.get("match", "mode") == "exact"


def test_config_save_load():
    path = os.path.join(test_dir, 'test_config2.json')
    config = Config(path)
    config.set("match", "mode", "fuzzy")
    config.save()
    
    config2 = Config(path)
    assert config2.get("match", "mode") == "fuzzy"


def test_config_update_recent():
    path = os.path.join(test_dir, 'test_config3.json')
    config = Config(path)
    config.update_recent(keyword_dir="/test/dir")
    assert config.get("recent", "keyword_dir") == "/test/dir"


test('默认配置', test_config_default)
test('保存加载', test_config_save_load)
test('更新最近目录', test_config_update_recent)

# ==================== M2: keyword_loader.py ====================
print('\n[2/10] keyword_loader.py - 关键词库')

from keyword_loader import KeywordLoader


def test_load_txt():
    f = os.path.join(test_dir, 'kw.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('张三,李四,王五')
    result = KeywordLoader.load(f)
    assert result == ['张三', '李四', '王五']


def test_load_csv():
    f = os.path.join(test_dir, 'kw.csv')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('张三\n李四\n王五')
    result = KeywordLoader.load(f)
    assert len(result) == 3


def test_load_json():
    f = os.path.join(test_dir, 'kw.json')
    with open(f, 'w', encoding='utf-8') as fp:
        json.dump(['张三', '李四', '王五'], fp)
    result = KeywordLoader.load(f)
    assert result == ['张三', '李四', '王五']


def test_load_json_dict():
    f = os.path.join(test_dir, 'kw2.json')
    with open(f, 'w', encoding='utf-8') as fp:
        json.dump({'keywords': ['A', 'B', 'C']}, fp)
    result = KeywordLoader.load(f)
    assert result == ['A', 'B', 'C']


def test_load_excel():
    from openpyxl import Workbook
    f = os.path.join(test_dir, 'kw.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.append(['张三', '李四'])
    ws.append(['王五'])
    wb.save(f)
    result = KeywordLoader.load(f)
    assert len(result) == 3


def test_load_dedup():
    f = os.path.join(test_dir, 'kw_dup.txt')
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write('A,B,A,C,B')
    result = KeywordLoader.load(f)
    assert result == ['A', 'B', 'C']


def test_load_notfound():
    try:
        KeywordLoader.load('不存在.txt')
        assert False
    except FileNotFoundError:
        pass


test('加载TXT', test_load_txt)
test('加载CSV', test_load_csv)
test('加载JSON列表', test_load_json)
test('加载JSON字典', test_load_json_dict)
test('加载Excel', test_load_excel)
test('去重', test_load_dedup)
test('文件不存在', test_load_notfound)

# ==================== M3: pdf_parser_v2.py ====================
print('\n[3/10] pdf_parser_v2.py - PDF解析')

from pdf_parser_v2 import PDFParserV2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_test_pdf(path, pages=2):
    c = canvas.Canvas(path, pagesize=letter)
    for i in range(pages):
        c.drawString(100, 700, f'Page {i+1} Content')
        c.drawString(100, 680, f'John and Mary on page {i+1}')
        c.showPage()
    c.save()


def test_parser_single():
    pdf_path = os.path.join(test_dir, 'test.pdf')
    create_test_pdf(pdf_path, 3)
    
    parser = PDFParserV2(use_cache=False)
    pages = parser.parse_single_pdf(pdf_path)
    assert len(pages) == 3
    assert 'John' in pages[0].text


def test_parser_info():
    pdf_path = os.path.join(test_dir, 'test.pdf')
    parser = PDFParserV2()
    info = parser.get_pdf_info(pdf_path)
    assert info.page_count == 3
    assert info.name == 'test.pdf'


def test_parser_collect():
    pdf_path = os.path.join(test_dir, 'test.pdf')
    parser = PDFParserV2()
    
    files = parser.collect_pdf_files(pdf_path, 'single')
    assert len(files) == 1
    
    files = parser.collect_pdf_files(test_dir, 'folder')
    assert len(files) >= 1


def test_parser_cache():
    pdf_path = os.path.join(test_dir, 'test.pdf')
    parser = PDFParserV2(use_cache=True, cache_dir=os.path.join(test_dir, 'cache'))
    
    pages1 = parser.parse_single_pdf(pdf_path)
    pages2 = parser.parse_single_pdf(pdf_path)
    assert len(pages1) == len(pages2)


def test_parser_multiple():
    pdf1 = os.path.join(test_dir, 'a.pdf')
    pdf2 = os.path.join(test_dir, 'b.pdf')
    create_test_pdf(pdf1, 2)
    create_test_pdf(pdf2, 3)
    
    parser = PDFParserV2(use_cache=False)
    result = parser.parse_multiple_pdfs([pdf1, pdf2])
    assert result.total_pages == 5
    assert len(result.pdf_list) == 2


test('单个PDF解析', test_parser_single)
test('PDF信息', test_parser_info)
test('收集PDF文件', test_parser_collect)
test('缓存机制', test_parser_cache)
test('多PDF解析', test_parser_multiple)

# ==================== M4: match_engine.py ====================
print('\n[4/10] match_engine.py - 匹配引擎')

from match_engine import MatchEngine, MatchMode


def test_exact_match():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三', '李四'])
    result = engine.match_text('张三和李四去吃饭', 1, 'test.pdf', ['张三', '李四'])
    assert '张三' in result
    assert '李四' in result


def test_exact_no_substring():
    engine = MatchEngine(MatchMode.EXACT)
    engine.prepare(['张三', '张三丰'])
    result = engine.match_text('张三丰来了', 1, 'test.pdf', ['张三', '张三丰'])
    assert '张三丰' in result
    assert '张三' not in result


def test_fuzzy_match():
    engine = MatchEngine(MatchMode.FUZZY)
    engine.prepare(['张三'])
    result = engine.match_text('张 三来了', 1, 'test.pdf', ['张三'])
    assert '张三' in result


def test_regex_match():
    engine = MatchEngine(MatchMode.REGEX)
    engine.prepare(['张.{1}三'])
    result = engine.match_text('张大三来了', 1, 'test.pdf', ['张.{1}三'])
    assert '张.{1}三' in result


def test_case_insensitive():
    engine = MatchEngine(MatchMode.EXACT, case_sensitive=False)
    engine.prepare(['John', 'Mary'])
    result = engine.match_text('john and MARY', 1, 'test.pdf', ['John', 'Mary'])
    assert 'John' in result
    assert 'Mary' in result


def test_context_extraction():
    engine = MatchEngine(MatchMode.EXACT, context_length=10)
    engine.prepare(['张三'])
    result = engine.match_text('在项目中张三负责开发', 1, 'test.pdf', ['张三'])
    assert '张三' in result
    hit = result['张三'][0]
    assert len(hit.context_before) > 0


def test_match_all():
    from pdf_parser_v2 import ParsedPage
    pages = [
        ParsedPage('a.pdf', '/a.pdf', 1, '张三来了', True),
        ParsedPage('a.pdf', '/a.pdf', 2, '李四来了', True),
        ParsedPage('b.pdf', '/b.pdf', 1, '张三又来了', True),
    ]
    
    engine = MatchEngine(MatchMode.EXACT)
    result = engine.match_all(pages, ['张三', '李四'])
    assert result.total_hits == 3
    assert result.matched_keywords == 2
    assert result.keywords['张三'].count == 2
    assert result.keywords['张三'].first_page == 1
    assert result.keywords['张三'].last_page == 1


test('精确匹配', test_exact_match)
test('精确不匹配子串', test_exact_no_substring)
test('模糊匹配', test_fuzzy_match)
test('正则匹配', test_regex_match)
test('不区分大小写', test_case_insensitive)
test('上下文提取', test_context_extraction)
test('批量匹配', test_match_all)

# ==================== M5: context_extractor.py ====================
print('\n[5/10] context_extractor.py - 上下文提取')

from context_extractor import ContextExtractor


def test_format_context():
    result = ContextExtractor.format_context('前文', '关键词', '后文')
    assert '前文' in result
    assert '关键词' in result
    assert '后文' in result


def test_truncate():
    result = ContextExtractor.truncate_context('很长的文本内容在这里', 5)
    assert '...' in result
    assert len(result) <= 8  # 5 + "..."


test('格式化上下文', test_format_context)
test('截断文本', test_truncate)

# ==================== M6: stats.py ====================
print('\n[6/10] stats.py - 统计模块')

from stats import StatsCalculator, AnalysisStats


def test_stats_calculate():
    from match_engine import MatchResult, KeywordResult
    
    match_result = MatchResult(
        keywords={
            '张三': KeywordResult(keyword='张三', count=5, pages=[1, 3], pdfs=['a.pdf'], first_page=1, last_page=3),
            '李四': KeywordResult(keyword='李四', count=0, pages=[], pdfs=[], first_page=0, last_page=0),
        },
        total_hits=5,
        matched_keywords=1,
        total_keywords=2,
        total_pages=10,
        total_pdfs=1
    )
    
    stats = StatsCalculator.calculate(match_result, total_time=10.0)
    assert stats.keyword.total_keywords == 2
    assert stats.keyword.matched_keywords == 1
    assert stats.keyword.unmatched_keywords == 1
    assert stats.performance.total_time == 10.0


def test_stats_summary():
    from match_engine import MatchResult, KeywordResult
    
    match_result = MatchResult(
        keywords={
            'A': KeywordResult(keyword='A', count=10, pages=[1], pdfs=['a.pdf'], first_page=1, last_page=1),
        },
        total_hits=10,
        matched_keywords=1,
        total_keywords=1,
        total_pages=5,
        total_pdfs=1
    )
    
    stats = StatsCalculator.calculate(match_result, total_time=5.0)
    summary = stats.get_summary()
    assert '统计' in summary
    assert '10' in summary


def test_keyword_table():
    from match_engine import MatchResult, KeywordResult
    
    match_result = MatchResult(
        keywords={
            'B': KeywordResult(keyword='B', count=3, pages=[2], pdfs=['a.pdf'], first_page=2, last_page=2),
            'A': KeywordResult(keyword='A', count=10, pages=[1], pdfs=['a.pdf'], first_page=1, last_page=1),
        },
        total_hits=13,
        matched_keywords=2,
        total_keywords=2,
        total_pages=5,
        total_pdfs=1
    )
    
    table = StatsCalculator.get_keyword_table(match_result, 'count', 'desc')
    assert table[0]['keyword'] == 'A'  # 降序，A先


test('统计计算', test_stats_calculate)
test('统计摘要', test_stats_summary)
test('关键词表格排序', test_keyword_table)

# ==================== M7: exporter.py ====================
print('\n[7/10] exporter.py - 多格式导出')

from exporter import Exporter
from match_engine import MatchResult, KeywordResult, MatchHit


def create_test_match_result():
    return MatchResult(
        keywords={
            '张三': KeywordResult(
                keyword='张三', count=2, pages=[1, 3], pdfs=['a.pdf'],
                first_page=1, last_page=3,
                hits=[
                    MatchHit('张三', 1, 'a.pdf', 10, '前文', '后文', '张三'),
                    MatchHit('张三', 3, 'a.pdf', 20, '前文', '后文', '张三'),
                ]
            ),
            '李四': KeywordResult(keyword='李四', count=0, pages=[], pdfs=[], first_page=0, last_page=0),
        },
        total_hits=2,
        matched_keywords=1,
        total_keywords=2,
        total_pages=5,
        total_pdfs=1
    )


def test_export_excel():
    result = create_test_match_result()
    output = os.path.join(test_dir, 'export_test')
    files = Exporter.export(result, output, formats={'excel': True}, include_context=True)
    assert len(files) == 1
    assert files[0].endswith('.xlsx')
    assert os.path.exists(files[0])


def test_export_csv():
    result = create_test_match_result()
    output = os.path.join(test_dir, 'export_csv')
    files = Exporter.export(result, output, formats={'csv': True}, include_context=True)
    assert len(files) >= 1
    assert any(f.endswith('.csv') for f in files)


def test_export_json():
    result = create_test_match_result()
    output = os.path.join(test_dir, 'export_json')
    files = Exporter.export(result, output, formats={'json': True})
    assert len(files) == 1
    assert files[0].endswith('.json')


def test_export_all():
    result = create_test_match_result()
    output = os.path.join(test_dir, 'export_all')
    files = Exporter.export(result, output, formats={'excel': True, 'csv': True, 'json': True}, include_context=True)
    assert len(files) >= 3  # Excel + CSV + 上下文CSV + JSON


test('导出Excel', test_export_excel)
test('导出CSV', test_export_csv)
test('导出JSON', test_export_json)
test('全部格式导出', test_export_all)

# ==================== M8: ocr_module.py ====================
print('\n[8/10] ocr_module.py - OCR模块')

from ocr_module import OCRModule


def test_ocr_init():
    ocr = OCRModule()
    assert ocr.language == "chi_sim+eng"


def test_ocr_available():
    ocr = OCRModule()
    # 不管是否安装，不应该崩溃
    available = ocr.is_available()
    assert isinstance(available, bool)


test('OCR初始化', test_ocr_init)
test('OCR可用性检查', test_ocr_available)

# ==================== M9: cache_manager.py ====================
print('\n[9/10] cache_manager.py - 缓存管理')

from cache_manager import CacheManager


def test_cache_manager():
    cache_dir = os.path.join(test_dir, 'cm_cache')
    cm = CacheManager(cache_dir=cache_dir)
    
    # 创建测试缓存文件
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, 'test.json'), 'w') as f:
        json.dump({'test': True}, f)
    
    assert cm.get_cache_count() == 1
    assert cm.get_total_size() > 0


def test_cache_status():
    cache_dir = os.path.join(test_dir, 'cm_cache2')
    cm = CacheManager(cache_dir=cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    
    status = cm.get_status()
    assert 'file_count' in status
    assert 'total_size_str' in status


def test_cache_clear():
    cache_dir = os.path.join(test_dir, 'cm_cache3')
    cm = CacheManager(cache_dir=cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    
    with open(os.path.join(cache_dir, 'a.json'), 'w') as f:
        json.dump({}, f)
    with open(os.path.join(cache_dir, 'b.json'), 'w') as f:
        json.dump({}, f)
    
    assert cm.get_cache_count() == 2
    count = cm.clear_all()
    assert count == 2
    assert cm.get_cache_count() == 0


test('缓存管理器', test_cache_manager)
test('缓存状态', test_cache_status)
test('缓存清除', test_cache_clear)

# ==================== M10+M12: worker.py ====================
print('\n[10/10] worker.py - 任务调度')

from worker import TaskManager, MessageType, WorkerMessage
import queue


def test_task_manager_init():
    q = queue.Queue()
    tm = TaskManager(q)
    assert not tm.is_running


def test_message_types():
    assert MessageType.STATUS.value == "status"
    assert MessageType.ERROR.value == "error"


test('任务管理器初始化', test_task_manager_init)
test('消息类型', test_message_types)

# ==================== 清理 ====================
print('\n清理临时文件...')
shutil.rmtree(test_dir, ignore_errors=True)

# ==================== 结果 ====================
print('\n' + '=' * 60)
if errors:
    print(f'v2.0 基准测试完成: {len(errors)} 个错误')
    for name, err in errors:
        print(f'  ✗ {name}: {err}')
    sys.exit(1)
else:
    print('v2.0 基准测试完成: 全部通过 ✓')
print('=' * 60)
