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
        包含提取出的请求信息的列表，每项包含method(请求方法)、url和params(请求参数)
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
            
            # 添加到结果中
            results.append({
                'method': method,
                'url': url,
                'params': params
            })
    
    # 第二步：额外查找更多的API调用模式 - 直接查找URL并推断其上下文
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
                'params': params
            })
    
    return results