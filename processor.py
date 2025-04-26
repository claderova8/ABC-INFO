# -*- coding: utf-8 -*-
"""
处理不同输入类型（URL、文件、列表）的函数，
用于 JavaScript API 提取器。
"""

import requests
import re
from urllib.parse import urljoin, urlparse, urlunparse

# 从包内其他模块导入函数
# 假设这些模块 (extractor, formatter, utils) 在同一个包或目录下
try:
    from . import extractor
    from . import formatter
    from . import utils
except ImportError:
    # 如果作为简单脚本运行，则使用标准导入
    import extractor
    import formatter
    import utils

# --- 预编译正则表达式 ---

# 查找 HTML 中 <script src="..."> 标签的模式
# 改进以处理不同的引号类型和属性，并捕获可选的查询参数
script_src_pattern = re.compile(
    r'<script[^>]+src\s*=\s*["\'](?P<src>[^"\']+\.js(?:\?[^"\']*)?)["\']',
    re.IGNORECASE
)

# 查找 HTML 中内联 <script>...</script> 标签内容的模式
# 使用 DOTALL 标志以匹配包含换行的脚本内容
inline_script_pattern = re.compile(
    # 确保 script 标签没有 src 属性，并且捕获标签之间的所有内容（非贪婪）
    r'<script(?![^>]*src)(?:[^>]*)>(.*?)</script>',
    re.IGNORECASE | re.DOTALL
)

# --- 辅助函数 ---

def _is_valid_url(url):
    """检查字符串是否是有效的 HTTP/HTTPS URL"""
    if not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        # 必须包含协议 (http/https) 和网络位置 (域名/IP)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        # urlparse 可能在某些无效输入上引发 ValueError
        return False

def _normalize_url(base_url, link):
    """
    规范化 URL，处理相对路径、绝对路径和协议相对 URL。

    参数:
        base_url (str): 页面或来源的基准 URL。
        link (str): 从页面中提取的链接（可能是相对或绝对的）。

    返回:
        str: 规范化后的完整 URL，如果无法规范化则返回 None。
    """
    try:
        # 尝试直接解析链接
        parsed_link = urlparse(link)

        # 1. 如果链接已经是完整的 HTTP/HTTPS URL，直接返回
        if parsed_link.scheme in ['http', 'https'] and parsed_link.netloc:
            return urlunparse(parsed_link)

        # 2. 处理协议相对 URL (例如 //example.com/script.js)
        if link.startswith('//'):
            parsed_base = urlparse(base_url)
            # 使用基准 URL 的协议
            new_link_parts = (parsed_base.scheme, ) + parsed_link[1:]
            return urlunparse(new_link_parts)

        # 3. 处理绝对路径 URL (例如 /script.js) 或相对路径 URL (例如 script.js, ../script.js)
        # 使用 urljoin 处理相对路径和绝对路径
        joined_url = urljoin(base_url, link)
        parsed_joined = urlparse(joined_url)

        # 确保结果是有效的 HTTP/HTTPS URL
        if parsed_joined.scheme in ['http', 'https'] and parsed_joined.netloc:
            return urlunparse(parsed_joined)
        else:
            # urljoin 可能产生无效结果（例如，如果 base_url 无效）
            return None

    except Exception as e:
        # print(f"调试信息：规范化 URL '{link}' (基准 '{base_url}') 时出错: {e}") # 可选调试
        return None # 发生任何错误则返回 None

# --- 核心处理函数 ---

def process_js_content(js_content, source_name, output_file):
    """
    从给定的 JavaScript 内容中提取 API 请求，并将格式化的结果写入文件和控制台。

    参数:
        js_content (str): JavaScript 代码字符串。
        source_name (str): 标识 JS 内容来源的名称（例如 URL 或文件名）。
        output_file (str): 输出文件的路径。

    返回:
        list[str]: 包含此来源格式化输出行的列表。
    """
    output_lines = [] # 存储输出内容的列表
    # 添加来源标识和分隔符
    output_lines.append(f"\n--- 来源: {source_name} ---")
    output_lines.append("=" * 60)

    try:
        # 调用 extractor 模块提取请求
        results = extractor.extract_requests(js_content)
        if results:
            # 遍历提取到的每个请求结果
            for result in results:
                # 格式化请求行，包含类型和方法
                output_lines.append(f"类型: {result['type']}, 请求: \"{result['method']} {result['url']}\"")
                # 如果存在参数，则格式化参数
                if result['params']:
                    formatted_params = formatter.format_params(result['params'])
                    output_lines.append(f"请求参数: {formatted_params}")
                else:
                    # 如果没有参数，明确说明
                    output_lines.append("请求参数: 无参数")
                # 添加请求之间的分隔符
                output_lines.append("-" * 60)
        else:
            # 如果没有找到请求信息
            output_lines.append("未找到请求信息")

    except Exception as e:
        # 处理在提取或格式化过程中可能发生的任何错误
        output_lines.append(f"错误：处理 JS 内容时出错 ({source_name}): {str(e)}")

    # 将此来源的结果写入文件（追加模式）
    utils.write_to_file(output_file, "\n".join(output_lines) + "\n\n")
    # 同时打印到控制台
    print("\n".join(output_lines))

    return output_lines # 返回输出行列表

def process_js_url(url, output_file, processed_urls_cache):
    """
    处理单个 JavaScript URL，下载内容并提取请求。
    使用缓存避免重复处理相同的 URL。

    参数:
        url (str): JavaScript 文件的 URL。
        output_file (str): 输出文件的路径。
        processed_urls_cache (set): 用于跟踪已处理 URL 的集合。
    """
    print(f"\n正在获取 JS URL: {url}")

    # 检查 URL 是否有效且未被处理过
    if not _is_valid_url(url):
        error_msg = f"错误：提供的 JS URL 无效: {url}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
        return
    if url in processed_urls_cache:
        print(f"信息：跳过已处理的 JS URL: {url}")
        return

    try:
        # 设置请求头，模拟浏览器行为
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        # 发送 GET 请求，设置超时时间，禁用 SSL 验证（生产环境请谨慎使用）
        # verify=False 用于处理可能的 SSL 证书问题，但会带来安全风险
        response = requests.get(url, timeout=20, headers=headers, verify=False)
        # 检查请求是否成功 (状态码 2xx)
        response.raise_for_status()

        # 仔细解码内容，尝试自动检测编码，默认为 utf-8
        response.encoding = response.apparent_encoding or 'utf-8'
        js_content = response.text

        # 如果获取到内容，则进行处理
        if js_content:
             process_js_content(js_content, url, output_file)
             processed_urls_cache.add(url) # 处理成功后添加到缓存
        else:
             # 如果 URL 返回空内容
             print(f"警告：URL 返回空内容: {url}")
             utils.write_to_file(output_file, f"警告：URL 返回空内容: {url}\n\n")
             processed_urls_cache.add(url) # 也添加到缓存，避免重试

    except requests.exceptions.RequestException as e:
        # 处理网络请求相关的错误 (例如连接超时、DNS 解析失败、HTTP 错误状态码)
        error_msg = f"错误：无法下载 JS 文件 {url}: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
        # 即使失败也添加到缓存，避免在同一运行中重试失败的 URL
        processed_urls_cache.add(url)
    except Exception as e:
        # 处理其他可能发生的意外错误
        error_msg = f"错误：处理 JS URL {url} 时发生意外错误: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
        processed_urls_cache.add(url) # 添加到缓存

def process_js_file(file_path, output_file):
    """
    处理单个本地 JavaScript 文件，读取内容并提取请求。

    参数:
        file_path (str): 本地 JavaScript 文件的路径。
        output_file (str): 输出文件的路径。
    """
    print(f"\n正在读取 JS 文件: {file_path}")
    try:
        # 使用 utf-8 编码读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        # 如果文件内容非空，则进行处理
        if js_content:
            process_js_content(js_content, file_path, output_file)
        else:
            # 如果文件为空
             print(f"警告：文件为空: {file_path}")
             utils.write_to_file(output_file, f"警告：文件为空: {file_path}\n\n")

    except FileNotFoundError:
        # 处理文件未找到的错误
        error_msg = f"错误：本地 JS 文件未找到: {file_path}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
    except IOError as e:
        # 处理文件读取时可能发生的 IO 错误
        error_msg = f"错误：读取本地 JS 文件时出错 {file_path}: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
    except Exception as e:
        # 处理其他可能发生的意外错误
        error_msg = f"错误：处理本地 JS 文件 {file_path} 时发生意外错误: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")

def process_web_page(page_url, output_file, processed_js_urls_cache):
    """
    处理单个网页 URL，下载页面内容，提取并分析其中链接的 JS 文件和内联 JS 代码。

    参数:
        page_url (str): 网页的 URL。
        output_file (str): 输出文件的路径。
        processed_js_urls_cache (set): 用于跟踪已处理 JS URL 的集合，传递给 process_js_url。
    """
    print(f"\n正在分析网页: {page_url}")
    # 验证网页 URL 是否有效
    if not _is_valid_url(page_url):
        error_msg = f"错误：提供的网页 URL 无效: {page_url}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
        return

    # 在输出文件中写入网页分析的标题
    utils.write_to_file(output_file, f"## 分析网页: {page_url}\n" + "="*60 + "\n")

    try:
        # 设置请求头
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        # 发送 GET 请求下载网页，禁用 SSL 验证
        response = requests.get(page_url, timeout=20, headers=headers, verify=False)
        response.raise_for_status() # 检查 HTTP 状态码
        # 解码网页内容
        response.encoding = response.apparent_encoding or 'utf-8'
        html_content = response.text

        # 如果网页内容为空
        if not html_content:
            print(f"警告：网页返回空内容: {page_url}")
            utils.write_to_file(output_file, f"警告：网页返回空内容: {page_url}\n\n")
            return

        js_found_in_page = False # 标记是否在页面中找到了任何 JS

        # 1. 提取并处理链接的 JavaScript 文件 (<script src="...">)
        linked_js_count = 0
        # 使用预编译的正则表达式查找所有 <script src="...">
        for match in script_src_pattern.finditer(html_content):
            js_link_src = match.group('src') # 获取 src 属性值
            if js_link_src:
                # 规范化 URL (处理相对路径、绝对路径、协议相对路径)
                full_js_url = _normalize_url(page_url, js_link_src.strip())
                # 如果 URL 规范化成功且有效
                if full_js_url and _is_valid_url(full_js_url):
                    linked_js_count += 1
                    js_found_in_page = True
                    # 调用 process_js_url 处理这个 JS 文件 URL，传入缓存
                    process_js_url(full_js_url, output_file, processed_js_urls_cache)
                else:
                    print(f"信息：跳过无效或无法规范化的 JS 链接: {js_link_src} (来自: {page_url})")

        print(f"信息：在 {page_url} 中找到 {linked_js_count} 个有效的外部 JS 链接。")


        # 2. 提取并处理内联 JavaScript (<script>...</script>)
        inline_scripts_content = []
        # 使用预编译的正则表达式查找所有内联脚本内容
        for match in inline_script_pattern.finditer(html_content):
            script_content = match.group(1) # 获取 <script> 标签之间的内容
            if script_content and script_content.strip(): # 仅处理非空脚本
                inline_scripts_content.append(script_content.strip())

        # 如果找到了内联脚本
        if inline_scripts_content:
            js_found_in_page = True
            print(f"信息：在 {page_url} 中找到 {len(inline_scripts_content)} 个内联 JS 块。")
            utils.write_to_file(output_file, "\n--- 分析内联 JavaScript ---\n")
            print("\n--- 正在分析内联 JavaScript ---")
            # 将所有内联脚本合并为一个字符串进行分析（也可以选择单独分析每个块）
            combined_inline_js = "\n\n; // Inline Script Separator \n\n".join(inline_scripts_content)
            # 处理合并后的内联 JS 内容
            process_js_content(combined_inline_js, f"{page_url} (内联脚本)", output_file)
        else:
             print(f"信息：在 {page_url} 中未找到内联 JS。")

        # 如果页面中既没有找到外部 JS 链接也没有找到内联 JS
        if not js_found_in_page:
            no_js_msg = "信息：未在页面中找到外部或内联 JavaScript。"
            print(no_js_msg)
            utils.write_to_file(output_file, no_js_msg + "\n\n")

    except requests.exceptions.RequestException as e:
        # 处理访问网页时的网络错误
        error_msg = f"错误：无法访问网页 {page_url}: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
    except Exception as e:
        # 处理分析网页时的其他意外错误
        error_msg = f"错误：处理网页 {page_url} 时发生意外错误: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")


def process_url_list_file(file_path, is_js_list, output_file):
    """
    处理包含 URL 列表的文件（网页 URL 或 JS URL）。

    参数:
        file_path (str): 包含 URL 列表的文件路径。
        is_js_list (bool): 如果列表包含 JS URL 则为 True，否则为 False (表示网页 URL)。
        output_file (str): 输出文件的路径。
    """
    print(f"\n正在处理 URL 列表文件: {file_path}")
    # 在输出文件中写入列表文件分析的标题
    utils.write_to_file(output_file, f"## 分析 URL 列表文件: {file_path}\n" + "="*60 + "\n")
    processed_count = 0 # 记录处理的 URL 数量
    # 创建一个在此次列表处理中共享的 JS URL 缓存，避免重复下载和分析同一个 JS 文件
    processed_js_urls_cache = set()

    try:
        # 读取 URL 列表文件
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = f.readlines() # 读取所有行

        # 遍历文件中的每一行
        for line_num, line in enumerate(urls, 1):
            url = line.strip() # 去除首尾空格
            # 跳过空行和以 '#' 开头的注释行
            if not url or url.startswith('#'):
                continue

            print(f"\n--- 处理列表项 {line_num}: {url} ---")
            # 根据列表类型调用不同的处理函数
            if is_js_list:
                # 如果是 JS URL 列表，直接处理 JS URL
                process_js_url(url, output_file, processed_js_urls_cache)
            else:
                # 如果是网页 URL 列表，处理网页 URL
                process_web_page(url, output_file, processed_js_urls_cache)
            processed_count += 1
            # 在处理完每个 URL 后添加分隔符（可选）
            # utils.write_to_file(output_file, "\n" + "="*70 + "\n\n")

        # 如果文件中没有找到有效的 URL
        if processed_count == 0:
             no_urls_msg = "信息：URL 列表文件为空或未找到有效 URL。"
             print(no_urls_msg)
             utils.write_to_file(output_file, no_urls_msg + "\n")

    except FileNotFoundError:
        # 处理列表文件未找到的错误
        error_msg = f"错误：URL 列表文件未找到: {file_path}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
    except IOError as e:
        # 处理读取列表文件时的 IO 错误
        error_msg = f"错误：读取 URL 列表文件时出错 {file_path}: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")
    except Exception as e:
        # 处理分析列表文件时的其他意外错误
        error_msg = f"错误：处理 URL 列表文件 {file_path} 时发生意外错误: {e}"
        print(error_msg)
        utils.write_to_file(output_file, error_msg + "\n\n")

