# -*- coding: utf-8 -*-
"""
JavaScript API 提取器的实用工具函数。
包含文件写入和头部创建功能。
(优化版本)
"""

import os
import logging
from datetime import datetime

# --- 配置日志 ---
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def write_to_file(filepath, content, mode='a'):
    """
    将内容安全地写入指定的输出文件。

    参数:
        filepath (str): 输出文件的路径。
        content (str): 要写入的字符串内容。
        mode (str): 文件打开模式 ('a' 表示追加, 'w' 表示覆盖)。
    """
    try:
        # 确保目标目录存在，如果不存在则创建
        # 在尝试创建目录前检查路径是否为空或无效
        if not filepath:
             logging.error("文件路径为空，无法写入。")
             return
        dir_path = os.path.dirname(filepath)
        # 如果目录路径为空（例如，只提供文件名），则在当前目录创建
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # 使用 utf-8 编码打开文件并写入内容
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        # 处理文件写入时可能发生的 IO 错误
        logging.error(f"写入文件 {filepath} 时发生 IO 错误: {e}")
        # 可以在这里考虑重试或其他恢复机制
    except OSError as e:
         # 处理创建目录时可能发生的错误
         logging.error(f"创建目录 {os.path.dirname(filepath)} 时发生错误: {e}")
    except Exception as e:
        # 处理其他意外错误
        logging.error(f"写入文件 {filepath} 时发生意外错误: {e}", exc_info=True)

def create_output_header(filepath):
    """
    创建一个新的输出文件（或覆盖现有文件）并写入文件头信息。

    参数:
        filepath (str): 输出文件的路径。

    Raises:
        IOError: 如果无法写入文件头。
        OSError: 如果无法创建目录。
        Exception: 其他意外错误。
    """
    try:
        # 获取当前时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 定义文件头内容
        header = f"# JavaScript API 请求提取结果\n"
        header += f"# 生成时间: {timestamp}\n"
        header += "# 注意: 正则表达式提取可能存在误报或漏报，结果仅供参考。\n\n"
        # 以覆盖模式 ('w') 写入文件头
        write_to_file(filepath, header, mode='w')
        logging.info(f"输出文件 {filepath} 已初始化。")
    except Exception as e:
        # 将错误向上传递，以便主程序可以决定如何处理
        logging.error(f"无法初始化输出文件 {filepath}: {e}")
        raise # 重新抛出异常

