#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
URL处理器模块
功能：处理URL和网页，提取API信息
"""

import re
import requests
from urllib.parse import urljoin

from extractors.js_extractor import extract_requests
from formatters.param_formatter import format_params
from utils.output_utils import write_to_file

def process_js_url(url, output_to_file=True):
    """
    处理JavaScript URL并提取请求信息
    
    参数:
        url: JavaScript文件的URL
        output_to_file: 是否输出到文件
        
    返回:
        处理结果文本
    """
    output = []
    output.append(f"\n对应JS文件: {url}")
    output.append("=" * 60)
    
    try:
        # 下载JavaScript文件
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # 提取请求信息
            results = extract_requests(response.text)
            if results:
                for result in results:
                    # 添加API类型显示
                    api_type = result.get('api_type', 'HTTP API')
                    output.append(f"请求: \"{result['method']} {result['url']}\" [{api_type}]")
                    if result['params']:
                        formatted_params = format_params(result['params'])
                        output.append(f"请求参数: {formatted_params}")
                    output.append("-" * 60)
            else:
                output.append("未找到请求信息")
        else:
            output.append(f"无法下载JS文件，状态码: {response.status_code}")
    except Exception as e:
        output.append(f"处理URL时出错: {str(e)}")
    
    result_text = "\n".join(output)
    
    # 输出到控制台
    print(result_text)
    
    # 输出到文件
    if output_to_file:
        write_to_file(result_text + "\n")
    
    return result_text

def process_url_list(url_list, is_js=False, output_to_file=True):
    """
    处理URL列表
    
    参数:
        url_list: URL列表或包含URL列表的文件路径
        is_js: 是否为JavaScript URL列表（否则为网页URL）
        output_to_file: 是否输出到文件
    """
    overall_output = []
    
    # 如果输入是文件路径，读取文件内容
    if isinstance(url_list, str):
        try:
            with open(url_list, 'r', encoding='utf-8') as f:
                urls = f.read().splitlines()
        except Exception as e:
            error_msg = f"无法读取URL列表文件: {str(e)}"
            print(error_msg)
            if output_to_file:
                write_to_file(error_msg + "\n")
            return
    else:
        urls = url_list
    
    for url in urls:
        url = url.strip()
        # 跳过空行和注释行
        if not url or url.startswith('#'):
            continue
            
        if is_js:
            # 处理JavaScript URL
            result = process_js_url(url, output_to_file=False)
            overall_output.append(result)
        else:
            # 如果是网页URL，尝试提取页面中的JS
            try:
                overall_output.append(f"\n分析网页: {url}")
                overall_output.append("=" * 60)
                
                # 下载网页
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    # 提取页面中的JS链接
                    js_links = re.findall(r'<script\s+[^>]*src="([^"]+\.js)"', response.text)
                    if js_links:
                        for js_link in js_links:
                            # 将相对路径转为绝对URL
                            full_js_url = urljoin(url, js_link)
                            overall_output.append(f"\n发现JS文件: {full_js_url}")
                            # 处理每个JS文件
                            result = process_js_url(full_js_url, output_to_file=False)
                            overall_output.append(result)
                    
                    # 提取内联JS
                    inline_js = re.findall(r'<script[^>]*>(.*?)</script>', response.text, re.DOTALL)
                    if inline_js:
                        overall_output.append("\n分析网页内联JavaScript:")
                        overall_output.append("=" * 60)
                        
                        # 处理每段内联JS
                        for js in inline_js:
                            results = extract_requests(js)
                            if results:
                                for result in results:
                                    # 添加API类型显示
                                    api_type = result.get('api_type', 'HTTP API')
                                    overall_output.append(f"请求: \"{result['method']} {result['url']}\" [{api_type}]")
                                    if result['params']:
                                        formatted_params = format_params(result['params'])
                                        overall_output.append(f"请求参数: {formatted_params}")
                                    overall_output.append("-" * 60)
                    
                    # 如果没找到任何JavaScript
                    if not js_links and not inline_js:
                        overall_output.append("未在页面中找到JavaScript")
                else:
                    overall_output.append(f"无法访问 {url}，状态码: {response.status_code}")
            except Exception as e:
                overall_output.append(f"处理URL {url}时出错: {str(e)}")
        
        overall_output.append("\n" + "=" * 70 + "\n")
    
    # 将结果写入文件
    result_text = "\n".join(overall_output)
    if output_to_file:
        write_to_file(result_text + "\n")
        
    # 输出到控制台
    print(result_text)
    
    return result_text
