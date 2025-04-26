#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API 提取工具 (主脚本)
功能：从 JavaScript 文件或网页中提取 HTTP API 请求信息（包括 RESTful, GraphQL, WebSocket）。
(优化版本)
"""

import argparse
import os
import sys
import warnings
import logging

# --- 配置日志 ---
# 可以根据需要调整日志级别和格式
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# --- 忽略 requests 的 InsecureRequestWarning ---
# requests 通常在 verify=False 时发出此警告
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
    logging.debug("已禁用 InsecureRequestWarning。")
except ImportError:
    logging.debug("无法导入 InsecureRequestWarning，可能 requests 版本不同或未安装。")
    pass

# --- 模块导入 ---
# 导入本地模块中的函数
# 假设模块 (processor, utils) 与 main.py 在同一个包或目录下。
try:
    # 优先尝试相对导入（适用于作为包运行时）
    from . import processor
    from . import utils
    logging.debug("使用相对导入加载模块。")
except ImportError:
    # 如果相对导入失败（例如作为顶级脚本运行时），则尝试直接导入
    try:
        import processor
        import utils
        logging.debug("使用直接导入加载模块。")
    except ImportError as e:
        # 使用 logging 记录错误信息
        logging.critical(f"无法导入所需的模块 (processor, utils)。请确保它们与 main.py 在同一目录或位于 Python 路径中。")
        logging.critical(f"详细错误: {e}")
        # 打印到 stderr 以确保用户看到错误信息
        print(f"错误：无法导入所需的模块 (processor, utils)。请确保它们与 main.py 在同一目录或位于 Python 路径中。", file=sys.stderr)
        print(f"详细错误: {e}", file=sys.stderr)
        sys.exit(1) # 无法继续执行，退出

# --- 全局配置 ---
DEFAULT_OUTPUT_FILE = 'api_extraction_results.txt' # 默认输出文件名

# --- 主函数 ---
def main():
    """主函数：解析命令行参数并协调执行相应的处理流程"""
    global DEFAULT_OUTPUT_FILE # 允许命令行参数修改默认输出文件名

    # --- 参数解析器设置 ---
    parser = argparse.ArgumentParser(
        description='从 JavaScript 代码或网页中提取 HTTP API 请求信息 (RESTful, GraphQL, WebSocket)。',
        epilog='示例:\n'
               '  python main.py -u https://example.com -o results.txt\n'
               '  python main.py -f script.js\n'
               '  python main.py -l urls.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter # 保留 epilog 中的换行符
    )

    # --- 输入参数组 (互斥，必须提供其中一个) ---
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '-u', '--url',
        metavar='PAGE_URL', # 参数的元变量名，用于帮助信息
        help='要分析的单个网页 URL。将提取该页面引用的 JS 和内联 JS。' # 参数的帮助说明
    )
    input_group.add_argument(
        '-eu', '--extract-url',
        metavar='JS_URL',
        help='要直接分析的单个 JavaScript 文件 URL。'
    )
    input_group.add_argument(
        '-l', '--list',
        metavar='PAGE_URL_FILE',
        help='包含网页 URL 列表的文件路径 (每行一个 URL, # 开头为注释)。'
    )
    input_group.add_argument(
        '-el', '--extract-list',
        metavar='JS_URL_FILE',
        help='包含 JavaScript 文件 URL 列表的文件路径 (每行一个 URL, # 开头为注释)。'
    )
    input_group.add_argument(
        '-f', '--file',
        metavar='JS_FILE_PATH',
        help='要直接分析的本地 JavaScript 文件路径。'
    )

    # --- 输出文件参数 ---
    parser.add_argument(
        '-o', '--output',
        metavar='OUTPUT_FILE',
        help=f'指定输出结果的文件名 (默认为: {DEFAULT_OUTPUT_FILE})',
        default=DEFAULT_OUTPUT_FILE # 设置默认值
    )

    # --- 可选参数 ---
    parser.add_argument(
        '-v', '--verbose',
        action='store_true', # 如果出现此参数，则值为 True
        help='启用详细日志记录 (DEBUG 级别)。'
    )


    # --- 解析命令行参数 ---
    try:
        args = parser.parse_args()
    except SystemExit as e:
         # 如果参数解析出错（例如缺少必需参数），argparse 会调用 sys.exit()
         # argparse 默认会打印帮助信息，这里只需退出
         logging.error("命令行参数解析错误。")
         sys.exit(e.code) # 以 argparse 的退出码退出

    # --- 根据 verbose 参数调整日志级别 ---
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("已启用详细日志记录。")

    # --- 初始化 ---
    output_file_path = args.output # 获取最终的输出文件路径
    # 创建/覆盖输出文件，并写入文件头信息
    try:
        utils.create_output_header(output_file_path)
    except Exception as e:
        # 处理创建输出文件或写入文件头时可能发生的错误
        logging.critical(f"无法初始化输出文件 {output_file_path}: {e}", exc_info=True)
        print(f"错误：无法初始化输出文件 {output_file_path}: {e}", file=sys.stderr)
        sys.exit(1) # 无法继续，退出

    logging.info(f"开始分析，结果将保存到: {output_file_path}")
    print(f"开始分析，结果将保存到: {output_file_path}")

    # --- 根据解析的参数调用相应的处理函数 ---
    exit_code = 0 # 默认为成功退出
    try:
        if args.url:
            # 处理单个网页 URL
            js_cache = set()
            processor.process_web_page(args.url, output_file_path, js_cache)
        elif args.extract_url:
            # 处理单个 JS URL
            js_cache = set()
            processor.process_js_url(args.extract_url, output_file_path, js_cache)
        elif args.file:
            # 处理本地 JS 文件
            processor.process_js_file(args.file, output_file_path)
        elif args.list:
            # 处理网页 URL 列表文件
            processor.process_url_list_file(args.list, is_js_list=False, output_file=output_file_path)
        elif args.extract_list:
            # 处理 JS URL 列表文件
            processor.process_url_list_file(args.extract_list, is_js_list=True, output_file=output_file_path)
        # 此处不需要 else，因为 input_group 设置了 required=True

    except KeyboardInterrupt:
         logging.warning("\n用户中断了操作。")
         print("\n操作已被用户中断。", file=sys.stderr)
         utils.write_to_file(output_file_path, "\n\n# 操作已被用户中断。\n")
         exit_code = 1 # 设置退出码为 1 表示中断
    except Exception as e:
        # 捕获在处理过程中可能发生的未预料的顶层错误
        logging.critical(f"处理过程中发生意外错误: {e}", exc_info=True)
        print(f"\n处理过程中发生意外错误: {e}", file=sys.stderr)
        # 尝试向输出文件写入错误信息
        try:
            utils.write_to_file(output_file_path, f"\n\n# 处理过程中发生意外错误: {e}\n")
        except Exception as write_err:
            logging.error(f"无法将顶层错误写入输出文件: {write_err}")
        exit_code = 1 # 设置退出码为 1 表示错误

    finally:
        # 无论成功还是失败，都打印结束信息
        final_message = f"\n分析完成。结果已{'部分' if exit_code != 0 else ''}保存到: {output_file_path}"
        logging.info(final_message)
        print(final_message)
        sys.exit(exit_code) # 以相应的退出码退出

# --- 脚本入口点 ---
if __name__ == "__main__":
    # 当脚本被直接执行时 (__name__ == "__main__")，调用 main() 函数
    main()
