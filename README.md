# JavaScript API 提取工具
一个用于从 JavaScript 代码或网页中提取潜在 HTTP API 请求信息的 Python 脚本。支持分析本地 JS 文件、远程 JS URL、网页 URL，以及包含 URL 列表的文件，并可生成结构化、交互式的 HTML 报告。
# ✨ 功能特性
## 多源支持:
- 分析单个本地 JavaScript 文件 (.js)。
-- 分析单个远程 JavaScript 文件 URL。
分析单个网页 URL，自动提取页面中的外部和内联 JavaScript 进行分析。
批量分析包含网页 URL 或 JS URL 的列表文件。
API 类型识别: 尝试识别 RESTful, GraphQL 和 WebSocket 连接。
参数提取: 尝试提取与 API 请求相关的参数信息，包括 JSON 对象、数组、字符串字面量以及变量名。
智能参数处理: 对提取到的参数进行清理和格式化，使其更易读；尝试识别并恢复 JavaScript 表达式（如变量、函数调用）。
结果输出: 将提取到的 API 信息保存到结构化的文本文件中。
HTML 报告生成: 可选地生成一个美观、交互式的 HTML 报告，方便浏览和搜索提取结果。
彩色控制台输出: 提供清晰的彩色进度和结果提示信息。
🛠️ 安装
克隆仓库: (如果您的代码在一个仓库中)
git clone <仓库地址>
cd <仓库目录>

或者，如果您只有这些文件，请将所有 .py 文件放在同一个目录下。
安装依赖:
需要安装 requests 库用于网络请求，以及 beautifulsoup4 (推荐) 用于 HTML 解析。
pip install requests beautifulsoup4

如果您不想安装 beautifulsoup4，脚本将回退到使用正则表达式解析 HTML，但这可能不够健壮。
文件结构:
确保以下文件位于同一目录下：
.
├── main.py         # 主程序入口
├── processor.py    # 处理不同输入源
├── extractor.py    # API 提取核心逻辑
├── formatter.py    # 参数格式化
└── utils.py        # 实用工具 (文件操作, 颜色)


🚀 使用方法
通过命令行运行 main.py 脚本，并根据需要提供相应的参数。
python main.py [输入选项] [其他选项]


输入选项 (必需，且只能选择一个):
-u <PAGE_URL>, --url <PAGE_URL>: 分析单个网页 URL。
-eu <JS_URL>, --extract-url <JS_URL>: 直接分析单个 JS 文件 URL。
-l <PAGE_URL_FILE>, --list <PAGE_URL_FILE>: 分析包含网页 URL 列表的文件。
-el <JS_URL_FILE>, --extract-list <JS_URL_FILE>: 分析包含 JS URL 列表的文件。
-f <JS_FILE_PATH>, --file <JS_FILE_PATH>: 分析单个本地 JS 文件。
其他选项:
--report [HTML_PATH]: 生成 HTML 报告。
如果只使用 --report，报告将自动命名（基于输出文件名，后缀 .html）。
如果指定 [HTML_PATH]，报告将保存到该路径。
-v, --verbose: 启用详细日志记录 (DEBUG 级别)，输出更多处理细节到控制台和日志。
使用示例:
分析单个网页并生成 HTML 报告:
python main.py -u https://example.com/page --report


直接分析单个远程 JS 文件并指定报告路径:
python main.py -eu https://example.com/script.js --report my_report.html


分析本地 JS 文件 (不生成报告):
python main.py -f /path/to/local/script.js


批量分析网页 URL 列表文件:
python main.py -l page_urls.txt


批量分析 JS URL 列表文件并启用详细日志:
python main.py -el js_urls.txt -v


📊 输出
脚本会将提取到的详细 API 信息保存到文本文件中 (.txt)。默认文件名基于输入源自动生成，后缀为 _api_results.txt。
如果使用了 --report 参数，还将生成一个 HTML 文件 (.html)，提供更友好的可视化界面。
控制台输出格式:
控制台将输出带有颜色的关键进度和结果信息，格式如下：
--- 开始 API 提取 ---
提取结果将保存到: <提取结果文件路径>

🔎开始分析 <目标类型>: <目标源>
    👁️从 <来源名称> 发现 <数量> 个接口 (<带参数数量> 个带参数)
    # 如果有错误或警告，会在这里缩进显示，例如:
    ❌ 无效 JS URL: <无效URL>
    ⚠️ 页面中未找到 JS: <页面URL>

# ... (重复分析过程)

✅ 提取完成---开始生成 HTML 报告... # 如果生成报告

--- 处理完成 ---
  🎮提取结果: <提取结果文件路径>
  🎁HTML报告: <HTML报告文件路径> # 如果成功生成报告
  # 如果报告生成失败或跳过，也会在这里显示相应的提示


📄 文件说明
main.py: 脚本的入口点，负责解析命令行参数，调用 processor 处理输入，以及调用 bg 生成报告。
processor.py: 处理不同类型的输入 (URL, 文件, 列表)，协调内容的获取和提取，并调用 extractor 和 formatter。
extractor.py: 包含从 JavaScript 代码中识别和提取 API 请求的核心逻辑。
formatter.py: 负责清理、验证和格式化提取到的参数字符串。
utils.py: 提供一些通用的实用函数，如文件写入、创建文件头以及控制台颜色控制。

![image](https://github.com/user-attachments/assets/cb79fad4-90b6-4cdc-9d55-d4bed065c84f)

