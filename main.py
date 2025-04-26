#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API 提取工具 (主脚本)
功能：从 JavaScript 文件或网页中提取 HTTP API 请求信息，并可选择生成 HTML 报告。
(优化版本 v4 - 移除 -o 参数)
"""

import argparse
import os
import sys
import warnings
import logging
from pathlib import Path
from urllib.parse import urlparse

# --- 配置日志 ---
# 日志级别将在解析参数后根据 -v/--verbose 设置
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__) # 获取主模块日志记录器

# --- 忽略 requests 的 InsecureRequestWarning ---
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
    log.debug("已禁用 InsecureRequestWarning。")
except ImportError:
    log.debug("无法导入 InsecureRequestWarning，可能 requests 版本不同或未安装。")
    pass

# --- 模块导入 ---
try:
    from . import processor
    from . import utils
    from . import reporter
    log.debug("使用相对导入加载模块。")
except ImportError:
    try:
        import processor
        import utils
        import reporter
        log.debug("使用直接导入加载模块。")
    except ImportError as e:
        log.critical(f"无法导入所需的模块 (processor, utils, reporter)。请确保它们与 main.py 在同一目录或位于 Python 路径中。")
        log.critical(f"详细错误: {e}")
        print(f"错误：无法导入所需的模块 (processor, utils, reporter)。请确保它们与 main.py 在同一目录或位于 Python 路径中。", file=sys.stderr)
        print(f"详细错误: {e}", file=sys.stderr)
        sys.exit(1)

# --- 全局配置 ---
DEFAULT_RESULTS_SUFFIX = '_api_results.txt' # 提取结果文件后缀
DEFAULT_REPORT_SUFFIX = '.html' # 报告文件后缀

# --- 辅助函数 ---

def slugify(text: str) -> str:
    """将文本转换为适合用作文件名的 slug 格式 (更通用)"""
    # 移除协议头
    text = re.sub(r'^(https?://|ws?://)', '', text)
    # 替换掉常见的 URL 特殊字符和空格为下划线
    text = re.sub(r'[/:?#\[\]@!$&\'()*+,;=\s]+', '_', text.strip())
    # 移除其他可能不安全的字符（除了字母数字、下划线、连字符、点）
    text = re.sub(r'[^\w\.\-]+', '', text)
    # 移除开头和结尾的下划线/点/连字符
    slug = text.strip('._-')
    # 防止文件名过长
    return slug[:100] # 限制最大长度

def determine_output_filename(args: argparse.Namespace) -> Path:
    """根据输入参数自动确定提取结果的输出文件名"""
    base_name = "api_extraction" # 默认基础名

    if args.file:
        input_path = Path(args.file)
        base_name = input_path.stem # 使用文件名（不含扩展名）
    elif args.list:
        input_path = Path(args.list)
        base_name = input_path.stem + "_list"
    elif args.extract_list:
        input_path = Path(args.extract_list)
        base_name = input_path.stem + "_jslist"
    elif args.url:
        try:
            parsed_url = urlparse(args.url)
            # 使用域名作为基础名，如果路径不为空，可以附加路径的最后部分
            domain = parsed_url.netloc
            path_part = Path(parsed_url.path).name if parsed_url.path and Path(parsed_url.path).name else ''
            base_name = slugify(domain + "_" + path_part if path_part else domain)
        except Exception:
            log.warning(f"无法从 URL '{args.url}' 解析基础文件名，将使用默认名称。")
            base_name = slugify(args.url) # 尝试 slugify 整个 URL
    elif args.extract_url:
         try:
            parsed_url = urlparse(args.extract_url)
            domain = parsed_url.netloc
            path_part = Path(parsed_url.path).name if parsed_url.path and Path(parsed_url.path).name else ''
            base_name = slugify(domain + "_" + path_part if path_part else domain) + "_js"
         except Exception:
            log.warning(f"无法从 JS URL '{args.extract_url}' 解析基础文件名，将使用默认名称。")
            base_name = slugify(args.extract_url) # 尝试 slugify 整个 URL

    # 如果 base_name 为空或无效，则使用默认值
    if not base_name:
        base_name = "api_extraction"

    return Path(f"{base_name}{DEFAULT_RESULTS_SUFFIX}")

# --- 主函数 ---
def main():
    """主函数：解析命令行参数并协调执行提取和报告生成流程"""
    global DEFAULT_RESULTS_SUFFIX, DEFAULT_REPORT_SUFFIX

    # --- 参数解析器设置 ---
    parser = argparse.ArgumentParser(
        description='从 JavaScript 代码或网页中提取 HTTP API 请求信息，并可生成 HTML 报告。\n提取结果将自动保存到基于输入源命名的 .txt 文件中。',
        epilog='示例:\n'
               '  python main.py -u https://example.com --report report.html\n'
               '  python main.py -f script.js --report\n'
               '  python main.py -l urls.txt -v',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # --- 输入参数组 ---
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-u', '--url', metavar='PAGE_URL', help='要分析的单个网页 URL。')
    input_group.add_argument('-eu', '--extract-url', metavar='JS_URL', help='要直接分析的单个 JavaScript 文件 URL。')
    input_group.add_argument('-l', '--list', metavar='PAGE_URL_FILE', help='包含网页 URL 列表的文件路径。')
    input_group.add_argument('-el', '--extract-list', metavar='JS_URL_FILE', help='包含 JavaScript 文件 URL 列表的文件路径。')
    input_group.add_argument('-f', '--file', metavar='JS_FILE_PATH', help='要直接分析的本地 JavaScript 文件路径。')

    # --- 报告参数 ---
    parser.add_argument(
        '--report',
        nargs='?',
        const=True,
        metavar='HTML_REPORT_PATH',
        help=f'生成 HTML 报告。可选地指定报告输出路径，否则将自动生成（基于输入源命名，后缀为 {DEFAULT_REPORT_SUFFIX}）。'
    )

    # --- 可选参数 ---
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='启用详细日志记录 (DEBUG 级别)。'
    )

    # --- 解析命令行参数 ---
    try:
        args = parser.parse_args()
    except SystemExit as e:
         log.error("命令行参数解析错误。")
         sys.exit(e.code)

    # --- 根据 verbose 参数调整日志级别 ---
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("已启用详细日志记录。")
    else:
         logging.getLogger().setLevel(logging.INFO)

    # --- 初始化 ---
    # 自动确定输出文件名
    output_file_path = determine_output_filename(args)
    log.info(f"提取结果将保存到: {output_file_path}")

    # 创建/覆盖提取结果输出文件，并写入文件头信息
    try:
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        utils.create_output_header(str(output_file_path))
    except Exception as e:
        log.critical(f"无法初始化提取结果输出文件 {output_file_path}: {e}", exc_info=True)
        print(f"错误：无法初始化提取结果输出文件 {output_file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"开始分析，提取结果将保存到: {output_file_path}")

    # --- 执行提取 ---
    extraction_success = True
    exit_code = 0
    try:
        # 将 Path 对象转换为字符串传递给旧函数（如果它们需要）
        output_path_str = str(output_file_path)
        if args.url:
            js_cache = set()
            processor.process_web_page(args.url, output_path_str, js_cache)
        elif args.extract_url:
            js_cache = set()
            processor.process_js_url(args.extract_url, output_path_str, js_cache)
        elif args.file:
            processor.process_js_file(args.file, output_path_str)
        elif args.list:
            processor.process_url_list_file(args.list, is_js_list=False, output_file=output_path_str)
        elif args.extract_list:
            processor.process_url_list_file(args.extract_list, is_js_list=True, output_file=output_path_str)

    except KeyboardInterrupt:
         log.warning("\n用户中断了提取操作。")
         print("\n提取操作已被用户中断。", file=sys.stderr)
         utils.write_to_file(output_path_str, "\n\n# 提取操作已被用户中断。\n")
         extraction_success = False
         exit_code = 1
    except Exception as e:
        log.critical(f"提取过程中发生意外错误: {e}", exc_info=True)
        print(f"\n提取过程中发生意外错误: {e}", file=sys.stderr)
        try:
            utils.write_to_file(output_path_str, f"\n\n# 提取过程中发生意外错误: {e}\n")
        except Exception as write_err:
            log.error(f"无法将提取错误写入输出文件: {write_err}")
        extraction_success = False
        exit_code = 1

    # --- 提取完成信息 ---
    if extraction_success:
        log.info(f"提取完成。结果已保存到: {output_file_path}")
        print(f"提取完成。结果已保存到: {output_file_path}")
    else:
        log.error(f"提取过程未成功完成。结果可能不完整: {output_file_path}")
        print(f"提取过程未成功完成。结果可能不完整: {output_file_path}", file=sys.stderr)

    # --- 生成报告 (如果需要且提取成功) ---
    report_output_path_str = "" # 初始化报告路径字符串
    report_generated = False
    if args.report and extraction_success:
        log.info("开始生成 HTML 报告...")
        print("\n开始生成 HTML 报告...")

        if isinstance(args.report, str): # 如果用户指定了报告路径
            report_output_path = Path(args.report)
        elif args.report is True: # 如果用户只提供了 --report 标志
            # 基于提取输出文件名自动生成报告文件名
            report_output_path = output_file_path.with_suffix(DEFAULT_REPORT_SUFFIX)
            log.info(f"未指定报告路径，将使用默认路径: {report_output_path}")
        else:
             log.error("无效的 --report 参数值。")
             exit_code = 1 # 标记错误
             report_output_path = None # 防止后续尝试生成报告

        if report_output_path:
            report_output_path_str = str(report_output_path)
            try:
                # 调用 reporter 模块的函数
                report_success = reporter.create_report(str(output_file_path), report_output_path_str)
                if report_success:
                    log.info(f"HTML 报告已成功生成: {report_output_path_str}")
                    print(f"HTML 报告已成功生成: {report_output_path_str}")
                    report_generated = True
                else:
                    log.error(f"生成 HTML 报告失败。请检查日志。")
                    print(f"错误：生成 HTML 报告失败。请检查日志。", file=sys.stderr)
                    exit_code = 1 # 标记错误
            except Exception as report_err:
                log.critical(f"生成报告时发生意外错误: {report_err}", exc_info=True)
                print(f"\n生成报告时发生意外错误: {report_err}", file=sys.stderr)
                exit_code = 1 # 标记错误

    elif args.report and not extraction_success:
        log.warning("由于提取过程未成功完成，跳过报告生成。")
        print("由于提取过程未成功完成，跳过报告生成。", file=sys.stderr)

    # --- 最终退出 ---
    final_message = f"\n处理完成。"
    if extraction_success:
        final_message += f" 提取结果: {output_file_path}"
    if report_generated:
        final_message += f" HTML报告: {report_output_path_str}"
    elif args.report and report_output_path_str: # 如果尝试生成报告但失败
         final_message += f" 报告生成失败 (目标路径: {report_output_path_str})"

    log.info(final_message)
    print(final_message)
    sys.exit(exit_code)

# --- 脚本入口点 ---
if __name__ == "__main__":
    main()
