# -*- coding: utf-8 -*-
"""
JavaScript 内容中 API 请求的核心提取逻辑。
旨在识别 RESTful, GraphQL, 和 WebSocket 端点。
"""

import re
import json
import logging
from typing import List, Dict, Any, Set, Tuple, Optional

# --- 配置日志 ---
log = logging.getLogger(__name__)

# --- 模块导入 ---
try:
    # 导入本项目依赖的 formatter 模块，用于参数的格式化和清理
    import formatter
except ImportError as e:
    # 如果导入失败，记录严重错误并重新抛出异常，终止程序运行
    log.critical(f"无法导入 extractor 依赖的模块 (formatter): {e}", exc_info=True)
    raise # 重新抛出异常

# --- 常量定义 ---
# 参数搜索窗口：在找到请求匹配位置后，向前和向后搜索参数的字符数范围
PARAM_SEARCH_WINDOW_BEFORE = 500 # 扩大向前搜索窗口，以便有更大机会找到变量赋值
PARAM_SEARCH_WINDOW_AFTER = 800  # 扩大向后搜索窗口，以覆盖更多参数位置
# 参数匹配距离惩罚：对请求位置之前的参数匹配增加的距离值，降低其优先级
# 这是因为参数通常出现在请求调用之后
PARAM_DISTANCE_PENALTY_BEFORE = 200 # 增加惩罚值
# 参数字符串最大长度限制：防止匹配过大的、不太可能是参数的内容，例如整个文件剩余部分
MAX_PARAM_STRING_LENGTH = 5000 # 稍微放宽限制，但仍需限制以避免性能问题和错误匹配
# 常见的非 API 文件扩展名元组，用于过滤 URL，避免将静态资源误判为 API
NON_API_EXTENSIONS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
                      '.html', '.htm', '.woff', '.woff2', '.ttf', '.eot',
                      '.map', '.json', '.xml', '.txt', '.ico', '.wasm') # 添加 .wasm
# API 相关关键词模式，用于辅助判断相对路径是否为 API 调用
API_KEYWORDS_PATTERN = re.compile(r'api|v\d+|fetch|xhr|ajax|http|request|send|load|save|update|delete|query|mutation|rpc|graphql', re.IGNORECASE) # 添加 xhr, send
# 常见动态脚本后缀，用于辅助判断相对路径
DYNAMIC_SCRIPT_EXTENSIONS = ('.php', '.asp', '.jsp', '.do', '.action', '.cgi', '.pl') # 添加 cgi, pl

# 常见的参数包装键，例如 `{ data: {...} }` 或 `{ params: {...} }`
PARAM_WRAPPER_KEYS = ['params', 'data', 'json', 'body', 'variables', 'args', 'payload'] # 添加 args, payload

# --- 预编译正则表达式 ---

# WebSocket URL 模式：匹配 `new WebSocket(...)` 或 `new WebSocket(` 后面的 URL
WEBSOCKET_PATTERN = re.compile(
    r'new\s+WebSocket\s*\(\s*[\'"`](?P<url>(?:ws|wss)://[^\'"`]+)[\'"`]\s*\)',
    re.IGNORECASE
)

# GraphQL 端点模式
# 1. 匹配 fetch/axios/ajax/http/request 后跟 GraphQL URL 和 method: 'POST'
GRAPHQL_POST_PATTERN = re.compile(
    r'(?:fetch|axios|ajax|http|request)\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]\s*,'
    r'\s*\{[^}]*(?:method|type)\s*:\s*[\'"`]POST[\'"`]',
    re.IGNORECASE | re.DOTALL
)
# 2. 匹配 axios/http/request/ajax 的 .post 方法后跟 GraphQL URL
GRAPHQL_METHOD_POST_PATTERN = re.compile(
    r'(?:axios|http|request|ajax)\.post\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
# 3. 匹配任意引号包围的包含 '/graphql' 的 URL (作为通用 GraphQL 端点，可能需要进一步判断方法)
GRAPHQL_GENERIC_URL_PATTERN = re.compile(
    r'[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
# 将 GraphQL POST 模式组合
GQL_POST_PATTERNS = [GRAPHQL_POST_PATTERN, GRAPHQL_METHOD_POST_PATTERN]

# RESTful API 模式
# 匹配常见的 HTTP 客户端库方法调用 (axios, http, request, ajax, $)
REST_URL_METHOD_PATTERNS = [
    # axios/http/request/ajax 的 .method(url, ...) 形式
    re.compile(r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # axios({ url: ..., method: ... }) 形式
    re.compile(
        r'axios\s*\(\s*\{[^}]*' # 匹配 axios({
        r'(?:url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method1>\w+)[\'"`]' # url在前，method在后
        r'|method\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`])' # method在前，url在后
        r'[^}]*\}\s*\)', # 匹配 })
        re.IGNORECASE | re.DOTALL
    ),
    # fetch(url, { method: ... }) 形式
    re.compile(r'fetch\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]\s*,\s*\{[^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    # $.ajax({ url: ..., type/method: ... }) 形式
    re.compile(
        r'\$\.ajax\s*\(\s*\{[^}]*' # 匹配 $.ajax({
        r'(?:url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*(?:type|method)\s*:\s*[\'"`](?P<method1>\w+)[\'"`]' # url在前，type/method在后
        r'|(?:type|method)\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`])' # type/method在前，url在后
        r'[^}]*\}\s*\)', # 匹配 })
        re.IGNORECASE | re.DOTALL
    ),
    # $.get(url, ...) 或 $.post(url, ...) 形式
    re.compile(r'\$\.(?P<method>get|post)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # 更通用的 method(url, ...) 形式，匹配任意对象或变量后跟 .method 调用
    re.compile(r'(?:[a-zA-Z0-9_$]{2,}\.)(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # XMLHttpRequest 的 open 方法 (method, url)
    re.compile(r'(?:new\s+XMLHttpRequest\s*\(\s*\)|[a-zA-Z_$][a-zA-Z0-9_$]*)\.open\s*\(\s*[\'"`](?P<method>\w+)[\'"`]\s*,\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
]

# 参数模式 - 按优先级分组
PARAM_PATTERNS = [
    # 组 1: 高优先级 - 在特定键 (data, params 等) 后直接跟着对象 {} 或数组 [] 字面量
    re.compile(r'(?:data|params|body|json|query|variables|args|payload)\s*:\s*(?P<param_value>\{.*?\})', re.IGNORECASE | re.DOTALL | re.MULTILINE),
    re.compile(r'(?:data|params|body|json|query|variables|args|payload)\s*:\s*(?P<param_value>\[.*?\])', re.IGNORECASE | re.DOTALL | re.MULTILINE),

    # 组 2: 中优先级 - 在函数调用参数中直接跟着对象 {} 或数组 [] 字面量，或在 JSON.stringify() 中
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(?P<param_value>\{.*?\})', re.DOTALL | re.MULTILINE), # 函数调用的第二个参数 (对象)
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(?P<param_value>\[.*?\])', re.DOTALL | re.MULTILINE), # 函数调用的第二个参数 (数组)
    re.compile(r'JSON\.stringify\s*\(\s*(?P<param_value>\{.*?\})\s*\)', re.IGNORECASE | re.DOTALL), # JSON.stringify 对象
    re.compile(r'JSON\.stringify\s*\(\s*(?P<param_value>\[.*?\])\s*\)', re.IGNORECASE | re.DOTALL), # JSON.stringify 数组

    # 组 3: 低优先级 - 在特定键后跟着变量名或属性访问链 (不是函数调用)
    # 确保变量名后不是 '('，排除函数调用
    re.compile(r'(?:data|params|body|json|query|variables|args|payload)\s*:\s*(?P<param_value>[a-zA-Z_$][a-zA-Z0-9_$.]*)\s*(?!\s*\()', re.IGNORECASE),
    # 在函数调用参数中跟着变量名或属性访问链 (不是函数调用)
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(?P<param_value>[a-zA-Z_$][a-zA-Z0-9_$.]*)\s*(?!\s*\()'),

    # 组 4: 最低优先级 - 在特定键后跟着字符串字面量
    re.compile(r'(?:data|params|body|json|query|variables|args|payload)\s*:\s*(?P<param_value>[\'"`].*?[\'"`])', re.IGNORECASE | re.DOTALL | re.MULTILINE),
    # 在 JSON.stringify() 中跟着字符串字面量
    re.compile(r'JSON\.stringify\s*\(\s*(?P<param_value>[\'"`].*?[\'"`])\s*\)', re.IGNORECASE | re.DOTALL),
]

# 简单的相对 URL 模式 (推断为 GET 方法) - 使用后向否定断言排除特定后缀
# 匹配以 '/' 开头 (但不是 '//') 的相对路径，后跟可选的查询参数和片段
# 并且路径部分不以常见的非 API 文件扩展名结尾
try:
    # 构建非 API 扩展名的正则表达式部分，用于排除
    _non_api_ext_pattern = '|'.join(re.escape(ext[1:]) for ext in NON_API_EXTENSIONS)
    SIMPLE_RELATIVE_URL_PATTERN = re.compile(
         r'[\'"`]'                                   # 起始引号 (单引号, 双引号, 反引号)
         r'(?P<url>/(?!/)'                          # 必须以 '/' 开头，但不匹配 '//' (协议相对 URL)
         r'[^\'"\s?#]+'                             # 路径部分 (一个或多个非引号、空白、问号、井号字符)
         r'(?:\?[^\'"\s#]*)?'                       # 可选的查询参数部分 (?...)
         r'(?:#[^\'"\s]*)?'                         # 可选的片段标识符部分 (#...)
         r')'                                       # 结束 URL 捕获组
         # 后向否定断言：确保捕获的 URL 部分不以 .ext + 结束字符 (引号, 空白, ?, #) 结尾
         # 使用 re.escape 确保扩展名中的点号被正确转义
         r'(?!\.(?:' + _non_api_ext_pattern + r')[\'"\s?#])'
         r'[\'"`]'                                   # 结束引号
    )
except re.error as compile_err:
    log.critical(f"Failed to compile SIMPLE_RELATIVE_URL_PATTERN regex: {compile_err}", exc_info=True)
    # 如果编译失败，定义一个永远不会匹配的模式作为备用，防止程序崩溃
    SIMPLE_RELATIVE_URL_PATTERN = re.compile(r'(?!x)x') # 匹配任何内容都失败
except Exception as e:
    log.critical(f"Unexpected error while defining SIMPLE_RELATIVE_URL_PATTERN: {e}", exc_info=True)
    SIMPLE_RELATIVE_URL_PATTERN = re.compile(r'(?!x)x')

# 验证是否是有效的 JS 变量名或属性访问链
VALID_JS_VARIABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_$][a-zA-Z0-9_$.]*$')

# 匹配变量赋值语句 (简单的形式: var/let/const 或直接赋值)
# 捕获变量名和赋给它的值。改进模式以更好地匹配对象/数组/字符串等值。
ASSIGNMENT_PATTERN = re.compile(
    r'(?:var|let|const)\s+(?P<var_name>[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?P<assigned_value>\{.*?\}(?:[^;]*?\{.*?\})*|\[.*?\](?:[^;]*?\[.*?\])*|[\'"`].*?[\'"`]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*;?',
    re.DOTALL | re.MULTILINE
)
# 匹配直接赋值 (没有 var/let/const)
DIRECT_ASSIGNMENT_PATTERN = re.compile(
    r'(?P<var_name>[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?P<assigned_value>\{.*?\}(?:[^;]*?\{.*?\})*|\[.*?\](?:[^;]*?\[.*?\])*|[\'"`].*?[\'"`]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*;?',
    re.DOTALL | re.MULTILINE
)
# 将两种赋值模式组合
ASSIGNMENT_PATTERNS = [ASSIGNMENT_PATTERN, DIRECT_ASSIGNMENT_PATTERN]


# --- 辅助函数 ---

def _is_likely_api_url(url: str) -> bool:
    """
    更精细地判断一个 URL 字符串是否可能是 API 调用，而不是静态资源或外部链接。

    Args:
        url: 要检查的 URL 字符串。

    Returns:
        如果 URL 可能是 API 调用，返回 True，否则返回 False。
    """
    if not url or not isinstance(url, str): return False
    url = url.strip()
    if not url or url == '/' or url == '#': return False # 排除空URL, 根路径, 片段标识符
    # 排除 data URIs 和 javascript: 伪协议
    if url.startswith(('data:', 'javascript:')):
        log.debug(f"URL '{url[:100]}...' filtered as it is a data/javascript URI.")
        return False
    # 协议相对 URL (//...) 可以是 API，允许它们
    if url.startswith('//'):
        pass # 允许

    # 检查是否看起来像模块导入路径 (例如 './', '../') - 相对路径
    # 如果路径以 '.' 开头但不以 '/' 开头 (排除绝对路径 '/...'), 并且不包含 API 关键词
    if re.match(r'^\.?\.?/', url) and not url.startswith('/') and not API_KEYWORDS_PATTERN.search(url):
        # 如果路径的最后一部分包含点号，且不是动态脚本后缀，且 URL 不以 '/' 结尾，则很可能是文件引用
        filename = url.split('/')[-1]
        if '.' in filename and not filename.endswith(DYNAMIC_SCRIPT_EXTENSIONS) and not url.endswith('/'):
            log.debug(f"URL '{url[:100]}...' filtered as it looks like a module import or local file reference (no API keywords).")
            return False

    # 提取路径部分并转为小写进行扩展名检查
    try:
        path_part = url.split('?')[0].split('#')[0].lower()
    except Exception: # 处理可能的分割错误
        path_part = url.lower()

    # 排除以常见静态文件扩展名结尾的 URL
    if path_part.endswith(NON_API_EXTENSIONS):
        log.debug(f"URL '{url[:100]}...' filtered as it ends with a non-API file extension.")
        return False

    # 通过所有检查，认为是 API URL
    return True

def _parse_named_groups(match: re.Match) -> Tuple[Optional[str], Optional[str]]:
    """
    安全地从 re.Match 对象中提取 'method' 和 'url' 命名捕获组的值。
    处理不同模式中可能使用不同组名 ('method', 'method1', 'method2', 'url', 'url1', 'url2') 的情况。

    Args:
        match: 正则表达式匹配对象。

    Returns:
        一个元组：(方法名大写字符串, URL 字符串) 或 (None, None) 如果提取失败。
    """
    if not match: # 如果 match 对象为 None
        log.warning("Attempted to extract named groups from None Match object.")
        return None, None
    try:
        group_dict = match.groupdict() # 获取所有命名捕获组的字典
        # 尝试从不同的命名组中获取方法名和 URL
        method = group_dict.get('method') or group_dict.get('method1') or group_dict.get('method2')
        url = group_dict.get('url') or group_dict.get('url1') or group_dict.get('url2')
        # 返回方法名的大写形式 (如果存在) 和去除首尾空白的 URL (如果存在)
        return method.upper() if method else None, url.strip() if url else None
    except Exception as e: # 捕获其他意外错误
        log.error(f"提取命名组时发生错误: {e}", exc_info=True)
        return None, None

def _normalize_param_for_deduplication(param_repr: Optional[str]) -> Any:
    """
    尝试将参数字符串规范化为可哈希的表示形式，用于去重。
    优先尝试解析为 JSON 并生成规范化的字符串，否则使用原始字符串。
    处理 JS 变量名和简单的原始值。

    Args:
        param_repr: 原始参数字符串。

    Returns:
        参数的可哈希表示形式 (通常是规范化的 JSON 字符串、原始字符串或变量名)。
    """
    if not param_repr or not isinstance(param_repr, str):
        return param_repr # 不是字符串或为空，直接返回

    cleaned_param = param_repr.strip()
    # 如果是有效的 JS 变量名，直接使用变量名作为键
    if VALID_JS_VARIABLE_NAME_PATTERN.match(cleaned_param):
        return cleaned_param # 变量名本身作为去重键

    # 尝试进行基本的 JSON 清理，以便尝试解析
    # 注意：这里的清理是为解析做准备，可能会修改字符串
    # 使用 formatter 模块的清理函数
    cleaned_for_json, _ = formatter.clean_and_validate_json(cleaned_param)

    if not cleaned_for_json:
        # 如果清理后为空，使用原始清理后的字符串
        return cleaned_param

    try:
        # 只有当清理后的字符串看起来像 JSON 对象或数组时才尝试解析
        if (cleaned_for_json.startswith('{') and cleaned_for_json.endswith('}')) or \
           (cleaned_for_json.startswith('[') and cleaned_for_json.endswith(']')):
            # 尝试解析为 JSON
            parsed_param = json.loads(cleaned_for_json)
            # 返回排序键、无空白的 JSON 字符串作为规范化表示
            return json.dumps(parsed_param, sort_keys=True, separators=(',', ':'))
        else:
            # 如果不像 JSON 对象或数组 (如简单字符串字面量)，使用清理后的字符串
            return cleaned_for_json
    except (json.JSONDecodeError, TypeError):
        # JSON 解析失败，使用清理后的原始字符串作为去重键
        log.debug(f"Parameter could not be parsed as JSON, will use cleaned string for deduplication: {cleaned_for_json[:100]}...")
        return cleaned_for_json
    except Exception as e:
         # 其他未知错误，使用原始字符串作为去重键
         log.warning(f"Unknown error during parameter normalization: {e}. Parameter: {param_repr[:100]}...")
         return param_repr # 发生错误时使用原始字符串

# --- 提取函数 ---

def extract_requests(js_content: str) -> List[Dict[str, Any]]:
    """
    从 JavaScript 源代码字符串中提取潜在的 API 请求信息。
    流程：
    1. 使用预编译的正则表达式查找 WebSocket, GraphQL, RESTful, 简单相对 URL 匹配。
    2. 记录初步匹配结果及其在源代码中的位置。
    3. 对初步匹配结果按位置排序。
    4. 遍历排序后的匹配结果，在请求位置附近的窗口内搜索参数。
    5. 对找到的参数进行优先级排序 (字面量 > 变量 > 字符串)。
    6. 如果找到的是变量名，向后搜索其赋值，尝试提取实际值。
    7. 将提取到的请求和参数添加到最终结果列表。
    8. 对最终结果列表进行去重 (基于类型、方法、URL 和规范化后的参数)。

    Args:
        js_content: JavaScript 源代码字符串。

    Returns:
        一个字典列表，包含提取到的去重后的请求信息 [{'type', 'method', 'url', 'params'}, ...]。
    """
    match_positions: List[Dict[str, Any]] = [] # 存储初步匹配结果和位置
    # 初步去重签名集合 (类型, 方法, URL)，用于避免重复添加相同的请求 URL
    found_signatures: Set[Tuple[str, str, str]] = set()

    log.debug("Starting API request extraction...")

    # --- 步骤 1: 提取 WebSocket 连接 ---
    log.debug("Step 1: Extracting WebSocket connections...")
    try:
        for match in WEBSOCKET_PATTERN.finditer(js_content):
            url = match.group('url').strip()
            if not url: continue
            # 签名用于初步去重
            signature = ('WebSocket', 'WS', url)
            if signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'WebSocket', 'method': 'WS', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
                log.debug(f"  Found WebSocket: {url}")
    except re.error as e:
        log.warning(f"Regex error while extracting WebSocket: {e}")
    except Exception as e:
        log.error(f"Unexpected error while extracting WebSocket: {e}", exc_info=True)


    # --- 步骤 2: 提取 GraphQL POST 请求 ---
    log.debug("Step 2: Extracting GraphQL POST requests...")
    for pattern in GQL_POST_PATTERNS:
        try:
            for match in pattern.finditer(js_content):
                url = match.group('url').strip()
                if not url: continue
                signature = ('GraphQL', 'POST', url)
                if signature not in found_signatures:
                    found_signatures.add(signature)
                    match_positions.append({
                        'type': 'GraphQL', 'method': 'POST', 'url': url,
                        'match_start': match.start(), 'match_end': match.end()
                    })
                    log.debug(f"  Found GraphQL POST: {url}")
        except re.error as e:
            log.warning(f"Regex error while extracting GraphQL POST (Pattern: {pattern.pattern}): {e}")
        except IndexError:
            log.debug(f"Caught IndexError while processing GraphQL POST pattern: {pattern.pattern}")
        except Exception as e:
            log.error(f"Unexpected error while extracting GraphQL POST (Pattern: {pattern.pattern}): {e}", exc_info=True)

    # --- 步骤 3: 提取通用 GraphQL URL (推断为 POST) ---
    log.debug("Step 3: Extracting generic GraphQL URLs (inferred POST)...")
    try:
        for match in GRAPHQL_GENERIC_URL_PATTERN.finditer(js_content):
            url = match.group('url').strip()
            if not url: continue
            signature_post = ('GraphQL', 'POST', url)
            # 检查是否已经找到了相同 URL 的 GraphQL 或 WebSocket 请求
            is_duplicate = any(s[2] == url and s[0] in ['GraphQL', 'WebSocket'] for s in found_signatures)
            if not is_duplicate:
                found_signatures.add(signature_post)
                match_positions.append({
                    'type': 'GraphQL', 'method': 'POST', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
                log.debug(f"  Found generic GraphQL URL (inferred POST): {url}")
    except re.error as e:
         log.warning(f"Regex error while extracting generic GraphQL URL: {e}")
    except Exception as e:
        log.error(f"Unexpected error while extracting generic GraphQL URL: {e}", exc_info=True)


    # --- 步骤 4: 提取 RESTful 请求 ---
    log.debug("Step 4: Extracting RESTful requests...")
    for pattern in REST_URL_METHOD_PATTERNS:
        try:
            for match in pattern.finditer(js_content):
                method, url = _parse_named_groups(match)
                # 进一步验证 URL 的有效性
                if not method or not url or not _is_likely_api_url(url):
                    continue
                # 避免将已经被识别为 GQL/WS 的 URL 误判为 RESTful
                is_duplicate = any(pos['url'] == url and pos['type'] in ['GraphQL', 'WebSocket'] for pos in match_positions)
                if is_duplicate:
                    continue
                signature = ('RESTful', method, url)
                if signature not in found_signatures:
                    found_signatures.add(signature)
                    match_positions.append({
                        'type': 'RESTful', 'method': method, 'url': url,
                        'match_start': match.start(), 'match_end': match.end()
                    })
                    log.debug(f"  Found RESTful: {method} {url}")
        except re.error as e:
            log.warning(f"Regex error while extracting RESTful requests (Pattern: {pattern.pattern}): {e}")
        except IndexError:
             log.debug(f"Caught IndexError while processing RESTful pattern: {pattern.pattern}")
        except Exception as e:
            log.error(f"Unexpected error while extracting RESTful requests (Pattern: {pattern.pattern}): {e}", exc_info=True)


    # --- 步骤 5: 提取简单的相对 URL (推断为 GET) ---
    log.debug("Step 5: Extracting simple relative URLs (inferred GET)...")
    try:
        for match in SIMPLE_RELATIVE_URL_PATTERN.finditer(js_content):
            url = match.group('url').strip()
            # 严格使用 _is_likely_api_url 再次验证
            if not url or not _is_likely_api_url(url):
                continue
            # 避免添加已经识别过的 URL (任何类型)
            if any(pos['url'] == url for pos in match_positions):
                 continue
            method = "GET" # 推断为 GET 方法
            signature = ('RESTful', method, url)
            if signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'RESTful', 'method': method, 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
                log.debug(f"  Found simple relative URL (inferred GET): {url}")
    except re.error as e:
        log.warning(f"Regex error while extracting simple relative URLs: {e}")
    except Exception as e:
        log.error(f"Unexpected error while extracting simple relative URLs: {e}", exc_info=True)


    # --- 排序和参数查找 ---
    log.debug(f"Found {len(match_positions)} potential requests, starting sorting and parameter finding...")
    # 按匹配的起始位置对所有初步结果进行排序
    match_positions.sort(key=lambda x: x['match_start'])

    # 合并具有相同 URL 的请求，优先保留信息更完整的匹配 (例如，显式方法优于推断方法)
    # 使用字典来辅助合并，键为 URL
    merged_matches: Dict[str, Dict[str, Any]] = {}
    for res in match_positions:
        key = res['url']
        if key not in merged_matches:
            merged_matches[key] = res
        else:
            # 优先级判断：
            # 1. 非推断类型 (GraphQL, WebSocket) 优先于 推断类型 (RESTful 推断)
            if res['type'] != 'RESTful (推断)' and merged_matches[key]['type'] == 'RESTful (推断)':
                 merged_matches[key] = res
            # 2. 如果类型相同，显式方法 (GET, POST等) 优先于 推断方法 (GET 推断)
            elif res['type'] == merged_matches[key]['type'] and res['method'] != 'GET (推断)' and merged_matches[key]['method'] == 'GET (推断)':
                 merged_matches[key] = res
            # 3. 其他情况保持原有的 (先遇到的) 匹配

    # 将合并后的结果再次按原始匹配位置排序，以便按顺序查找参数
    sorted_merged_matches = sorted(merged_matches.values(), key=lambda x: x['match_start'])
    log.debug(f"After merging, {len(sorted_merged_matches)} requests remaining for parameter finding.")


    final_results_list: List[Dict[str, Any]] = [] # 存储最终提取结果
    # processed_indices: Set[int] = set() # 跟踪已处理的索引 (在 sorted_merged_matches 中) - 此处似乎不再需要显式跟踪，因为我们遍历并处理每个请求

    # 遍历排序后的请求匹配，查找参数
    for i, res in enumerate(sorted_merged_matches):
        # if i in processed_indices: continue # 如果需要跳过已处理的索引，则取消注释

        params: Optional[str] = None # 初始化参数为 None
        # 只为 RESTful 和 GraphQL 请求查找参数
        if res['type'] in ['RESTful', 'GraphQL']:
            log.debug(f"Looking for parameters for request {res['method']} {res['url'][:100]}... (Position {res['match_start']})...")
            best_param_match_str: Optional[str] = None # 存储找到的最佳参数字符串
            min_distance = float('inf') # 存储最佳参数匹配的最小优先级距离

            # --- 定义参数搜索的上下文窗口 ---
            search_start = max(0, res['match_start'] - PARAM_SEARCH_WINDOW_BEFORE) # 搜索起始位置 (向前)
            # 找到下一个相关的请求 (RESTful 或 GraphQL) 的起始位置，作为当前请求参数搜索窗口的上限
            next_relevant_match_start = float('inf')
            for j in range(i + 1, len(sorted_merged_matches)):
                # 只考虑 RESTful 和 GraphQL 作为下一个相关的请求
                if sorted_merged_matches[j]['type'] in ['RESTful', 'GraphQL']:
                    next_relevant_match_start = sorted_merged_matches[j]['match_start']
                    break
            # 确定最终的搜索结束位置：当前匹配结束位置 + 向后窗口，但不超过下一个相关请求的起始位置
            search_end = min(len(js_content), res['match_end'] + PARAM_SEARCH_WINDOW_AFTER, next_relevant_match_start)
            # 提取上下文代码片段
            context = js_content[search_start:search_end]
            # 计算请求在上下文中的相对起始位置
            match_relative_start = res['match_start'] - search_start
            log.debug(f"  Search window: {search_start}-{search_end} (Context length: {len(context)})")
            log.debug(f"  Request relative position within context: {match_relative_start}")

            # --- 遍历参数模式，在上下文内查找匹配 ---
            # 存储找到的潜在参数详情列表：(优先级距离, 参数字符串, 在上下文中的起始位置, 在上下文中的结束位置, 使用的模式索引)
            found_param_details = []
            for p_idx, pattern in enumerate(PARAM_PATTERNS):
                try:
                    # 使用 finditer 查找所有匹配，并使用 group('param_value') 获取命名捕获组的值
                    for param_match in pattern.finditer(context):
                        potential_param = param_match.group('param_value')

                        # 计算距离：参数值在上下文中的起始位置与请求在上下文中的起始位置之间的绝对距离
                        param_start_in_context = param_match.start('param_value')
                        distance = abs(param_start_in_context - match_relative_start)
                        # 计算优先级距离：对请求位置之前的参数匹配增加惩罚值
                        priority_distance = distance if param_start_in_context >= match_relative_start else distance + PARAM_DISTANCE_PENALTY_BEFORE

                        # 检查潜在参数是否有效且非空
                        if potential_param and potential_param.strip():
                            potential_param_strip = potential_param.strip()
                            # 基本验证：确保它看起来像一个对象、数组、字符串或有效的变量名，并检查长度限制
                            is_obj_arr = potential_param_strip.startswith(('{', '[')) and potential_param_strip.endswith(('}', ']'))
                            is_str = potential_param_strip.startswith(('"', "'", "`")) and potential_param_strip.endswith(('"', "'", "`"))
                            is_var = VALID_JS_VARIABLE_NAME_PATTERN.match(potential_param_strip) is not None
                            # 允许简单的原始值 (true, false, null, 数字)
                            is_simple_value = re.fullmatch(r'true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', potential_param_strip, re.IGNORECASE) is not None

                            if (is_obj_arr or is_str or is_var or is_simple_value) and len(potential_param_strip) < MAX_PARAM_STRING_LENGTH:
                                # 如果通过基本验证，添加到潜在参数详情列表
                                found_param_details.append((priority_distance, potential_param_strip, param_match.start('param_value'), param_match.end('param_value'), p_idx))
                                log.debug(f"  Found potential parameter (Pattern {p_idx}, Distance {priority_distance:.0f}): {potential_param_strip[:100]}...")
                            else:
                                log.debug(f"  Skipping invalid or too long potential parameter (Pattern {p_idx}): {potential_param_strip[:100]}...")

                except re.error as e:
                    log.warning(f"Regex error while finding parameters (Pattern {p_idx}: {pattern.pattern}): {e}")
                except IndexError:
                    # 捕获可能的组索引错误 (使用命名组通常不会发生，但作为 safeguard)
                    log.debug(f"Caught IndexError while finding parameters (Pattern {p_idx}: {pattern.pattern})")
                    continue
                except Exception as e:
                    log.error(f"Unexpected error while finding parameters (Pattern {p_idx}: {pattern.pattern}): {e}", exc_info=True)

            # --- 参数选择逻辑 ---
            selected_param_str: Optional[str] = None # 最终选定的参数字符串
            best_var_match = None # 存储找到的最佳变量名匹配
            best_str_match = None # 存储找到的最佳字符串字面量匹配

            if found_param_details:
                 # 按优先级距离对潜在参数匹配进行排序 (距离越小优先级越高)
                 found_param_details.sort(key=lambda x: x[0])

                 # 遍历排序后的潜在参数匹配
                 for dist, param_str_raw, start, end, p_idx in found_param_details:
                     param_str_strip = param_str_raw.strip()

                     # 检查是否是直接的对象/数组字面量
                     is_obj_arr_literal = (param_str_strip.startswith('{') and param_str_strip.endswith('}')) or \
                                          (param_str_strip.startswith('[') and param_str_strip.endswith(']'))

                     # 检查是否是变量名或属性访问链
                     is_var_name = VALID_JS_VARIABLE_NAME_PATTERN.match(param_str_strip) is not None

                     # 检查是否是字符串字面量
                     is_str_literal = (param_str_strip.startswith(('"', "'", "`")) and param_str_strip.endswith(('"', "'", "`")))

                     # 优先级：对象/数组字面量 > 变量名 > 字符串字面量 > 简单值
                     if is_obj_arr_literal:
                         # --- 优化：检查这个对象/数组是否被常见的参数键包装 ---
                         unwrapped_value = None
                         # 尝试移除常见的包装键，例如 `{ data: {...} }` -> `{...}`
                         # 遍历所有可能的包装键
                         for wrapper_key in PARAM_WRAPPER_KEYS:
                             # 构建一个特定的正则表达式，用于在当前对象/数组字面量内部查找包装键并捕获其值
                             # 这个模式需要处理键周围的潜在空白和引号
                             # 使用原始字符串进行查找，避免清理引入的问题
                             # 注意：这里的查找是在 param_str_strip 内部进行
                             wrapper_pattern = re.compile(
                                 r'^\{\s*(?:\"' + re.escape(wrapper_key) + r'\"|\'' + re.escape(wrapper_key) + r'\'|' + re.escape(wrapper_key) + r')\s*:\s*(?P<unwrapped_value>\{.*?\}(?:[^;]*?\{.*?\})*|\[.*?\](?:[^;]*?\[.*?\])*)',
                                 re.DOTALL | re.MULTILINE
                             )
                             match_wrapper = wrapper_pattern.search(param_str_strip)
                             if match_wrapper:
                                 # 如果找到包装键，提取其值
                                 unwrapped_value = match_wrapper.group('unwrapped_value').strip()
                                 log.debug(f"  Found wrapper key '{wrapper_key}'. Extracted unwrapped value: {unwrapped_value[:100]}...")
                                 break # 找到一个包装键并提取了值，停止检查其他包装键

                         if unwrapped_value:
                             # 如果成功提取了包装的值，使用它作为选定的参数
                             selected_param_str = unwrapped_value
                             log.debug(f"  Selected unwrapped parameter value.")
                             break # 找到了最佳类型的参数 (解包后的字面量)，停止搜索
                         else:
                             # 如果是对象/数组字面量但没有被已知键包装，使用整个字面量
                             log.debug(f"  Selected closest object/array literal parameter (not wrapped).")
                             selected_param_str = param_str_strip
                             break # 找到了最佳类型的参数 (字面量)，停止搜索

                     elif is_var_name and best_var_match is None:
                         # 如果当前最佳匹配是变量名，存储它作为一种可能性，但继续查找字面量
                         log.debug(f"  Closest match is variable '{param_str_strip}', considering for backward search.")
                         best_var_match = (dist, param_str_strip, start, end, p_idx)
                         # 不中断循环，继续搜索更高优先级的匹配 (字面量)

                     elif is_str_literal and selected_param_str is None and best_var_match is None:
                         # 如果当前最佳匹配是字符串字面量，且还没有找到字面量或变量名，存储它作为一种可能性
                          log.debug(f"  Closest match is string literal, considering.")
                          # 如果还没有最佳字符串匹配，或者当前匹配距离更近，则更新最佳字符串匹配
                          if best_str_match is None or dist < best_str_match[0]:
                               best_str_match = (dist, param_str_strip, start, end, p_idx)
                          # 不中断循环，继续搜索更高优先级的匹配 (字面量和变量)

                     # 如果是简单的原始值 (true, false, null, 数字)，且没有找到其他更高优先级的匹配
                     # 暂时不特别处理，它们会作为字符串字面量被 _normalize_param_for_deduplication 处理

                 # 在遍历所有潜在匹配之后：
                 if selected_param_str:
                     # 如果已经选定了字面量或解包后的值，则参数已确定
                     pass
                 elif best_var_match:
                     # 如果没有选定字面量，但找到了变量名，则尝试向后搜索其赋值
                     dist, variable_name, start_in_context, end_in_context, p_idx = best_var_match

                     # 向后搜索的结束位置是参数匹配在 js_content 中的绝对起始位置
                     search_back_end_pos_in_js = search_start + start_in_context
                     # 向后搜索的起始位置：从结束位置向前回溯 PARAM_SEARCH_WINDOW_BEFORE 字符，但不小于 0
                     search_back_start_pos_in_js = max(0, search_back_end_pos_in_js - PARAM_SEARCH_WINDOW_BEFORE)

                     log.debug(f"  Best match is variable '{variable_name}'. Searching backwards for assignment in range {search_back_start_pos_in_js}-{search_back_end_pos_in_js}...")

                     # 提取向后搜索的上下文代码片段
                     backward_context_slice = js_content[search_back_start_pos_in_js:search_back_end_pos_in_js]

                     # 在向后上下文中查找变量的赋值语句
                     assignments_found = []
                     # 遍历所有赋值模式
                     for assign_pattern in ASSIGNMENT_PATTERNS:
                          try:
                              # 构建一个专门针对该变量名的赋值模式
                              # 使用 re.escape 确保变量名中的特殊字符被正确处理
                              variable_assignment_pattern_str = re.escape(variable_name) + r'\s*=\s*(?P<assigned_value>\{.*?\}(?:[^;]*?\{.*?\})*|\[.*?\](?:[^;]*?\[.*?\])*|[\'"`].*?[\'"`]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*;?'
                              variable_assignment_pattern = re.compile(variable_assignment_pattern_str, re.DOTALL | re.MULTILINE | re.IGNORECASE)

                              # 在向后上下文中查找所有匹配
                              assignments_found.extend(list(variable_assignment_pattern.finditer(backward_context_slice)))
                          except re.error as e:
                              log.warning(f"Regex error while searching for variable assignment for '{variable_name}': {e}")
                          except Exception as e:
                              log.error(f"Unexpected error while searching for variable assignment for '{variable_name}': {e}", exc_info=True)


                     if assignments_found:
                         # 如果找到了赋值，选择距离向后上下文结束位置 (即参数匹配开始位置) 最近的一个
                         # 按距离向后上下文结束位置的距离排序 (距离越小越靠后，越可能是最近的赋值)
                         assignments_found.sort(key=lambda m: (len(backward_context_slice) - m.end()))

                         closest_assignment = assignments_found[0] # 最近的赋值匹配
                         assigned_value = closest_assignment.group('assigned_value') # 提取赋给变量的值
                         if assigned_value:
                             assigned_value_strip = assigned_value.strip()
                             # 验证提取到的赋值是否是有效的参数类型 (对象, 数组, 字符串, 简单值)
                             is_obj_arr = assigned_value_strip.startswith(('{', '[')) and assigned_value_strip.endswith(('}', ']'))
                             is_str = assigned_value_strip.startswith(('"', "'", "`")) and assigned_value_strip.endswith(('"', "'", "`"))
                             is_simple_value = re.fullmatch(r'true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', assigned_value_strip, re.IGNORECASE) is not None

                             # 如果是有效的类型且长度在限制内，则使用这个赋值作为参数
                             if (is_obj_arr or is_str or is_simple_value) and len(assigned_value_strip) < MAX_PARAM_STRING_LENGTH:
                                 selected_param_str = assigned_value_strip
                                 log.debug(f"  Found and selected assigned value for '{variable_name}': {selected_param_str[:100]}...")
                             else:
                                 # 赋值的值无效或太长，回退到使用变量名
                                 log.debug(f"  Found assignment for '{variable_name}', but assigned value doesn't look like a valid parameter type or is too long.")
                                 selected_param_str = variable_name # 回退
                         else:
                             # 找到了赋值，但捕获的值为空，回退到使用变量名
                             log.debug(f"  Found assignment for '{variable_name}' but captured value is empty.")
                             selected_param_str = variable_name # 回退
                     else:
                         # 在向后搜索窗口内没有找到变量的赋值，回退到使用变量名
                         log.debug(f"  No assignment found for variable '{variable_name}' in backward search window.")
                         selected_param_str = variable_name # 回退到变量名
                 elif best_str_match:
                      # 如果没有选定字面量或变量名，使用找到的最佳字符串字面量
                      selected_param_str = best_str_match[1].strip()
                      log.debug(f"  Selected closest string literal parameter.")
                 # else: selected_param_str 保持为 None，最终参数将是 "无参数"

            params = selected_param_str # 将选定的参数字符串赋值给 params

        # 将提取到的请求和参数添加到最终结果列表
        final_results_list.append({
            'type': res['type'], 'method': res['method'], 'url': res['url'], 'params': params
        })
        # processed_indices.add(i) # 如果需要跳过已处理的索引，则取消注释

    # --- 最终去重 (基于类型、方法、URL 和规范化后的参数) ---
    log.debug(f"Parameter finding complete, starting final deduplication (Current {len(final_results_list)} results)...")
    unique_results: List[Dict[str, Any]] = [] # 存储去重后的结果列表
    # 使用一个集合来存储最终的唯一签名 (类型, 方法, URL, 规范化参数)
    seen_final: Set[Tuple[str, str, str, Any]] = set()

    # 遍历包含参数的初步结果列表
    for item in final_results_list:
        # 对参数进行规范化，以便进行可靠的去重比较
        param_key = _normalize_param_for_deduplication(item.get('params'))

        # 构建用于去重的元组签名 (类型, 方法, URL, 规范化参数)
        item_tuple = (item['type'], item['method'], item['url'], param_key)

        # 如果这个签名还没有被添加到 seen_final 集合中
        if item_tuple not in seen_final:
            log.debug(f"Adding unique request: {item['method']} {item['url'][:100]}...")
            unique_results.append(item) # 添加到唯一结果列表
            seen_final.add(item_tuple) # 将签名添加到 seen_final 集合
        else:
            # 如果签名已存在，说明是重复的请求，跳过
            log.debug(f"Skipping duplicate request: {item['method']} {item['url'][:100]}... (Params: {str(param_key)[:100]}...)")

    log.info(f"Extraction complete, found {len(unique_results)} unique potential API requests.")
    return unique_results # 返回最终去重后的结果列表

# --- 独立执行入口 (通常不会直接运行 extractor.py) ---
# 保留此部分以防需要独立测试，但在主程序中不会执行
if __name__ == '__main__':
    # 确保独立运行时日志有基本配置
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    print("--- Running extractor.py independently for testing ---")

    # 示例 JavaScript 代码
    test_js_content = """
    // WebSocket example
    var ws = new WebSocket("wss://example.com/realtime");

    // GraphQL examples
    fetch('/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: '{ users { id name } }', variables: { userId: 123 } }) // object literal + JSON.stringify
    });

    axios.post('/api/graphql', {
        query: `
            mutation CreateUser($name: String!) {
                createUser(name: $name) { id }
            }
        `, // backtick string literal
        variables: userVariables // variable name
    });

    // RESTful examples
    axios.get('/api/users/1');
    http.post('/api/products', { name: 'test', price: 10 }); // object literal
    request.put('/api/orders/abc', orderData); // variable name
    $.ajax({
        url: '/api/items',
        type: 'DELETE',
        data: { itemId: 456 } // object literal
    });
    $.get('/api/status');
    customClient.patch('/api/config', configUpdates); // variable name

    // Simple relative URL
    fetch('/data/list?page=1');

    // URL that should be filtered
    fetch('/static/js/main.js');
    fetch('/images/logo.png');
    var link = './components/button.js'; // looks like module import

    // Assignment example for variable lookup
    var userVariables = { name: 'newUser', email: 'test@example.com' };
    var orderData = { items: [], total: 100 };
    const configUpdates = { setting1: true, setting2: false };
    """

    # 提取请求
    extracted_requests = extract_requests(test_js_content)

    print(f"\n--- Extracted {len(extracted_requests)} unique requests ---")
    for req in extracted_requests:
        print(f"Type: {req['type']}, Method: {req['method']}, URL: {req['url']}")
        if req['params']:
            print(f"Params: {req['params'][:100]}...") # Print first 100 chars of params
        else:
            print("Params: None")
        print("-" * 20)

    # 示例使用 formatter 模块 (独立测试时需要确保 formatter.py 可导入)
    print("\n--- Testing formatter.format_params with extracted params ---")
    for req in extracted_requests:
        if req['params']:
            print(f"Original Params for {req['url']}: {req['params'][:100]}...")
            formatted = formatter.format_params(req['params'])
            print("Formatted Params:")
            print(formatted)
            print("-" * 20)
