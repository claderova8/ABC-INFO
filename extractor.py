# -*- coding: utf-8 -*-
"""
JavaScript内容的API请求核心提取逻辑。
识别 RESTful, GraphQL, 和 WebSocket 端点。
(优化版本)
"""

import re
import json
import logging # 使用日志记录代替打印调试信息

# --- 配置日志 ---
# 可以根据需要调整日志级别和格式
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# --- 预编译正则表达式以提高性能 ---

# WebSocket URL 模式
# 匹配: new WebSocket('ws://...') 或 new WebSocket("wss://...")
# 注意: 对于URL内部包含引号的情况，此模式可能不够健壮
websocket_pattern = re.compile(
    r'new\s+WebSocket\s*\(\s*[\'"`](?P<url>(?:ws|wss)://[^\'"`]+)[\'"`]\s*\)',
    re.IGNORECASE
)

# GraphQL 端点模式 (通常是 POST 到 /graphql 或类似路径)
# 模式1: 显式 fetch/axios/ajax 等 POST 到 graphql URL
graphql_post_pattern = re.compile(
    r'(?:fetch|axios|ajax|http|request)\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]\s*,\s*\{[^}]*(?:method|type)\s*:\s*[\'"`]POST[\'"`]',
    re.IGNORECASE | re.DOTALL
)
# 模式2: 包含 'graphql' 的 URL 与特定库的 POST 方法调用一起使用
graphql_method_post_pattern = re.compile(
    r'(?:axios|http|request|ajax)\.post\s*\(\s*[\'"`](?P<url>[^\'"`]*?/graphql[^\'"`]*)[\'"`]',
    re.IGNORECASE
)
# 模式3: 包含 'graphql' 的通用 URL - 可能需要结合上下文判断方法 (默认假定 POST)
# 注意: 此模式较通用，可能匹配非API链接，依赖后续过滤
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
    # Axios: axios({ url: '...', method: '...' }) 或 axios({ method: '...', url: '...' }) - 合并模式
    re.compile(
        r'axios\s*\(\s*\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method1>\w+)[\'"`]' # url first
        r'|'
        r'method\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]' # method first
        r')'
        r'[^}]*\}\s*\)',
        re.IGNORECASE | re.DOTALL
    ),
    # Fetch: fetch('/api/data', { method: 'POST', ... })
    re.compile(r'fetch\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]\s*,\s*\{[^}]*method\s*:\s*[\'"`](?P<method>\w+)[\'"`]', re.IGNORECASE | re.DOTALL),
    # jQuery Ajax: $.ajax({ url: '/api/data', type/method: 'POST', ... }) - 合并模式
    re.compile(
        r'\$\.ajax\s*\(\s*\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*(?:type|method)\s*:\s*[\'"`](?P<method1>\w+)[\'"`]' # url first
        r'|'
        r'(?:type|method)\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]' # type/method first
        r')'
        r'[^}]*\}\s*\)',
        re.IGNORECASE | re.DOTALL
    ),
    # jQuery Ajax: $.get/post('/api', ...)
    re.compile(r'\$\.(?P<method>get|post)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
    # 通用模式: { url: '...', method: '...' } 或 { method: '...', url: '...' } - 合并模式
    re.compile(
        r'\{[^}]*'
        r'(?:'
        r'url\s*:\s*[\'"`](?P<url1>[^\'"`]+)[\'"`][^}]*method\s*:\s*[\'"`](?P<method1>\w+)[\'"`]' # url first
        r'|'
        r'method\s*:\s*[\'"`](?P<method2>\w+)[\'"`][^}]*url\s*:\s*[\'"`](?P<url2>[^\'"`]+)[\'"`]' # method first
        r')'
        r'[^}]*\}',
        re.IGNORECASE | re.DOTALL
    ),
    # 通用模式: 匹配 obj.get(...) 但尝试避免简单的函数调用如 element.get(...)
    # 注意: 此模式可能误报，(e.g., `myString.get(index)`)，需要依赖后续过滤或更复杂的上下文分析
    re.compile(r'(?:[a-zA-Z0-9_$]+\.)(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"`](?P<url>[^\'"`]+)[\'"`]', re.IGNORECASE),
]

# 用于查找参数的模式 (通常在 URL/方法定义附近)
# 增加了对 GraphQL 'query' 和 'variables' 的支持
# 注意: 对象/数组的匹配使用非贪婪 .*?，对于复杂嵌套可能不完美
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
# 增加了对查询参数和片段标识符的考虑
simple_rest_url_pattern = re.compile(
     r'[\'"`](?P<url>/(?!/)[^\'"\s?#]+(?:\?[^\'"\s#]*)?(?:#[^\'"\s]*)?\b(?<!\.(?:js|css|png|jpg|jpeg|gif|svg|html|htm|woff|woff2|ttf|eot|map|json|xml|txt|ico)))[\'"`]'
)

# 常见的非 API 文件扩展名 (用于过滤)
NON_API_EXTENSIONS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
                      '.html', '.htm', '.woff', '.woff2', '.ttf', '.eot',
                      '.map', '.json', '.xml', '.txt', '.ico')

# --- 辅助函数 ---

def _is_likely_api_url(url):
    """基于 URL 格式和常见模式判断是否可能是 API URL（基础过滤）"""
    if not url or url == '/':
        return False
    # 跳过绝对 URL、data URI 或 JS 代码片段
    if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:')):
        return False
    # 跳过看起来像文件路径的 URL (常见于 import/require)
    # 改进：允许更复杂的相对路径，但仍然排除纯粹的模块导入模式
    if re.match(r'^\.?\.?/[a-zA-Z0-9_./-]+$', url) and not re.search(r'api|v\d+', url, re.IGNORECASE):
         return False
    # 跳过以常见非 API 文件扩展名结尾的 URL (检查 ? 和 # 之前的部分)
    path_part = url.split('?')[0].split('#')[0].lower()
    if path_part.endswith(NON_API_EXTENSIONS):
         return False
    return True

def _parse_named_groups(match):
    """从匹配对象中提取 'method' 和 'url'，处理合并后的模式"""
    group_dict = match.groupdict()
    method = group_dict.get('method') or group_dict.get('method1') or group_dict.get('method2')
    url = group_dict.get('url') or group_dict.get('url1') or group_dict.get('url2')
    return method.upper() if method else None, url.strip() if url else None


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
    # 记录所有匹配的位置，以便后续参数查找
    match_positions = []

    # --- 提取逻辑 ---

    # 步骤 1: 查找 WebSocket 连接
    try:
        for match in websocket_pattern.finditer(js_content):
            url = match.group('url').strip()
            signature = ('WebSocket', 'WS', url) # 类型, 方法, URL
            if url and signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'WebSocket', 'method': 'WS', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
        logging.warning(f"正则表达式错误 (websocket_pattern): {e}")
        pass # 忽略此模式的错误并继续

    # 步骤 2: 查找显式的 GraphQL POST 请求
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
            logging.warning(f"正则表达式错误 (graphql pattern {pattern.pattern}): {e}")
            continue # 跳过导致错误的模式

    # 步骤 3: 查找通用的 GraphQL URL 并检查上下文 (很可能是 POST)
    try:
        for match in graphql_generic_url_pattern.finditer(js_content):
            url = match.group('url').strip()
            # 如果尚未捕获，则假定为 POST
            signature_post = ('GraphQL', 'POST', url)
            # 检查是否已被其他方法捕获 (例如 GET /graphql)
            signature_other = next((s for s in found_signatures if s[0] == 'GraphQL' and s[2] == url), None)

            if url and signature_post not in found_signatures and not signature_other:
                # 为简单起见，我们假设通用的 /graphql URL 是 POST
                found_signatures.add(signature_post)
                match_positions.append({
                    'type': 'GraphQL', 'method': 'POST', 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
         logging.warning(f"正则表达式错误 (graphql_generic_url_pattern): {e}")
         pass

    # 步骤 4: 查找显式的 RESTful 请求 (尚未识别为 GraphQL/WS 的)
    for pattern in rest_url_method_patterns:
        try:
            for match in pattern.finditer(js_content):
                method, url = _parse_named_groups(match)

                if not method or not url: # 跳过无效匹配
                    continue

                # --- 基本 URL 验证/过滤 ---
                if not _is_likely_api_url(url):
                    continue

                # 检查此 URL 是否已被捕获为 GraphQL/WS
                if any(pos['url'] == url and pos['type'] in ['GraphQL', 'WebSocket'] for pos in match_positions):
                    continue

                # --- 添加到结果 ---
                signature = ('RESTful', method, url)
                if signature not in found_signatures:
                    found_signatures.add(signature)
                    match_positions.append({
                        'type': 'RESTful', 'method': method, 'url': url,
                        'match_start': match.start(), 'match_end': match.end()
                    })
        except re.error as e:
            logging.warning(f"正则表达式错误 (rest_url_method_pattern {pattern.pattern}): {e}")
            continue # 跳过导致错误的模式
        except IndexError:
             # _parse_named_groups 应该处理这个问题，但以防万一
             logging.debug(f"索引错误处理RESTful模式匹配: {pattern.pattern}")
             continue

    # 步骤 5: 查找简单的相对 URL 并推断 RESTful GET 方法
    try:
        for match in simple_rest_url_pattern.finditer(js_content):
            url = match.group('url').strip()

            # 检查此 URL 是否已被其他模式捕获
            if any(pos['url'] == url for pos in match_positions):
                 continue

            # 对于未被其他方式捕获的简单相对路径，假定为 GET
            method = "GET"
            signature = ('RESTful', method, url)

            if signature not in found_signatures:
                found_signatures.add(signature)
                match_positions.append({
                    'type': 'RESTful', 'method': method, 'url': url,
                    'match_start': match.start(), 'match_end': match.end()
                })
    except re.error as e:
        logging.warning(f"正则表达式错误 (simple_rest_url_pattern): {e}")
        pass

    # --- 排序匹配项 ---
    # 按起始位置排序，以便按顺序处理参数查找
    match_positions.sort(key=lambda x: x['match_start'])

    # --- 处理参数查找和最终结果构建 ---
    final_results_list = []
    processed_indices = set() # 跟踪已处理的匹配项索引

    # 步骤 6: 为每个已识别的请求 (RESTful 和 GraphQL) 查找参数
    for i, res in enumerate(match_positions):
        if i in processed_indices:
            continue

        params = None
        # 参数提取与 WebSocket 关系不大
        if res['type'] in ['RESTful', 'GraphQL']:
            best_param_match = None
            min_distance = float('inf')

            # 确定搜索窗口
            # 窗口开始：当前匹配开始位置往前 N 个字符
            search_start = max(0, res['match_start'] - 150)
            # 窗口结束：当前匹配结束位置往后 M 个字符，或者下一个 API 匹配开始的位置（取较小者），以避免参数匹配到下一个 API 调用
            next_match_start = float('inf')
            for j in range(i + 1, len(match_positions)):
                if match_positions[j]['type'] in ['RESTful', 'GraphQL']: # 只考虑可能带参数的下一个匹配
                    next_match_start = match_positions[j]['match_start']
                    break
            search_end = min(len(js_content), res['match_end'] + 500, next_match_start)

            context = js_content[search_start:search_end]
            match_relative_start = res['match_start'] - search_start

            # 遍历所有参数模式
            for pattern in param_patterns:
                try:
                    for param_match in pattern.finditer(context):
                        # 计算参数匹配位置与原始 URL/方法匹配位置的距离
                        distance = abs(param_match.start() - match_relative_start)
                        # 优先考虑更近的匹配项，略微偏好在 URL/方法定义之后的匹配项
                        priority_distance = distance if param_match.start() >= match_relative_start else distance + 50

                        if priority_distance < min_distance:
                            potential_param = param_match.group(1)
                            if potential_param and potential_param.strip():
                                potential_param_strip = potential_param.strip()
                                # 基本验证：检查它是否看起来像对象、数组、变量或字符串字面量
                                if potential_param_strip.startswith(('{', '[')) or \
                                   potential_param_strip.startswith(('"', "'", "`")) or \
                                   re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$.]*$', potential_param_strip):
                                    # 避免匹配可能不是参数的过长字符串
                                    if len(potential_param_strip) < 2000:
                                        min_distance = priority_distance
                                        best_param_match = potential_param_strip
                except re.error as e:
                    logging.warning(f"正则表达式错误 (param_pattern {pattern.pattern}): {e}")
                    continue
                except IndexError:
                    continue # 模式可能没有捕获组

            params = best_param_match # 将找到的最佳参数（或 None）赋给结果

        # 添加到最终列表
        final_results_list.append({
            'type': res['type'],
            'method': res['method'],
            'url': res['url'],
            'params': params
        })
        processed_indices.add(i)


    # --- 最终去重 ---
    # 根据类型、方法、URL 和参数移除完全重复的项
    unique_results = []
    seen_final = set() # 用于存储已见过的最终结果签名

    for item in final_results_list:
        param_repr = item.get('params')
        param_key = None

        if param_repr and isinstance(param_repr, str):
            # 尝试将参数解析为 JSON 以进行更健壮的比较
            # 注意：这可能因包含 JS 表达式而失败
            try:
                # 简单的清理尝试，可能不足以处理所有 JS 表达式
                cleaned_param = param_repr.strip()
                # 尝试替换常见的 JS 布尔值和 null 为 JSON 等效项
                cleaned_param = re.sub(r':\s*true\b', ': true', cleaned_param)
                cleaned_param = re.sub(r':\s*false\b', ': false', cleaned_param)
                cleaned_param = re.sub(r':\s*null\b', ': null', cleaned_param)
                # 简单的引号处理（可能不完善）
                cleaned_param = re.sub(r"'\s*:", '":', cleaned_param) # key
                cleaned_param = re.sub(r":\s*'", ': "', cleaned_param) # value start
                cleaned_param = re.sub(r"'\s*([,}])", '"\1', cleaned_param) # value end

                parsed_param = json.loads(cleaned_param)
                # 对解析后的对象进行规范化表示（例如，排序后的 JSON 字符串）
                param_key = json.dumps(parsed_param, sort_keys=True, separators=(',', ':'))
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败或不是字符串，回退到基于分割和排序的简单规范化
                # 这种方法对于键顺序不同或空格不同的相同结构无法识别为重复
                param_key = tuple(sorted(param_repr.split()))
        else:
             # 如果参数为 None 或非字符串，直接使用
             param_key = param_repr


        # 创建包含类型、方法、URL 和规范化参数的元组签名
        item_tuple = (item['type'], item['method'], item['url'], param_key)

        # 如果此签名未见过
        if item_tuple not in seen_final:
            unique_results.append(item) # 添加到唯一结果列表
            seen_final.add(item_tuple) # 将签名添加到已见集合

    logging.info(f"提取完成，找到 {len(unique_results)} 个唯一请求。")
    return unique_results # 返回去重后的结果列表
