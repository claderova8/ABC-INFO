# -*- coding: utf-8 -*-
"""
JavaScript API 提取器的实用工具函数。
包含文件写入和头部创建功能。
(优化版本 v2)
"""

import os
import logging
from datetime import datetime
from pathlib import Path # 引入 Path

# --- 配置日志 ---
log = logging.getLogger(__name__)


def write_to_file(filepath_str: str, content: str, mode: str = 'a'):
    """将内容安全地写入指定的输出文件"""
    filepath = Path(filepath_str) # 转为 Path 对象
    try:
        # 确保目标目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        # 使用 utf-8 编码打开文件并写入内容
        with filepath.open(mode, encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        log.error(f"写入文件 {filepath} 时发生 IO 错误: {e}")
    except OSError as e:
         log.error(f"创建目录 {filepath.parent} 时发生错误: {e}")
    except Exception as e:
        log.error(f"写入文件 {filepath} 时发生意外错误: {e}", exc_info=True)

def create_output_header(filepath_str: str):
    """创建新的输出文件（或覆盖）并写入文件头信息"""
    filepath = Path(filepath_str) # 转为 Path 对象
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"# JavaScript API 请求提取结果\n"
        header += f"# 生成时间: {timestamp}\n"
        header += "# 注意: 正则表达式提取可能存在误报或漏报，结果仅供参考。\n\n"
        # 以覆盖模式 ('w') 写入文件头
        write_to_file(str(filepath), header, mode='w') # write_to_file 接收字符串
        log.info(f"输出文件 {filepath} 已初始化。")
    except Exception as e:
        # 将错误向上传递
        log.error(f"无法初始化输出文件 {filepath}: {e}")
        raise
