# -*- coding: utf-8 -*-
"""
URL 处理器模块 (异步版本)
功能：处理 URL 和网页，提取 API 信息 (使用 aiohttp, BeautifulSoup, AST)
"""
import asyncio
import aiohttp
from urllib.parse import urljoin
from bs4 import BeautifulSoup # 用于解析 HTML
import logging

from extractors.js_extractor import extract_requests # 使用新的 AST 提取器
from formatters.param_formatter import format_params # 使用新的格式化器
from utils.output_utils import write_to_file, append_to_file # 假设 output_utils 适配

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 异步 HTTP 请求 ---
async def fetch_content(session, url, timeout=10):
    """异步获取 URL 内容"""
    try:
        async with session.get(url, timeout=timeout, ssl=False) as response: # ssl=False 忽略证书错误 (慎用)
            response.raise_for_status() # 检查 HTTP 错误 (4xx, 5xx)
            # 尝试多种编码解码
            content = None
            try:
                 content = await response.text(encoding='utf-8')
            except UnicodeDecodeError:
                 try:
                     content = await response.text(encoding='gbk')
                 except UnicodeDecodeError:
                      # 使用原始字节流和猜测的编码
                      raw_content = await response.read()
                      content = raw_content.decode(response.charset or 'utf-8', errors='replace')

            return content
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP error fetching {url}: {e.status} {e.message}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url} after {timeout} seconds.")
    except aiohttp.ClientError as e:
        logger.error(f"Client error fetching {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
    return None

# --- JS 处理 ---
async def process_js_content(js_content, source_url="inline/local", output_to_file=True):
    """处理 JavaScript 内容字符串 (来自文件或 URL)"""
    output_lines = []
    output_lines.append(f"\n--- 分析来源: {source_url} ---")
    output_lines.append("-" * 60)

    results = extract_requests(js_content) # 使用 AST 提取器

    if results:
        for result in results:
            api_type = result.get('api_type', 'HTTP API')
            method = result.get('method', 'UNKNOWN')
            url = result.get('url', 'UNKNOWN')
            loc = result.get('source_loc', {})
            loc_str = f" (Line: {loc.get('line', '?')})" if loc else ""

            output_lines.append(f"请求: \"{method} {url}\" [{api_type}]{loc_str}")

            params = result.get('params')
            if params is not None: # 检查是否为 None
                formatted_params = format_params(params) # 使用新的格式化器
                output_lines.append(f"参数:\n{formatted_params}")
            output_lines.append("-" * 60)
    else:
        output_lines.append("在此来源未找到 API 请求信息")

    result_text = "\n".join(output_lines) + "\n"

    # 异步写入文件 (如果 output_utils 支持) 或同步写入
    if output_to_file:
        # write_to_file(result_text) # 如果是同步的
        await append_to_file(result_text) # 假设 output_utils 有异步追加函数

    return result_text


async def process_js_url(session, url, output_to_file=True):
    """处理单个 JavaScript URL"""
    logger.info(f"Fetching JS from URL: {url}")
    js_content = await fetch_content(session, url)
    if js_content:
        logger.info(f"Processing JS content from: {url}")
        return await process_js_content(js_content, source_url=url, output_to_file=output_to_file)
    else:
        error_msg = f"\n--- 无法获取或处理 JS URL: {url} ---\n"
        if output_to_file:
             await append_to_file(error_msg)
        return error_msg


# --- 网页处理 ---
async def process_html_page(session, page_url, output_to_file=True):
    """处理单个网页 URL，提取并分析 JS"""
    page_output = []
    page_output.append(f"\n{'='*30} 分析网页: {page_url} {'='*30}")

    logger.info(f"Fetching HTML page: {page_url}")
    html_content = await fetch_content(session, page_url)

    if not html_content:
        error_msg = f"无法获取网页内容: {page_url}\n"
        page_output.append(error_msg)
        if output_to_file:
            await append_to_file("\n".join(page_output))
        return "\n".join(page_output)

    logger.info(f"Parsing HTML and extracting scripts from: {page_url}")
    soup = BeautifulSoup(html_content, 'html.parser') # 使用 bs4 解析 HTML

    js_tasks = []
    processed_js_urls = set() # 防止重复处理同一个 JS URL

    # 提取外部 JS 文件链接
    script_tags_src = soup.find_all('script', src=True)
    if script_tags_src:
        page_output.append("\n发现外部 JavaScript 文件:")
        for tag in script_tags_src:
            js_link = tag['src']
            if not js_link: continue
            full_js_url = urljoin(page_url, js_link) # 处理相对路径
            if full_js_url not in processed_js_urls:
                 page_output.append(f"- {full_js_url}")
                 # 创建异步任务来处理这个 JS URL
                 js_tasks.append(process_js_url(session, full_js_url, output_to_file=False))
                 processed_js_urls.add(full_js_url)
    else:
         page_output.append("\n未发现外部 JavaScript 文件链接。")


    # 提取内联 JS
    inline_script_tags = soup.find_all('script', src=False)
    inline_js_found = False
    if inline_script_tags:
        page_output.append("\n分析内联 JavaScript:")
        for i, tag in enumerate(inline_script_tags):
            inline_js = tag.string
            if inline_js and inline_js.strip():
                inline_js_found = True
                source_name = f"inline script {i+1} on {page_url}"
                 # 创建异步任务处理内联 JS
                js_tasks.append(process_js_content(inline_js, source_url=source_name, output_to_file=False))
    if not inline_js_found:
        page_output.append("\n未发现有效的内联 JavaScript 代码。")


    # ---- 并发执行所有 JS 分析任务 ----
    if js_tasks:
         logger.info(f"Waiting for {len(js_tasks)} JS analysis tasks for {page_url}...")
         js_results = await asyncio.gather(*js_tasks)
         logger.info(f"Finished JS analysis tasks for {page_url}.")
         # 将每个 JS 分析结果追加到页面输出
         for js_result_text in js_results:
             page_output.append(js_result_text)
    else:
        page_output.append("\n未找到可分析的 JavaScript (外部或内联)。")


    page_output.append(f"\n{'='*30} 结束分析网页: {page_url} {'='*30}\n")
    final_page_text = "\n".join(page_output)

    # 统一写入该页面的所有分析结果
    if output_to_file:
        await append_to_file(final_page_text)

    return final_page_text


# --- 列表处理 ---
async def process_url_list(url_list_source, is_js=False, output_to_file=True, concurrency=10):
    """
    异步处理 URL 列表 (来自文件或列表对象)
    """
    urls = []
    if isinstance(url_list_source, str): # 是文件路径
        try:
            with open(url_list_source, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            logger.info(f"Read {len(urls)} URLs from file: {url_list_source}")
        except FileNotFoundError:
            logger.error(f"URL list file not found: {url_list_source}")
            if output_to_file: await append_to_file(f"Error: URL list file not found: {url_list_source}\n")
            return
        except Exception as e:
            logger.error(f"Error reading URL list file {url_list_source}: {e}")
            if output_to_file: await append_to_file(f"Error reading URL list file {url_list_source}: {e}\n")
            return
    elif isinstance(url_list_source, list):
        urls = [url.strip() for url in url_list_source if isinstance(url, str) and url.strip() and not url.strip().startswith('#')]
        logger.info(f"Processing {len(urls)} URLs from list.")
    else:
        logger.error("Invalid url_list_source type. Expected file path (str) or list.")
        return

    if not urls:
        logger.warning("No valid URLs found to process.")
        if output_to_file: await append_to_file("Info: No valid URLs found to process.\n")
        return

    # 创建 aiohttp 客户端会话
    async with aiohttp.ClientSession() as session:
        tasks = []
        # 创建处理任务
        for url in urls:
            if is_js:
                tasks.append(process_js_url(session, url, output_to_file=output_to_file))
            else:
                tasks.append(process_html_page(session, url, output_to_file=output_to_file))

        # 使用 Semaphore 控制并发数量
        semaphore = asyncio.Semaphore(concurrency)
        async def run_with_semaphore(task):
            async with semaphore:
                return await task

        logger.info(f"Starting processing of {len(tasks)} tasks with concurrency limit {concurrency}...")
        # 并发执行任务
        results = await asyncio.gather(*(run_with_semaphore(task) for task in tasks))
        logger.info("Finished processing all URLs.")

        # (可选) 可以在这里处理或汇总 results，但结果已写入文件
        # print("\n--- Overall Summary ---")
        # print(f"Processed {len(results)} URLs/Pages.")

