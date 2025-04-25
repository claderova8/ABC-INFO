# -*- coding: utf-8 -*-
"""
JavaScript API 提取器模块（基于 AST）
功能：从 JavaScript AST 中提取 HTTP 和 WebSocket API 请求信息
"""
import json
import logging
import re  # 符合 PEP8，将 re 引入置顶
from utils.ast_parser import parse_js_to_ast  # 导入 AST 解析器

# 配置日志记录器
logger = logging.getLogger(__name__)

# --- AST 辅助函数 ---

def get_node_value(node):
    """
    从 AST 节点获取静态值（字符串、数字、布尔、null、undefined）。
    对于无法静态计算的表达式返回 None 或动态标识。
    """
    if not node:
        return None
    node_type = node.get('type')
    if node_type == 'Literal':
        # 处理正则字面量为字符串
        if 'regex' in node:
            return f"/{node['regex']['pattern']}/{node['regex']['flags']}"
        return node.get('value')  # Esprima 直接提供 value
    elif node_type == 'Identifier' and node.get('name') == 'undefined':
        return None  # 将 undefined 表示为 None
    elif node_type == 'TemplateLiteral':
        # 仅在无表达式时直接返回模板值
        quasis = node.get('quasis', [])
        exprs = node.get('expressions', [])
        if not exprs and len(quasis) == 1:
            return quasis[0].get('value', {}).get('cooked')
        return '[Template Literal]'  # 带表达式的模板视作动态
    # 可扩展对一元表达式（如 -1）的处理
    return None


def get_identifier_name(node):
    """
    获取标识符节点的名称。
    """
    if node and node.get('type') == 'Identifier':
        return node.get('name')
    return None


def get_member_expression_string(node):
    """
    将 MemberExpression 转为点分隔字符串，如 axios.get、this.api.call 等。
    """
    if not node or node.get('type') != 'MemberExpression':
        return None
    obj = node.get('object')
    prop = node.get('property')
    # 解析属性名（支持 obj.prop 和 obj['prop']）
    prop_name = get_identifier_name(prop)
    if not prop_name and prop.get('type') == 'Literal':
        prop_name = str(prop.get('value'))
    if not prop_name:
        # 计算属性 obj[propVar]
        if prop.get('type') == 'Identifier' and node.get('computed'):
            return f"[Computed Property: {get_identifier_name(prop)}]"
        return None
    # 解析对象部分（标识符、嵌套成员、this、调用表达式）
    obj_type = obj.get('type')
    if obj_type == 'Identifier':
        base = get_identifier_name(obj)
        return f"{base}.{prop_name}" if base else None
    elif obj_type == 'MemberExpression':
        base = get_member_expression_string(obj)
        return f"{base}.{prop_name}" if base else None
    elif obj_type == 'ThisExpression':
        return f"this.{prop_name}"
    elif obj_type == 'CallExpression':
        callee_str = get_call_expression_string(obj)
        return f"{callee_str}.{prop_name}" if callee_str else None
    return None


def get_call_expression_string(node):
    """
    将 CallExpression 表达式转换为字符串，如 func(...) 或 obj.method(...)。
    """
    if not node or node.get('type') != 'CallExpression':
        return None
    callee = node.get('callee')
    if callee.get('type') == 'Identifier':
        name = get_identifier_name(callee)
    elif callee.get('type') == 'MemberExpression':
        name = get_member_expression_string(callee)
    else:
        name = None
    return f"{name}(...)" if name else "[Unknown Call](...)"


def extract_object_literal(node):
    """
    从 ObjectExpression 节点提取简单键值对，处理嵌套、展开等常见类型。
    返回字典或 None。
    """
    if not node or node.get('type') != 'ObjectExpression':
        return None
    params = {}
    for prop in node.get('properties', []):
        ptype = prop.get('type')
        # 标准属性对
        if ptype == 'Property':
            key_node = prop.get('key')
            val_node = prop.get('value')
            # 获取键名
            key = None
            if key_node.get('type') == 'Identifier':
                key = key_node.get('name')
            elif key_node.get('type') == 'Literal':
                key = str(key_node.get('value'))
            if not key:
                continue
            # 尝试静态值
            value = get_node_value(val_node)
            if value is not None:
                params[key] = value
            else:
                # 动态值分类
                vtype = val_node.get('type')
                if vtype == 'Identifier':
                    params[key] = f"[Variable: {get_identifier_name(val_node)}]"
                elif vtype == 'MemberExpression':
                    expr = get_member_expression_string(val_node)
                    params[key] = f"[Member Expr: {expr}]" if expr else "[Dynamic Member Expr]"
                elif vtype == 'CallExpression':
                    call = get_call_expression_string(val_node)
                    params[key] = f"[Call: {call}]"
                elif vtype == 'ObjectExpression':
                    nested = extract_object_literal(val_node)
                    params[key] = nested if nested is not None else "[Object]"
                elif vtype == 'ArrayExpression':
                    params[key] = "[Array]"
                elif vtype in ('ArrowFunctionExpression', 'FunctionExpression'):
                    params[key] = "[Function]"
                elif vtype == 'BinaryExpression':
                    params[key] = "[Binary Expression]"
                elif vtype == 'ConditionalExpression':
                    params[key] = "[Conditional Expr]"
                elif vtype == 'NewExpression':
                    params[key] = "[New Expression]"
                else:
                    params[key] = f"[Dynamic: {vtype}]"
        # 处理展开语法
        elif ptype == 'SpreadElement':
            arg = prop.get('argument')
            name = None
            if arg.get('type') == 'Identifier':
                name = get_identifier_name(arg)
            elif arg.get('type') == 'MemberExpression':
                name = get_member_expression_string(arg)
            key = f"...{name}" if name else "...[Dynamic Spread]"
            params[key] = "[Spread]"
    return params if params else None


# --- API 提取核心逻辑 ---

# 已知 HTTP 方法
KNOWN_HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options'}
# 常见网络请求库对象
HTTP_LIB_OBJECTS = {'axios', 'http', 'request', '$', 'jQuery', 'superagent', 'fetch'}

def find_api_calls(ast):
    """
    遍历 AST，识别 HTTP/Fetch/$.ajax/WebSocket 等 API 调用模式，返回结果列表。
    """
    results = []
    if not ast or not isinstance(ast, dict):
        logger.warning("AST 无效或为空，跳过 API 调用搜索。")
        return results

    visited = set()
    queue = [ast]

    while queue:
        node = queue.pop(0)
        if not isinstance(node, dict):
            continue
        # 防止循环遍历
        rng = tuple(node.get('range', [-1, -1]))
        if rng in visited or rng == (-1, -1):
            continue
        visited.add(rng)

        # 处理函数调用
        if node.get('type') == 'CallExpression':
            callee = node.get('callee')
            args = node.get('arguments', [])
            api_info = None
            # 模式1：库方法调用，如 axios.get/post
            if callee.get('type') == 'MemberExpression':
                call_str = get_member_expression_string(callee)
                method = get_identifier_name(callee.get('property'))
                obj = callee.get('object')
                obj_name = None
                if obj.get('type') == 'Identifier':
                    obj_name = get_identifier_name(obj)
                elif obj.get('type') == 'ThisExpression':
                    obj_name = 'this'
                # HTTP 方法匹配
                if method and method.lower() in KNOWN_HTTP_METHODS:
                    url = get_node_value(args[0]) if args else None
                    params = extract_object_literal(args[1]) if len(args) > 1 else None
                    if isinstance(url, str) and not should_skip_url(url):
                        api_info = {
                            'method': method.upper(),
                            'url': url,
                            'params': params,
                            'api_type': classify_api_endpoint(url, method.upper()),
                            'source_loc': node.get('loc', {}).get('start', {})
                        }
                # $.ajax 特殊处理
                elif call_str and call_str.lower() in ('$.ajax', 'jquery.ajax') and args:
                    opt = args[0]
                    if opt.get('type') == 'ObjectExpression':
                        opts = extract_object_literal(opt)
                        url = opts.get('url')
                        method = opts.get('type', opts.get('method', 'GET'))
                        params = opts.get('data')
                        if isinstance(url, str) and not should_skip_url(url):
                            api_info = {
                                'method': method.upper(),
                                'url': url,
                                'params': params,
                                'api_type': classify_api_endpoint(url, method.upper()),
                                'source_loc': node.get('loc', {}).get('start', {})
                            }
            # 模式2：全局 fetch 调用
            elif callee.get('type') == 'Identifier' and callee.get('name') == 'fetch':
                url = get_node_value(args[0]) if args else None
                method = 'GET'
                params = None
                if len(args) > 1 and args[1].get('type') == 'ObjectExpression':
                    opts = extract_object_literal(args[1])
                    method = opts.get('method', 'GET')
                    body = opts.get('body')
                    if body is not None:
                        params = {'body': body}
                if isinstance(url, str) and not should_skip_url(url):
                    api_info = {
                        'method': method.upper(),
                        'url': url,
                        'params': params,
                        'api_type': classify_api_endpoint(url, method.upper()),
                        'source_loc': node.get('loc', {}).get('start', {})
                    }
            # 收集结果
            if api_info:
                add_unique_result(results, api_info)
        # 模式3：WebSocket 构造
        elif node.get('type') == 'NewExpression':
            callee = node.get('callee')
            args = node.get('arguments', [])
            if callee.get('type') == 'Identifier' and callee.get('name') == 'WebSocket':
                url = get_node_value(args[0]) if args else None
                if isinstance(url, str) and url.lower().startswith(('ws://', 'wss://')):
                    api_info = {
                        'method': 'WEBSOCKET',
                        'url': url,
                        'params': None,
                        'api_type': 'WebSocket',
                        'source_loc': node.get('loc', {}).get('start', {})
                    }
                    add_unique_result(results, api_info)
        # 将子节点加入队列
        for v in node.values():
            if isinstance(v, dict):
                queue.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        queue.append(item)
    return results


def extract_requests(js_content):
    """
    从 JavaScript 代码字符串中提取 HTTP/Fetch/$.ajax/WebSocket 请求。
    返回包含请求信息的字典列表。
    """
    if not js_content or not isinstance(js_content, str):
        logger.warning("提供的 js_content 无效或为空，忽略提取。")
        return []

    logger.debug("解析 JavaScript 为 AST...")
    ast = parse_js_to_ast(js_content)
    if not ast:
        logger.error("AST 生成失败，跳过提取。")
        return []
    if 'errors' in ast and ast['errors']:
        sample = ast['errors'][:3]
        logger.warning(f"AST 解析出错 {len(ast['errors'])} 项（示例：{sample}），结果可能不完整。")

    logger.debug("开始查找 API 调用...")
    body = ast.get('body') if isinstance(ast.get('body'), list) else ast
    try:
        results = find_api_calls(body)
        logger.debug(f"AST 遍历发现 {len(results)} 个潜在 API 调用。")
    except Exception as e:
        logger.error(f"AST 遍历出错：{e}", exc_info=True)
        results = []
    return results


# --- URL 过滤与分类 ---

def should_skip_url(url):
    """
    判断是否应跳过非 API 请求（静态资源、伪协议等）。
    返回 True 则跳过。
    """
    if not url or not isinstance(url, str) or len(url) < 2:
        return True
    low = url.lower()
    if low.startswith(('data:', 'javascript:', 'mailto:', 'tel:')):
        return True
    if url.startswith('#') or url == '/':
        return True
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        path = p.path.lower()
        static_ext = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
                      '.woff', '.woff2', '.ttf', '.eot', '.otf', '.map', '.txt', '.pdf', '.xml', '.json',
                      '.mp4', '.webm', '.ogg', '.mp3', '.wav', '.html', '.htm', '.md', '.csv', '.zip', '.gz', '.rar')
        if any(path.endswith(ext) for ext in static_ext):
            # .json 特殊保留路径含 /api/
            if path.endswith('.json') and '/api/' in path:
                return False
            return True
        static_dirs = ('/static/', '/assets/', '/images/', '/css/', '/js/', '/scripts/', '/dist/', '/build/')
        if any(d in path for d in static_dirs):
            if any(api_kw in path for api_kw in ('/api/', '/service/')):
                return False
            return True
    except:
        pass
    # 相对 URL 保留
    if '://' not in low:
        return False
    return False


def add_unique_result(results, new_res):
    """
    将新结果添加到列表，避免重复。相同 URL+METHOD 时合并参数或类型。
    """
    if not new_res or not isinstance(new_res.get('url'), str):
        logger.warning(f"跳过无效结果：{new_res}")
        return
    url = new_res['url']
    method = new_res.get('method', '').upper()
    norm = url.split('?')[0].rstrip('/')
    for exist in results:
        if exist.get('method') == method and exist.get('url').split('?')[0].rstrip('/') == norm:
            # 合并参数（优先 dict 且键更多者）
            np = new_res.get('params')
            ep = exist.get('params')
            if isinstance(np, dict) and (not isinstance(ep, dict) or len(np) > len(ep)):
                exist['params'] = np
            # 合并类型（优先更具体类型）
            order = ['WebSocket', 'GraphQL', 'RPC', 'Auth API', 'Upload API', 'RESTful', 'HTTP API', 'UNKNOWN']
            try:
                if order.index(new_res.get('api_type')) < order.index(exist.get('api_type')):
                    exist['api_type'] = new_res.get('api_type')
            except: pass
            return
    # 无重复则直接添加
    new_res.setdefault('params', None)
    new_res.setdefault('api_type', 'HTTP API')
    new_res.setdefault('source_loc', {})
    results.append(new_res)
    logger.debug(f"添加新 API 调用：{method} {url}")


def classify_api_endpoint(url, method):
    """
    根据 URL 和 HTTP 方法对 API 端点进行分类，如 RESTful、GraphQL、Auth API 等。
    返回分类字符串。
    """
    if not url or not isinstance(url, str):
        return 'UNKNOWN'
    ul = url.lower()
    mu = method.upper()
    if ul.startswith(('ws://', 'wss://')) or mu == 'WEBSOCKET':
        return 'WebSocket'
    if '/graphql' in ul or '/gql' in ul:
        return 'GraphQL'
    if '/rpc' in ul or '/jsonrpc' in ul:
        return 'RPC'
    if any(x in ul for x in ('/oauth', '/token', '/auth', '/login', '/register', '/session')):
        return 'Auth API'
    if any(x in ul for x in ('upload', '/file', '/image', '/media')):
        return 'Upload API'
    # 版本和方法指示 RESTful
    if re.search(r'/api/v\d+/', ul) or re.search(r'/v\d+/', ul) or mu in ('PUT', 'DELETE', 'PATCH'):
        return 'RESTful'
    if '/api/' in ul or '/service/' in ul or '/gateway/' in ul:
        return 'RESTful'
    return 'HTTP API'
