#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API提取器模块
功能：从JavaScript代码中提取HTTP API请求信息
"""

import re

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
    url_method_patterns = [
        # axios模式
        r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        # fetch模式
        r'fetch\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]\s*,\s*\{\s*method\s*:\s*[\'"](?P<method>[^\'"]*)[\'"]',
        # jQuery ajax模式
        r'\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*[\'"](?P<url>[^\'"]*)[\'"](,|\})[^}]*type\s*:\s*[\'"](?P<method>[^\'"]*)[\'"]',
        r'\$\.ajax\s*\(\s*\{[^}]*type\s*:\s*[\'"](?P<method>[^\'"]*)[\'"][^}]*url\s*:\s*[\'"](?P<url>[^\'"]*)[\'"](,|\})',
        # 更通用的形式
        r'(?:\.|\s+)(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        r'method\s*:\s*[\'"](?P<method>[^\'"]*)[\'"][^}]*url\s*:\s*[\'"](?P<url>[^\'"]*)[\'"](,|\})',
        r'url\s*:\s*[\'"](?P<url>[^\'"]*)[\'"](,|\})[^}]*method\s*:\s*[\'"](?P<method>[^\'"]*)[\'"]',
        
        # Angular HttpClient模式
        r'this\.http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        r'http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # Vue Axios/Resource模式
        r'this\.\$(?:http|axios|resource)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # 通用函数调用，URL作为参数
        r'(?:request|api|client|http)(?:Request|Call|Fetch)?\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # React Query/SWR等模式
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*\[\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # 模板字符串URL模式 (新增)
        r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*`(?P<url>[^`]*)`(,|\))',
        r'fetch\s*\(\s*`(?P<url>[^`]*)`\s*,\s*\{\s*method\s*:\s*[\'"](?P<method>[^\'"]*)[\'"]',
    ]
    
    # GraphQL请求模式
    graphql_patterns = [
        # Apollo Client
        r'(?:apolloClient|client)\.query\s*\(\s*\{[^}]*query\s*:\s*(?:gql|graphql)`(?P<query>[^`]*)`',
        r'(?:apolloClient|client)\.mutate\s*\(\s*\{[^}]*mutation\s*:\s*(?:gql|graphql)`(?P<query>[^`]*)`',
        # 通用GraphQL请求
        r'(?:graphql|gql)\s*`(?P<query>[^`]*)`',
        # 其他GraphQL客户端
        r'(?:request|fetch|post)\s*\(\s*[\'"](?P<url>[^\'"]*(?:graphql|gql)[^\'"]*)[\'"]',
        # GraphQL变量 (新增)
        r'(?:query|mutation)\s+(?P<operation>\w+)[\s\{]',
    ]
    
    # WebSocket连接模式
    websocket_patterns = [
        r'(?:new\s+)?WebSocket\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',
        r'(?:new\s+)?ReconnectingWebSocket\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',
        r'socket\s*\=\s*io\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',  # Socket.io
        r'connect\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',  # 通用WebSocket连接
        # 使用模板字符串的WebSocket连接 (新增)
        r'(?:new\s+)?WebSocket\s*\(\s*`(?P<url>[^`]*)`',
    ]
    
    # 提取请求参数的正则表达式模式
    param_patterns = [
        # 查找data: {...}或params: {...}形式的请求参数
        r'(?:data|params|body|json)\s*:\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        # 查找JSON.stringify({...})形式的参数
        r'JSON\.stringify\s*\((\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})\)',
        # 查找函数调用中的参数对象
        r'(?:post|put|patch|get)\s*\([^\)]*,\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        # 查找URL后面附加的参数对象
        r'[\'"`](?:[^\'"`]*/[^\'"`]*)[\'"`]\s*,\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        # 查找URL前后附近的参数对象
        r'(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})\s*[,;)]\s*[\'"`](?:[^\'"`]*/[^\'"`]*)[\'"`]',
        r'[\'"`](?:[^\'"`]*/[^\'"`]*)[\'"`](?:\s*[,;)]|\s*\+\s*\w+)\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        
        # GraphQL变量参数模式
        r'variables\s*:\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        # 改进的参数识别 (新增)
        r'(?:options|config|requestOptions)\s*=\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
    ]
    
    # 使用更精确的大括号匹配策略
    curl_bracket_pattern = r'\{\s*(?:["\']?\w+["\']?\s*:\s*[^{},]+(?:\s*,\s*["\']?\w+["\']?\s*:\s*[^{},]+)*|[^{}]*\{[^{}]*\}[^{}]*)\s*\}'
    
    # 处理URL方法匹配
    for pattern in url_method_patterns:
        try:
            matches = re.finditer(pattern, js_content, re.IGNORECASE)
            for match in matches:
                method = match.group('method').upper()
                url = match.group('url').strip()
                
                # 过滤非API URL
                if should_skip_url(url):
                    continue
                    
                context = extract_context(js_content, match.start(), match.end())
                params = extract_params(context, param_patterns, curl_bracket_pattern, match.start())
                api_type = classify_api_endpoint(url, method, context)
                
                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': api_type
                })
        except Exception as e:
            # 如果某个模式匹配出错，继续尝试其他模式
            continue
    
    # 处理GraphQL请求
    extract_graphql_requests(js_content, graphql_patterns, results)
    
    # 处理WebSocket连接
    extract_websocket_connections(js_content, websocket_patterns, results)
    
    # 查找可能的额外URL
    extract_additional_urls(js_content, param_patterns, curl_bracket_pattern, results)
    
    return results

def should_skip_url(url):
    """判断URL是否需要跳过（非API URL）"""
    # 跳过明显不是API的URL
    if not url or len(url) < 2:  # 跳过空URL或太短的URL
        return True
        
    # 跳过静态资源
    static_extensions = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.html', 
                         '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map')
    if url.lower().endswith(static_extensions):
        return True
        
    # 跳过包含明显静态资源路径的URL
    static_path_indicators = ('/static/', '/assets/', '/images/', '/img/', '/css/', '/js/', 
                             '/fonts/', '/dist/', '/build/', '/vendor/')
    if any(indicator in url.lower() for indicator in static_path_indicators):
        return True
        
    # 跳过完整的外部URLs（除非是已知API域名）
    if url.startswith(('http://', 'https://')) and not any(api_domain in url.lower() for api_domain in 
                                                         ['api.', '/api', 'graphql', 'gql', 'service', 
                                                          'gateway', 'rest', 'v1/', 'v2/', 'data']):
        # 检查外部URL是否看起来像静态资源
        if '.' in url.split('/')[-1] and not url.endswith(('.php', '.asp', '.aspx', '.jsp', '.do', '.action')):
            return True
            
    return False

def extract_context(js_content, start_pos, end_pos, before_chars=400, after_chars=800):
    """提取API调用上下文的辅助函数，增大上下文范围"""
    # 找到代码块的边界，增加上下文的准确性
    code_start = start_pos
    # 向前查找代码块开始（函数定义，对象定义等）
    for i in range(start_pos, max(0, start_pos - before_chars), -1):
        if js_content[i] == '{' or js_content[i] == ';':
            code_start = i + 1
            break
        elif i <= 5 and js_content[i:i+8].strip().startswith(('function', 'const', 'let', 'var')):
            code_start = i
            break
    
    code_end = end_pos
    # 向后查找代码块结束
    brace_count = 0
    for i in range(end_pos, min(len(js_content), end_pos + after_chars)):
        if js_content[i] == '{':
            brace_count += 1
        elif js_content[i] == '}':
            if brace_count > 0:
                brace_count -= 1
            else:
                code_end = i + 1
                break
        elif js_content[i] == ';' and brace_count == 0:
            code_end = i + 1
            break
    
    # 最终确定要返回的上下文范围
    start = max(0, code_start - 200)  # 额外添加一些前导上下文
    end = min(len(js_content), code_end + 200)  # 额外添加一些后续上下文
    
    return js_content[start:end]

def extract_params(context, param_patterns, curl_bracket_pattern, match_pos=None):
    """从上下文中提取参数，增强参数识别能力"""
    # 使用匹配位置来更准确地定位上下文
    if match_pos is None:
        match_pos = len(context) // 2  # 假设匹配位置在上下文中间
    else:
        # 将外部传入的匹配位置相对于上下文调整
        match_pos = match_pos - max(0, match_pos - 400)  # 根据更大的上下文范围调整
    
    # 首先尝试使用精准的参数模式查找
    for param_pattern in param_patterns:
        try:
            # 使用更宽松的搜索范围
            search_start = max(0, match_pos - 200)
            search_end = min(len(context), match_pos + 400)
            search_context = context[search_start:search_end]
            
            param_matches = re.search(param_pattern, search_context, re.DOTALL)
            if param_matches:
                params = param_matches.group(1)
                
                # 验证提取的参数是否为有效的JSON对象结构（至少有一个键值对）
                if re.search(r'["\']?\w+["\']?\s*:', params):
                    return re.sub(r'\s+', ' ', params).strip()
        except Exception:
            continue
    
    # 尝试通用的大括号查找 - 在附近查找JSON对象
    try:
        # 优先搜索URL后面的参数对象
        post_context = context[match_pos:min(match_pos + 300, len(context))]
        bracket_matches = list(re.finditer(r'[,\(]\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})', post_context, re.DOTALL))
        if bracket_matches and len(bracket_matches[0].group(1)) > 5:  # 确保不是空对象
            return re.sub(r'\s+', ' ', bracket_matches[0].group(1)).strip()
            
        # 如果URL后面没有找到，尝试查找整个上下文中的对象
        curl_matches = list(re.finditer(curl_bracket_pattern, context, re.DOTALL))
        
        if curl_matches:
            # 找到离匹配位置最近的大括号对象
            valid_matches = [m for m in curl_matches if len(m.group(0)) > 5 and ":" in m.group(0)]
            if valid_matches:
                closest_match = min(valid_matches, key=lambda m: abs(match_pos - (m.start() + m.end()) // 2))
                
                # 只考虑相对接近调用的对象（250字符内）
                if abs(match_pos - (closest_match.start() + closest_match.end()) // 2) < 250:
                    return re.sub(r'\s+', ' ', closest_match.group(0)).strip()
    except Exception:
        pass
        
    return None

def extract_graphql_requests(js_content, graphql_patterns, results):
    """提取GraphQL请求，改进查询处理"""
    for pattern in graphql_patterns:
        try:
            matches = re.finditer(pattern, js_content, re.DOTALL)
            for match in matches:
                method = "POST"  # GraphQL请求默认为POST
                
                if 'url' in match.groupdict():
                    url = match.group('url')
                else:
                    # 从上下文中提取GraphQL端点
                    context = extract_context(js_content, match.start(), match.end(), 400, 100)
                    url_match = re.search(r'(?:url|uri|endpoint|path)\s*[=:]\s*[\'"`]([^\'"`.]*(?:graphql|gql)[^\'"`.]*)[\'"`]', context)
                    url = url_match.group(1) if url_match else "/graphql"
                
                if 'query' in match.groupdict():
                    query = match.group('query')
                    # 安全地格式化GraphQL查询
                    query = format_graphql_query(query)
                    params = f'{{"query": "{query}"}}'
                elif 'operation' in match.groupdict():
                    operation = match.group('operation')
                    # 提取操作类型（query/mutation）和名称
                    context = extract_context(js_content, match.start(), match.end(), 100, 500)
                    query_fragment = context[match.start() - max(0, match.start() - 100):min(len(context), match.start() + 500)]
                    params = f'{{"operation": "{operation}", "fragment": "{clean_code_for_json(query_fragment)}"}}'
                else:
                    params = None
                
                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': 'GraphQL'
                })
        except Exception:
            continue

def format_graphql_query(query):
    """安全地格式化GraphQL查询，处理复杂的转义情况"""
    if not query:
        return ""
        
    # 移除模板字符串分隔符和注释
    query = re.sub(r'`|//.*$|/\*.*?\*/', '', query, flags=re.MULTILINE | re.DOTALL)
    
    # 标准化换行和缩进
    query = re.sub(r'\s+', ' ', query)
    
    # 安全地转义JSON特殊字符，但保留GraphQL语法
    query = query.replace('\\', '\\\\')
    query = query.replace('"', '\\"')
    
    return query.strip()

def clean_code_for_json(code):
    """清理代码片段以安全地包含在JSON字符串中"""
    if not code:
        return ""
        
    # 移除注释
    code = re.sub(r'//.*$|/\*.*?\*/', '', code, flags=re.MULTILINE | re.DOTALL)
    
    # 转义JSON特殊字符
    code = code.replace('\\', '\\\\')
    code = code.replace('"', '\\"')
    code = code.replace('\n', '\\n')
    code = code.replace('\r', '\\r')
    code = code.replace('\t', '\\t')
    
    return code.strip()

def extract_websocket_connections(js_content, websocket_patterns, results):
    """提取WebSocket连接，增加对模板字符串的支持"""
    for pattern in websocket_patterns:
        try:
            matches = re.finditer(pattern, js_content)
            for match in matches:
                # 检查groupdict中是否有'url'
                if 'url' in match.groupdict():
                    url = match.group('url').strip()
                    # 跳过明显无效的WebSocket URL
                    if not url or len(url) < 2:
                        continue
                    
                    # 处理WebSocket URL中的模板字符串
                    if '${' in url:
                        # 提取模板变量
                        template_vars = re.findall(r'\${([^}]+)}', url)
                        context = extract_context(js_content, match.start(), match.end(), 500, 200)
                        # 尝试从上下文中解析模板变量
                        for var in template_vars:
                            var_match = re.search(r'(?:const|let|var)\s+' + re.escape(var) + r'\s*=\s*[\'"`]([^\'"`.]+)[\'"`]', context)
                            if var_match:
                                url = url.replace(f'${{{var}}}', var_match.group(1))
                    
                    # 如果URL不以ws://或wss://开头，尝试添加前缀
                    if not url.startswith(('ws://', 'wss://')):
                        context = extract_context(js_content, match.start(), match.end())
                        if 'secure' in context.lower() or 'ssl' in context.lower() or 'https' in context.lower():
                            url = 'wss://' + url.lstrip('/')
                        else:
                            url = 'ws://' + url.lstrip('/')
                    
                    add_unique_result(results, {
                        'method': 'CONNECT',
                        'url': url,
                        'params': None,
                        'api_type': 'WebSocket'
                    })
        except Exception:
            continue

def extract_additional_urls(js_content, param_patterns, curl_bracket_pattern, results):
    """额外查找URL模式，改进API URL识别"""
    # 使用更精确的URL模式，避免匹配到静态资源
    url_patterns = [
        # 路径格式的API URL
        r'[\'"`](?P<url>/(?:api|v\d|service|gateway)/[^\'"`.]*)[\'"`]',
        # REST风格资源URL
        r'[\'"`](?P<url>/[a-z][a-z0-9_]*(?:/[a-z][a-z0-9_]*)+)[\'"`]',
        # 以斜杠开头但避免静态资源的URL
        r'[\'"`](?P<url>/[^\'"`/][^\'"`.]*(?<!\.js|\.css|\.html|\.png|\.jpg|\.gif))[\'"`]'
    ]
    
    for url_pattern in url_patterns:
        try:
            url_matches = re.finditer(url_pattern, js_content)
            for url_match in matches_with_limit(url_matches, 100):  # 限制处理数量
                url = url_match.group('url')
                
                # 跳过无效URL
                if should_skip_url(url):
                    continue
                
                # 查找上下文
                context = extract_context(js_content, url_match.start(), url_match.end())
                
                # 猜测请求方法
                method = guess_http_method(context)
                
                # 查找参数
                params = extract_params(context, param_patterns, curl_bracket_pattern, url_match.start())
                
                # 确定API类型
                api_type = classify_api_endpoint(url, method, context)
                
                add_unique_result(results, {
                    'method': method,
                    'url': url,
                    'params': params,
                    'api_type': api_type
                })
        except Exception:
            pass

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
    method_indicators = {
        'post': 'POST',
        'put': 'PUT',
        'delete': 'DELETE',
        'patch': 'PATCH',
        'create': 'POST',   # 创建资源通常使用POST
        'update': 'PUT',    # 更新资源通常使用PUT或PATCH
        'remove': 'DELETE', # 删除资源通常使用DELETE
        'save': 'POST',     # 保存新资源通常使用POST
        'modify': 'PATCH'   # 修改资源通常使用PATCH
    }
    
    context_lower = context.lower()
    # 首先检查直接方法指示器
    for indicator, http_method in method_indicators.items():
        method_pattern = fr'[\.\s](?:{indicator}|"{indicator}"|[\'\`]{indicator}[\'\`])'
        if re.search(method_pattern, context_lower):
            method = http_method
            break
    
    # 检查函数名和变量名提示
    function_match = re.search(r'function\s+(\w+)', context_lower)
    if function_match:
        func_name = function_match.group(1)
        for indicator, http_method in method_indicators.items():
            if indicator in func_name:
                method = http_method
                break
    
    # 检查CRUD操作相关的上下文
    if method == "GET" and any(word in context_lower for word in ['submit', 'send', 'upload', 'create']):
        method = 'POST'
    
    return method

def add_unique_result(results, new_result):
    """添加唯一的结果，避免重复，优化更新逻辑"""
    if not new_result['url']:
        return  # 忽略空URL
        
    # 标准化URL
    url = new_result['url'].rstrip('/')
    new_result['url'] = url
    
    # 检查是否已存在相同URL和方法的结果
    for existing in results:
        existing_url = existing['url'].rstrip('/')
        if existing_url == url and existing['method'] == new_result['method']:
            # 如果新的参数更详细，更新参数
            if new_result['params'] and (not existing['params'] or 
                                       len(new_result['params']) > len(existing['params'])):
                existing['params'] = new_result['params']
            
            # 如果新的API类型更具体，更新API类型
            if new_result['api_type'] != 'HTTP API' and existing['api_type'] == 'HTTP API':
                existing['api_type'] = new_result['api_type']
                
            return  # 已存在，无需添加
    
    # 不存在相同结果，添加新结果
    results.append(new_result)

def classify_api_endpoint(url, method, context=""):
    """
    对API端点进行分类，增强分类能力
    
    参数:
        url: API端点URL
        method: HTTP方法
        context: API调用的上下文代码
        
    返回:
        API类型: 'RESTful', 'GraphQL', 'WebSocket', 'RPC' 等
    """
    # URL为空时返回通用类型
    if not url:
        return 'HTTP API'
        
    url_lower = url.lower()
    context_lower = context.lower()
    
    # 检查是否为GraphQL端点
    if '/graphql' in url_lower or '/gql' in url_lower or 'graphql' in context_lower:
        return 'GraphQL'
    
    # 检查是否为WebSocket连接
    if url.startswith(('ws://', 'wss://')) or 'websocket' in context_lower or 'socket.io' in context_lower:
        return 'WebSocket'
    
    # 检查是否为gRPC或其他RPC调用
    if '/rpc' in url_lower or 'rpc' in context_lower or '/jsonrpc' in url_lower:
        return 'RPC'
    
    # 检查是否为OAuth或认证端点
    if '/oauth' in url_lower or '/token' in url_lower or '/auth' in url_lower or 'login' in url_lower:
        return 'Auth API'
    
    # 判断是否为常见的REST资源模式
    if re.search(r'/(?:api/v\d+/)?[a-z]+(?:/[a-z]+)*(?:/\d+)?$', url):
        return 'RESTful'
    
    # 检查PUT/DELETE/PATCH方法通常与RESTful API一起使用
    if method in ['PUT', 'DELETE', 'PATCH']:
        return 'RESTful'
    
    # 检查常见的REST操作
    operations = ['create', 'update', 'delete', 'get', 'list', 'search', 'query']
    if any(op in url_lower for op in operations):
        return 'RESTful'
    
    # 对于更复杂的URL，进一步判断
    if '/api/' in url:
        # 检查是否带有版本号
        if re.search(r'/api/v\d+/', url):
            return 'RESTful'
        # 检查是否是典型的REST资源URLs模式
        if re.search(r'/api/[a-z_]+(?:/\d+)?(?:/[a-z_]+)*', url):
            return 'RESTful'
    
    # 如果没有明确的匹配，默认为HTTP API
    return 'HTTP API'
