# JavaScript API 提取工具分析

这是一个用 Python 编写的工具，旨在从 JavaScript 代码中提取和分析 HTTP API 请求信息。无论是分析网页中的内联 JavaScript、外部 JavaScript 文件，还是直接处理本地 JavaScript 文件，该工具均可提取其中的 API 请求细节。&#8203;:contentReference[oaicite:1]{index=1}

## 项目结构

:contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3}

### 1. 主模块 (`main.py`)

- :contentReference[oaicite:4]{index=4}
- :contentReference[oaicite:5]{index=5}&#8203;:contentReference[oaicite:6]{index=6}

### 2. 处理器模块 (`processors/`)

- `file_processor.py`：&#8203;:contentReference[oaicite:7]{index=7}
- `url_processor.py`：&#8203;:contentReference[oaicite:8]{index=8}&#8203;:contentReference[oaicite:9]{index=9}

### 3. 提取器模块 (`extractors/`)

- `js_extractor.py`：&#8203;:contentReference[oaicite:10]{index=10}&#8203;:contentReference[oaicite:11]{index=11}

### 4. 格式化器模块 (`formatters/`)

- `param_formatter.py`：&#8203;:contentReference[oaicite:12]{index=12}&#8203;:contentReference[oaicite:13]{index=13}

### 5. 工具模块 (`utils/`)

- `output_utils.py`：&#8203;:contentReference[oaicite:14]{index=14}&#8203;:contentReference[oaicite:15]{index=15}

## 核心功能

### 1. API 请求提取

:contentReference[oaicite:16]{index=16}&#8203;:contentReference[oaicite:17]{index=17}

- **REST API 调用**：&#8203;:contentReference[oaicite:18]{index=18}
- **GraphQL 请求**：&#8203;:contentReference[oaicite:19]{index=19}
- **WebSocket 连接**：&#8203;:contentReference[oaicite:20]{index=20}
- **通用 HTTP 请求**：&#8203;:contentReference[oaicite:21]{index=21}&#8203;:contentReference[oaicite:22]{index=22}

### 2. 参数处理

:contentReference[oaicite:23]{index=23}&#8203;:contentReference[oaicite:24]{index=24}

- :contentReference[oaicite:25]{index=25}
- :contentReference[oaicite:26]{index=26}
- :contentReference[oaicite:27]{index=27}&#8203;:contentReference[oaicite:28]{index=28}

### 3. API 分类

:contentReference[oaicite:29]{index=29}&#8203;:contentReference[oaicite:30]{index=30}

- :contentReference[oaicite:31]{index=31}
- :contentReference[oaicite:32]{index=32}
- :contentReference[oaicite:33]{index=33}
- RPC
- :contentReference[oaicite:34]{index=34}&#8203;:contentReference[oaicite:35]{index=35}

### 4. 使用方式

工具支持多种输入方式：

- `-u`, `--url`：&#8203;:contentReference[oaicite:36]{index=36}
- `-eu`, `--extract-url`：&#8203;:contentReference[oaicite:37]{index=37}
- `-l`, `--list`：&#8203;:contentReference[oaicite:38]{index=38}
- `-el`, `--extract-list`：&#8203;:contentReference[oaicite:39]{index=39}
- `-f`, `--file`：&#8203;:contentReference[oaicite:40]{index=40}
- `-o`, `--output`：&#8203;:contentReference[oaicite:41]{index=41}&#8203;:contentReference[oaicite:42]{index=42}

### 5.示例

```bash
# 分析特定的 JavaScript 文件
python main.py -f path/to/script.js

# 批量分析多个网页
python main.py -l urls.txt

# 指定输出文件
python main.py -u https://example.com -o results.txt
