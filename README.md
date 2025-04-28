# JavaScript API 请求提取工具

这是一个用于从网页或 JavaScript 文件中提取潜在 HTTP API 请求（包括 RESTful, GraphQL, WebSocket）的 Python 工具。它可以分析单个 URL、本地文件或包含 URL 列表的文件，并将提取结果保存到文本文件，并可选择生成交互式 HTML 报告。

## 目录
✨ 功能特性  
⬇️ 安装  
🚀 使用方法  
📂 文件结构说明  
📄 输出格式  
📊 HTML 报告  
🙌 贡献  
⚖️ 许可证  

---

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
