# -*- coding: utf-8 -*-
"""
处理不同输入类型（URL、文件、列表）的函数模块。
协调内容的获取（下载或读取）与 API 提取逻辑的调用。
(优化版本 v4.6 - 精确控制彩色打印输出)
"""

import requests
import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from requests.exceptions import RequestException, Timeout, HTTPError, ConnectionError
from pathlib import Path
from typing import Set, Optional, Generator, Union, List, Dict, Any

# --- 配置日志 ---
log = logging.getLogger(__name__) # 获取当前模块的日志记录器

# --- 模块导入 ---
try:
    # 导入本项目其他模块
    import extractor # API 提取核心逻辑
    import formatter # 参数格式化逻辑
    import utils     # 实用工具 (文件写入, 颜色等)
    from utils import Colors # 导入颜色类，用于控制台彩色输出
except ImportError as e:
    # 关键依赖缺失，记录严重错误并重新抛出异常
    log.critical(f"无法导入 processor 依赖的模块 (extractor, formatter, utils): {e}", exc_info=True)
    raise # 抛出异常，终止程序运行

# --- HTML 解析库检查 ---
# 尝试导入 BeautifulSoup4，如果可用则优先使用它解析 HTML
BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
    log.debug("BeautifulSoup4 可用，将用于解析 HTML。")
except ImportError:
    # 如果未安装 BS4，则记录警告，程序将回退到使用正则表达式解析 HTML
    log.warning("BeautifulSoup4 未安装。将使用正则表达式解析 HTML，这可能不够健壮。强烈建议运行 'pip install beautifulsoup4'。")

# --- 常量定义 ---
DEFAULT_TIMEOUT = 30 # 网络请求默认超时时间 (秒)
# 默认请求头，模拟浏览器行为
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7', # 添加中文语言偏好
    'Accept-Encoding': 'gzip, deflate, br', # 请求接受压缩内容
}

# --- 正则表达式 (主要作为 BeautifulSoup 的后备或补充) ---
# 匹配 <script> 标签中的 src 属性 (外部 JS 文件)
SCRIPT_SRC_PATTERN = re.compile(
    r'<script[^>]+src\s*=\s*["\'](?P<src>[^"\']+\.js(?:\?[^"\']*)?)["\']', re.IGNORECASE
)
# 匹配内联 <script> 标签的内容 (不含 src 属性的 script 标签)
INLINE_SCRIPT_PATTERN = re.compile(
    r'<script(?![^>]*\ssrc\s*=)(?:[^>]*)>(.*?)</script>', re.IGNORECASE | re.DOTALL
)

# --- 辅助函数 ---

def _is_valid_url(url: Optional[str]) -> bool:
    """检查字符串是否是有效的 HTTP 或 HTTPS URL。"""
    if not isinstance(url, str): # 确保输入是字符串
        return False
    try:
        result = urlparse(url) # 解析 URL
        # 检查协议是否为 http 或 https，并且网络位置 (域名) 存在
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        # 解析失败，可能 URL 格式错误
        log.warning(f"解析 URL 时出错 (可能无效): {url}")
        return False

def _normalize_url(base_url: str, link: Optional[str]) -> Optional[str]:
    """
    将相对 URL 或协议相对 URL (//...) 规范化为绝对 URL。
    Args:
        base_url: 当前页面的基础 URL。
        link: 从页面中提取的链接 (可能是相对或绝对的)。
    Returns:
        规范化后的绝对 URL 字符串，如果无法规范化或无效则返回 None。
    """
    if not link or not isinstance(link, str): # 检查 link 是否有效
        return None
    link = link.strip() # 去除首尾空白
    if not link:
        return None
    try:
        # urljoin 会根据 base_url 自动处理相对路径 (如 /path, ../path, path) 和绝对路径
        joined_url = urljoin(base_url, link)
        # 再次解析以确保结果有效并进行标准化
        parsed_joined = urlparse(joined_url)
        if parsed_joined.scheme in ['http', 'https'] and parsed_joined.netloc:
            # 使用 urlunparse 重新组合 URL，确保格式标准
            return urlunparse(parsed_joined)
        else:
            # 如果规范化后的 URL 仍然无效 (例如，变成了 file:// 或缺少域名)
            log.warning(f"规范化后的 URL 无效: '{joined_url}' (基准: '{base_url}', 链接: '{link}')")
            return None
    except Exception as e:
        # 处理 urljoin 或 urlparse 可能出现的异常
        log.error(f"规范化 URL '{link}' (基准: '{base_url}') 时出错: {e}", exc_info=True)
        return None

def _fetch_content(url: str) -> Optional[str]:
    """
    下载给定 URL 的文本内容。
    Args:
        url: 要下载的 URL。
    Returns:
        下载到的文本内容字符串，如果下载失败则返回 None。
    """
    log.debug(f"尝试下载 URL: {url}")
    try:
        # 发送 GET 请求
        response = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT, # 设置超时
            headers=DEFAULT_HEADERS, # 使用模拟浏览器的请求头
            verify=False, # 警告: 禁用 SSL 证书验证 (在处理某些 https 站点时可能需要，但有安全风险)
            stream=True # 建议使用 stream=True，特别是对于大文件
        )
        response.raise_for_status() # 检查 HTTP 错误状态码 (例如 404, 500)
        # 确定响应内容的编码。优先使用响应头指定的编码，其次是 requests 推测的编码，最后默认 utf-8
        response.encoding = response.encoding or response.apparent_encoding or 'utf-8'
        content = response.text # 获取解码后的文本内容
        log.debug(f"成功下载 URL: {url} (内容长度: {len(content)})")
        return content
    except Timeout:
        log.error(f"请求 URL 超时 {url} (超时: {DEFAULT_TIMEOUT}s)")
        # 恢复下载失败打印到 stderr
        print(f"  {Colors.FAIL}❌ 下载或处理 URL 超时: {url}{Colors.RESET}", file=sys.stderr)
    except HTTPError as e:
        log.error(f"请求 URL 失败 {url} (HTTP状态码: {e.response.status_code})")
        # 恢复下载失败打印到 stderr
        print(f"  {Colors.FAIL}❌ 请求 URL 失败 ({e.response.status_code}): {url}{Colors.RESET}", file=sys.stderr)
    except ConnectionError as e:
        log.error(f"请求 URL 连接错误 {url}: {e}")
        # 恢复下载失败打印到 stderr
        print(f"  {Colors.FAIL}❌ 请求 URL 连接错误: {url} - {e}{Colors.RESET}", file=sys.stderr)
    except RequestException as e:
        # 捕获 requests 库的其他网络相关异常
        log.error(f"请求 URL 时发生其他网络错误 {url}: {e}")
        # 恢复下载失败打印到 stderr
        print(f"  {Colors.FAIL}❌ 请求 URL 时发生网络错误: {url} - {e}{Colors.RESET}", file=sys.stderr)
    except Exception as e:
        # 捕获其他意外错误
        log.error(f"下载 URL {url} 时发生意外错误: {e}", exc_info=True)
        # 恢复下载失败打印到 stderr
        print(f"  {Colors.FAIL}❌ 下载 URL 时发生意外错误: {url} - {e}{Colors.RESET}", file=sys.stderr)
    return None # 下载失败返回 None

# --- 核心处理函数 ---

def process_js_content(js_content: str, source_name: str, output_file_path: Union[str, Path]) -> int:
    """
    处理单段 JavaScript 源代码：提取 API 请求，并将详细结果写入文件。
    保留彩色摘要打印到控制台。

    Args:
        js_content: JavaScript 源代码字符串。
        source_name: 内容来源标识 (URL 或文件名)。
        output_file_path: 结果输出文件的路径 (字符串或 Path 对象)。

    Returns:
        提取到的请求数量。
    """
    output_lines_for_file = [f"\n--- 来源: {source_name} ---", "=" * 60] # 文件输出内容的列表
    extracted_count = 0 # 提取到的总请求数
    param_count = 0     # 带参数的请求数

    try:
        # 调用 extractor 模块进行 API 提取
        results: List[Dict[str, Any]] = extractor.extract_requests(js_content)
        extracted_count = len(results)

        if results:
            log.info(f"在 {source_name} 中找到 {extracted_count} 个潜在请求。")
            for result in results:
                # --- 准备文件输出内容 ---
                # 写入类型、方法和 URL
                output_lines_for_file.append(f"类型: {result['type']}, 请求: \"{result['method']} {result['url']}\"")
                # 调用 formatter 格式化参数
                formatted_params = formatter.format_params(result.get('params'))
                output_lines_for_file.append(f"请求参数: {formatted_params}")
                output_lines_for_file.append("-" * 60) # 添加分隔符

                # --- 统计带参数的请求 ---
                # 检查原始参数是否存在且格式化后不是 "无参数"
                if result.get('params') and formatted_params != "无参数":
                    param_count += 1

            # --- 打印彩色摘要到控制台 ---
            # 恢复彩色摘要打印，修改格式以匹配示例
            print(f"\t👁️{Colors.INFO}从 {Colors.SOURCE}{source_name}{Colors.RESET}{Colors.INFO} 发现 {Colors.COUNT}{extracted_count}{Colors.RESET}{Colors.INFO} 个接口 ({Colors.PARAM_COUNT}{param_count}{Colors.RESET}{Colors.INFO} 个带参数){Colors.RESET}")

        else:
            # 未找到请求
            output_lines_for_file.append("未找到请求信息")
            log.info(f"在 {source_name} 中未找到请求信息。")
            # 恢复未找到的摘要打印，修改格式以匹配示例
            print(f"\t👁️{Colors.INFO}从 {Colors.SOURCE}{source_name}{Colors.RESET}{Colors.INFO} 发现 {Colors.COUNT}0{Colors.RESET}{Colors.INFO} 个接口 (0 个带参数){Colors.RESET}")

    except Exception as e:
        # 处理 JS 内容分析过程中可能出现的异常
        error_msg = f"错误：处理 JS 内容时出错 ({source_name}): {e}"
        output_lines_for_file.append(error_msg) # 记录到文件
        log.error(error_msg, exc_info=True)     # 记录到日志
        # 恢复错误打印到控制台
        print(f"\t{Colors.FAIL}❌ 处理 JS 内容时出错 ({Colors.SOURCE}{source_name}{Colors.RESET}{Colors.FAIL}): {e}{Colors.RESET}", file=sys.stderr)

    # 将详细结果写入文件
    utils.write_to_file(output_file_path, "\n".join(output_lines_for_file) + "\n\n")

    return extracted_count

def process_js_url(url: str, output_file_path: Union[str, Path], processed_urls_cache: Set[str]) -> None:
    """
    处理单个 JavaScript URL：下载内容并进行分析。
    保留打印信息。

    Args:
        url: JS 文件 URL。
        output_file_path: 结果输出文件的路径 (字符串或 Path 对象)。
        processed_urls_cache: 已处理 URL 的缓存集合 (避免重复处理)。
    """
    log.info(f"准备处理 JS URL: {url}")
    # 恢复开始分析的消息打印，修改格式以匹配示例
    print(f"🔎{Colors.INFO}开始分析 JS URL: {Colors.PATH}{url}{Colors.RESET}")

    # 验证 URL 格式
    if not _is_valid_url(url):
        error_msg = f"错误：提供的 JS URL 无效或不支持: {url}"
        log.error(error_msg)
        # 恢复无效 URL 打印到 stderr
        print(f"\t{Colors.FAIL}❌ 无效 JS URL: {url}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file_path, error_msg + "\n\n")
        return

    # 检查是否已处理过此 URL
    if url in processed_urls_cache:
        log.info(f"跳过已处理的 JS URL: {url}")
        # 恢复跳过打印
        print(f"\t{Colors.WARNING}⚠️ 跳过已处理的 JS URL: {url}{Colors.RESET}")
        return

    # 将当前 URL 添加到缓存
    processed_urls_cache.add(url)
    # 下载 JS 内容
    js_content = _fetch_content(url)

    if js_content is not None: # 检查是否下载成功
        # (可选) 检查 Content-Type，增加警告信息
        try:
            response = requests.head(url, timeout=5, headers=DEFAULT_HEADERS, verify=False)
            content_type = response.headers.get('content-type', '').lower()
            if 'javascript' not in content_type and 'text/plain' not in content_type:
                log.warning(f"URL {url} 的 Content-Type ('{content_type}') 可能不是 JS，但仍将处理。")
        except Exception as head_err:
            log.debug(f"无法获取 URL {url} 的 HEAD 信息: {head_err}")

        # 如果内容非空，则进行处理
        if js_content:
             process_js_content(js_content, url, output_file_path)
        else:
             # 内容为空
             log.warning(f"URL 返回空内容: {url}")
             # 恢复空内容警告打印
             print(f"\t{Colors.WARNING}⚠️ URL 返回空内容: {url}{Colors.RESET}")
             utils.write_to_file(output_file_path, f"警告：URL 返回空内容: {url}\n\n")
    # else: 下载失败的错误已经在 _fetch_content 中处理并打印


def process_js_file(file_path_str: str, output_file_path: Union[str, Path]) -> None:
    """
    处理单个本地 JavaScript 文件。
    保留打印信息。

    Args:
        file_path_str: 本地 JS 文件路径字符串。
        output_file_path: 结果输出文件的路径 (字符串或 Path 对象)。
    """
    file_path = Path(file_path_str) # 转换为 Path 对象
    log.info(f"准备处理本地 JS 文件: {file_path}")
    # 恢复开始分析的消息打印，修改格式以匹配示例
    print(f"🔎{Colors.INFO}开始分析本地文件: {Colors.PATH}{file_path}{Colors.RESET}")

    try:
        # 检查文件是否存在且是文件类型
        if not file_path.is_file():
             raise FileNotFoundError(f"文件不存在或不是一个有效文件: {file_path}")
        # 读取文件内容，指定 utf-8 编码，忽略无法解码的字符
        js_content = file_path.read_text(encoding='utf-8', errors='ignore')
        # 如果内容非空，则进行处理
        if js_content:
            process_js_content(js_content, str(file_path), output_file_path)
        else:
             # 文件为空
             log.warning(f"文件为空: {file_path}")
             # 恢复文件为空警告打印
             print(f"\t{Colors.WARNING}⚠️ 文件为空: {file_path}{Colors.RESET}")
             utils.write_to_file(output_file_path, f"警告：文件为空: {file_path}\n\n")
    except FileNotFoundError as e:
        error_msg = f"错误：本地 JS 文件未找到: {e}"
        log.error(error_msg)
        # 恢复文件未找到打印到 stderr
        print(f"\t{Colors.FAIL}❌ 文件未找到: {e}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file_path, error_msg + "\n\n")
    except IOError as e:
        error_msg = f"错误：读取本地 JS 文件时出错 {file_path}: {e}"
        log.error(error_msg)
        # 恢复读取文件错误打印到 stderr
        print(f"\t{Colors.FAIL}❌ 读取文件时出错: {file_path} - {e}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file_path, error_msg + "\n\n")
    except Exception as e:
        error_msg = f"错误：处理本地 JS 文件 {file_path} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        # 恢复处理文件意外错误打印到 stderr
        print(f"\t{Colors.FAIL}❌ 处理文件时意外出错: {file_path} - {e}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file_path, error_msg + "\n\n")

def _extract_js_from_html(html_content: str, base_url: str, output_file_path: Union[str, Path], processed_js_urls_cache: Set[str]) -> bool:
    """
    从 HTML 内容中提取外部和内联 JS 并进行处理。
    移除打印信息。

    Args:
        html_content: HTML 源代码字符串。
        base_url: HTML 页面的基础 URL，用于规范化相对路径。
        output_file_path: 结果输出文件的路径。
        processed_js_urls_cache: 已处理 JS URL 的缓存。

    Returns:
        如果找到了任何 JS (外部或内联)，则返回 True，否则返回 False。
    """
    js_found = False # 标记是否找到 JS
    total_js_links = 0 # 找到的外部 JS 链接总数

    # --- 优先使用 BeautifulSoup (如果可用) ---
    if BS4_AVAILABLE:
        try:
            log.debug(f"使用 BeautifulSoup 解析 HTML (来源: {base_url})")
            soup = BeautifulSoup(html_content, 'html.parser') # 使用 html.parser

            # --- 提取外部 JS ---
            script_tags = soup.find_all('script', src=True) # 查找所有带 src 属性的 script 标签
            total_js_links = len(script_tags)
            log.info(f"在 {base_url} 中找到 {total_js_links} 个外部 JS 链接 (BS4)。")
            # 移除找到外部 JS 数量的打印 (不符合示例格式)
            # if total_js_links > 0:
            #      print(f"  发现 {Colors.COUNT}{total_js_links}{Colors.RESET} 个外部 JS 文件链接。")

            # 遍历找到的 script 标签
            for tag in script_tags:
                js_src = tag.get('src') # 获取 src 属性值
                if js_src:
                    # 规范化 URL
                    full_js_url = _normalize_url(base_url, js_src)
                    if full_js_url:
                        js_found = True # 标记找到 JS
                        # 处理这个 JS URL (下载和分析)
                        # process_js_url 函数内部的打印也已经被移除
                        # 注意：这里不打印 "开始分析 JS URL"，因为这是从 HTML 中提取的子任务
                        # 提取结果摘要会在 process_js_content 中打印
                        if full_js_url not in processed_js_urls_cache:
                             # 仅在未处理过时打印简略信息并处理
                             log.info(f"  提取到外部 JS: {full_js_url}")
                             process_js_url(full_js_url, output_file_path, processed_js_urls_cache)
                        else:
                             log.info(f"  跳过已处理的外部 JS: {full_js_url}")


                    else:
                        # 记录无法处理的链接
                        log.info(f"跳过无效或无法规范化的 JS 链接: {js_src} (来自: {base_url})")
                        # 移除无效链接打印 (不符合示例格式)
                        # print(f"  {Colors.WARNING}⚠️ 跳过无效或无法规范化的 JS 链接: {js_src}{Colors.RESET}")


            # --- 提取内联 JS ---
            # 查找所有不带 src 属性且内容不为空的 script 标签
            inline_scripts = [tag.string for tag in soup.find_all('script', src=False) if tag.string and tag.string.strip()]
            if inline_scripts:
                js_found = True # 标记找到 JS
                log.info(f"在 {base_url} 中找到 {len(inline_scripts)} 个内联 JS 块 (BS4)。")
                # 移除找到内联 JS 数量的打印 (不符合示例格式)
                # print(f"  {Colors.INFO}发现 {Colors.COUNT}{len(inline_scripts)}{Colors.RESET}{Colors.INFO} 个内联 JS 块。{Colors.RESET}")
                # 写入文件分隔符
                utils.write_to_file(output_file_path, "\n--- 分析内联 JavaScript ---\n")
                # 合并所有内联脚本进行一次性处理，提高效率
                combined_inline = "\n\n; // Inline Script Separator \n\n".join(inline_scripts)
                # 处理合并后的内联脚本内容
                # process_js_content 函数内部的打印也已经被移除
                process_js_content(combined_inline, f"{base_url} (内联脚本)", output_file_path)
            else:
                log.info(f"在 {base_url} 中未找到内联 JS (BS4)。")
                # 移除未找到内联 JS 打印 (不符合示例格式)
                # print(f"  {Colors.WARNING}⚠️ 在 {base_url} 中未找到内联 JS。{Colors.RESET}")


        except Exception as bs_err:
            # 处理 BeautifulSoup 解析时可能发生的错误
            log.error(f"使用 BeautifulSoup 解析 HTML 时出错 ({base_url}): {bs_err}", exc_info=True)
            # 恢复 HTML 解析失败打印到 stderr
            print(f"  {Colors.FAIL}❌ HTML 解析失败 (BeautifulSoup): {base_url} - {bs_err}{Colors.RESET}", file=sys.stderr)
            utils.write_to_file(output_file_path, f"错误：HTML 解析失败 ({base_url}): {bs_err}\n\n")
            return False # 解析失败

    # --- 使用正则表达式 (如果 BS4 不可用) ---
    else:
        log.debug(f"使用正则表达式解析 HTML (来源: {base_url})")
        # --- 提取外部 JS (正则) ---
        js_links_found = []
        try:
            for match in SCRIPT_SRC_PATTERN.finditer(html_content):
                js_src = match.group('src')
                if js_src:
                    full_js_url = _normalize_url(base_url, js_src)
                    if full_js_url:
                        js_links_found.append(full_js_url)
                    else:
                        log.info(f"跳过无效或无法规范化的 JS 链接: {js_src} (来自: {base_url})")
            total_js_links = len(js_links_found)
            log.info(f"在 {base_url} 中找到 {total_js_links} 个外部 JS 链接 (正则)。")
            # 移除找到外部 JS 数量的打印 (不符合示例格式)
            # if total_js_links > 0:
            #      print(f"  发现 {Colors.COUNT}{total_js_links}{Colors.RESET} 个外部 JS 文件链接。")

            # 处理找到的 JS 链接
            for full_js_url in js_links_found:
                 js_found = True
                 # process_js_url 函数内部的打印也已经被移除
                 # 注意：这里不打印 "开始分析 JS URL"
                 if full_js_url not in processed_js_urls_cache:
                     log.info(f"  提取到外部 JS: {full_js_url}")
                     process_js_url(full_js_url, output_file_path, processed_js_urls_cache)
                 else:
                     log.info(f"  跳过已处理的外部 JS: {full_js_url}")


        except Exception as regex_err:
             log.error(f"使用正则提取外部 JS 时出错 ({base_url}): {regex_err}", exc_info=True)
             # 恢复错误打印到 stderr
             print(f"  {Colors.FAIL}❌ 使用正则提取外部 JS 时出错: {base_url} - {regex_err}{Colors.RESET}", file=sys.stderr)


        # --- 提取内联 JS (正则) ---
        inline_scripts = []
        try:
            for match in INLINE_SCRIPT_PATTERN.finditer(html_content):
                script_content = match.group(1)
                if script_content and script_content.strip():
                    inline_scripts.append(script_content.strip())
            if inline_scripts:
                js_found = True
                log.info(f"在 {base_url} 中找到 {len(inline_scripts)} 个内联 JS 块 (正则)。")
                # 移除找到内联 JS 数量的打印 (不符合示例格式)
                # print(f"  {Colors.INFO}发现 {Colors.COUNT}{len(inline_scripts)}{Colors.RESET}{Colors.INFO} 个内联 JS 块。{Colors.RESET}")
                utils.write_to_file(output_file_path, "\n--- 分析内联 JavaScript ---\n")
                combined_inline = "\n\n; // Inline Script Separator \n\n".join(inline_scripts)
                # process_js_content 函数内部的打印也已经被移除
                process_js_content(combined_inline, f"{base_url} (内联脚本)", output_file_path)
            else:
                log.info(f"在 {base_url} 中未找到内联 JS (正则)。")
                # 移除未找到内联 JS 打印 (不符合示例格式)
                # print(f"  {Colors.WARNING}⚠️ 在 {base_url} 中未找到内联 JS。{Colors.RESET}")

        except Exception as regex_err:
             log.error(f"使用正则提取内联 JS 时出错 ({base_url}): {regex_err}", exc_info=True)
             # 恢复错误打印到 stderr
             print(f"  {Colors.FAIL}❌ 使用正则提取内联 JS 时出错: {base_url} - {regex_err}{Colors.RESET}", file=sys.stderr)


    # 如果整个页面既没有外部 JS 也没有内联 JS
    if not js_found:
        parser_method = "BeautifulSoup" if BS4_AVAILABLE else "正则匹配"
        no_js_msg = f"信息：页面中未找到外部或内联 JavaScript (使用 {parser_method})。"
        log.info(no_js_msg)
        # 恢复未找到 JS 警告打印
        print(f"  {Colors.WARNING}⚠️ 页面中未找到 JS: {base_url}{Colors.RESET}")
        utils.write_to_file(output_file_path, no_js_msg + "\n\n")

    return js_found


def read_urls_from_file(file_path: Path) -> Generator[str, None, None]:
    """
    从文件中逐行读取有效的 URL (忽略空行和 # 注释行)。
    使用生成器以节省内存。
    """
    try:
        # 使用 utf-8 编码打开文件，忽略解码错误
        with file_path.open('r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                url = line.strip() # 去除首尾空白
                if url and not url.startswith('#'): # 如果行内容非空且不是注释
                    yield url # 产生 URL
                elif url.startswith('#'):
                    log.debug(f"跳过注释行 {line_num}: {url}")
                # 空行会被自动忽略 (因为 url 为 False)
    except FileNotFoundError:
        log.error(f"URL 列表文件未找到: {file_path}")
        # 恢复文件未找到打印到 stderr
        print(f"{Colors.FAIL}❌ URL 列表文件未找到: {file_path}{Colors.RESET}", file=sys.stderr)
        raise # 重新抛出，让上层处理
    except IOError as e:
        log.error(f"读取 URL 列表文件时出错 {file_path}: {e}")
        # 恢复读取文件错误打印到 stderr
        print(f"{Colors.FAIL}❌ 读取 URL 列表文件时出错: {file_path} - {e}{Colors.RESET}", file=sys.stderr)
        raise # 重新抛出
    except Exception as e:
        error_msg = f"读取 URL 列表文件 {file_path} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        # 恢复处理文件意外错误打印到 stderr
        print(f"{Colors.FAIL}❌ 读取 URL 列表文件时意外出错: {file_path} - {e}{Colors.RESET}", file=sys.stderr)
        raise

def process_url_list_file(file_path_str: str, is_js_list: bool, output_file: Union[str, Path]) -> None:
    """
    处理包含 URL 列表的文件（网页 URL 或 JS URL）。
    保留打印信息。

    Args:
        file_path_str: URL 列表文件路径字符串。
        is_js_list: True 表示文件内容是 JS URL 列表, False 表示是网页 URL 列表。
        output_file: 结果输出文件的路径 (字符串或 Path 对象)。
    """
    file_path = Path(file_path_str) # 转换为 Path 对象
    list_type = "JavaScript URL" if is_js_list else "网页 URL" # 确定列表类型描述
    log.info(f"准备处理 {list_type} 列表文件: {file_path}")
    # 恢复开始处理列表文件的消息打印，修改格式以匹配示例
    print(f"🔎{Colors.INFO}开始分析列表文件: {Colors.PATH}{file_path}{Colors.RESET}")
    # 写入文件分隔符
    utils.write_to_file(output_file, f"## 分析 {list_type} 列表文件: {file_path}\n" + "="*60 + "\n")

    processed_count = 0 # 成功处理的 URL 数量
    error_count = 0     # 处理失败的 URL 数量
    # 为本次列表处理创建一个独立的 JS URL 缓存
    processed_js_urls_cache: Set[str] = set()

    try:
        # 先读取所有有效 URL 到列表，以便计算总数并显示进度
        urls_to_process = list(read_urls_from_file(file_path))
        total_urls = len(urls_to_process)
        # 移除找到 URL 总数的打印 (不符合示例格式)
        # print(f"  发现 {Colors.COUNT}{total_urls}{Colors.RESET} 个 URL 条目。")

        # 遍历 URL 列表进行处理
        for i, url in enumerate(urls_to_process, 1):
            # 移除打印当前处理进度 (不符合示例格式)
            # print(f"\n[{i}/{total_urls}] ", end="") # end="" 避免额外换行，让后续处理函数打印自己的起始信息
            log.info(f"[{i}/{total_urls}] Processing {list_type}: {url}") # 记录到日志
            try:
                # 根据列表类型调用不同的处理函数
                if is_js_list:
                    # process_js_url 函数内部的打印也已经被移除
                    # 注意：这里不打印 "开始分析 JS URL"，因为这是列表项
                    # 提取结果摘要会在 process_js_content 中打印
                    process_js_url(url, output_file, processed_js_urls_cache)
                else:
                    # process_web_page 函数内部的打印也已经被移除
                    # 注意：这里不打印 "开始分析网页"，因为这是列表项
                    # 提取结果摘要会在 process_js_content 中打印
                    process_web_page(url, output_file, processed_js_urls_cache)
                processed_count += 1 # 成功处理，计数加一
            except Exception as e:
                 # 捕获处理单个 URL 时未被内部处理函数捕获的顶层异常 (理论上少见)
                 log.error(f"处理列表项 {i} ({url}) 时发生顶层错误: {e}", exc_info=True)
                 # 恢复处理列表项失败打印到 stderr
                 print(f"\t{Colors.FAIL}❌ 处理列表项 {i} ({url}) 时失败: {e}{Colors.RESET}", file=sys.stderr)
                 utils.write_to_file(output_file, f"错误：处理列表项 {i} ({url}) 时失败: {e}\n\n")
                 error_count += 1 # 处理失败，计数加一

        # --- 列表处理完成后的总结信息 ---
        if processed_count == 0 and error_count == 0 and total_urls == 0:
             # 文件存在但为空或无有效 URL 的情况
             if file_path.is_file() and file_path.stat().st_size == 0:
                 no_urls_msg = f"信息：URL 列表文件 '{file_path}' 为空。"
             else:
                 # 文件不存在或存在但无有效 URL
                 no_urls_msg = f"信息：URL 列表文件 '{file_path}' 中未找到有效 URL 或文件不存在。"
             log.info(no_urls_msg)
             # 恢复警告打印
             print(f"\t{Colors.WARNING}⚠️ {no_urls_msg}{Colors.RESET}")
             utils.write_to_file(output_file, no_urls_msg + "\n")
        else:
             # 打印处理结果总结 - 移除打印，只记录日志 (不符合示例格式)
             summary_msg = f"{list_type} 列表文件 {file_path} 处理完成，共成功处理 {processed_count} 个 URL，失败 {error_count} 个。"
             log.info(summary_msg)
             # print(f"\n{Colors.SUCCESS}✅ {summary_msg}{Colors.RESET}")
             utils.write_to_file(output_file, f"\n{summary_msg}\n")

    except (FileNotFoundError, IOError):
        # 处理文件读取错误 (已在 read_urls_from_file 中记录日志)
        error_msg = f"错误：无法读取 URL 列表文件: {file_path}"
        log.error(error_msg)
        # 恢复错误打印到 stderr
        print(f"{Colors.FAIL}❌ {error_msg}{Colors.RESET}", file=sys.stderr)
        # 再次写入错误信息到输出文件
        utils.write_to_file(output_file, error_msg + "\n\n")
    except Exception as e:
        # 处理读取或循环过程中其他意外错误
        error_msg = f"处理 URL 列表文件 {file_path} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        # 恢复错误打印到 stderr
        print(f"{Colors.FAIL}❌ {error_msg}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file, error_msg + "\n\n")

def process_web_page(page_url: str, output_file_path: Union[str, Path], processed_js_urls_cache: Set[str]) -> None:
    """
    处理单个网页 URL：下载 HTML，提取并分析其中的 JS。
    保留打印信息。

    Args:
        page_url: 网页 URL。
        output_file_path: 结果输出文件的路径 (字符串或 Path 对象)。
        processed_js_urls_cache: 已处理 JS URL 的缓存集合。
    """
    log.info(f"准备分析网页: {page_url}")
    # 恢复开始分析网页的消息打印，修改格式以匹配示例
    print(f"🔎{Colors.INFO}开始分析网页: {Colors.PATH}{page_url}{Colors.RESET}")

    # 验证 URL
    if not _is_valid_url(page_url):
        error_msg = f"错误：提供的网页 URL 无效或不支持: {page_url}"
        log.error(error_msg)
        # 恢复无效网页 URL 打印到 stderr
        print(f"\t{Colors.FAIL}❌ 无效网页 URL: {page_url}{Colors.RESET}", file=sys.stderr)
        utils.write_to_file(output_file_path, error_msg + "\n\n")
        return

    # 写入文件分隔符
    utils.write_to_file(output_file_path, f"## 分析网页: {page_url}\n" + "="*60 + "\n")
    # 下载 HTML 内容
    html_content = _fetch_content(page_url)

    if html_content is not None: # 检查下载是否成功
        if html_content: # 检查内容是否为空
            # 调用函数提取并处理 HTML 中的 JS
            # _extract_js_from_html 函数内部的打印也已经被移除
            _extract_js_from_html(html_content, page_url, output_file_path, processed_js_urls_cache)
            # 找到 JS 的消息在 _extract_js_from_html 内部打印 - 现在也移除了
        else:
            # 网页内容为空
            log.warning(f"网页返回空内容: {page_url}")
            # 恢复网页返回空内容警告打印
            print(f"\t{Colors.WARNING}⚠️ 网页返回空内容: {page_url}{Colors.RESET}")
            utils.write_to_file(output_file_path, f"警告：网页返回空内容: {page_url}\n\n")
    # else: 下载失败的错误已经在 _fetch_content 中处理并打印
