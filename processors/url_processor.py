#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavaScript API提取工具 (异步 + AST 版本)
功能：从JavaScript文件或网页中提取HTTP API请求信息
作者：优化版本
日期：2025-04-25
"""
import argparse
import asyncio
import time
import logging
from datetime import datetime

# 确保在导入其他模块之前配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s] %(message)s')
logger = logging.getLogger(__name__)

# 导入重构后的模块
from processors.url_processor import process_js_url, process_url_list, process_html_page
from processors.file_processor import process_js_file # file_processor 保持同步，但调用新的提取器
from utils.output_utils import write_to_file, setup_output_file, OUTPUT_FILE, append_to_file # 假设 output_utils 已更新
import utils.ast_parser # 确保可以找到 Node.js

async def main():
    """主函数：处理命令行参数并执行相应操作 (异步)"""
    global OUTPUT_FILE # 允许修改全局输出文件名

    parser = argparse.ArgumentParser(description='提取JavaScript中的API请求信息 (Async + AST Version)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--url', help='要分析的网页URL')
    group.add_argument('-eu', '--extract-url', help='直接分析的JavaScript URL')
    group.add_argument('-l', '--list', help='包含网页URL列表的文件')
    group.add_argument('-el', '--extract-list', help='包含JavaScript URL列表的文件')
    group.add_argument('-f', '--file', help='直接分析本地JavaScript文件')
    parser.add_argument('-o', '--output', help=f'指定输出文件名 (默认: {OUTPUT_FILE})')
    parser.add_argument('-c', '--concurrency', type=int, default=10, help='处理URL列表时的并发数 (默认: 10)')
    parser.add_argument('--debug', action='store_true', help='启用 DEBUG 级别的日志')

    args = parser.parse_args()

    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    # 更新输出文件名
    if args.output:
        OUTPUT_FILE = args.output
        logger.info(f"Output file set to: {OUTPUT_FILE}")

    # 初始化输出文件 (写入标题)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"# JavaScript API 请求提取结果 (Async + AST)\n# 生成时间: {timestamp}\n"
    header += f"# 命令参数: {' '.join(sys.argv[1:])}\n" # 记录运行参数
    setup_output_file(header) # 使用 setup 函数清空并写入头部

    start_time = time.time()

    # --- 执行任务 ---
    try:
        if args.url:
            await append_to_file(f"## 分析单个网页: {args.url}\n")
            # 需要创建 aiohttp session 来调用 process_html_page
            async with aiohttp.ClientSession() as session:
                 await process_html_page(session, args.url, output_to_file=True)

        elif args.extract_url:
            await append_to_file(f"## 分析单个 JavaScript URL: {args.extract_url}\n")
            async with aiohttp.ClientSession() as session:
                await process_js_url(session, args.extract_url, output_to_file=True)

        elif args.file:
            # 本地文件处理保持同步，但内部调用已更新的 extract_requests
            logger.info(f"Analyzing local JavaScript file: {args.file}")
            await append_to_file(f"## 分析本地 JavaScript 文件: {args.file}\n")
            process_js_file(args.file, output_to_file=True) # 假设 process_js_file 内部调用 await append_to_file

        elif args.list:
            logger.info(f"Analyzing webpage URL list file: {args.list} with concurrency {args.concurrency}")
            await append_to_file(f"## 分析网页 URL 列表文件: {args.list}\n")
            await process_url_list(args.list, is_js=False, output_to_file=True, concurrency=args.concurrency)

        elif args.extract_list:
            logger.info(f"Analyzing JavaScript URL list file: {args.extract_list} with concurrency {args.concurrency}")
            await append_to_file(f"## 分析 JavaScript URL 列表文件: {args.extract_list}\n")
            await process_url_list(args.extract_list, is_js=True, output_to_file=True, concurrency=args.concurrency)

    except Exception as e:
         logger.critical(f"An critical error occurred during processing: {e}", exc_info=True)
         await append_to_file(f"\nCRITICAL ERROR: {e}\n")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Processing finished in {duration:.2f} seconds.")
        logger.info(f"Analysis results saved to: {OUTPUT_FILE}")
        await append_to_file(f"\n# 分析完成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        await append_to_file(f"# 总耗时: {duration:.2f} 秒\n")

if __name__ == "__main__":
    # 导入 aiohttp 和 sys (如果需要记录参数)
    import aiohttp
    import sys
    # 运行异步主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user.")
    except Exception as e:
         logger.critical(f"Failed to run the async application: {e}", exc_info=True)

