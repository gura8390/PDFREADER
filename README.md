# PDF Keyword Analyzer · PDF 关键词分析工具

带 Tkinter 图形界面的 Python 工具，用于在 PDF 中查找关键词，统计出现次数、页码和上下文，并导出报告。人名名单是其中一种使用场景。A desktop PDF keyword analyzer with report export.

## 能做什么

- 从 TXT、CSV、Excel 或 JSON 文件加载关键词。
- 选择单个、多份 PDF，或指定目录批量分析。
- 按精确、模糊或正则模式匹配，按需区分大小写。
- 查看命中页码和前后文，导出 Excel、CSV、JSON 报告。
- 对扫描型 PDF 使用可选 OCR 模块；OCR 需要额外依赖。

项目保留多个解析器和测试脚本，正常 GUI 入口为 `main.py`。当前仓库提供源码，没有正式的二进制 Release 下载。

## 安装与运行

安装包含 Tkinter 的 Python 3，然后执行：

```powershell
git clone https://github.com/gura8390/PDFREADER.git
cd PDFREADER
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

`requirements.txt` 中的核心依赖是 `pdfplumber` 和 `openpyxl`。其他系统也可使用虚拟环境中的 Python 运行 `main.py`，跨平台 GUI 兼容性需要另行核验。

## 基本操作

1. 选择关键词库和待分析的 PDF 文件或目录。
2. 设置匹配模式、上下文范围和导出格式。
3. 选择输出位置并开始分析。
4. 查看结果，再打开导出的报告进行核对。

## 扫描件与 OCR

扫描件可能没有可直接提取的文本层。按需安装 `pytesseract`、`Pillow`、`pdf2image`，并配置系统中的 Tesseract 和 Poppler；这些组件不包含在核心依赖安装中。OCR 识别结果和统计结果需要人工核对。

## 文件说明

| 文件 | 用途 |
|---|---|
| `main.py` | GUI 启动入口 |
| `keyword_loader.py` | 关键词库读取 |
| `pdf_parser.py`、`pdf_parser_v2.py` | PDF 解析模块 |
| `match_engine.py`、`name_matcher.py` | 匹配相关实现 |
| `context_extractor.py` | 命中上下文 |
| `exporter.py`、`excel_exporter.py` | 结果导出 |
| `integration_test.py`、`stress_test.py`、`benchmark*.py` | 开发检查脚本，使用前查看所需输入 |

Python 字节码和缓存目录不提交版本库。配置、缓存、虚拟环境和实际处理的文件应保留在本地，不要将含有个人资料的输入文件放入公开提交。

## 许可证

[MIT License](LICENSE)。
