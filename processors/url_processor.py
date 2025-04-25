#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
URL处理器模块
功能：处理URL和网页，提取API信息
"""

import re
import requests
from urllib.parse import urljoin
from requests.exceptions import RequestException, Timeout

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
        # 下载JavaScript文件，设置更短的超时时间
        response = requests.get(url, timeout=5) # 缩短超时时间
        response.raise_for_status() # 检查HTTP请求是否成功

        # 提取请求信息
        results = extract_requests(response.text)
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

    except Timeout:
        output.append(f"下载JS文件超时: {url}")
    except RequestException as e:
        output.append(f"下载JS文件时发生网络错误: {url} - {str(e)}")
    except Exception as e:
        # 捕获其他未知错误
        output.append(f"处理URL时发生未知错误: {url} - {str(e)}")

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
    urls = []
    if isinstance(url_list, str):
        try:
            with open(url_list, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        except FileNotFoundError:
            error_msg = f"URL列表文件未找到: {url_list}"
            print(error_msg)
            if output_to_file:
                write_to_file(error_msg + "\n")
            return
        except Exception as e:
            error_msg = f"无法读取URL列表文件: {url_list} - {str(e)}"
            print(error_msg)
            if output_to_file:
                write_to_file(error_msg + "\n")
            return
    else:
        urls = [url.strip() for url in url_list if url.strip() and not url.strip().startswith('#')]

    if not urls:
        info_msg = "未找到有效的URL进行处理。"
        print(info_msg)
        if output_to_file:
            write_to_file(info_msg + "\n")
        return

    for url in urls:
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
                response.raise_for_status() # 检查HTTP请求是否成功

                # 提取页面中的JS链接
                # 改进的正则表达式，更精确地匹配src属性
                js_links = re.findall(r'<script\s+[^>]*src=["\'](.*?\.js(?:[^"\'>]*)?)["\']', response.text, re.IGNORECASE)
                if js_links:
                    overall_output.append("\n发现外部JavaScript文件:")
                    for js_link in js_links:
                        # 将相对路径转为绝对URL
                        full_js_url = urljoin(url, js_link)
                        overall_output.append(f"- {full_js_url}")
                        # 处理每个JS文件
                        result = process_js_url(full_js_url, output_to_file=False)
                        overall_output.append(result)

                # 提取内联JS
                # 改进的正则表达式，更精确地匹配script标签内容
                inline_js_blocks = re.findall(r'<script[^>]*>(.*?)</script>', response.text, re.DOTALL | re.IGNORECASE)
                if inline_js_blocks:
                    overall_output.append("\n分析网页内联JavaScript:")
                    overall_output.append("=" * 60)

                    # 处理每段内联JS
                    for i, js in enumerate(inline_js_blocks):
                         overall_output.append(f"\n--- 内联JS块 {i+1} ---")
                         results = extract_requests(js)
                         if results:
                             for result in results:
                                 # 添加API类型显示
                                 api_type = result.get('api_type', 'HTTP API')
                                 output_line = f"请求: \"{result['method']} {result['url']}\" [{api_type}]"
                                 overall_output.append(output_line)
                                 if result['params']:
                                     formatted_params = format_params(result['params'])
                                     overall_output.append(f"请求参数: {formatted_params}")
                                 overall_output.append("-" * 60)
                         else:
                             overall_output.append("未找到请求信息")


                # 如果没找到任何JavaScript
                if not js_links and not inline_js_blocks:
                    overall_output.append("未在页面中找到JavaScript")

            except Timeout:
                overall_output.append(f"访问网页超时: {url}")
            except RequestException as e:
                overall_output.append(f"访问网页时发生网络错误: {url} - {str(e)}")
            except Exception as e:
                overall_output.append(f"处理网页 {url} 时发生未知错误: {str(e)}")

        overall_output.append("\n" + "=" * 70 + "\n")

    # 将结果写入文件
    result_text = "\n".join(overall_output)
    if output_to_file:
        write_to_file(result_text + "\n")

    # 输出到控制台
    print(result_text)

    return result_text
