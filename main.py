#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API提取工具
功能：从JavaScript文件或网页中提取HTTP API请求信息
作者：优化版本
日期：2025-04-20
"""

import argparse
from datetime import datetime
from processors.url_processor import process_js_url, process_url_list
from processors.file_processor import process_js_file
from utils.output_utils import write_to_file, OUTPUT_FILE

def main():
    """主函数：处理命令行参数并执行相应操作"""
    global OUTPUT_FILE
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='提取JavaScript中的API请求信息')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--url', help='要分析的网页URL')
    group.add_argument('-eu', '--extract-url', help='直接分析的JavaScript URL')
    group.add_argument('-l', '--list', help='包含网页URL列表的文件')
    group.add_argument('-el', '--extract-list', help='包含JavaScript URL列表的文件')
    group.add_argument('-f', '--file', help='直接分析本地JavaScript文件')
    parser.add_argument('-o', '--output', help='指定输出文件名', default=OUTPUT_FILE)
    
    args = parser.parse_args()
    
    # 如果指定了输出文件，更新全局变量
    if args.output:
        OUTPUT_FILE = args.output
    
    # 创建新文件并写入标题
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"# JavaScript API请求提取结果\n# 生成时间: {timestamp}\n\n"
    write_to_file(header, mode='w')
    
    # 处理单个网页URL
    if args.url:
        write_to_file(f"## 分析网页: {args.url}\n")
        process_url_list([args.url], is_js=False, output_to_file=True)
    
    # 处理单个JavaScript URL
    elif args.extract_url:
        write_to_file(f"## 分析JavaScript URL: {args.extract_url}\n")
        process_js_url(args.extract_url)
    
    # 处理本地JavaScript文件
    elif args.file:
        write_to_file(f"## 分析本地JavaScript文件: {args.file}\n")
        process_js_file(args.file)
    
    # 处理网页URL列表
    elif args.list:
        write_to_file(f"## 分析URL列表文件: {args.list}\n")
        process_url_list(args.list, is_js=False)
    
    # 处理JavaScript URL列表
    elif args.extract_list:
        write_to_file(f"## 分析JavaScript URL列表文件: {args.extract_list}\n")
        process_url_list(args.extract_list, is_js=True)
    
    print(f"\n分析结果已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()