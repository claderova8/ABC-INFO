# -*- coding: utf-8 -*-
"""
输出工具模块（异步版本）
功能：将提取结果异步写入文件，确保并发安全
"""
import asyncio
import logging
import aiofiles  # 使用 aiofiles 进行异步文件操作

logger = logging.getLogger(__name__)

# 默认输出文件名，可由主脚本覆盖
OUTPUT_FILE = "api_extraction_results.md"

# 锁对象，防止多任务并发写入时发生竞态
output_lock = asyncio.Lock()

async def setup_output_file(header: str, filename: str = None):
    """
    异步创建或清空输出文件，并写入头部信息。

    参数:
        header (str): 要写入的头部内容
        filename (str, 可选): 输出文件名，默认为 OUTPUT_FILE
    抛出:
        IOError: 无法写入文件时抛出
    """
    file_to_write = filename or OUTPUT_FILE
    async with output_lock:
        try:
            async with aiofiles.open(file_to_write, mode='w', encoding='utf-8') as f:
                await f.write(header)
            logger.debug(f"已初始化输出文件：'{file_to_write}'，并写入头部信息。")
        except IOError as e:
            logger.error(f"初始化输出文件时出错：'{file_to_write}' - {e}")
            raise

async def append_to_file(content: str, filename: str = None):
    """
    异步将内容追加到输出文件。

    参数:
        content (str): 要追加的文本内容
        filename (str, 可选): 输出文件名，默认为 OUTPUT_FILE
    """
    file_to_write = filename or OUTPUT_FILE
    async with output_lock:
        try:
            async with aiofiles.open(file_to_write, mode='a', encoding='utf-8') as f:
                await f.write(content)
            # 可选调试日志，可能会过于冗余
            # logger.debug(f"已将内容追加到文件：'{file_to_write}'。")
        except IOError as e:
            logger.error(f"追加写入输出文件时出错：'{file_to_write}' - {e}")
            # 如需在写入失败时抛出异常，可在此处使用 raise
