# -*- coding: utf-8 -*-
"""
文件处理器模块
功能：处理本地JavaScript文件并提取API信息 (调用 AST 提取器)
"""
import os
import logging
import asyncio # 如果需要异步写入

# 导入新的提取器和格式化器
from extractors.js_extractor import extract_requests
from formatters.param_formatter import format_params
# 假设 output_utils 有 append_to_file
from utils.output_utils import append_to_file

logger = logging.getLogger(__name__)

# 注意：这个函数本身保持同步，但内部调用的 extract_requests 现在使用 AST
# 如果需要完全异步化本地文件处理（例如使用 aiofiles），则需要更大改动
def process_js_file(file_path, output_to_file=True):
    """
    处理本地JavaScript文件并提取请求信息

    参数:
        file_path: 本地JavaScript文件路径
        output_to_file: 是否输出到文件

    返回:
        处理结果文本 (同步返回，但写入可能是异步触发)
    """
    output_lines = []
    output_lines.append(f"\n--- 分析本地文件: {file_path} ---")
    output_lines.append("=" * 60)

    if not os.path.exists(file_path):
        error_msg = f"错误: 本地文件未找到: {file_path}"
        logger.error(error_msg)
        output_lines.append(error_msg)
        result_text = "\n".join(output_lines) + "\n"
        if output_to_file:
             # 触发异步写入
             asyncio.create_task(append_to_file(result_text))
        return result_text # 同步返回错误信息

    try:
        # 读取本地JavaScript文件
        with open(file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        logger.info(f"Extracting requests from local file: {file_path}")
        # 调用新的 AST 提取器
        results = extract_requests(js_content)

        if results:
            for result in results:
                api_type = result.get('api_type', 'HTTP API')
                method = result.get('method', 'UNKNOWN')
                url = result.get('url', 'UNKNOWN')
                loc = result.get('source_loc', {})
                loc_str = f" (Line: {loc.get('line', '?')})" if loc else ""

                output_lines.append(f"请求: \"{method} {url}\" [{api_type}]{loc_str}")

                params = result.get('params')
                if params is not None:
                    # 调用新的格式化器
                    formatted_params = format_params(params)
                    output_lines.append(f"参数:\n{formatted_params}")
                output_lines.append("-" * 60)
        else:
            output_lines.append("在此文件未找到 API 请求信息")

    except FileNotFoundError:
         error_msg = f"错误: 读取文件时发生 FileNotFoundError: {file_path}"
         logger.error(error_msg)
         output_lines.append(error_msg)
    except Exception as e:
        error_msg = f"处理文件时发生未知错误: {file_path} - {str(e)}"
        logger.error(error_msg, exc_info=True) # 添加堆栈跟踪
        output_lines.append(error_msg)

    result_text = "\n".join(output_lines) + "\n"

    # 输出到控制台 (可选)
    # print(result_text)

    # 触发异步写入文件
    if output_to_file:
        asyncio.create_task(append_to_file(result_text))

    return result_text # 同步返回结果文本
