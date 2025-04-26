# -*- coding: utf-8 -*-
"""
JavaScript内容的API请求核心提取逻辑。
识别 RESTful, GraphQL, 和 WebSocket 端点。
"""

import re

# --- 预编译正则表达式以提高性能 ---

# WebSocket URL 模式
# 匹配: new WebSocket('ws://...') 或 new WebSocket("wss://...")
websocket_pattern = re.compile(
    r'new\s+WebSocket\s*\(\s*[\'"`](?P<url>(?:ws|wss)://[^\'"`]+)[\'"`]\s*\)',
    re.IGNORECASE
)

# GraphQL 端点模式 (通常是 POST 到 /graphql 或类似路径)
# 模式1: 显式 fetch/axios POST 到 graphql URL
graphql_post_pattern = re.compile(
    r'(?:fetch|axios|ajax|http|request)\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]\s*,\s*\{[^}]*(?:method|type)\s*:\s*[\'"`]POST[\'"`]',
    re.IGNORECASE | re.DOTALL
)
# 模式2: 包含 'graphql' 的 URL 与 POST 方法调用一起使用
graphql_method_post_pattern = re.compile(
    r'(?:axios|http|request|ajax)\.post\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
# 模式3: 包含 'graphql' 的通用 URL - 很大可能是 POST，但需检查上下文
graphql_generic_url_pattern = re.compile(
    r'[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
# GraphQL 相关模式列表
gql_patterns = [graphql_post_pattern, graphql_method_post_pattern]


# 通用 RESTful API 模式 (排除已匹配为 GraphQL/WS 的)
# 涵盖常见库 (axios, fetch, jQuery) 和通用模式
rest_url_method_patterns = [
    # Axios: axios.get/post/put/delete/patch('/api/data', config)
    re.compile(r'(?:axios|http|request|ajax)\.(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # Axios: axios({ method: '...', url: '...' })
    re.compile(r'axios\s*\(\s*\{[^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE | re.DOTALL),
    re.compile(r'axios\s*\(\s*\{[^}]*url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    # Fetch: fetch('/api/data', { method: 'POST', ... })
    re.compile(r'fetch\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]\s*,\s*\{[^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    # jQuery Ajax: $.ajax({ url: '/api/data', type: 'POST', ... }) or $.get/post('/api', ...)
    re.compile(r'\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`][^}]*(?:type|method)\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    re.compile(r'\$\.ajax\s*\(\s*\{[^}]*(?:type|method)\s*:\s*[\'"`](?P<method>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE | re.DOTALL),
    re.compile(r'\$\.(?P<method>get|post)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # 通用模式: { method: '...', url: '...' } 或 someObj.post('/url', ...)
    re.compile(r'method\s*:\s*[\'"`](?P<method>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE | re.DOTALL),
    re.compile(r'url\s*:\s*[\'"`](?P<url>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    # 匹配 obj.get(...) 但尝试避免简单的函数调用如 element.get(...)
    re.compile(r'(?:[a-zA-Z0-9_$]+\.)?(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
]

# 用于查找参数的模式 (通常在 URL/方法定义附近)
# 增加了对 GraphQL 'query' 和 'variables' 的支持
param_patterns = [
    # 显式键: data: {...}, params: {...}, body: {...}, json: {...}, query: "...", variables: {...}
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*(\{.*?\})', re.IGNORECASE | re.DOTALL | re.MULTILINE), # 对象字面量
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*(\[.*?\])', re.IGNORECASE | re.DOTALL | re.MULTILINE), # 数组字面量
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)', re.IGNORECASE), # 变量名 (可能嵌套)
    re.compile(r'(?:data|params|body|json|query|variables)\s*:\s*([\'"`].*?[\'"`])', re.IGNORECASE | re.DOTALL | re.MULTILINE), # 字符串字面量 (例如 GraphQL 查询字符串)
    # JSON.stringify({...} or JSON.stringify([...]))
    re.compile(r'JSON\.stringify\s*\(([\{\[].*?[\}\]])\)', re.IGNORECASE | re.DOTALL),
    # 对象/数组/变量字面量作为 URL 后的下一个参数: get('/url', {...})
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(\{.*?\})', re.DOTALL | re.MULTILINE),
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*(\[.*?\])', re.DOTALL | re.MULTILINE),
    re.compile(r'[\'"`][^\'"`]+[\'"`]\s*,\s*([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)'), # 变量名
]

# 查找简单相对 URL 的模式 (以 / 开头)，可能指向 API 端点
# 排除常见文件扩展名。用于推断 REST GET 请求。
simple_rest_url_pattern = re.compile(
     r'[\'"`](?P<url>/(?!/)[^\'"\s?#]+\b(?<!\.(?:js|css|png|jpg|jpeg|gif|svg|html|htm|woff|woff2|ttf|eot|map|json|xml|txt|ico)))[\'"`]'
)

# --- 提取函数 ---

def extract_requests(js_content):
    """
    从 JavaScript 内容中提取潜在的 HTTP、GraphQL 和 WebSocket 请求。

    参数:
        js_content: 包含 JavaScript 代码的字符串。

    返回:
        一个字典列表，每个字典代表一个找到的请求，
        包含 'type' (类型), 'method' (方法), 'url' (地址), 和 'params' (参数，原始字符串或 None)。
        如果未找到请求，则返回空列表。
    """
    results = []
    # 使用集合跟踪找到的唯一签名 (类型, 方法, URL)，以避免重复处理步骤
    found_signatures = set()

    # --- 提取逻辑 ---

    # 步骤 1: 查找 WebSocket 连接
    try:
        for match in websocket_pattern.finditer(js_content):
            url = match.group('url').strip()
            signature = ('WebSocket', 'WS', url) # 类型, 方法, URL
            if url and signature not in found_signatures:
                found_signatures.add(signature)
                results.append({
                    'type': 'WebSocket',
                    'method': 'WS', # 使用 'WS' 表示 WebSocket 连接
                    'url': url,
                    'params': None, # 参数通常不以相同方式适用于 WebSocket
                    'match_start': match.start(), # 记录匹配位置，用于后续参数查找
                    'match_end': match.end()
                })
    except re.error as e:
        # print(f"正则表达式错误 (websocket_pattern): {e}") # 可选的调试信息
        pass # 忽略此模式的错误并继续

    # 步骤 2: 查找显式的 GraphQL POST 请求
    for pattern in gql_patterns:
        try:
            for match in pattern.finditer(js_content):
                url = match.group('url').strip()
                signature = ('GraphQL', 'POST', url)
                if url and signature not in found_signatures:
                    found_signatures.add(signature)
                    results.append({
                        'type': 'GraphQL',
                        'method': 'POST',
                        'url': url,
                        'params': None, # 参数占位符
                        'match_start': match.start(),
                        'match_end': match.end()
                    })
        except re.error as e:
            # print(f"正则表达式错误 (graphql pattern): {e}") # 可选的调试信息
            continue # 跳过导致错误的模式

    # 步骤 3: 查找通用的 GraphQL URL 并检查上下文 (很可能是 POST)
    try:
        for match in graphql_generic_url_pattern.finditer(js_content):
            url = match.group('url').strip()
            # 如果尚未捕获，则假定为 POST
            signature = ('GraphQL', 'POST', url)
            if url and signature not in found_signatures:
                # 如果需要，可以双重检查上下文以查找除 POST 之外的显式方法
                # 为简单起见，我们假设通用的 /graphql URL 是 POST
                found_signatures.add(signature)
                results.append({
                    'type': 'GraphQL',
                    'method': 'POST',
                    'url': url,
                    'params': None, # 参数占位符
                    'match_start': match.start(),
                    'match_end': match.end()
                })
    except re.error as e:
         # print(f"正则表达式错误 (graphql_generic_url_pattern): {e}") # 可选的调试信息
         pass

    # 步骤 4: 查找显式的 RESTful 请求 (尚未识别为 GraphQL/WS 的)
    for pattern in rest_url_method_patterns:
        try:
            for match in pattern.finditer(js_content):
                # 尝试获取 method 和 url, 如果模式不匹配这些组名，会抛出 IndexError
                try:
                    method = match.group('method').upper()
                    url = match.group('url').strip()
                except IndexError:
                    continue # 跳过没有 'method' 或 'url' 组的匹配

                # --- 基本 URL 验证/过滤 ---
                # 跳过绝对 URL、根路径、data URI 或 JS 代码片段
                if not url or url.startswith(('http://', 'https://', '//', 'data:', 'javascript:')) or url == '/':
                    continue
                # 跳过看起来像文件路径的 URL (常见于 import/require)
                if re.match(r'^\.?\.?/[a-zA-Z0-9_./-]+$', url):
                     continue
                # 跳过以常见非 API 文件扩展名结尾的 URL (检查 ? 之前的部分)
                if url.split('?')[0].lower().endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.html', '.htm', '.woff', '.woff2', '.ttf', '.eot', '.map', '.json', '.xml', '.txt', '.ico')):
                     continue

                # 检查此 URL 是否已被捕获为 GraphQL/WS
                if any(r['url'] == url and r['type'] in ['GraphQL', 'WebSocket'] for r in results):
                    continue

                # --- 添加到结果 ---
                signature = ('RESTful', method, url)
                if signature not in found_signatures:
                    found_signatures.add(signature)
                    results.append({
                        'type': 'RESTful',
                        'method': method,
                        'url': url,
                        'params': None, # 参数占位符
                        'match_start': match.start(),
                        'match_end': match.end()
                    })
        except re.error as e:
            # print(f"正则表达式错误 (rest_url_method_pattern): {e}") # 可选的调试信息
            continue # 跳过导致错误的模式

    # 步骤 5: 查找简单的相对 URL 并推断 RESTful GET 方法
    try:
        for match in simple_rest_url_pattern.finditer(js_content):
            url = match.group('url').strip()

            # 检查此 URL 是否已被其他模式捕获
            if any(r['url'] == url for r in results):
                 continue

            # 对于未被其他方式捕获的简单相对路径，假定为 GET
            method = "GET"
            signature = ('RESTful', method, url)

            if signature not in found_signatures:
                found_signatures.add(signature)
                results.append({
                    'type': 'RESTful',
                    'method': method,
                    'url': url,
                    'params': None, # 参数占位符
                    'match_start': match.start(),
                    'match_end': match.end()
                })
    except re.error as e:
        # print(f"正则表达式错误 (simple_rest_url_pattern): {e}") # 可选的调试信息
        pass

    # 步骤 6: 为每个已识别的请求 (RESTful 和 GraphQL) 查找参数
    final_results_list = []
    for res in results:
        # 参数提取与 WebSocket 关系不大
        if res['type'] in ['RESTful', 'GraphQL']:
            params = None
            # 在原始 URL/方法匹配的附近查找参数
            # 调整了搜索窗口以适应可能更大的 GraphQL 查询/变更
            search_start = max(0, res['match_start'] - 150) # 向前查找 150 字符
            search_end = min(len(js_content), res['match_end'] + 500) # 向后查找 500 字符
            context = js_content[search_start:search_end] # 获取上下文代码片段

            best_param_match = None
            min_distance = float('inf')
            # 原始匹配在上下文窗口中的相对起始位置
            match_relative_start = res['match_start'] - search_start

            # 遍历所有参数模式
            for pattern in param_patterns:
                try:
                    # 在上下文中查找所有潜在的参数匹配项
                    for param_match in pattern.finditer(context):
                        # 计算参数匹配位置与原始 URL/方法匹配位置的距离
                        distance = abs(param_match.start() - match_relative_start)

                        # 优先考虑更近的匹配项，略微偏好在 URL/方法定义之后的匹配项
                        # 如果参数出现在 URL/方法之前，增加一点距离惩罚
                        priority_distance = distance if param_match.start() >= match_relative_start else distance + 50

                        # 如果当前匹配比已找到的最佳匹配更近
                        if priority_distance < min_distance:
                            # 第 1 组捕获应该包含实际的参数内容
                            potential_param = param_match.group(1)
                            if potential_param and potential_param.strip(): # 确保参数非空
                                potential_param_strip = potential_param.strip()
                                # 基本验证：检查它是否看起来像对象、数组、变量或字符串字面量
                                if potential_param_strip.startswith(('{', '[')) or \
                                   potential_param_strip.startswith(('"', "'", "`")) or \
                                   re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$.]*$', potential_param_strip):

                                    # 避免匹配可能不是参数的过长字符串 (限制参数长度)
                                    if len(potential_param_strip) < 2000:
                                        min_distance = priority_distance
                                        best_param_match = potential_param_strip # 更新最佳匹配
                except re.error as e:
                    # print(f"正则表达式错误 (param_pattern): {e}") # 可选的调试信息
                    continue # 跳过导致错误的模式
                except IndexError:
                    # 模式可能没有第 1 组捕获 (当前模式不应发生)
                    continue

            res['params'] = best_param_match # 将找到的最佳参数（或 None）赋给结果

        # 将处理后的结果添加到最终列表，移除临时键 ('match_start', 'match_end')
        final_results_list.append({
            'type': res['type'],
            'method': res['method'],
            'url': res['url'],
            'params': res.get('params') # 使用 .get 以防万一，尽管 'params' 应该存在
        })

    # --- 最终去重 ---
    # 根据类型、方法、URL 和参数移除完全重复的项
    unique_results = []
    seen_final = set() # 用于存储已见过的最终结果签名
    for item in final_results_list:
        # 创建一个元组表示以检查重复项
        # 在元组中正确处理 None 参数
        # 对参数进行轻微规范化以进行比较 (例如，移除空格或排序键，这里简化为排序分割后的词)
        param_repr = item.get('params')
        # 将参数字符串按空格分割并排序，如果参数存在且为字符串，否则使用原始参数（可能为None）
        param_key = tuple(sorted(param_repr.split())) if param_repr and isinstance(param_repr, str) else param_repr

        # 创建包含类型、方法、URL 和规范化参数的元组签名
        item_tuple = (item['type'], item['method'], item['url'], param_key)

        # 如果此签名未见过
        if item_tuple not in seen_final:
            unique_results.append(item) # 添加到唯一结果列表
            seen_final.add(item_tuple) # 将签名添加到已见集合

    return unique_results # 返回去重后的结果列表
