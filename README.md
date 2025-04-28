# JavaScript API 请求提取工具

这是一个用于从网页或 JavaScript 文件中提取潜在 HTTP API 请求（包括 RESTful, GraphQL, WebSocket）的 Python 工具。它可以分析单个 URL、本地文件或包含 URL 列表的文件，并将提取结果保存到文本文件，并可选择生成交互式 HTML 报告。

## 目录
- [✨ 功能特性](#功能特性)  
- [⬇️ 安装](#安装)  
- [🚀 使用方法](#使用方法)  
- [📂 文件结构说明](#文件结构说明)  
- [📄 输出格式](#输出格式)  
- [📊 HTML 报告](#html-报告)  
- [🙌 贡献](#贡献)
  
## ✨ 功能特性
- 支持分析单个网页 URL，自动抓取页面中的外部和内联 JavaScript。
- 支持直接分析单个 JavaScript 文件 URL。
- 支持分析本地 JavaScript 文件。
- 支持从包含网页 URL 或 JavaScript URL 列表的文件中批量提取。
- 能够识别常见的 HTTP 方法（GET, POST, PUT, DELETE, PATCH）以及 WebSocket 和 GraphQL 端点。
- 尝试提取与 API 请求相关的参数信息，并进行格式化（支持 JSON 格式化和 JS 表达式占位符处理）。
- 将提取结果输出到易于阅读的文本文件。
- 可选择生成交互式 HTML 报告，方便浏览和分析提取结果。
- 命令行接口，易于集成和自动化。

## ⬇️ 安装
1.确保您已安装 Python 3.6 或更高版本。  
2.克隆本仓库或下载所有脚本文件 (main.py, processor.py, extractor.py, formatter.py, bg.py, utils.py) 到同一个目录。  
3.安装所需的 Python 库：
```bash
pip install requests beautifulsoup4
```
- requests 用于进行网络请求。
- beautifulsoup4 用于更健壮地解析 HTML（如果未安装，将回退到正则表达式解析，但强烈推荐安装）。
## 🚀 使用方法
通过命令行运行 main.py 脚本。

```bash
python main.py [选项]
```
#### 必需参数 (选择其中一个):
- -u <PAGE_URL>, --url <PAGE_URL>: 分析单个网页 URL。
- -eu <JS_URL>, --extract-url <JS_URL>: 直接分析单个 JS 文件 URL。
- -l <PAGE_URL_FILE>, --list <PAGE_URL_FILE>: 分析包含网页 URL 列表的文件。
- -el <JS_URL_FILE>, --extract-list <JS_URL_FILE>: 分析包含 JS 文件 URL 列表的文件。
- -f <JS_FILE_PATH>, --file <JS_FILE_PATH>: 分析本地 JS 文件。

#### 可选参数:
- --report [HTML_PATH]: 生成 HTML 报告。如果未指定 HTML_PATH，将自动生成文件名（基于输入源，后缀为 .html）。
- -v, --verbose: 启用详细日志记录（DEBUG 级别），输出更多调试信息。

### 示例:
分析单个网页并生成报告：
```bash
python main.py -u https://example.com --report report.html
```
分析本地 JS 文件并生成报告（自动命名报告文件）：
```bash
python main.py -f script.js --report
```
批量分析网页 URL 列表文件：
```bash
python main.py -l urls.txt
```
批量分析 JS URL 列表文件并启用详细日志：
```bash
python main.py -el js_urls.txt -v
```
## 📂 文件结构说明
- main.py: 程序主入口，负责解析命令行参数，调用 processor 模块处理输入，并根据需要调用 bg 模块生成报告。
- processor.py: 处理不同类型的输入（URL、文件、列表）。它负责获取内容（下载网页/JS 文件或读取本地文件），并调用 extractor 模块进行分析。
- extractor.py: 核心提取逻辑。使用正则表达式从 JavaScript 源代码中识别 API 请求模式，并尝试在请求附近查找参数。
- formatter.py: 参数格式化模块。负责清理和美化提取到的参数字符串，尝试将其格式化为易读的 JSON，并处理 JavaScript 表达式。
- bg.py: HTML 报告生成模块。读取 main.py 生成的文本结果文件，解析内容，并生成一个交互式、结构化的 HTML 报告。
- utils.py: 包含一些实用工具函数，如安全的文件写入、创建输出文件头部以及控制台颜色控制。
  
## 📄 输出格式
提取结果将保存到一个文本文件中（默认后缀为 _api_results.txt）。文件内容结构如下：
```bash
# JavaScript API 请求提取结果
# 生成时间:YYYY-MM-DD HH:MM:SS
# 工具版本: 1.0
# 注意: 结果基于启发式规则，可能存在误报或漏报，请结合实际情况分析。

## 分析网页: https://example.com
============================================================

--- 来源: https://example.com/path/to/script.js ---
------------------------------------------------------------
类型: RESTful, 请求: "GET /api/users"
请求参数: 无参数
------------------------------------------------------------
类型: RESTful, 请求: "POST /api/data"
请求参数: {
  "key1": "value1",
  "key2": 123
}
------------------------------------------------------------

--- 来源: https://example.com (内联脚本) ---
------------------------------------------------------------
类型: GraphQL, 请求: "POST /graphql"
请求参数: {
  "query": "{ items { id name } }",
  "variables": {
    "itemId": __JS_EXPR_0__
  }
}
------------------------------------------------------------
类型: WebSocket, 请求: "WS wss://example.com/realtime"
请求参数: 无参数
------------------------------------------------------------

... (更多来源和请求)

## 分析网页: https://another-example.com
============================================================
...

# 提取操作已被用户中断。
# 提取过程中发生意外错误: ...
```

- 每个来源（外部 JS 文件 URL、内联脚本块）都以 --- 来源: ... --- 开头。
- 每个提取到的请求包含 类型、请求（方法和 URL）和 请求参数。
- 参数会尝试格式化，JavaScript 表达式会用 __JS_EXPR_X__ 占位符表示。
- 文件头部包含生成时间、工具版本和注意事项。
- 处理列表文件时，每个 URL 的分析结果会依次追加。
- 程序中断或发生错误时会在文件末尾添加提示信息。

![image](https://github.com/user-attachments/assets/9fbd2f5f-fd11-4566-aaf9-9a992eb4bb07)

## 📊 HTML 报告
使用 --report 选项可以生成一个交互式的 HTML 报告。报告包含：
- 报告标题和生成时间。
- 可搜索的目录，方便快速跳转到不同的来源（JS 文件或内联脚本）。
- 结构化的内容区域，按来源分组显示提取到的 API 请求列表。
- 每个请求显示序号、类型、方法、URL 和参数。
- 参数区域支持展开/折叠，方便查看详细内容。
- 支持返回顶部。
HTML 报告提供了一种更直观的方式来浏览和分析大量的提取结果。

![image](https://github.com/user-attachments/assets/6e39cd48-581d-4e7c-9039-9252115c5c13)

## 🙌 贡献
欢迎对本项目提出建议或贡献代码。如果您发现 Bug 或有改进想法，请提交 Issue 或 Pull Request。


