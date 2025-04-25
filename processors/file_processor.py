# -*- coding: utf-8 -*-
"""
文件处理器模块（异步版本）
功能：处理本地 JavaScript 文件并提取 API 信息（调用 AST 提取器）
"""
import os
import logging
import asyncio
import aiofiles  # 使用 aiofiles 异步读取文件
from functools import partial # 导入 partial 用于 run_in_executor

# 导入新的提取器和格式化器
from extractors.js_extractor import extract_requests
from formatters.param_formatter import format_params
# 异步追加写入函数及默认输出文件
from utils.output_utils import append_to_file, OUTPUT_FILE as DEFAULT_OUTPUT_FILE

logger = logging.getLogger(__name__)

async def process_js_file(file_path, output_to_file=True, output_filename=None):
    """
    异步处理本地 JavaScript 文件并提取请求信息。
    将同步的 CPU 密集型任务 (extract_requests) 放到线程池中执行。

    参数:
        file_path (str): 本地 JavaScript 文件路径
        output_to_file (bool): 是否将结果写入输出文件
        output_filename (str|None): 输出文件名（如果 output_to_file 为 True）

    返回:
        bool: 如果处理成功（包括未找到 API 情况）返回 True，发生错误返回 False
    """
    # 确定输出文件名
    out_file = output_filename or DEFAULT_OUTPUT_FILE

    output_lines = []
    output_lines.append(f"\n--- 分析本地文件：{file_path} ---")
    output_lines.append("=" * 60)
    success = False
    js_content = None # 初始化 js_content

    # 检查文件是否存在
    if not os.path.exists(file_path):
        error_msg = f"错误：本地文件未找到：{file_path}"
        logger.error(error_msg)
        output_lines.append(error_msg)
        success = False # 明确设置失败
    else:
        try:
            # 异步读取文件内容
            async with aiofiles.open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
                js_content = await f.read()
            logger.info(f"已读取文件：{file_path}")
        except FileNotFoundError:
            error_msg = f"错误：读取文件时发生 FileNotFoundError：{file_path}"
            logger.error(error_msg)
            output_lines.append(error_msg)
            success = False
        except UnicodeDecodeError as e:
            error_msg = f"错误：文件编码异常：{file_path} - {e}，请检查文件编码是否为 UTF-8。"
            logger.error(error_msg)
            output_lines.append(error_msg)
            success = False
        except Exception as e:
            error_msg = f"读取文件时发生未知错误：{file_path} - {e}"
            logger.error(error_msg, exc_info=True)
            output_lines.append(error_msg)
            success = False

    # 仅在成功读取文件后才进行处理
    if js_content is not None:
        try:
            logger.info(f"开始在线程池中提取请求信息：{file_path}")
            # --- 性能优化：将同步阻塞操作放入线程池 ---
            loop = asyncio.get_running_loop()
            # 使用 partial 传递参数给要在线程中执行的函数
            # 注意: parse_js_to_ast (在 extract_requests 内部调用) 仍是性能瓶颈
            results = await loop.run_in_executor(
                None,  # 使用默认线程池
                partial(extract_requests, js_content)
            )
            # 对于 Python 3.9+, 可以使用 asyncio.to_thread(extract_requests, js_content)

            logger.info(f"提取完成：{file_path}")

            if results:
                found_count = 0
                for item in results:
                    api_type = item.get('api_type', 'HTTP API')
                    method = item.get('method', 'UNKNOWN')
                    url = item.get('url', 'UNKNOWN')
                    loc = item.get('source_loc', {})
                    loc_str = f"（行号: {loc.get('line', '?')}）" if loc else ""

                    output_lines.append(f"请求：\"{method} {url}\" [{api_type}]{loc_str}")

                    params = item.get('params')
                    # 格式化参数（同步，通常很快，可以在主线程做）
                    formatted = format_params(params)
                    if formatted not in ("无参数", "无参数 (空对象)"):
                        output_lines.append(f"参数：\n{formatted}")
                    output_lines.append("-" * 60)
                    found_count += 1

                logger.info(f"共在 {file_path} 中发现 {found_count} 个 API 调用")
                output_lines.append(f"总计找到 {found_count} 个 API 调用。")
            else:
                output_lines.append("该文件未发现任何 API 请求信息")
                logger.info(f"未在文件中发现 API 调用：{file_path}")

            success = True

        except Exception as e:
            # 捕获提取或格式化过程中可能发生的错误
            error_msg = f"处理文件内容时发生未知错误：{file_path} - {e}"
            logger.error(error_msg, exc_info=True)
            output_lines.append(error_msg)
            success = False

    # --- 统一写入文件 ---
    result_text = "\n".join(output_lines) + "\n"

    if output_to_file:
        try:
            await append_to_file(result_text, out_file)
        except Exception as e:
            logger.error(f"写入结果到输出文件失败：{out_file} - {e}")
            success = False # 如果写入失败，也标记为失败

    return success
