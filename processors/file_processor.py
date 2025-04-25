#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件处理器模块
功能：处理本地JavaScript文件并提取API信息
"""

from extractors.js_extractor import extract_requests
from formatters.param_formatter import format_params
from utils.output_utils import write_to_file
import os # 导入os模块用于文件路径检查

def process_js_file(file_path, output_to_file=True):
    """
    处理本地JavaScript文件并提取请求信息

    参数:
        file_path: 本地JavaScript文件路径
        output_to_file: 是否输出到文件

    返回:
        处理结果文本
    """
    output = []
    output.append(f"\n对应JS文件: {file_path}")
    output.append("=" * 60)

    # 检查文件是否存在
    if not os.path.exists(file_path):
        error_msg = f"错误: 本地文件未找到: {file_path}"
        print(error_msg)
        if output_to_file:
            write_to_file(error_msg + "\n")
        return error_msg

    try:
        # 读取本地JavaScript文件
        with open(file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
            # 提取请求信息
            results = extract_requests(js_content)
            if results:
                for result in results:
                    # 添加API类型显示
                    api_type = result.get('api_type', 'HTTP API')
                    output.append(f"请求: \"{result['method']} {result['url']}\" [{api_type}]")
                    if result['params']:
                         # 格式化参数，并处理格式化失败的情况
                        formatted_params = format_params(result['params'])
                        output.append(f"请求参数: {formatted_params}")
                    output.append("-" * 60)
            else:
                output.append("未找到请求信息")
    except FileNotFoundError:
         error_msg = f"错误: 读取文件时发生FileNotFoundError: {file_path}"
         print(error_msg)
         if output_to_file:
             write_to_file(error_msg + "\n")
         return error_msg
    except Exception as e:
        # 捕获其他未知错误
        error_msg = f"处理文件时发生未知错误: {file_path} - {str(e)}"
        print(error_msg)
        if output_to_file:
            write_to_file(error_msg + "\n")
        return error_msg

    result_text = "\n".join(output)

    # 输出到控制台
    print(result_text)

    # 输出到文件
    if output_to_file:
        write_to_file(result_text + "\n")

    return result_text
