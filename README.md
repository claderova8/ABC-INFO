# JavaScript API 提取工具分析

这是一个用 Python 编写的工具，主要功能是从 JavaScript 代码中提取和分析 HTTP API 请求信息。无论是分析网页中的内联 JavaScript、外部 JavaScript 文件，还是直接处理本地 JavaScript 文件，都能提取出其中的 API 请求细节。

## 项目结构

该工具采用模块化设计，主要组件包括：

1. **主模块 (`main.py`)**  
   负责处理命令行参数，根据不同参数调用相应的处理功能。

2. **处理器模块 (`processors/`)**  
   - `file_processor.py`：处理本地 JavaScript 文件。  
   - `url_processor.py`：处理网页和远程 JavaScript 文件。

3. **提取器模块 (`extractors/`)**  
   - `js_extractor.py`：负责从 JavaScript 代码中提取 HTTP 请求。

4. **格式化器模块 (`formatters/`)**  
   - `param_formatter.py`：处理和格式化 API 参数。

5. **工具模块 (`utils/`)**  
   - `output_utils.py`：处理结果输出到文件。

## 核心功能

### 1. API 请求提取

工具使用正则表达式等方法，从 JavaScript 代码中识别并提取各类 HTTP API 请求：

- **REST API 调用**：检测 `axios.get()`、`$.ajax()` 等常见库调用  
- **GraphQL 请求**：识别带有 `query` 或 `mutation` 的 GraphQL 查询及变量  
- **WebSocket 连接**：提取 `new WebSocket(url)` 或 `WebSocket.open()` 初始化调用  
- **通用 HTTP 请求**：支持原生 `fetch()`、`XMLHttpRequest` 和其他 HTTP 方法（GET/POST/PUT/DELETE/PATCH）  

### 2. 参数处理

对提取到的请求参数进行解析与格式化：

- **JSON 清理**：修复不合规或缺少引号的 JSON 字符串  
- **表达式解析**：替换或评估简单的 JavaScript 变量、模板字符串等  
- **格式化输出**：统一缩进和排序，使参数结构清晰可读  

### 3. API 分类

根据 URL 特征和调用上下文，对提取到的 API 进行自动分类：

- **RESTful API**：基于 URL 路径和 HTTP 方法判定  
- **GraphQL**：通过关键词（`query`, `mutation`）及请求体结构识别  
- **WebSocket**：根据使用的协议和构造函数区分  
- **RPC**：检测 JSON-RPC、XML-RPC 等远程调用格式  
- **通用 HTTP API**：无法归类时，作为通用 HTTP 请求处理  


### 4. 使用方式

工具支持多种输入方式：

- `-u`, `--url`：要分析的网页URL
- `-eu`, `--extract-url`：直接分析的JavaScript URL
- `-l`, `--list`：包含网页URL列表的文件
- `-el`, `--extract-list`：包含JavaScript URL列表的文件
- `-f`, `--file`：直接分析本地JavaScript文件
- `-o`, `--output`：指定输出文件名（默认为ok.txt）

### 5.示例

```bash
# 分析特定的 JavaScript 文件
python main.py -f path/to/script.js

# 批量分析多个网页
python main.py -l urls.txt

# 指定输出文件
python main.py -u https://example.com -o results.txt

```

## 技术亮点

- **灵活的正则表达式匹配**  
  使用多种模式匹配不同框架和库的 API 调用

- **上下文分析**  
  查找 API 调用周围的上下文来识别参数和方法

- **智能参数提取**  
  能够处理多种参数格式和边缘情况

- **API 自动分类**  
  根据 URL 和上下文自动判断 API 类型

## 使用场景

此工具适合以下场景：

- **渗透测试前期信息收集**  
  快速发现目标应用的 API 端点

- **API 端点发现**  
  帮助开发人员梳理项目中的 API 调用

- **代码审计**  
  审查 JavaScript 代码中的 API 使用

  ![image](https://github.com/user-attachments/assets/cb79fad4-90b6-4cdc-9d55-d4bed065c84f)

