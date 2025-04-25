#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavaScript API 提取工具（异步 + AST 版本）
功能：从 JavaScript 文件或网页中异步提取 HTTP API 请求信息
作者：优化版本
日期：2025-04-25
"""
import argparse
import asyncio
import time
import logging
import sys
import os
from datetime import datetime
import aiohttp

# --- 配置日志（统一配置） ---
# 根据调试标志确定根日志记录器级别
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] %(message)s')
root_logger = logging.getLogger()
# 默认日志级别，后续根据 --debug 参数修改
root_logger.setLevel(logging.INFO)

# 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# 本模块专用日志记录器
logger = logging.getLogger(__name__)

# --- 导入项目模块 ---
# 确保脚本在项目根目录运行，或根据需要调整 PYTHONPATH
try:
    from processors.url_processor import process_js_url, process_url_list, process_html_page
    from processors.file_processor import process_js_file  # 异步处理本地文件
    from utils.output_utils import setup_output_file, append_to_file, OUTPUT_FILE as DEFAULT_OUTPUT_FILE
    import utils.ast_parser
except ImportError as e:
    logger.critical(f"导入项目模块失败：{e}。请确保从项目根目录运行脚本或配置路径正确。")
    sys.exit(1)

# --- 主函数 ---
async def main():
    """主函数：处理命令行参数并执行相应操作（异步）"""
    # 使用默认输出文件，可通过 -o/--output 覆盖
    output_file = DEFAULT_OUTPUT_FILE

    parser = argparse.ArgumentParser(
        description='提取 JavaScript 中的 API 请求信息（Async + AST 版本）',
        formatter_class=argparse.RawDescriptionHelpFormatter  # 保持描述格式
    )
    # 输入源选项组（必选）
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--url', help='要分析的网页 URL')
    group.add_argument('-eu', '--extract-url', help='直接分析的 JavaScript URL')
    group.add_argument('-l', '--list', help='包含网页 URL 列表的文件路径')
    group.add_argument('-el', '--extract-list', help='包含 JavaScript URL 列表的文件路径')
    group.add_argument('-f', '--file', help='直接分析本地 JavaScript 文件路径')

    # 输出和并发选项
    parser.add_argument('-o', '--output', help=f'指定输出文件名（默认: {DEFAULT_OUTPUT_FILE}）')
    parser.add_argument('-c', '--concurrency', type=int, default=10,
                        help='处理 URL 列表时的并发数（默认: 10）')
    parser.add_argument('--debug', action='store_true', help='启用 DEBUG 级别的日志')

    args = parser.parse_args()

    # --- 配置日志级别和输出文件 ---
    if args.debug:
        root_logger.setLevel(logging.DEBUG)
        logger.debug("已启用调试日志。")
    else:
        root_logger.setLevel(logging.INFO)

    if args.output:
        output_file = args.output
        # 更新 utils.output_utils 中的全局输出文件名（如有必要）
        import utils.output_utils
        utils.output_utils.OUTPUT_FILE = output_file
        logger.info(f"输出文件已设置为：{output_file}")
    else:
        logger.info(f"使用默认输出文件：{output_file}")

    # --- 初始化输出文件 ---
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    script_name = os.path.basename(sys.argv[0])  # 使用脚本文件名简化展示
    command_args = ' '.join(sys.argv[1:])
    header = f"# JavaScript API 请求提取结果（Async + AST）\n"
    header += f"# 生成时间：{timestamp}\n"
    header += f"# 命令：{script_name} {command_args}\n\n"
    try:
        await setup_output_file(header, output_file)
    except Exception as e:
        logger.critical(f"初始化输出文件失败：{e}", exc_info=True)
        sys.exit(1)

    start_time = time.time()
    tasks_completed = 0
    tasks_failed = 0

    # --- 执行任务 ---
    try:
        # 使用单个 Session 进行多次 HTTP 请求以提高效率
        async with aiohttp.ClientSession() as session:
            if args.url:
                logger.info(f"分析单个网页 URL：{args.url}")
                await append_to_file(f"## 分析单个网页：{args.url}\n", output_file)
                success = await process_html_page(session, args.url,
                                                  output_to_file=True,
                                                  output_filename=output_file)
                tasks_completed += 1 if success else 0
                tasks_failed += 0 if success else 1

            elif args.extract_url:
                logger.info(f"分析单个 JavaScript URL：{args.extract_url}")
                await append_to_file(f"## 分析单个 JavaScript URL：{args.extract_url}\n", output_file)
                success = await process_js_url(session, args.extract_url,
                                               output_to_file=True,
                                               output_filename=output_file)
                tasks_completed += 1 if success else 0
                tasks_failed += 0 if success else 1

            elif args.file:
                logger.info(f"分析本地 JavaScript 文件：{args.file}")
                await append_to_file(f"## 分析本地 JavaScript 文件：{args.file}\n", output_file)
                success = await process_js_file(args.file,
                                                output_to_file=True,
                                                output_filename=output_file)
                tasks_completed += 1 if success else 0
                tasks_failed += 0 if success else 1

            elif args.list:
                logger.info(f"分析网页 URL 列表文件：{args.list}，并发数：{args.concurrency}")
                await append_to_file(f"## 分析网页 URL 列表文件：{args.list}\n", output_file)
                completed, failed = await process_url_list(
                    session, args.list, is_js=False,
                    output_to_file=True,
                    concurrency=args.concurrency,
                    output_filename=output_file
                )
                tasks_completed += completed
                tasks_failed += failed

            elif args.extract_list:
                logger.info(f"分析 JavaScript URL 列表文件：{args.extract_list}，并发数：{args.concurrency}")
                await append_to_file(f"## 分析 JavaScript URL 列表文件：{args.extract_list}\n", output_file)
                completed, failed = await process_url_list(
                    session, args.extract_list, is_js=True,
                    output_to_file=True,
                    concurrency=args.concurrency,
                    output_filename=output_file
                )
                tasks_completed += completed
                tasks_failed += failed

    except FileNotFoundError as e:
        logger.critical(f"输入文件未找到：{e}", exc_info=True)
        await append_to_file(f"\nCRITICAL ERROR：输入文件未找到 - {e}\n", output_file)
        tasks_failed += 1
    except aiohttp.ClientError as e:
        logger.critical(f"HTTP 客户端错误：{e}", exc_info=True)
        await append_to_file(f"\nCRITICAL ERROR：HTTP 客户端错误 - {e}\n", output_file)
        tasks_failed += 1
    except Exception as e:
        logger.critical(f"处理过程中发生未知错误：{e}", exc_info=True)
        await append_to_file(f"\nCRITICAL ERROR：{e}\n", output_file)
        tasks_failed += 1
    finally:
        # --- 结束处理 ---
        end_time = time.time()
        duration = end_time - start_time
        summary = f"\n# 分析完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        summary += f"# 总耗时：{duration:.2f} 秒\n"
        summary += f"# 任务完成数：{tasks_completed}，任务失败数：{tasks_failed}\n"

        logger.info(f"处理完成，用时 {duration:.2f} 秒。完成：{tasks_completed}，失败：{tasks_failed}")
        logger.info(f"分析结果已保存至：{output_file}")
        try:
            await append_to_file(summary, output_file)
        except Exception as e:
            logger.error(f"写入摘要到输出文件失败：{e}")

        # 可选：如果有任何任务失败，则使用非零退出码退出
        if tasks_failed > 0:
            sys.exit(1)

if __name__ == "__main__":
    # 预先检查 Node.js（可选，ast_parser 也会处理）
    try:
        utils.ast_parser.create_node_script()
    except Exception as e:
        logger.warning(f"未能确保 Node.js 脚本存在：{e}")

    # 运行异步主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户已中断处理。")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"异步应用运行失败：{e}", exc_info=True)
        sys.exit(1)
