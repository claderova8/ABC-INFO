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
    results = []
    
    # 匹配请求方式和URL的正则表达式模式
    # 包含各种常见的AJAX请求模式，如axios.get(), $.ajax(), fetch()等
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
        
        # 新增: Angular HttpClient模式
        r'this\.http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        r'http\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # 新增: Vue Axios/Resource模式
        r'this\.\$(?:http|axios|resource)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # 新增: 通用函数调用，URL作为参数
        r'(?:request|api|client|http)(?:Request|Call|Fetch)?\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        
        # 新增: React Query/SWR等模式
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
        r'use(?:Query|SWR|Request|Fetch)\s*\(\s*\[\s*[\'"](?P<url>[^\'"]*)[\'"](,|\))',
    ]
    
    # 新增: GraphQL请求模式
    graphql_patterns = [
        # Apollo Client
        r'(?:apolloClient|client)\.query\s*\(\s*\{[^}]*query\s*:\s*(?:gql|graphql)`(?P<query>[^`]*)`',
        r'(?:apolloClient|client)\.mutate\s*\(\s*\{[^}]*mutation\s*:\s*(?:gql|graphql)`(?P<query>[^`]*)`',
        # 通用GraphQL请求
        r'(?:graphql|gql)\s*`(?P<query>[^`]*)`',
        # 其他GraphQL客户端
        r'(?:request|fetch|post)\s*\(\s*[\'"](?P<url>[^\'"]*(?:graphql|gql)[^\'"]*)[\'"]',
    ]
    
    # 新增: WebSocket连接模式
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
        
        # 新增: GraphQL变量参数模式
        r'variables\s*:\s*(\{[^}{]*(?:\{[^}{]*\}[^}{]*)*\})',
    ]
    
    # 使用更通用的大括号查找策略 - 优化JSON对象参数识别
    # 该正则表达式匹配JSON对象的各种形式
    curl_bracket_pattern = r'\{\s*(?:["\']?[\w_]+["\']?\s*:\s*(?:["\'][^"\']*["\']|[-\d.]+|true|false|null|\[[^\]]*\]|\{[^{}]*\}|[\w.]+(?:\.\w+)+|\w+)(?:\s*,\s*["\']?[\w_]+["\']?\s*:\s*(?:["\'][^"\']*["\']|[-\d.]+|true|false|null|\[[^\]]*\]|\{[^{}]*\}|[\w.]+(?:\.\w+)+|\w+))*|["\']?\w+["\']?(?:\s*,\s*["\']?\w+["\']?)*)\s*\}'
    
    # 第一步：查找请求方法和URL
    for pattern in url_method_patterns:
        matches = re.finditer(pattern, js_content, re.IGNORECASE)
        for match in matches:
            method = match.group('method').upper()  # 将方法名转为大写
            url = match.group('url')
            
            # 忽略明显不是API的URL（例如完整的http链接、静态资源）
            if url.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.html')):
                continue
                
            # 提取这个请求周围的参数（查找上下文）
            start_pos = max(0, match.start() - 200)  # 向前查找200个字符
            end_pos = min(len(js_content), match.end() + 500)  # 向后查找500个字符
            context = js_content[start_pos:end_pos]
            
            params = None
            # 首先尝试使用精准的参数模式查找
            for param_pattern in param_patterns:
                param_matches = re.search(param_pattern, context, re.DOTALL)
                if param_matches:
                    params = param_matches.group(1)
                    # 清理和格式化参数
                    params = re.sub(r'\s+', ' ', params).strip()
                    break
            
            # 如果没找到，尝试通用的大括号查找 - 寻找附近的JSON对象
            if not params:
                # 查找附近的JSON对象 - 接口调用前后200个字符内查找JSON对象
                curl_matches = re.finditer(curl_bracket_pattern, context, re.DOTALL)
                closest_match = None
                min_distance = float('inf')
                match_position = match.start() - start_pos  # 请求在上下文中的相对位置
                
                for curl_match in curl_matches:
                    curl_start = curl_match.start()
                    distance = abs(match_position - curl_start)
                    # 只考虑相对接近调用的对象（100字符内）
                    if distance < 100 and distance < min_distance:
                        min_distance = distance
                        closest_match = curl_match
                
                if closest_match:
                    params = closest_match.group(0)
                    params = re.sub(r'\s+', ' ', params).strip()
            
            # 确定API类型
            api_type = classify_api_endpoint(url, method, context)
            
            # 添加到结果中
            results.append({
                'method': method,
                'url': url,
                'params': params,
                'api_type': api_type
            })
    
    # 第二步：提取GraphQL请求
    for pattern in graphql_patterns:
        matches = re.finditer(pattern, js_content, re.DOTALL)
        for match in matches:
            # 对于GraphQL请求，我们设置method为POST（默认）
            method = "POST"
            
            # 如果是具有URL的GraphQL请求
            if 'url' in match.groupdict():
                url = match.group('url')
            else:
                # 尝试从上下文中获取GraphQL端点URL
                start_pos = max(0, match.start() - 300)
                end_pos = min(len(js_content), match.end() + 100)
                context = js_content[start_pos:end_pos]
                
                # 尝试查找GraphQL端点URL
                url_match = re.search(r'(?:url|uri|endpoint)\s*:\s*[\'"]([^\'"]*(?:graphql|gql)[^\'"]*)[\'"]', context)
                if url_match:
                    url = url_match.group(1)
                else:
                    # 如果找不到明确的URL，使用通用GraphQL端点
                    url = "/graphql"
            
            # 获取GraphQL查询
            if 'query' in match.groupdict():
                query = match.group('query')
                params = f'{{"query": "{query.replace("`", "").replace('"', "\'")}"}}' 
            else:
                params = None
            
            # 添加到结果
            results.append({
                'method': method,
                'url': url,
                'params': params,
                'api_type': 'GraphQL'
            })
    
    # 第三步：提取WebSocket连接
    for pattern in websocket_patterns:
        matches = re.finditer(pattern, js_content)
        for match in matches:
            url = match.group('url')
            
            # 添加到结果
            results.append({
                'method': 'CONNECT',  # WebSocket使用CONNECT作为方法标识
                'url': url,
                'params': None,
                'api_type': 'WebSocket'
            })
    
    # 第四步：额外查找更多的API调用模式 - 直接查找URL并推断其上下文
    url_pattern = r'[\'"](?P<url>/[^\'"/][^\'"]*)[\'"]\s*(?:[,;)\]]|$)'
    url_matches = re.finditer(url_pattern, js_content)
    for url_match in url_matches:
        url = url_match.group('url')
        
        # 忽略明显不是API的URL
        if url.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.html')):
            continue
        
        # 查找这个URL附近的上下文
        start_pos = max(0, url_match.start() - 200)
        end_pos = min(len(js_content), url_match.end() + 200)
        context = js_content[start_pos:end_pos]
        
        # 根据上下文尝试确定请求方法
        method = "GET"  # 默认为GET
        method_indicators = {
            'post': 'POST',
            'put': 'PUT',
            'delete': 'DELETE',
            'patch': 'PATCH'
        }
        
        for indicator, http_method in method_indicators.items():
            if indicator in context.lower() or f'"{indicator}"' in context.lower() or f"'{indicator}'" in context.lower():
                method = http_method
                break
        
        # 查找参数
        params = None
        # 尝试所有参数模式
        for param_pattern in param_patterns:
            param_matches = re.search(param_pattern, context, re.DOTALL)
            if param_matches:
                params = param_matches.group(1)
                params = re.sub(r'\s+', ' ', params).strip()
                break
        
        # 如果没找到，尝试通用的大括号查找
        if not params:
            curl_matches = re.finditer(curl_bracket_pattern, context, re.DOTALL)
            closest_match = None
            min_distance = float('inf')
            match_position = url_match.start() - start_pos
            
            for curl_match in curl_matches:
                curl_start = curl_match.start()
                distance = abs(match_position - curl_start)
                if distance < 100 and distance < min_distance:  # 只考虑100字符内的参数对象
                    min_distance = distance
                    closest_match = curl_match
            
            if closest_match:
                params = closest_match.group(0)
                params = re.sub(r'\s+', ' ', params).strip()
        
        # 确定API类型
        api_type = classify_api_endpoint(url, method, context)
        
        # 判断是否已经有相同的请求（去重）
        is_duplicate = False
        for result in results:
            if result['url'] == url and result['method'] == method:
                is_duplicate = True
                # 如果新找到的参数更好（更详细），则更新
                if params and (not result['params'] or len(params) > len(result['params'])):
                    result['params'] = params
                break
        
        # 如果不是重复的，添加到结果
        if not is_duplicate:
            results.append({
                'method': method,
                'url': url,
                'params': params,
                'api_type': api_type
            })
    
    return results

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
    # 检查是否为GraphQL端点
    if '/graphql' in url.lower() or '/gql' in url.lower() or 'graphql' in context.lower():
        return 'GraphQL'
    
    # 检查是否为WebSocket连接
    if url.startswith(('ws://', 'wss://')) or 'websocket' in context.lower() or 'socket.io' in context.lower():
        return 'WebSocket'
    
    # 检查是否为gRPC或其他RPC调用
    if '/rpc' in url.lower() or 'rpc' in context.lower() or '/jsonrpc' in url.lower():
        return 'RPC'
    
    # 判断是否为常见的REST资源模式 (例如 /users/{id} 等)
    if re.search(r'/(?:api/v\d+/)?[a-z]+(?:/[a-z]+)*(?:/\d+)?$', url):
        return 'RESTful'
    
    # 检查PUT/DELETE/PATCH方法通常与RESTful API一起使用
    if method in ['PUT', 'DELETE', 'PATCH']:
        return 'RESTful'
    
    # 对于更复杂的URL，进一步判断
    if '/api/' in url:
        # 检查是否带有版本号 (例如 /api/v1/)
        if re.search(r'/api/v\d+/', url):
            return 'RESTful'
        # 检查是否是典型的REST资源URLs模式
        if re.search(r'/api/[a-z_]+(?:/\d+)?(?:/[a-z_]+)*', url):
            return 'RESTful'
    
    # 如果没有明确的匹配，默认为HTTP API
    return 'HTTP API'
