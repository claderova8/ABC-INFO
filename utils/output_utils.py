#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
输出工具模块
功能：处理结果输出到文件
"""

# 全局变量声明
OUTPUT_FILE = 'ok.txt'  # 默认输出文件名

def write_to_file(content, mode='a'):
    """
    写入内容到输出文件
    
    参数:
        content: 要写入的内容
        mode: 文件打开模式，'a'为追加，'w'为覆盖
    """
    with open(OUTPUT_FILE, mode, encoding='utf-8') as f:
        f.write(content)