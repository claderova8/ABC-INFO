# -*- coding: utf-8 -*-
"""
JavaScript API 提取器的实用工具函数模块。
包含文件写入、创建输出文件头和控制台颜色功能。
(优化版本 v4.3 - 添加中文注释和优化)
"""

import logging
import sys # 导入 sys 用于平台检查
from datetime import datetime
from pathlib import Path
from typing import Union

# --- 配置日志 ---
log = logging.getLogger(__name__) # 获取当前模块的日志记录器

# --- 控制台颜色类 ---
class Colors:
    """
    用于控制台输出的 ANSI 颜色代码。
    如果标准输出不是 TTY (例如重定向到文件)，则禁用颜色。
    """
    _supports_color = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() # 检查是否支持颜色

    # ANSI 转义码
    HEADER = '\033[95m' if _supports_color else ''    # 紫色 (页眉)
    OKBLUE = '\033[94m' if _supports_color else ''    # 蓝色 (信息)
    OKCYAN = '\033[96m' if _supports_color else ''    # 青色 (路径/源)
    OKGREEN = '\033[92m' if _supports_color else ''   # 绿色 (成功/计数)
    WARNING = '\033[93m' if _supports_color else ''   # 黄色 (警告)
    FAIL = '\033[91m' if _supports_color else ''      # 红色 (失败/错误)
    ENDC = '\033[0m' if _supports_color else ''       # 重置颜色
    BOLD = '\033[1m' if _supports_color else ''       # 粗体
    UNDERLINE = '\033[4m' if _supports_color else ''  # 下划线

    # 为特定输出格式定义的语义化颜色
    INFO = OKBLUE           # 普通信息
    SUCCESS = OKGREEN       # 成功消息
    SOURCE = OKCYAN         # 来源标识 (URL/文件名)
    COUNT = BOLD + OKGREEN  # 计数 (加粗绿色)
    PARAM_COUNT = BOLD + OKBLUE # 带参数计数 (加粗蓝色)
    PATH = UNDERLINE + OKCYAN # 文件/URL 路径 (下划线青色)
    RESET = ENDC            # 用于重置颜色

# --- 文件操作函数 ---

def write_to_file(filepath: Union[str, Path], content: str, mode: str = 'a') -> bool:
    """
    将内容安全地写入指定的文件。

    Args:
        filepath: 要写入的文件路径 (字符串或 Path 对象)。
        content: 要写入的字符串内容。
        mode: 文件打开模式 ('a' 追加, 'w' 覆盖)。

    Returns:
        写入成功返回 True，否则返回 False。
    """
    try:
        # 统一转换为 Path 对象，提高路径操作的健壮性
        path_obj = Path(filepath)

        # 确保目标目录存在，如果不存在则递归创建
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # 使用 utf-8 编码写入文件，确保兼容性
        with path_obj.open(mode, encoding='utf-8') as f:
            f.write(content)
        log.debug(f"内容已成功写入文件: {path_obj} (模式: {mode})")
        return True

    except FileNotFoundError:
        # 虽然上面创建了目录，但路径本身可能仍有问题
        log.error(f"写入文件失败：路径不存在或无效 {filepath}")
        return False
    except PermissionError:
        # 处理文件权限问题
        log.error(f"写入文件失败：没有权限访问 {filepath}")
        return False
    except IOError as e:
        # 处理通用的输入/输出错误
        log.error(f"写入文件 {filepath} 时发生 IO 错误: {e}")
        return False
    except OSError as e:
         # 处理更广泛的操作系统级别错误，如磁盘空间不足
         log.error(f"写入文件或创建目录 {Path(filepath).parent} 时发生系统错误: {e}")
         return False
    except Exception as e:
        # 捕获所有其他未预料的错误
        log.error(f"写入文件 {filepath} 时发生意外错误: {e}", exc_info=True)
        return False

def create_output_header(filepath: Union[str, Path]) -> None:
    """
    创建新的输出文件（或覆盖现有文件）并写入标准的头部信息。
    如果写入失败，会记录错误并抛出异常。

    Args:
        filepath: 要创建/覆盖的文件路径 (字符串或 Path 对象)。

    Raises:
        IOError: 如果无法写入文件头。
        Exception: 其他底层写入错误。
    """
    path_obj = Path(filepath) # 转换为 Path 对象

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # 获取当前时间戳
        tool_version = "1.0" # 工具版本号 (可以根据需要修改或从其他地方获取)

        # 构建文件头内容
        header = (
            f"# JavaScript API 请求提取结果\n"
            f"# 生成时间: {timestamp}\n"
            f"# 工具版本: {tool_version}\n"
            f"# 注意: 结果基于启发式规则，可能存在误报或漏报，请结合实际情况分析。\n\n"
        )

        # 以覆盖模式 ('w') 写入文件头，并检查写入是否成功
        if not write_to_file(path_obj, header, mode='w'):
            # 如果 write_to_file 返回 False，表示写入失败，抛出异常
            raise IOError(f"无法写入文件头到 {path_obj}")

        log.info(f"输出文件 {path_obj} 已成功初始化并写入文件头。")

    except Exception as e:
        # 捕获 write_to_file 可能抛出的异常或其他错误
        log.error(f"初始化输出文件 {path_obj} 失败: {e}")
        # 将异常向上抛出，由调用者处理
        raise
