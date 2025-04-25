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
    ]
    
    # WebSocket连接模式
    websocket_patterns = [
        r'(?:new\s+)?WebSocket\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',
        r'(?:new\s+)?ReconnectingWebSocket\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',
        r'socket\s*\=\s*io\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',  # Socket.io
        r'connect\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"]',  # 通用WebSocket连接
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
        r'[\'"](?:[^\'"]*/[^\'"]*)[\'"]\s*,\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        # 查找URL前后附近的参数对象
        r'(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})\s*[,;)]\s*[\'"](?:[^\'"]*/[^\'"]*)[\'"]',
        r'[\'"](?:[^\'"]*/[^\'"]*)[\'"](?:\s*[,;)]|\s*\+\s*\w+)\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
        
        # GraphQL变量参数模式
        r'variables\s*:\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
    ]
    
    # 使用更简化的大括号查找策略，原来的过于复杂可能导致性能问题
    curl_bracket_pattern = r'\{\s*["\']?\w+["\']?\s*:\s*[^{}]+(?:\s*,\s*["\']?\w+["\']?\s*:\s*[^{}]+)*\s*\}'
    
    # 处理URL方法匹配
    for pattern in url_method_patterns:
        try:
            matches = re.finditer(pattern, js_content, re.IGNORECASE)
            for match in matches:
                method = match.group('method').upper()
                url = match.group('url')
                
                # 过滤非API URL
                if should_skip_url(url):
                    continue
                    
                context = extract_context(js_content, match.start(), match.end())
                params = extract_params(context, param_patterns, curl_bracket_pattern)
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
    static_extensions = ('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.html', '.ico', '.woff', '.ttf')
    if url.endswith(static_extensions):
        return True
        
    # 跳过完整的外部URLs（除非是已知API域名）
    if url.startswith(('http://', 'https://')) and not any(api_domain in url.lower() for api_domain in 
                                                          ['api.', '/api', 'graphql', 'service', 'gateway']):
        # 检查外部URL是否看起来像静态资源
        if '.' in url.split('/')[-1] and not url.endswith(('.php', '.asp', '.aspx', '.jsp')):
            return True
            
    return False

def extract_context(js_content, start_pos, end_pos, before_chars=200, after_chars=500):
    """提取API调用上下文的辅助函数"""
    start = max(0, start_pos - before_chars)
    end = min(len(js_content), end_pos + after_chars)
    return js_content[start:end]

def extract_params(context, param_patterns, curl_bracket_pattern):
    """从上下文中提取参数"""
    # 首先尝试使用精准的参数模式查找
    for param_pattern in param_patterns:
        try:
            param_matches = re.search(param_pattern, context, re.DOTALL)
            if param_matches:
                params = param_matches.group(1)
                return re.sub(r'\s+', ' ', params).strip()
        except Exception:
            continue
    
    # 尝试通用的大括号查找 - 在附近查找JSON对象
    try:
        match_pos = len(context) // 3  # 假设上下文中间位置附近是请求调用
        curl_matches = list(re.finditer(curl_bracket_pattern, context, re.DOTALL))
        
        if curl_matches:
            # 找到离中间位置最近的大括号对象
            closest_match = min(curl_matches, key=lambda m: abs(match_pos - (m.start() + m.end()) // 2))
            
            # 只考虑相对接近调用的对象（150字符内）
            if abs(match_pos - (closest_match.start() + closest_match.end()) // 2) < 150:
                return re.sub(r'\s+', ' ', closest_match.group(0)).strip()
    except Exception:
        pass
        
    return None

def extract_graphql_requests(js_content, graphql_patterns, results):
    """提取GraphQL请求"""
    for pattern in graphql_patterns:
        try:
            matches = re.finditer(pattern, js_content, re.DOTALL)
            for match in matches:
                method = "POST"  # GraphQL请求默认为POST
                
                if 'url' in match.groupdict():
                    url = match.group('url')
                else:
                    # 从上下文中提取GraphQL端点
                    context = extract_context(js_content, match.start(), match.end(), 300, 100)
                    url_match = re.search(r'(?:url|uri|endpoint)\s*:\s*[\'"]([^\'"]*(?:graphql|gql)[^\'"]*)[\'"]', context)
                    url = url_match.group(1) if url_match else "/graphql"
                
                if 'query' in match.groupdict():
                    query = match.group('query')
                    # 格式化并转义GraphQL查询
                    query = query.replace("`", "").replace('"', "'").replace('\n', ' ')
                    params = f'{{"query": "{query}"}}'
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

def extract_websocket_connections(js_content, websocket_patterns, results):
    """提取WebSocket连接"""
    for pattern in websocket_patterns:
        try:
            matches = re.finditer(pattern, js_content)
            for match in matches:
                url = match.group('url')
                # 跳过明显无效的WebSocket URL
                if not url or len(url) < 2:
                    continue
                    
                add_unique_result(results, {
                    'method': 'CONNECT',
                    'url': url,
                    'params': None,
                    'api_type': 'WebSocket'
                })
        except Exception:
            continue

def extract_additional_urls(js_content, param_patterns, curl_bracket_pattern, results):
    """额外查找URL模式"""
    # 直接查找URL模式
    url_pattern = r'[\'"](?P<url>/[^\'"/][^\'"]*)[\'"]\s*(?:[,;)\]]|$)'
    try:
        url_matches = re.finditer(url_pattern, js_content)
        for url_match in url_matches:
            url = url_match.group('url')
            
            # 跳过无效URL
            if should_skip_url(url):
                continue
            
            # 查找上下文
            context = extract_context(js_content, url_match.start(), url_match.end())
            
            # 猜测请求方法
            method = guess_http_method(context)
            
            # 查找参数
            params = extract_params(context, param_patterns, curl_bracket_pattern)
            
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

def guess_http_method(context):
    """根据上下文猜测HTTP方法"""
    method = "GET"  # 默认为GET
    method_indicators = {
        'post': 'POST',
        'put': 'PUT',
        'delete': 'DELETE',
        'patch': 'PATCH'
    }
    
    context_lower = context.lower()
    for indicator, http_method in method_indicators.items():
        if indicator in context_lower or f'"{indicator}"' in context_lower or f"'{indicator}'" in context_lower:
            method = http_method
            break
            
    return method

def add_unique_result(results, new_result):
    """添加唯一的结果，避免重复"""
    # 检查是否已存在相同URL和方法的结果
    for existing in results:
        if existing['url'] == new_result['url'] and existing['method'] == new_result['method']:
            # 如果新的参数更详细，更新参数
            if new_result['params'] and (not existing['params'] or 
                                        len(new_result['params']) > len(existing['params'])):
                existing['params'] = new_result['params']
            return  # 已存在，无需添加
    
    # 不存在相同结果，添加新结果
    results.append(new_result)

def classify_api_endpoint(url, method, context=""):
    """
    对API端点进行分类
    
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
    
    # 判断是否为常见的REST资源模式
    if re.search(r'/(?:api/v\d+/)?[a-z]+(?:/[a-z]+)*(?:/\d+)?$', url):
        return 'RESTful'
    
    # 检查PUT/DELETE/PATCH方法通常与RESTful API一起使用
    if method in ['PUT', 'DELETE', 'PATCH']:
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
