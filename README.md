#JavaScript API 提取工具分析
这是一个用 Python 编写的工具，主要功能是从 JavaScript 代码中提取和分析 HTTP API 请求信息。无论是分析网页中的内联 JavaScript、外部 JavaScript 文件，还是直接处理本地 JavaScript 文件，都能提取出其中的 API 请求细节。
#项目结构
##项目采用模块化设计，分为几个主要组件：
###1、主模块 (main.py)：
  处理命令行参数
  根据不同参数调用相应的处理功能
  
###2、处理器模块（processors/）：
  file_processor.py - 处理本地 JS 文件
  url_processor.py - 处理网页和远程 JS 文件

###3、提取器模块（extractors/）：
  js_extractor.py - 负责从 JS 代码中提取 HTTP 请求

###4、格式化器模块（formatters/）：
  param_formatter.py - 处理和格式化 API 参数
  
###5、工具模块（utils/）：
  output_utils.py - 处理结果输出到文件

##核心功能
###1. API 请求提取
工具使用正则表达式识别各种类型的 API 请求：
  REST API 调用：如 axios.get(), $.ajax() 等
  GraphQL 请求：识别 GraphQL 查询和变量
  WebSocket 连接：识别 WebSocket 初始化
  通用 HTTP 请求：能够检测各种 HTTP 方法（GET, POST, PUT, DELETE, PATCH）

###2. 参数处理
工具会尝试提取请求参数并进行格式化：
  清理不合规的 JSON 字符串
  处理 JavaScript 表达式和变量
  格式化 JSON 参数使其易读

###3. API 分类
根据 URL 和上下文，工具能够自动判断 API 类型：
  RESTful API
  GraphQL
  WebSocket
  RPC
  通用 HTTP API

###4. 使用方式
工具支持多种输入方式：
  -u, --url           要分析的网页URL
  -eu, --extract-url  直接分析的JavaScript URL
  -l, --list          包含网页URL列表的文件
  -el, --extract-list 包含JavaScript URL列表的文件
  -f, --file          直接分析本地JavaScript文件
  -o, --output        指定输出文件名（默认为ok.txt）
____________________________________________________________
##技术亮点
  灵活的正则表达式匹配：使用多种模式匹配不同框架和库的 API 调用
  上下文分析：查找 API 调用周围的上下文来识别参数和方法
  智能参数提取：能处理多种参数格式和边缘情况
  API 自动分类：根据 URL 和上下文自动判断 API 类型
  
##使用场景
此工具适合以下场景：
  渗透测试前期信息收集：快速发现目标应用的 API 端点
  API 端点发现：帮助开发人员梳理项目中的 API 调用
  代码审计：审查 JavaScript 代码中的 API 使用

实际使用示例
bash# 分析单个网页
python main.py -u https://example.com

# 分析特定的 JavaScript 文件
python main.py -f path/to/script.js

# 批量分析多个网页
python main.py -l urls.txt

# 指定输出文件
python main.py -u https://example.com -o results.txt
