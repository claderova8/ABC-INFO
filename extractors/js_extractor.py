# -*- coding: utf-8 -*-
"""
JavaScript API提取器模块 (基于 AST)
功能：从JavaScript AST中提取HTTP API请求信息
"""
import json
import logging
from utils.ast_parser import parse_js_to_ast # 导入 AST 解析器

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- AST 辅助函数 ---

def get_node_value(node):
    """尝试从 AST 节点获取静态值 (字符串, 数字, 布尔, null)"""
    if not node:
        return None
    if node['type'] == 'Literal':
        return node.get('value') # Esprima 直接提供 value
    # 可以扩展处理 TemplateLiteral 等
    return None

def get_identifier_name(node):
    """获取标识符节点的名称"""
    if node and node['type'] == 'Identifier':
        return node.get('name')
    return None

def get_member_expression_string(node):
    """将成员表达式转换为点分隔的字符串 (e.g., axios.get)"""
    if not node or node['type'] != 'MemberExpression':
        return None
    obj = node.get('object')
    prop = node.get('property')

    prop_name = get_identifier_name(prop)
    if not prop_name:
        return None # 无法解析属性名

    if obj['type'] == 'Identifier':
        return f"{get_identifier_name(obj)}.{prop_name}"
    elif obj['type'] == 'MemberExpression':
        base = get_member_expression_string(obj)
        return f"{base}.{prop_name}" if base else None
    elif obj['type'] == 'ThisExpression':
         return f"this.{prop_name}"
    # 可以扩展处理其他对象类型
    return None

def extract_object_literal(node):
    """从 ObjectExpression AST 节点提取简单的键值对"""
    if not node or node['type'] != 'ObjectExpression':
        return None
    params = {}
    for prop in node.get('properties', []):
        if prop['type'] == 'Property':
            key_node = prop.get('key')
            value_node = prop.get('value')

            # 获取键名 (可以是 Identifier 或 Literal)
            key_name = None
            if key_node['type'] == 'Identifier':
                key_name = key_node.get('name')
            elif key_node['type'] == 'Literal':
                key_name = str(key_node.get('value')) # 确保是字符串

            if key_name:
                # 尝试获取值的静态表示
                value = get_node_value(value_node)
                if value is not None:
                    params[key_name] = value
                elif value_node['type'] == 'Identifier':
                    # 值是变量，标记为动态
                    params[key_name] = f"[Variable: {get_identifier_name(value_node)}]"
                elif value_node['type'] == 'MemberExpression':
                     params[key_name] = f"[MemberExpression: {get_member_expression_string(value_node)}]"
                elif value_node['type'] == 'CallExpression':
                     callee_str = get_member_expression_string(value_node.get('callee')) or get_identifier_name(value_node.get('callee'))
                     params[key_name] = f"[Call: {callee_str}(...)]"
                elif value_node['type'] == 'ObjectExpression':
                     # 嵌套对象，递归提取（简化处理）
                     nested_params = extract_object_literal(value_node)
                     params[key_name] = nested_params if nested_params else "[Object]"
                elif value_node['type'] == 'ArrayExpression':
                     # 数组处理（简化）
                     params[key_name] = "[Array]"
                else:
                    # 其他复杂类型，标记为动态
                    params[key_name] = f"[Dynamic Value: {value_node['type']}]"
    return params if params else None


# --- API 提取逻辑 ---

KNOWN_HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options'}

def find_api_calls(ast):
    """遍历 AST 查找已知的 API 调用模式"""
    results = []
    if not ast or not isinstance(ast, dict):
        return results

    # 使用递归或迭代方式遍历 AST 节点
    nodes_to_visit = [ast]
    visited_ranges = set() # 防止重复处理同一范围的节点

    while nodes_to_visit:
        node = nodes_to_visit.pop(0) # BFS 方式遍历

        if not node or not isinstance(node, dict):
            continue

        # 避免重复访问和处理过大的节点（可能导致性能问题）
        node_range = tuple(node.get('range', [-1, -1]))
        if node_range in visited_ranges or node_range == (-1,-1):
             continue
        visited_ranges.add(node_range)


        # 检查当前节点是否为函数调用 (CallExpression)
        if node.get('type') == 'CallExpression':
            callee = node.get('callee')
            arguments = node.get('arguments', [])

            # 模式 1: MemberExpression (e.g., axios.get, this.http.post, $.ajax)
            if callee and callee.get('type') == 'MemberExpression':
                call_str = get_member_expression_string(callee)
                method_node = callee.get('property')
                method_name = get_identifier_name(method_node)

                # 检查是否是已知的 HTTP 方法
                if call_str and method_name and method_name.lower() in KNOWN_HTTP_METHODS:
                    # 尝试提取 URL (通常是第一个参数)
                    url = get_node_value(arguments[0]) if arguments else None
                    # 尝试提取参数 (通常是第二个参数，或选项对象)
                    params_node = arguments[1] if len(arguments) > 1 else None
                    params = extract_object_literal(params_node)

                    if url and not should_skip_url(url):
                         api_type = classify_api_endpoint(url, method_name.upper())
                         add_unique_result(results, {
                             'method': method_name.upper(),
                             'url': url,
                             'params': params, # 现在是 dict 或 None
                             'api_type': api_type,
                             'source_loc': node.get('loc', {}).get('start', {}) # 添加来源位置
                         })

                # 特殊处理 $.ajax (url 和 type 在配置对象中)
                elif call_str and call_str.lower() == '$.ajax' and arguments:
                    options_node = arguments[0]
                    if options_node.get('type') == 'ObjectExpression':
                        ajax_options = extract_object_literal(options_node)
                        if ajax_options:
                             url = ajax_options.get('url')
                             method = ajax_options.get('type', ajax_options.get('method', 'GET')) # 默认为 GET
                             # data 参数可能需要进一步处理
                             params_data = ajax_options.get('data', None)

                             if isinstance(url, str) and not should_skip_url(url):
                                 api_type = classify_api_endpoint(url, method.upper())
                                 add_unique_result(results, {
                                     'method': method.upper(),
                                     'url': url,
                                     'params': params_data, # 可能需要进一步解析
                                     'api_type': api_type,
                                     'source_loc': node.get('loc', {}).get('start', {})
                                 })


            # 模式 2: fetch 调用 (Identifier 'fetch')
            elif callee and callee.get('type') == 'Identifier' and callee.get('name') == 'fetch':
                url = get_node_value(arguments[0]) if arguments else None
                method = 'GET' # 默认是 GET
                params = None
                options_node = arguments[1] if len(arguments) > 1 else None
                if options_node and options_node.get('type') == 'ObjectExpression':
                    fetch_options = extract_object_literal(options_node)
                    if fetch_options:
                        method = fetch_options.get('method', 'GET')
                        # body 参数通常需要特殊处理 (可能是字符串、FormData 等)
                        body_val = fetch_options.get('body')
                        if body_val:
                             params = {"body": body_val} # 简化表示

                if isinstance(url, str) and not should_skip_url(url):
                    api_type = classify_api_endpoint(url, method.upper())
                    add_unique_result(results, {
                        'method': method.upper(),
                        'url': url,
                        'params': params,
                        'api_type': api_type,
                        'source_loc': node.get('loc', {}).get('start', {})
                    })

            # 模式 3: WebSocket (new WebSocket(...))
            elif callee and callee.get('type') == 'Identifier' and callee.get('name') == 'WebSocket' and node.get('parent', {}).get('type') == 'NewExpression':
                 url = get_node_value(arguments[0]) if arguments else None
                 if isinstance(url, str) and not url.startswith(('http:', 'https:')): # 基础过滤
                     add_unique_result(results, {
                         'method': 'CONNECT',
                         'url': url,
                         'params': None,
                         'api_type': 'WebSocket',
                         'source_loc': node.get('loc', {}).get('start', {})
                     })

            # 模式 4: GraphQL (查找 gql 标签模板或特定客户端调用) - 简化
            # TODO: 实现更精确的 GraphQL AST 模式匹配

        # 递归遍历子节点
        for key, value in node.items():
             # 排除父节点引用，避免无限循环
             if key == 'parent':
                 continue
             if isinstance(value, dict):
                 # 为子节点添加父节点引用，方便上下文分析
                 value['parent'] = node
                 nodes_to_visit.append(value)
             elif isinstance(value, list):
                 for item in value:
                     if isinstance(item, dict):
                          item['parent'] = node
                          nodes_to_visit.append(item)

    return results

def extract_requests(js_content):
    """
    从JavaScript内容中提取HTTP请求 (使用 AST)

    参数:
        js_content: JavaScript代码字符串

    返回:
        包含提取出的请求信息的列表
    """
    if not js_content or not isinstance(js_content, str):
        logger.warning("Invalid js_content provided.")
        return []

    logger.info("Parsing JavaScript content to AST...")
    ast = parse_js_to_ast(js_content)

    if not ast:
        logger.error("Failed to generate AST. Skipping extraction for this content.")
        return []
    if ast.get('errors'): # Esprima 的 tolerant 模式会报告错误
        logger.warning(f"AST parsing generated errors: {ast.get('errors')}")


    logger.info("AST generated successfully. Finding API calls...")
    results = find_api_calls(ast)
    logger.info(f"Found {len(results)} potential API calls.")

    # TODO: 可以补充基于字符串的简单 URL 提取作为后备

    return results


# --- 结果处理和分类 (基本保持不变，但参数现在是 dict) ---

def should_skip_url(url):
    """判断URL是否需要跳过（非API URL），增加更多过滤规则"""
    if not url or not isinstance(url, str) or len(url) < 2:
        return True
    static_extensions = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.html',
                         '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map', '.txt', '.pdf', '.xml', '.json', '.webp', '.mp4', '.mp3')
    url_lower = url.lower()
    if url_lower.endswith(static_extensions):
        return True
    static_path_indicators = ('/static/', '/assets/', '/images/', '/img/', '/css/', '/js/',
                             '/fonts/', '/dist/', '/build/', '/vendor/', '/node_modules/', '/public/')
    if any(indicator in url_lower for indicator in static_path_indicators):
        return True
    if url.startswith(('http://', 'https://')):
         # 允许包含 /api 等路径的外部 URL
        if any(api_indicator in url_lower for api_indicator in ['/api', 'service', 'gateway', 'rest', 'v1', 'v2', 'data', 'query']):
             return False
         # 允许没有扩展名的外部 URL (可能是 API)
        if '.' not in url.split('/')[-1]:
             return False
         # 否则，默认跳过其他外部 URL
        return True
    if url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
        return True
    if url == '/':
        return True
    return False

def add_unique_result(results, new_result):
    """添加唯一的结果，避免重复，优化更新逻辑"""
    if not new_result.get('url') or not isinstance(new_result['url'], str):
        return

    url_norm = new_result['url'].split('?')[0].rstrip('/')
    method = new_result.get('method', 'GET').upper()

    for existing in results:
        existing_url_norm = existing.get('url', '').split('?')[0].rstrip('/')
        existing_method = existing.get('method', 'GET').upper()

        if existing_url_norm == url_norm and existing_method == method:
            # 如果新的参数更详细（基于键的数量判断），更新参数
            new_params = new_result.get('params')
            existing_params = existing.get('params')
            if isinstance(new_params, dict) and (not isinstance(existing_params, dict) or len(new_params) > len(existing_params)):
                 existing['params'] = new_params
            # 更新 API 类型（如果新的更具体）
            api_type_priority = ['WebSocket', 'GraphQL', 'RPC', 'Auth API', 'Upload API', 'RESTful', 'HTTP API']
            try:
                 new_priority = api_type_priority.index(new_result.get('api_type', 'HTTP API'))
                 existing_priority = api_type_priority.index(existing.get('api_type', 'HTTP API'))
                 if new_priority < existing_priority:
                     existing['api_type'] = new_result['api_type']
            except ValueError:
                 pass # 未知类型，不更新
            return

    # 添加来源位置信息
    new_result['source_loc'] = new_result.get('source_loc', {})
    results.append(new_result)


def classify_api_endpoint(url, method, context=""): # context 在 AST 中不太需要了
    """对API端点进行分类"""
    if not url or not isinstance(url, str):
        return 'HTTP API'
    url_lower = url.lower()

    if url.startswith(('ws://', 'wss://')): return 'WebSocket'
    if '/graphql' in url_lower or '/gql' in url_lower: return 'GraphQL'
    if '/rpc' in url_lower or '/jsonrpc' in url_lower: return 'RPC'
    if '/oauth' in url_lower or '/token' in url_lower or '/auth' in url_lower or 'login' in url_lower or 'register' in url_lower or 'session' in url_lower: return 'Auth API'
    if 'upload' in url_lower or 'file' in url_lower or 'image' in url_lower: return 'Upload API'

    # RESTful 判定
    if re.search(r'/(?:api/v\d+/)?(?:[a-z_]+(?:-[a-z_]+)*)+(?:/\d+|/[a-z_]+(?:-[a-z_]+)*)?$', url_lower): return 'RESTful'
    if method.upper() in ['PUT', 'DELETE', 'PATCH']: return 'RESTful'
    operations = ['create', 'update', 'delete', 'get', 'list', 'search', 'query', 'add', 'remove', 'info', 'data']
    if any(op in url_lower.split('/') for op in operations): return 'RESTful'
    if '/api/' in url_lower: return 'RESTful'

    return 'HTTP API'

# 需要导入 re 模块
import re
