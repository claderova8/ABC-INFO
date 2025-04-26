# -*- coding: utf-8 -*-
"""
处理不同输入类型（URL、文件、列表）的函数，
用于 JavaScript API 提取器。
(优化版本 v2)
"""

import requests
import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from requests.exceptions import RequestException
from pathlib import Path # 引入 Path

# --- 配置日志 ---
log = logging.getLogger(__name__)

# --- 模块导入 ---
try:
    from . import extractor
    from . import formatter
    from . import utils
except ImportError:
    import extractor
    import formatter
    import utils

# --- 预编译正则表达式 ---
# 强烈建议使用 BeautifulSoup 解析 HTML
script_src_pattern = re.compile(
    r'<script[^>]+src\s*=\s*["\'](?P<src>[^"\']+\.js(?:\?[^"\']*)?)["\']',
    re.IGNORECASE
)
inline_script_pattern = re.compile(
    r'<script(?![^>]*\ssrc\s*=)(?:[^>]*)>(.*?)</script>',
    re.IGNORECASE | re.DOTALL
)

# --- 辅助函数 ---

def _is_valid_url(url):
    """检查字符串是否是有效的、可处理的 HTTP/HTTPS URL"""
    if not isinstance(url, str): return False
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        log.warning(f"解析 URL 时出错 (可能无效): {url}")
        return False

def _normalize_url(base_url, link):
    """规范化 URL"""
    if not link or not isinstance(link, str): return None
    link = link.strip()
    if not link: return None
    try:
        parsed_link = urlparse(link)
        if parsed_link.scheme in ['http', 'https'] and parsed_link.netloc:
            return urlunparse(parsed_link)
        if link.startswith('//'):
            parsed_base = urlparse(base_url)
            if not parsed_base.scheme:
                 log.warning(f"无法处理协议相对 URL '{link}'，基准 URL '{base_url}' 缺少协议")
                 return None
            new_link_parts = (parsed_base.scheme, ) + parsed_link[1:]
            normalized = urlunparse(new_link_parts)
            return normalized if _is_valid_url(normalized) else None
        joined_url = urljoin(base_url, link)
        if _is_valid_url(joined_url):
            return urlunparse(urlparse(joined_url)) # 标准化
        else:
            log.warning(f"规范化后的 URL 无效: '{joined_url}' (基准 '{base_url}', 链接 '{link}')")
            return None
    except Exception as e:
        log.error(f"规范化 URL '{link}' (基准 '{base_url}') 时出错: {e}")
        return None

# --- 核心处理函数 ---

def process_js_content(js_content, source_name, output_file_str):
    """从 JS 内容提取 API 请求并写入文件"""
    output_lines = [f"\n--- 来源: {source_name} ---", "=" * 60]
    print(f"\n--- 正在分析来源: {source_name} ---")
    extracted_count = 0
    try:
        results = extractor.extract_requests(js_content)
        extracted_count = len(results)
        if results:
            log.info(f"在 {source_name} 中找到 {extracted_count} 个潜在请求。")
            for result in results:
                output_lines.append(f"类型: {result['type']}, 请求: \"{result['method']} {result['url']}\"")
                formatted_params = formatter.format_params(result.get('params'))
                output_lines.append(f"请求参数: {formatted_params}")
                output_lines.append("-" * 60)
        else:
            output_lines.append("未找到请求信息")
            log.info(f"在 {source_name} 中未找到请求信息。")
    except Exception as e:
        error_msg = f"错误：处理 JS 内容时出错 ({source_name}): {str(e)}"
        output_lines.append(error_msg)
        log.error(error_msg, exc_info=True)

    utils.write_to_file(output_file_str, "\n".join(output_lines) + "\n\n")
    print("\n".join(output_lines[1:])) # 打印除第一行外的详细信息
    return extracted_count

def process_js_url(url, output_file_str, processed_urls_cache):
    """处理单个 JavaScript URL"""
    log.info(f"准备处理 JS URL: {url}")
    if not _is_valid_url(url):
        error_msg = f"错误：提供的 JS URL 无效或不支持: {url}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
        return
    if url in processed_urls_cache:
        log.info(f"跳过已处理的 JS URL: {url}")
        return

    print(f"\n正在获取 JS URL: {url}")
    processed_urls_cache.add(url)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=20, headers=headers, verify=False, stream=True)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        if 'javascript' not in content_type and 'text/plain' not in content_type:
             log.warning(f"URL {url} 的 Content-Type ('{content_type}') 可能不是 JS，仍尝试处理。")
        response.encoding = response.apparent_encoding or 'utf-8'
        js_content = response.text
        if js_content:
             process_js_content(js_content, url, output_file_str)
        else:
             log.warning(f"URL 返回空内容: {url}")
             utils.write_to_file(output_file_str, f"警告：URL 返回空内容: {url}\n\n")
    except RequestException as e:
        error_msg = f"错误：无法下载 JS 文件 {url}: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except Exception as e:
        error_msg = f"错误：处理 JS URL {url} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        utils.write_to_file(output_file_str, error_msg + "\n\n")

def process_js_file(file_path_str, output_file_str):
    """处理单个本地 JavaScript 文件"""
    file_path = Path(file_path_str) # 转为 Path 对象
    log.info(f"准备处理本地 JS 文件: {file_path}")
    print(f"\n正在读取 JS 文件: {file_path}")
    try:
        if not file_path.is_file():
             raise FileNotFoundError(f"文件不存在或不是一个有效文件: {file_path}")
        with file_path.open('r', encoding='utf-8', errors='ignore') as f:
            js_content = f.read()
        if js_content:
            process_js_content(js_content, str(file_path), output_file_str) # 传递字符串路径作为 source_name
        else:
             log.warning(f"文件为空: {file_path}")
             utils.write_to_file(output_file_str, f"警告：文件为空: {file_path}\n\n")
    except FileNotFoundError as e:
        error_msg = f"错误：本地 JS 文件未找到: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except IOError as e:
        error_msg = f"错误：读取本地 JS 文件时出错 {file_path}: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except Exception as e:
        error_msg = f"错误：处理本地 JS 文件 {file_path} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        utils.write_to_file(output_file_str, error_msg + "\n\n")

def process_web_page(page_url, output_file_str, processed_js_urls_cache):
    """处理单个网页 URL (建议使用 BeautifulSoup)"""
    log.info(f"准备分析网页: {page_url}")
    if not _is_valid_url(page_url):
        error_msg = f"错误：提供的网页 URL 无效或不支持: {page_url}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
        return

    print(f"\n正在分析网页: {page_url}")
    utils.write_to_file(output_file_str, f"## 分析网页: {page_url}\n" + "="*60 + "\n")
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        response = requests.get(page_url, timeout=30, headers=headers, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        html_content = response.text
        if not html_content:
            log.warning(f"网页返回空内容: {page_url}")
            utils.write_to_file(output_file_str, f"警告：网页返回空内容: {page_url}\n\n")
            return

        js_found_in_page = False
        log.warning("正在使用正则表达式解析 HTML，可能不健壮，推荐使用 BeautifulSoup。")

        # 1. 提取外部 JS
        linked_js_count = 0
        for match in script_src_pattern.finditer(html_content):
            js_link_src = match.group('src')
            if js_link_src:
                full_js_url = _normalize_url(page_url, js_link_src)
                if full_js_url:
                    linked_js_count += 1
                    js_found_in_page = True
                    process_js_url(full_js_url, output_file_str, processed_js_urls_cache)
                else:
                    log.info(f"跳过无效或无法规范化的 JS 链接: {js_link_src} (来自: {page_url})")
        log.info(f"在 {page_url} 中找到 {linked_js_count} 个外部 JS 链接 (正则匹配)。")

        # 2. 提取内联 JS
        inline_scripts_content = []
        for match in inline_script_pattern.finditer(html_content):
            script_content = match.group(1)
            if script_content and script_content.strip():
                inline_scripts_content.append(script_content.strip())
        if inline_scripts_content:
            js_found_in_page = True
            log.info(f"在 {page_url} 中找到 {len(inline_scripts_content)} 个内联 JS 块 (正则匹配)。")
            utils.write_to_file(output_file_str, "\n--- 分析内联 JavaScript ---\n")
            combined_inline_js = "\n\n; // Inline Script Separator \n\n".join(inline_scripts_content)
            process_js_content(combined_inline_js, f"{page_url} (内联脚本)", output_file_str)
        else:
             log.info(f"在 {page_url} 中未找到内联 JS (正则匹配)。")

        if not js_found_in_page:
            no_js_msg = "信息：未在页面中找到外部或内联 JavaScript (正则匹配)。"
            log.info(no_js_msg)
            utils.write_to_file(output_file_str, no_js_msg + "\n\n")

    except RequestException as e:
        error_msg = f"错误：无法访问网页 {page_url}: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except Exception as e:
        error_msg = f"错误：处理网页 {page_url} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        utils.write_to_file(output_file_str, error_msg + "\n\n")

def process_url_list_file(file_path_str, is_js_list, output_file_str):
    """处理包含 URL 列表的文件"""
    file_path = Path(file_path_str) # 转为 Path 对象
    log.info(f"准备处理 URL 列表文件: {file_path} (JS列表: {is_js_list})")
    print(f"\n正在处理 URL 列表文件: {file_path}")
    utils.write_to_file(output_file_str, f"## 分析 URL 列表文件: {file_path}\n" + "="*60 + "\n")
    processed_count = 0
    processed_js_urls_cache = set()
    try:
        if not file_path.is_file():
             raise FileNotFoundError(f"列表文件不存在或不是一个有效文件: {file_path}")
        with file_path.open('r', encoding='utf-8') as f:
            urls = f.readlines()

        for line_num, line in enumerate(urls, 1):
            url = line.strip()
            if not url or url.startswith('#'): continue
            print(f"\n--- 处理列表项 {line_num}: {url} ---")
            try:
                if is_js_list:
                    process_js_url(url, output_file_str, processed_js_urls_cache)
                else:
                    process_web_page(url, output_file_str, processed_js_urls_cache)
                processed_count += 1
            except Exception as e:
                 log.error(f"处理列表项 {line_num} ({url}) 时出错: {e}", exc_info=True)
                 utils.write_to_file(output_file_str, f"错误：处理列表项 {line_num} ({url}) 时失败: {e}\n\n")

        if processed_count == 0:
             no_urls_msg = "信息：URL 列表文件为空或未找到有效 URL。"
             log.info(no_urls_msg)
             utils.write_to_file(output_file_str, no_urls_msg + "\n")
        else:
             log.info(f"URL 列表文件 {file_path} 处理完成，共处理 {processed_count} 个有效 URL。")

    except FileNotFoundError as e:
        error_msg = f"错误：URL 列表文件未找到: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except IOError as e:
        error_msg = f"错误：读取 URL 列表文件时出错 {file_path}: {e}"
        log.error(error_msg)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
    except Exception as e:
        error_msg = f"错误：处理 URL 列表文件 {file_path} 时发生意外错误: {e}"
        log.error(error_msg, exc_info=True)
        utils.write_to_file(output_file_str, error_msg + "\n\n")
