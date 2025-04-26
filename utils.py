# -*- coding: utf-8 -*-
"""
JavaScript API 提取器的实用工具函数。
包含文件写入和头部创建功能。
"""

import os
from datetime import datetime

def write_to_file(filepath, content, mode='a'):
    """
    将内容写入指定的输出文件。

    参数:
        filepath (str): 输出文件的路径。
        content (str): 要写入的字符串内容。
        mode (str): 文件打开模式 ('a' 表示追加, 'w' 表示覆盖)。
    """
    try:
        # 确保目标目录存在，如果不存在则创建
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # 使用 utf-8 编码打开文件并写入内容
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        # 处理文件写入时可能发生的 IO 错误
        print(f"错误：写入文件 {filepath} 时出错: {e}")
    except Exception as e:
        # 处理其他意外错误
        print(f"错误：写入文件时发生意外错误: {e}")

def create_output_header(filepath):
    """
    创建一个新的输出文件（或覆盖现有文件）并写入文件头信息。

    参数:
        filepath (str): 输出文件的路径。
    """
    # 获取当前时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 定义文件头内容
    header = f"# JavaScript API 请求提取结果\n# 生成时间: {timestamp}\n\n"
    # 以覆盖模式 ('w') 写入文件头
    write_to_file(filepath, header, mode='w')

