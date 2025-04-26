# -*- coding: utf-8 -*-
"""
JavaScript内容的API请求核心提取逻辑。
识别 RESTful, GraphQL, 和 WebSocket 端点。
(优化版本 v2)
"""

import re
import json
import logging

# --- 配置日志 ---
log = logging.getLogger(__name__)

# --- 预编译正则表达式以提高性能 ---

# WebSocket URL 模式
websocket_pattern = re.compile(
    r'new\s+WebSocket\s*\(\s*[\'"`](?P<url>(?:ws|wss)://[^\'"`]+)[\'"`]\s*\)',
    re.IGNORECASE
)

# GraphQL 端点模式
graphql_post_pattern = re.compile(
    r'(?:fetch|axios|ajax|http|request)\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]\s*,\s*\{[^}]*(?:method|type)\s*:\s*[\'"`]POST[\'"`]',
    re.IGNORECASE | re.DOTALL
)
graphql_method_post_pattern = re.compile(
    r'(?:axios|http|request|ajax)\.post\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
graphql_generic_url_pattern = re.compile(
    r'[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
gql_patterns = [graphql_post_pattern, graphql_method_post_pattern]

# RESTful API 模式
rest_url_method_patterns = [
    re.compile(r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    re.compile(
        r'axios\s*\(\s*\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method1>\w+)[\'"`]'
        r'|'
        r'method\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]'
        r')'
        r'[^}]*\}\s*\)',
        re.IGNORECASE | re.DOTALL
    ),
    re.compile(r'fetch\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]\s*,\s*\{[^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    re.compile(
        r'\$\.ajax\s*\(\s*\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*(?:type|method)\s*:\s*[\'"`](?P<method1>\w+)[\'"`]'
        r'|'
        r'(?:type|method)\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]'
        r')'
        r'[^}]*\}\s*\)',
        re.IGNORECASE | re.DOTALL
    ),
    re.compile(r'\$\.(?P<method>get|post)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    re.compile(
        r'\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method1>\w+)[\'"`]'
        r'|'
        r'method\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]'
        r')'
        r'[^}]*\}',
        re.IGNORECASE | re.DOTALL
    ),
    re.compile(r'(?:[a-zA-Z0-9_$]+\.)(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
]

# 参数模式
param_patterns = [
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*(\{.*?\})', re.IGNORECASE | re.DOTALL | re.MULTILINE),
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*(\[.*?\])', re.IGNORECASE | re.DOTALL | re.MULTILINE),
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)', re.IGNORECASE),
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*([\'"`].*?[\'"`])', re.IGNORECASE | re.DOTALL | re.MULTILINE),
    re.compile(r'JSON\.stringify\s*\(([\{\[].*?[\}\]])\)', re.IGNORECASE | re.DOTALL),
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(\{.*?\})', re.DOTALL | re.MULTILINE),
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(\[.*?\])', re.DOTALL | re.MULTILINE),
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)'),
]

# 简单相对 URL 模式 (推断 GET)
simple_rest_url_pattern = re.compile(
     r'[\'"`](?P<url>/(?!/)[^\'"\s?#]+(?:\?[^\'"\s#]*)?(?:#[^\'"\s]*)?\b(?<!\.(?:js|css|png|jpg|jpeg|gif|svg|html|htm|woff|woff2|ttf|eot|map|json|xml|txt|ico)))[\'"`]'
)

# 常见的非 API 文件扩展名
NON_API_EXTENSIONS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
                      '.html', '.htm', '.woff', '.woff2', '.ttf', '.eot',
                      '.map', '.json', '.xml', '.txt', '.ico')

# --- 辅助函数 ---

def _is_likely_api_url(url):
    """基础过滤，判断 URL 是否可能是 API 调用"""
    if not url or url == '/': return False
    if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:')): return False
    # 改进：允许更复杂的相对路径，但仍然排除纯粹的模块导入模式
    if re.match(r'^\.?\.?/[a-zA-Z0-9_./-]+$', url) and not re.search(r'api|v\d+', url, re.IGNORECASE): return False
    path_part = url.split('?')[0].split('#')[0].lower()
    if path_part.endswith(NON_API_EXTENSIONS): return False
    return True

def _parse_named_groups(match):
    """从匹配对象中提取 'method' 和 'url'"""
    group_dict = match.groupdict()
    method = group_dict.get('method') or group_dict.get('method1') or group_dict.get('method2')
    url = group_dict.get('url') or group_dict.get('url1') or group_dict.get('url2')
    return method.upper() if method else None, url.strip() if url else None

# --- 提取函数 ---

def extract_requests(js_content):
    """从 JavaScript 内容中提取潜在的 API 请求"""
    results = []
    found_signatures = set()
    match_positions = []

    # 步骤 1: WebSocket
    try:
        for match in websocket_pattern.finditer(js_content):
            url = match.group('url').strip()
            signature = ('WebSocket', 'WS', url)
            if url and signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'WebSocket', 'method': 'WS', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
        log.warning(f"正则表达式错误 (websocket_pattern): {e}")

    # 步骤 2: GraphQL POST
    for pattern in gql_patterns:
        try:
            for match in pattern.finditer(js_content):
                url = match.group('url').strip()
                signature = ('GraphQL', 'POST', url)
                if url and signature not in found_signatures:
                    found_signatures.add(signature)
                    match_positions.append({
                        'type': 'GraphQL', 'method': 'POST', 'url': url,
                        'match_start': match.start(), 'match_end': match.end()
                    })
        except re.error as e:
            log.warning(f"正则表达式错误 (graphql pattern {pattern.pattern}): {e}")

    # 步骤 3: 通用 GraphQL URL (假定 POST)
    try:
        for match in graphql_generic_url_pattern.finditer(js_content):
            url = match.group('url').strip()
            signature_post = ('GraphQL', 'POST', url)
            signature_other = next((s for s in found_signatures if s[0] == 'GraphQL' and s[2] == url), None)
            if url and signature_post not in found_signatures and not signature_other:
                found_signatures.add(signature_post)
                match_positions.append({
                    'type': 'GraphQL', 'method': 'POST', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
         log.warning(f"正则表达式错误 (graphql_generic_url_pattern): {e}")

    # 步骤 4: RESTful 请求
    for pattern in rest_url_method_patterns:
        try:
            for match in pattern.finditer(js_content):
                method, url = _parse_named_groups(match)
                if not method or not url or not _is_likely_api_url(url):
                    continue
                if any(pos['url'] == url and pos['type'] in ['GraphQL', 'WebSocket'] for pos in match_positions):
                    continue
                signature = ('RESTful', method, url)
                if signature not in found_signatures:
                    found_signatures.add(signature)
                    match_positions.append({
                        'type': 'RESTful', 'method': method, 'url': url,
                        'match_start': match.start(), 'match_end': match.end()
                    })
        except re.error as e:
            log.warning(f"正则表达式错误 (rest_url_method_pattern {pattern.pattern}): {e}")
        except IndexError:
             log.debug(f"索引错误处理RESTful模式匹配: {pattern.pattern}")

    # 步骤 5: 简单相对 URL (推断 GET)
    try:
        for match in simple_rest_url_pattern.finditer(js_content):
            url = match.group('url').strip()
            if any(pos['url'] == url for pos in match_positions):
                 continue
            method = "GET"
            signature = ('RESTful', method, url)
            if signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'RESTful', 'method': method, 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
        log.warning(f"正则表达式错误 (simple_rest_url_pattern): {e}")

    # --- 排序和参数查找 ---
    match_positions.sort(key=lambda x: x['match_start'])
    final_results_list = []
    processed_indices = set()

    for i, res in enumerate(match_positions):
        if i in processed_indices: continue
        params = None
        if res['type'] in ['RESTful', 'GraphQL']:
            best_param_match = None
            min_distance = float('inf')
            search_start = max(0, res['match_start'] - 150)
            next_match_start = float('inf')
            for j in range(i + 1, len(match_positions)):
                if match_positions[j]['type'] in ['RESTful', 'GraphQL']:
                    next_match_start = match_positions[j]['match_start']
                    break
            search_end = min(len(js_content), res['match_end'] + 500, next_match_start)
            context = js_content[search_start:search_end]
            match_relative_start = res['match_start'] - search_start

            for pattern in param_patterns:
                try:
                    for param_match in pattern.finditer(context):
                        distance = abs(param_match.start() - match_relative_start)
                        priority_distance = distance if param_match.start() >= match_relative_start else distance + 50
                        if priority_distance < min_distance:
                            potential_param = param_match.group(1)
                            if potential_param and potential_param.strip():
                                potential_param_strip = potential_param.strip()
                                if potential_param_strip.startswith(('{', '[')) or \
                                   potential_param_strip.startswith(('"', "'", "`")) or \
                                   re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$.]*$', potential_param_strip):
                                    if len(potential_param_strip) < 2000:
                                        min_distance = priority_distance
                                        best_param_match = potential_param_strip
                except re.error as e:
                    log.warning(f"正则表达式错误 (param_pattern {pattern.pattern}): {e}")
                except IndexError: continue
            params = best_param_match

        final_results_list.append({
            'type': res['type'], 'method': res['method'], 'url': res['url'], 'params': params
        })
        processed_indices.add(i)

    # --- 最终去重 ---
    unique_results = []
    seen_final = set()
    for item in final_results_list:
        param_repr = item.get('params')
        param_key = None
        if param_repr and isinstance(param_repr, str):
            try:
                # 尝试更健壮的 JSON 解析比较
                cleaned_param = param_repr.strip()
                cleaned_param = re.sub(r':\s*true\b', ': true', cleaned_param)
                cleaned_param = re.sub(r':\s*false\b', ': false', cleaned_param)
                cleaned_param = re.sub(r':\s*null\b', ': null', cleaned_param)
                cleaned_param = re.sub(r"'\s*:", '":', cleaned_param)
                cleaned_param = re.sub(r":\s*'", ': "', cleaned_param)
                cleaned_param = re.sub(r"'\s*([,}])", '"\1', cleaned_param)
                parsed_param = json.loads(cleaned_param)
                param_key = json.dumps(parsed_param, sort_keys=True, separators=(',', ':'))
            except (json.JSONDecodeError, TypeError):
                # 回退到简单比较
                param_key = tuple(sorted(param_repr.split()))
        else:
             param_key = param_repr

        item_tuple = (item['type'], item['method'], item['url'], param_key)
        if item_tuple not in seen_final:
            unique_results.append(item)
            seen_final.add(item_tuple)

    log.info(f"提取完成，找到 {len(unique_results)} 个唯一请求。")
    return unique_results
