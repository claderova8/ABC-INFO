#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件处理器模块
功能：处理本地JavaScript文件并提取API信息
"""

from extractors.js_extractor import extract_requests
from formatters.param_formatter import format_params
from utils.output_utils import write_to_file

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
    
    try:
        # 读取本地JavaScript文件
        with open(file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
            # 提取请求信息
            results = extract_requests(js_content)
            if results:
                for result in results:
                    output.append(f"请求: \"{result['method']} {result['url']}\"")
                    if result['params']:
                        formatted_params = format_params(result['params'])
                        output.append(f"请求参数: {formatted_params}")
                    output.append("-" * 60)
            else:
                output.append("未找到请求信息")
    except Exception as e:
        output.append(f"处理文件时出错: {str(e)}")
    
    result_text = "\n".join(output)
    
    # 输出到控制台
    print(result_text)
    
    # 输出到文件
    if output_to_file:
        write_to_file(result_text + "\n")
    
    return result_text