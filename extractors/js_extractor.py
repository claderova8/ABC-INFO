#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API提取器模块
功能：从JavaScript代码中提取HTTP API请求信息
"""

import re
import json # 导入json模块用于参数处理

def extract_requests(js_content):
    """
    从JavaScript内容中提取HTTP请求

    参数:
        js_content: JavaScript代码字符串

    返回:
        包含提取出的请求信息的列表，每项包含method(请求方法)、url、params(请求参数)和api_type(API类型)
    """
    if not js_content or not isinstance(js_content, str):
        return []

    results = []

    # 匹配请求方式和URL的正则表达式模式
    # 改进的模式，更精确地匹配URL和方法，并考虑模板字符串
    url_method_patterns = [
        # axios, http, request, ajax 等库调用
        r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\'](?:[^)]*\)\s*[,;]|\s*,\s*\{[^}]*\}\s*\))',
        # fetch 调用
        r'fetch\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']\s*,\s*\{[^}]*method\s*:\s*["\'](?P<method>get|post|put|delete|patch)["\']',
        # jQuery ajax 调用
        r'\$\.ajax\s*\(\s*\{[^}]*(?:url\s*:\s*["\'](?P<url>[^"\']*)["\'][^}]*type\s*:\s*["\'](?P<method>[^"\']*)["\']|type\s*:\s*["\'](?P<method>[^"\']*)["\'][^}]*url\s*:\s*["\'](?P<url>[^"\']*)["\'])',
        # Angular HttpClient 调用
        r'this\.http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        r'http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        # Vue Axios/Resource 调用
        r'this\.\$(?:http|axios|resource)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        # 通用函数调用，URL作为参数
        r'(?:request|api|client|http)(?:Request|Call|Fetch)?\.(?P<method>get|post|put|delete|patch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        # React Query/SWR 等模式
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*\[\s*[`"\'](?P<url>[^`"\']*)["\']',
    ]

    # GraphQL请求模式 (改进，更专注于识别GraphQL关键字和结构)
    graphql_patterns = [
        # Apollo Client 或其他客户端的 query/mutate 调用
        r'(?:apolloClient|client|graphqlClient)\.(?:query|mutate)\s*\(\s*\{[^}]*(?:query|mutation)\s*:\s*(?:gql|graphql)?\s*[`"](?P<query>[^`"]*)["`]',
        # 直接的 gql 或 graphql 模板字符串/字符串
        r'(?:gql|graphql)\s*[`"](?P<query>[^`"]*)["`]',
        # 包含 graphql 或 gql 路径的 POST 请求 (作为补充)
        r'(?:axios|fetch|\$.ajax|http)\.(?:post|request)\s*\(\s*["\'](?P<url>[^"\']*(?:graphql|gql)[^"\']*)["\']',
    ]

    # WebSocket连接模式 (改进，更精确匹配构造函数和URL)
    websocket_patterns = [
        r'(?:new\s+)?(?:WebSocket|ReconnectingWebSocket)\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',
        r'socket\s*\=\s*io\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',  # Socket.io
        r'connect\s*\(\s*[`"\'](?P<url>[^`"\']*)["\']',  # 通用连接函数
    ]

    # 提取请求参数的正则表达式模式 (改进，更精确匹配对象字面量)
    # 注意：精确匹配嵌套括号非常困难，这里采用一种平衡的方法
    param_patterns = [
        # 查找 data: {...}, params: {...}, body: {...}, json: {...} 形式的请求参数
        r'(?:data|params|body|json)\s*:\s*(\{[^}]*\})',
        # 查找 JSON.stringify({...}) 形式的参数
        r'JSON\.stringify\s*\((\{[^}]*\})\)',
        # 查找函数调用中的参数对象 (例如 post('/url', {...}))
        r'(?:post|put|patch|get)\s*\([^\)]*,\s*(\{[^}]*\})',
        # 查找URL后面附加的参数对象
        r'["\'](?:[^"\']*?)["\']\s*,\s*(\{[^}]*\})',
        # 查找 options 或 config 对象，可能包含参数
        r'(?:options|config|requestOptions)\s*=\s*(\{[^}]*\})',
        # GraphQL variables 参数
        r'variables\s*:\s*(\{[^}]*\})',
    ]

    # 使用更精确的大括号匹配策略 (用于辅助参数提取)
    # 这个模式尝试匹配一个可能包含嵌套大括号的对象字面量，但有深度限制以避免性能问题
    nested_bracket_pattern = r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'


    # 处理URL方法匹配
    for pattern in url_method_patterns:
        try:
            # 使用 finditer 获取所有匹配及其位置
            matches = list(re.finditer(pattern, js_content, re.IGNORECASE))
            for match in matches_with_limit(matches, 200): # 限制处理数量，避免大型文件性能问题
                method = match.group('method').upper()
                url = match.group('url').strip()

                # 过滤非API URL
                if should_skip_url(url):
                    continue

                # 提取更宽泛的上下文来查找参数
                context = extract_context(js_content, match.start(), match.end(), before_chars=500, after_chars=1000)
                # 尝试从上下文中提取参数
                params = extract_params(context, param_patterns, nested_bracket_pattern, match.start())
                # 确定API类型
                api_type = classify_api_endpoint(url, method, context)

                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': api_type
                })
        except Exception as e:
            # 记录模式匹配错误，但不中断进程
            print(f"Error processing URL pattern {pattern}: {e}")
            continue # 继续尝试下一个模式


    # 处理GraphQL请求
    extract_graphql_requests(js_content, graphql_patterns, results)

    # 处理WebSocket连接
    extract_websocket_connections(js_content, websocket_patterns, results)

    # 查找可能的额外URL (改进，更精确地查找可能的API路径)
    extract_additional_urls(js_content, param_patterns, nested_bracket_pattern, results)


    return results

def should_skip_url(url):
    """判断URL是否需要跳过（非API URL），增加更多过滤规则"""
    # 跳过明显不是API的URL
    if not url or len(url) < 2:  # 跳过空URL或太短的URL
        return True

    # 跳过静态资源扩展名 (增加更多类型)
    static_extensions = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.html',
                         '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map', '.txt', '.pdf', '.xml', '.json') # 增加.json等常见静态文件
    if url.lower().endswith(static_extensions):
        return True

    # 跳过包含明显静态资源路径的URL
    static_path_indicators = ('/static/', '/assets/', '/images/', '/img/', '/css/', '/js/',
                             '/fonts/', '/dist/', '/build/', '/vendor/', '/node_modules/') # 增加node_modules
    if any(indicator in url.lower() for indicator in static_path_indicators):
        return True

    # 跳过完整的外部URLs，除非是已知API域名或包含API路径
    if url.startswith(('http://', 'https://')):
        # 检查是否包含常见的API路径指示器
        if any(api_indicator in url.lower() for api_indicator in ['/api', 'service', 'gateway', 'rest', 'v1', 'v2', 'data']):
             return False # 包含API指示器，不跳过

        # 如果不包含API指示器，检查是否看起来像静态资源
        if '.' in url.split('/')[-1] and not url.endswith(('.php', '.asp', '.aspx', '.jsp', '.do', '.action')):
             return True # 看起来像静态资源，跳过

        # 如果是完整的外部URL，且不包含API指示器，且不以常见动态脚本结尾，默认跳过
        return True # 默认跳过不明确的外部URL

    # 跳过以#开头的锚点或片段标识符
    if url.startswith('#'):
        return True

    # 跳过只有斜杠的URL
    if url == '/':
        return True

    return False

def extract_context(js_content, start_pos, end_pos, before_chars=500, after_chars=1000):
    """提取API调用上下文的辅助函数，增大上下文范围并尝试对齐代码块"""
    # 尝试向后找到语句结束或代码块结束
    code_end = end_pos
    brace_count = 0
    # 查找语句结束（分号）或代码块结束（大括号）
    for i in range(end_pos, min(len(js_content), end_pos + after_chars)):
        if js_content[i] == '{':
            brace_count += 1
        elif js_content[i] == '}':
            if brace_count > 0:
                brace_count -= 1
            else:
                code_end = i + 1
                break # 找到匹配的结束大括号
        elif js_content[i] == ';' and brace_count == 0:
            code_end = i + 1
            break # 找到语句结束
        elif js_content[i] in ('\n', '\r') and brace_count == 0:
             # 在没有未匹配大括号的情况下，换行也可能表示语句结束
             code_end = i + 1
             break


    # 尝试向前找到语句开始或代码块开始
    code_start = start_pos
    brace_count = 0
    # 查找语句开始（分号）或代码块开始（大括号）或变量/函数定义
    for i in range(start_pos, max(-1, start_pos - before_chars), -1):
         if js_content[i] == '}':
             brace_count += 1
         elif js_content[i] == '{':
             if brace_count > 0:
                 brace_count -= 1
             else:
                 code_start = i
                 break # 找到匹配的开始大括号
         elif js_content[i] == ';' and brace_count == 0:
             code_start = i + 1
             break # 找到语句开始
         elif i > 0 and js_content[i-1:i+8].strip().startswith(('function', 'const', 'let', 'var', 'class')):
             code_start = i -1 # 捕获变量/函数定义开始
             break
         elif js_content[i] in ('\n', '\r') and brace_count == 0:
              # 在没有未匹配大括号的情况下，换行也可能表示语句开始
              code_start = i + 1
              break


    # 最终确定要返回的上下文范围
    start = max(0, code_start - 100)  # 额外添加一些前导上下文
    end = min(len(js_content), code_end + 100)  # 额外添加一些后续上下文

    return js_content[start:end]


def extract_params(context, param_patterns, nested_bracket_pattern, match_pos=None):
    """从上下文中提取参数，增强参数识别能力，优先靠近匹配位置的对象"""
    if match_pos is None:
        match_pos = len(context) // 2  # 假设匹配位置在上下文中间
    else:
        # 将外部传入的匹配位置相对于上下文调整
        # 这里的调整需要考虑 context 是从 js_content 的哪个位置截取的
        # 由于 extract_context 已经处理了范围，这里可以直接使用 match_pos 相对于 context 的位置
        # 假设 match_pos 是在原始 js_content 中的位置
        context_start_in_js = max(0, match_pos - 500 - 100) # 估算上下文在原始js中的开始位置
        relative_match_pos = match_pos - context_start_in_js
        match_pos = relative_match_pos # 更新 match_pos 为相对于 context 的位置

    # 首先尝试使用精准的参数模式查找，优先搜索靠近匹配位置的区域
    search_radius = 300 # 在匹配位置前后300字符内搜索
    search_start = max(0, match_pos - search_radius)
    search_end = min(len(context), match_pos + search_radius)
    search_context = context[search_start:search_end]

    for param_pattern in param_patterns:
        try:
            # 在局部上下文中查找参数
            param_matches = list(re.finditer(param_pattern, search_context, re.DOTALL))
            if param_matches:
                 # 找到离匹配位置最近的参数对象
                 closest_match = min(param_matches, key=lambda m: abs(match_pos - (m.start() + search_start + m.end() + search_start) // 2))
                 params = closest_match.group(1)

                 # 验证提取的参数是否为有效的JSON对象结构（至少有一个键值对）
                 if re.search(r'["\']?\w+["\']?\s*:', params):
                     return re.sub(r'\s+', ' ', params).strip()
        except Exception:
            continue

    # 如果精准模式未找到，尝试通用的大括号查找 - 在整个上下文中查找JSON对象
    try:
        # 查找所有可能的对象字面量
        curl_matches = list(re.finditer(nested_bracket_pattern, context, re.DOTALL))

        if curl_matches:
            # 过滤掉太短或不包含键值对的对象
            valid_matches = [m for m in curl_matches if len(m.group(0)) > 5 and ":" in m.group(0)]
            if valid_matches:
                # 找到离匹配位置最近的大括号对象
                closest_match = min(valid_matches, key=lambda m: abs(match_pos - (m.start() + m.end()) // 2))

                # 只考虑相对接近调用的对象（400字符内）
                if abs(match_pos - (closest_match.start() + closest_match.end()) // 2) < 400:
                    return re.sub(r'\s+', ' ', closest_match.group(0)).strip()
    except Exception:
        pass

    return None


def extract_graphql_requests(js_content, graphql_patterns, results):
    """提取GraphQL请求，改进查询处理和变量提取"""
    for pattern in graphql_patterns:
        try:
            matches = re.finditer(pattern, js_content, re.DOTALL)
            for match in matches_with_limit(matches, 100): # 限制处理数量
                method = "POST"  # GraphQL请求默认为POST
                url = "/graphql" # 默认GraphQL端点

                # 尝试从上下文中提取GraphQL端点URL
                context = extract_context(js_content, match.start(), match.end(), 400, 400)
                url_match = re.search(r'(?:url|uri|endpoint|path)\s*[=:]\s*[`"\']([^\'"`.]*(?:graphql|gql)[^\'"`.]*)["\']', context)
                if url_match:
                    url = url_match.group(1)

                query = None
                params_obj = {}

                if 'query' in match.groupdict():
                    query = match.group('query')
                    # 安全地格式化GraphQL查询
                    query = format_graphql_query(query)
                    params_obj["query"] = query

                # 尝试提取 variables
                variables_match = re.search(r'variables\s*:\s*(\{[^}]*\})', context)
                if variables_match:
                    variables_str = variables_match.group(1)
                    try:
                        # 尝试解析 variables 为 JSON 对象
                        variables_obj = json.loads(variables_str)
                        params_obj["variables"] = variables_obj
                    except json.JSONDecodeError:
                        # 如果解析失败，将原始字符串作为变量值
                        params_obj["variables"] = variables_str


                params = json.dumps(params_obj, ensure_ascii=False) if params_obj else None


                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': 'GraphQL'
                })
        except Exception as e:
             print(f"Error processing GraphQL pattern {pattern}: {e}")
             continue


def format_graphql_query(query):
    """安全地格式化GraphQL查询，处理复杂的转义情况"""
    if not query:
        return ""

    # 移除模板字符串分隔符和注释
    query = re.sub(r'`|//.*$|/\*.*?\*/', '', query, flags=re.MULTILINE | re.DOTALL)

    # 标准化换行和缩进
    query = re.sub(r'\s+', ' ', query).strip()

    # 安全地转义JSON特殊字符，但保留GraphQL语法
    query = query.replace('\\', '\\\\')
    query = query.replace('"', '\\"')

    return query.strip()


def extract_websocket_connections(js_content, websocket_patterns, results):
    """提取WebSocket连接，增加对模板字符串和变量的解析尝试"""
    for pattern in websocket_patterns:
        try:
            matches = re.finditer(pattern, js_content)
            for match in matches_with_limit(matches, 100): # 限制处理数量
                # 检查groupdict中是否有'url'
                if 'url' in match.groupdict():
                    url = match.group('url').strip()
                    # 跳过明显无效的WebSocket URL
                    if not url or len(url) < 2:
                        continue

                    # 尝试解析模板字符串和变量
                    if '${' in url:
                        context = extract_context(js_content, match.start(), match.end(), 500, 200)
                        url = resolve_template_string(url, context)

                    # 如果URL不以ws://或wss://开头，尝试添加前缀
                    if not url.startswith(('ws://', 'wss://')):
                        context = extract_context(js_content, match.start(), match.end())
                        if 'secure' in context.lower() or 'ssl' in context.lower() or 'https' in context.lower():
                            url = 'wss://' + url.lstrip('/')
                        else:
                            url = 'ws://' + url.lstrip('/')

                    add_unique_result(results, {
                        'method': 'CONNECT', # WebSocket连接通常用CONNECT表示
                        'url': url,
                        'params': None, # WebSocket通常没有请求参数体
                        'api_type': 'WebSocket'
                    })
        except Exception as e:
             print(f"Error processing WebSocket pattern {pattern}: {e}")
             continue

def resolve_template_string(template_string, context):
    """尝试从上下文中解析模板字符串中的变量"""
    resolved_string = template_string
    template_vars = re.findall(r'\${([^}]+)}', template_string)

    for var_expr in template_vars:
        # 简化表达式，只取变量名或简单的属性访问
        var_name_match = re.match(r'([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)', var_expr.strip())
        if var_name_match:
            var_name = var_name_match.group(1)
            # 在上下文中查找变量的定义
            # 寻找 const/let/var 变量定义
            var_definition_match = re.search(
                fr'(?:const|let|var)\s+{re.escape(var_name)}\s*=\s*[`"\']([^`"\']*)["\']',
                context
            )
            if var_definition_match:
                resolved_string = resolved_string.replace(f'${{{var_expr}}}', var_definition_match.group(1))
                continue # 找到并替换，处理下一个变量

            # 寻找对象属性赋值 (例如 config.apiUrl = '...')
            property_assignment_match = re.search(
                 fr'{re.escape(var_name)}\s*=\s*[`"\']([^`"\']*)["\']',
                 context
            )
            if property_assignment_match:
                 resolved_string = resolved_string.replace(f'${{{var_expr}}}', property_assignment_match.group(1))
                 continue # 找到并替换，处理下一个变量

            # TODO: 可以增加对函数调用返回值等的解析，但这会非常复杂

    return resolved_string


def extract_additional_urls(js_content, param_patterns, nested_bracket_pattern, results):
    """额外查找URL模式，改进API URL识别，避免匹配静态资源"""
    # 使用更精确的URL模式，避免匹配到静态资源，并考虑常见的API路径结构
    url_patterns = [
        # 常见的API路径模式 (e.g., /api/v1/users, /service/data)
        r'["\'](?P<url>/(?:api|v\d+|service|gateway|rest)/[^\'"`\s]+)["\']',
        # REST风格资源URL (e.g., /users/123, /products) - 避免匹配单层路径或静态文件
        r'["\'](?P<url>/[a-z_][a-z0-9_]*(?:/[a-z_][a-z0-9_]*)+[^\'"`\s\.]*)["\']', # 至少两层路径，且不以点结尾
        # 包含特定关键词的URL (e.g., /data/get, /user/info)
        r'["\'](?P<url>/[^\'"`\s]*(?:get|post|put|delete|update|create|info|data|list|search)[^\'"`\s]*)["\']',
        # 以斜杠开头，后面紧跟非斜杠非点字符的URL (尝试捕获更多可能的API路径)
        r'["\'](?P<url>/[^\'"`/\s\.][^\'"`\s]*)["\']',
    ]

    for url_pattern in url_patterns:
        try:
            url_matches = re.finditer(url_pattern, js_content)
            for url_match in matches_with_limit(url_matches, 200): # 限制处理数量
                url = url_match.group('url')

                # 跳过无效URL或静态资源
                if should_skip_url(url):
                    continue

                # 查找上下文
                context = extract_context(js_content, url_match.start(), url_match.end(), before_chars=400, after_chars=600)

                # 猜测请求方法
                method = guess_http_method(context)

                # 查找参数
                params = extract_params(context, param_patterns, nested_bracket_pattern, url_match.start())

                # 确定API类型
                api_type = classify_api_endpoint(url, method, context)

                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': api_type
                })
        except Exception as e:
             print(f"Error processing additional URL pattern {url_pattern}: {e}")
             pass # 继续尝试下一个模式

def matches_with_limit(matches_iterator, limit):
    """限制处理的匹配数量，避免处理过多结果"""
    count = 0
    for match in matches_iterator:
        if count >= limit:
            break
        yield match
        count += 1

def guess_http_method(context):
    """根据上下文猜测HTTP方法，增强方法识别能力"""
    # 默认为GET
    method = "GET"
    # 增加更多方法指示器和权重
    method_indicators = {
        'post': ('POST', 3),
        'put': ('PUT', 3),
        'delete': ('DELETE', 3),
        'patch': ('PATCH', 3),
        'create': ('POST', 2),   # 创建资源通常使用POST
        'update': ('PUT', 2),    # 更新资源通常使用PUT或PATCH
        'remove': ('DELETE', 2), # 删除资源通常使用DELETE
        'save': ('POST', 2),     # 保存新资源通常使用POST
        'modify': ('PATCH', 2),   # 修改资源通常使用PATCH
        'send': ('POST', 1),     # 发送数据可能用POST
        'submit': ('POST', 1),   # 提交表单可能用POST
        'upload': ('POST', 1),   # 上传文件通常用POST
    }

    context_lower = context.lower()
    best_method = "GET"
    highest_weight = 0

    # 检查直接方法指示器和函数/变量名提示
    for indicator, (http_method, weight) in method_indicators.items():
        # 检查单词边界，避免匹配到部分单词
        method_pattern = fr'\b(?:{indicator}|{indicator}s)\b' # 考虑单复数
        if re.search(method_pattern, context_lower):
            if weight > highest_weight:
                best_method = http_method
                highest_weight = weight

    # 检查函数名和变量名提示 (权重较低)
    function_match = re.search(r'function\s+(\w+)', context_lower)
    if function_match:
        func_name = function_match.group(1)
        for indicator, (http_method, weight) in method_indicators.items():
            if indicator in func_name and weight > highest_weight:
                 best_method = http_method
                 highest_weight = weight

    # 如果仍然是GET，检查是否有请求体相关的关键词
    if best_method == "GET" and any(word in context_lower for word in ['data:', 'body:', 'json:']):
        best_method = 'POST' # 如果有请求体，更可能是POST

    return best_method


def add_unique_result(results, new_result):
    """添加唯一的结果，避免重复，优化更新逻辑"""
    if not new_result['url']:
        return  # 忽略空URL

    # 标准化URL (移除末尾斜杠和查询参数，便于去重)
    url = new_result['url'].split('?')[0].rstrip('/')
    new_result['url'] = url

    # 检查是否已存在相同URL和方法的结果
    for existing in results:
        existing_url = existing['url'].split('?')[0].rstrip('/')
        if existing_url == url and existing['method'] == new_result['method']:
            # 如果新的参数更详细，更新参数
            # 比较参数长度作为详细程度的简单指标
            if new_result['params'] and (not existing['params'] or
                                       len(new_result['params']) > len(existing['params'])):
                existing['params'] = new_result['params']

            # 如果新的API类型更具体，更新API类型
            # 例如，从 'HTTP API' 更新到 'RESTful' 或 'GraphQL'
            if new_result['api_type'] != 'HTTP API' and existing['api_type'] == 'HTTP API':
                existing['api_type'] = new_result['api_type']
            # 如果都是特定类型，优先保留更具体的（例如，Auth API 比 RESTful 更具体）
            elif new_result['api_type'] != 'HTTP API' and existing['api_type'] != 'HTTP API':
                 # 这里可以根据API类型的优先级进行更新，例如定义一个优先级列表
                 api_type_priority = ['WebSocket', 'GraphQL', 'RPC', 'Auth API', 'RESTful', 'HTTP API']
                 if api_type_priority.index(new_result['api_type']) < api_type_priority.index(existing['api_type']):
                      existing['api_type'] = new_result['api_type']

            return  # 已存在，无需添加

    # 不存在相同结果，添加新结果
    results.append(new_result)

def classify_api_endpoint(url, method, context=""):
    """
    对API端点进行分类，增强分类能力
    增加对常见认证、文件上传等API类型的识别
    """
    # URL为空时返回通用类型
    if not url:
        return 'HTTP API'

    url_lower = url.lower()
    context_lower = context.lower()

    # 检查是否为GraphQL端点
    if '/graphql' in url_lower or '/gql' in url_lower or 'graphql' in context_lower or '"query":' in context_lower:
        return 'GraphQL'

    # 检查是否为WebSocket连接
    if url.startswith(('ws://', 'wss://')) or 'websocket' in context_lower or 'socket.io' in context_lower:
        return 'WebSocket'

    # 检查是否为gRPC或其他RPC调用
    if '/rpc' in url_lower or 'rpc' in context_lower or '/jsonrpc' in url_lower or '"method":' in context_lower and '"params":' in context_lower:
        return 'RPC'

    # 检查是否为OAuth或认证端点 (增加更多关键词)
    if '/oauth' in url_lower or '/token' in url_lower or '/auth' in url_lower or 'login' in url_lower or 'register' in url_lower or 'authenticate' in url_lower or 'session' in url_lower:
        return 'Auth API'

    # 检查是否为文件上传端点
    if 'upload' in url_lower or 'file' in url_lower or 'image' in url_lower or 'document' in url_lower or 'multipart/form-data' in context_lower:
        return 'Upload API'

    # 检查是否为常见的REST资源模式 (改进正则表达式，更精确匹配资源路径)
    # 例如：/api/v1/users, /products/123, /orders
    if re.search(r'/(?:api/v\d+/)?(?:[a-z_]+(?:-[a-z_]+)*)+(?:/\d+|/[a-z_]+(?:-[a-z_]+)*)?$', url_lower):
         return 'RESTful'

    # 检查PUT/DELETE/PATCH方法通常与RESTful API一起使用
    if method in ['PUT', 'DELETE', 'PATCH']:
        return 'RESTful'

    # 检查常见的REST操作关键词
    operations = ['create', 'update', 'delete', 'get', 'list', 'search', 'query', 'add', 'remove']
    if any(op in url_lower for op in operations):
        return 'RESTful'

    # 对于更复杂的URL，进一步判断
    if '/api/' in url_lower:
        # 检查是否带有版本号
        if re.search(r'/api/v\d+/', url_lower):
            return 'RESTful'
        # 检查是否是典型的REST资源URLs模式
        if re.search(r'/api/[a-z_]+(?:/\d+|/[a-z_]+)*', url_lower):
            return 'RESTful'

    # 如果没有明确的匹配，默认为HTTP API
    return 'HTTP API'
