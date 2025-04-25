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
# ... (get_node_value, get_identifier_name, get_member_expression_string, get_call_expression_string, extract_object_literal 函数保持不变) ...
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
    queue = [ast] # 使用列表作为队列进行广度优先搜索

    while queue:
        node = queue.pop(0) # 从队列头部取出
        if not isinstance(node, dict):
            continue
        # 防止循环遍历 (基于AST节点范围)
        node_range = node.get('range')
        if node_range:
            rng = tuple(node_range)
            if rng in visited:
                continue
            visited.add(rng)
        else:
            # 如果节点没有范围信息，使用对象ID作为替代，但这可能不完全可靠
            # 更好的方法是确保Esprima总是提供range信息
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)


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
                    url_node = args[0] if args else None
                    url = get_node_value(url_node)
                    params_node = args[1] if len(args) > 1 else None
                    params = extract_object_literal(params_node)

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
                    opt_node = args[0]
                    if opt_node.get('type') == 'ObjectExpression':
                        opts = extract_object_literal(opt_node)
                        if opts: # 确保成功提取了对象
                            url = opts.get('url')
                            method = opts.get('type', opts.get('method', 'GET')) # 'type' 是旧版 jQuery 写法
                            # 确保 method 是字符串
                            if not isinstance(method, str): method = 'GET'
                            params = opts.get('data') # $.ajax 的 'data' 对应参数
                            if isinstance(url, str) and not should_skip_url(url):
                                api_info = {
                                    'method': method.upper(),
                                    'url': url,
                                    'params': params, # 'data' 可能不是对象，直接使用
                                    'api_type': classify_api_endpoint(url, method.upper()),
                                    'source_loc': node.get('loc', {}).get('start', {})
                                }
            # 模式2：全局 fetch 调用
            elif callee.get('type') == 'Identifier' and callee.get('name') == 'fetch':
                url_node = args[0] if args else None
                url = get_node_value(url_node)
                method = 'GET'
                params = None
                if len(args) > 1 and args[1].get('type') == 'ObjectExpression':
                    opts = extract_object_literal(args[1])
                    if opts:
                        method = opts.get('method', 'GET')
                        if not isinstance(method, str): method = 'GET' # 确保是字符串
                        body = opts.get('body') # fetch 通常用 body
                        # 如果 body 是动态的，保留标记；如果是静态的，直接用
                        params = {'body': body} if body is not None else None

                if isinstance(url, str) and not should_skip_url(url):
                    api_info = {
                        'method': method.upper(),
                        'url': url,
                        'params': params, # 使用 fetch 的参数结构
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
                url_node = args[0] if args else None
                url = get_node_value(url_node)
                if isinstance(url, str) and url.lower().startswith(('ws://', 'wss://')):
                    # 确保不被 should_skip_url 过滤掉 WebSocket URL
                    # (虽然 WebSocket URL 通常不包含需要过滤的扩展名)
                    api_info = {
                        'method': 'WEBSOCKET',
                        'url': url,
                        'params': None, # WebSocket 构造函数通常没有请求体参数
                        'api_type': 'WebSocket',
                        'source_loc': node.get('loc', {}).get('start', {})
                    }
                    add_unique_result(results, api_info)

        # --- 递归遍历子节点 ---
        # 遍历所有可能的子节点或节点列表
        for key, value in node.items():
            # 跳过非结构化数据如 'type', 'range', 'loc'
            if key in ('type', 'range', 'loc', 'raw', 'value', 'name'):
                continue

            if isinstance(value, dict):
                queue.append(value) # 将子字典加入队列
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        queue.append(item) # 将列表中的子字典加入队列

    return results


def extract_requests(js_content):
    """
    从 JavaScript 代码字符串中提取 HTTP/Fetch/$.ajax/WebSocket 请求。
    返回包含请求信息的字典列表。

    注意: 内部调用 parse_js_to_ast 是一个潜在的性能瓶颈，因为它会启动子进程。
    """
    if not js_content or not isinstance(js_content, str):
        logger.warning("提供的 js_content 无效或为空，忽略提取。")
        return []

    logger.debug("调用 Node.js 解析 JavaScript 为 AST...")
    # --- 性能注意: 此处调用 parse_js_to_ast 会启动子进程 ---
    ast = parse_js_to_ast(js_content)
    if not ast:
        logger.error("AST 生成失败或返回为空，跳过提取。")
        return []

    # Esprima 可能在 AST 顶层包含 'errors' 列表 (使用 tolerant: true 时)
    if 'errors' in ast and ast['errors']:
        error_count = len(ast['errors'])
        sample_errors = [e.get('message', str(e)) for e in ast['errors'][:3]]
        logger.warning(f"AST 解析时出现 {error_count} 个容忍错误 (示例: {sample_errors})，结果可能不完整。")
        # 根据需要决定是否继续处理有错误的 AST
        # if error_count > SOME_THRESHOLD: return []

    logger.debug("开始查找 API 调用...")
    # AST 的主体通常在 'body' 键下，但也可能直接是顶层对象 (如表达式)
    ast_body = ast.get('body') if isinstance(ast.get('body'), list) else ast

    # 处理顶层可能不是列表的情况，例如，如果 JS 代码只是一个表达式
    # 将其包装在列表中，以便 find_api_calls 可以统一处理
    root_node_for_search = {'type': 'Program', 'body': ast_body if isinstance(ast_body, list) else [ast_body]}

    try:
        results = find_api_calls(root_node_for_search)
        logger.debug(f"AST 遍历发现 {len(results)} 个潜在 API 调用。")
    except Exception as e:
        logger.error(f"AST 遍历过程中发生意外错误：{e}", exc_info=True)
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
    # 过滤常见伪协议
    if low.startswith(('data:', 'javascript:', 'mailto:', 'tel:', 'blob:')):
        return True
    # 过滤锚点和根路径 (通常不是 API)
    if url.startswith('#') or url == '/':
        # 但允许 /api/ 等明确的根路径 API
        if url.startswith(('/api/', '/service/', '/gateway/')):
            return False
        return True

    # 使用 urlparse 解析路径
    try:
        from urllib.parse import urlparse, urlsplit
        # 使用 urlsplit 避免 params 部分被误认
        p = urlsplit(url)
        path = p.path.lower() if p.path else ''

        # 过滤常见静态文件扩展名
        static_ext = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
                      '.woff', '.woff2', '.ttf', '.eot', '.otf', '.map', '.txt', '.pdf', '.xml',
                      '.mp4', '.webm', '.ogg', '.mp3', '.wav', '.html', '.htm', '.md', '.csv', '.zip', '.gz', '.rar')
        if any(path.endswith(ext) for ext in static_ext):
            # 特殊情况：允许以 .json 结尾但路径包含 /api/ 的 URL
            if path.endswith('.json') and '/api/' in path:
                return False
            return True # 否则，过滤掉这些静态文件

        # 过滤常见静态资源目录（更宽松的匹配）
        # 注意: 这可能误判 '/user/jsmith' 这样的路径，需要谨慎使用
        # static_dirs = ('/static/', '/assets/', '/images/', '/css/', '/js/', '/scripts/', '/dist/', '/build/', '/media/', '/fonts/')
        # if any(d in path for d in static_dirs):
        #     # 如果路径中也包含 API 指示符，则不跳过
        #     if any(api_kw in path for api_kw in ('/api/', '/service/')):
        #         return False
        #     return True # 否则，认为是静态资源路径

    except ValueError:
         # 处理无效 URL (例如，包含无法解析的字符)
         logger.warning(f"无法解析 URL '{url}'，将跳过。")
         return True
    except Exception as e:
        # 其他 urlparse 错误
        logger.warning(f"解析 URL '{url}' 时出错: {e}，将跳过。")
        return True

    # 对于相对路径或看起来像 API 的绝对路径 (不含上述过滤项)，不跳过
    return False


def add_unique_result(results, new_res):
    """
    将新结果添加到列表，避免重复。相同 URL+METHOD 时合并参数或类型。
    """
    if not new_res or not isinstance(new_res.get('url'), str):
        logger.warning(f"尝试添加无效结果，已跳过：{new_res}")
        return
    url = new_res['url']
    method = new_res.get('method', '').upper()

    # 规范化 URL 以进行比较（移除查询参数和尾部斜杠）
    norm_url = url.split('?')[0].rstrip('/')

    for exist in results:
        exist_url = exist.get('url', '')
        exist_method = exist.get('method', '').upper()
        exist_norm_url = exist_url.split('?')[0].rstrip('/')

        # 如果方法和规范化 URL 都相同，则认为是重复项
        if exist_method == method and exist_norm_url == norm_url:
            logger.debug(f"发现重复 API 调用，尝试合并：{method} {url}")
            # 合并参数（优先选择看起来更完整的参数，例如非空字典优先于 None 或标记）
            np = new_res.get('params')
            ep = exist.get('params')
            # 如果新参数是字典且现有参数不是，或者新字典键更多，则更新
            if isinstance(np, dict) and (not isinstance(ep, dict) or len(np) > len(ep)):
                exist['params'] = np
            # 如果新参数不是字典但现有参数是 None，也更新 (例如，用 '[Variable: data]' 替换 None)
            elif np is not None and ep is None:
                 exist['params'] = np

            # 合并类型（优先选择更具体的类型）
            order = ['WebSocket', 'GraphQL', 'RPC', 'Auth API', 'Upload API', 'RESTful', 'HTTP API', 'UNKNOWN']
            new_type = new_res.get('api_type', 'UNKNOWN')
            exist_type = exist.get('api_type', 'UNKNOWN')
            try:
                # 如果新类型的索引小于现有类型的索引（即更靠前/更具体），则更新
                if order.index(new_type) < order.index(exist_type):
                    exist['api_type'] = new_type
            except ValueError:
                # --- BUG 修复: 处理类型不在 order 列表中的情况 ---
                logger.warning(f"API 类型 '{new_type}' 或 '{exist_type}' 不在预定义顺序列表中，无法比较优先级。")
            except Exception as e:
                # --- BUG 修复: 捕获其他潜在错误并记录 ---
                logger.error(f"合并 API 类型时出错: {e}. New: {new_type}, Existing: {exist_type}", exc_info=True)

            # 找到重复项并处理后，直接返回，不再添加新条目
            return

    # 如果循环结束都没有找到重复项，则添加新结果
    # 设置默认值以确保结构一致性
    new_res.setdefault('params', None)
    new_res.setdefault('api_type', 'HTTP API') # 默认类型
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
    mu = method.upper() # 确保方法是大写

    # 1. WebSocket (最高优先级)
    if ul.startswith(('ws://', 'wss://')) or mu == 'WEBSOCKET':
        return 'WebSocket'

    # 2. GraphQL
    if '/graphql' in ul or '/gql' in ul:
        # 通常是 POST，但也可能是 GET 用于内省查询
        return 'GraphQL'

    # 3. RPC (JSON-RPC, gRPC-Web 等)
    if '/rpc' in ul or '/jsonrpc' in ul or 'grpc' in ul: # 添加 grpc 检查
        return 'RPC'

    # 4. 认证相关
    # 使用更具体的路径段匹配
    auth_paths = ('/oauth', '/token', '/auth', '/login', '/logout', '/register', '/session', '/signin', '/signup')
    if any(p in ul for p in auth_paths):
        return 'Auth API'

    # 5. 文件上传相关
    # 匹配路径段或常见的参数名 (需要解析查询参数，这里简化为只看 URL)
    upload_hints = ('upload', '/file', '/image', '/media', '/attachment', '/asset')
    if any(hint in ul for hint in upload_hints):
         # 通常是 POST 或 PUT
         if mu in ('POST', 'PUT'):
             return 'Upload API'

    # 6. RESTful 指示符
    # - 版本号 (如 /api/v1/, /v2/)
    # - 使用 PUT, DELETE, PATCH 方法
    # - 包含 /api/, /service/, /resource/, /endpoint/, /gateway/ 等路径段
    rest_indicators = ('/api/v', '/v\d+/', '/api/', '/service/', '/resource', '/endpoint', '/gateway')
    if mu in ('PUT', 'DELETE', 'PATCH') or any(re.search(indicator, ul) for indicator in rest_indicators):
        return 'RESTful'

    # 7. 如果以上都不是，归类为通用 HTTP API
    # 避免将静态文件路径误判为 HTTP API (虽然 should_skip_url 已处理大部分)
    if any(ul.endswith(ext) for ext in ('.js', '.css', '.html', '.png', '.jpg')): # 简单检查
         return 'UNKNOWN' # 可能还是静态资源

    return 'HTTP API'
