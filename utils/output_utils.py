# -*- coding: utf-8 -*-
"""
输出工具模块 (适配异步写入)
功能：处理结果输出到文件
"""
import asyncio
import aiofiles # 需要安装 aiofiles: pip install aiofiles
import logging
import os

logger = logging.getLogger(__name__)

OUTPUT_FILE = 'output_results.md' # 更改默认扩展名为 .md
_file_lock = asyncio.Lock() # 异步锁，确保写入操作的原子性

def setup_output_file(header_content):
    """清空或创建输出文件，并写入头部内容 (同步操作)"""
    global OUTPUT_FILE
    try:
        # 确保目录存在
        output_dir = os.path.dirname(OUTPUT_FILE)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir)
             logger.info(f"Created output directory: {output_dir}")

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(header_content)
        logger.info(f"Output file '{OUTPUT_FILE}' initialized.")
    except IOError as e:
        logger.error(f"Failed to initialize output file '{OUTPUT_FILE}': {e}")
        # 可以考虑退出程序或使用备用文件名
        raise # 重新抛出异常，让调用者知道初始化失败

async def append_to_file(content):
    """异步追加内容到输出文件 (线程/协程安全)"""
    global OUTPUT_FILE
    async with _file_lock: # 获取锁
        try:
            async with aiofiles.open(OUTPUT_FILE, mode='a', encoding='utf-8') as f:
                await f.write(content)
        except Exception as e:
            logger.error(f"Failed to append content to '{OUTPUT_FILE}': {e}")

# 保留旧的同步写入函数，以防万一或用于非异步部分
def write_to_file(content, mode='a'):
    """同步写入内容到输出文件 (非协程安全)"""
    global OUTPUT_FILE
    try:
        # 确保目录存在 (以防万一 setup 未运行)
        output_dir = os.path.dirname(OUTPUT_FILE)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir)

        with open(OUTPUT_FILE, mode, encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write content synchronously to '{OUTPUT_FILE}': {e}")

