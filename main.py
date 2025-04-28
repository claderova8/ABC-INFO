#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JavaScript API 提取工具 (主脚本)
功能：从 JavaScript 文件或网页中提取 HTTP API 请求信息，并可选择生成 HTML 报告。
(优化版本 v7.6 - 精确控制彩色打印输出)
"""

import argparse
import os
import re # 用于生成安全的文件名 (slugify)
import sys
import warnings
import logging
from pathlib import Path # 用于面向对象的路径操作
from urllib.parse import urlparse # 用于解析 URL
from typing import Optional, NoReturn, Set # 类型提示

# --- 配置日志 ---
# 保留日志配置，日志信息会写入日志系统
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' # 日志格式
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT) # 基础日志配置
log = logging.getLogger(__name__) # 获取主模块的日志记录器

# --- 忽略 requests 的 InsecureRequestWarning ---
# 在进行 HTTPS 请求且 verify=False 时，requests 会发出警告，这里选择忽略
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
    log.debug("已禁用 InsecureRequestWarning。")
except ImportError:
    # 如果导入失败 (例如 requests 版本不同)，则记录调试信息
    log.debug("无法导入 InsecureRequestWarning，可能 requests 版本不同或未安装。")
    pass

# --- 模块导入 ---
# 导入本项目其他模块，并处理可能的导入错误
try:
    import processor # 处理不同输入的模块
    import utils     # 实用工具模块 (文件、颜色等)
    import bg as reporter # HTML 报告生成模块 (别名为 reporter)
    from utils import Colors # 导入颜色类，用于控制台彩色输出
    log.debug("使用直接导入加载模块。")
except ImportError as e:
    # 关键依赖缺失，打印错误信息到 stderr 并退出
    # 保留这里的打印，因为这是程序启动失败的关键信息
    print(f"[CRITICAL] 无法导入所需的模块。请确保 processor.py, utils.py, bg.py, extractor.py, formatter.py 在同一目录或 PYTHONPATH 中。", file=sys.stderr)
    print(f"[CRITICAL] 详细错误: {e}", file=sys.stderr)
    # 尝试从错误信息中提取缺失的模块名，提供更具体的提示
    module_name = "未知模块"
    try:
        match = re.search(r"No module named '(\w+)'", str(e))
        if match: module_name = match.group(1)
        elif "cannot import name" in str(e):
             match = re.search(r"cannot import name '(\w+)'", str(e))
             if match: module_name = match.group(1) + " (内部导入)"
    except Exception: pass
    log.critical(f"无法导入所需的模块 ({module_name})。请确保依赖文件存在且可访问。", exc_info=True)
    sys.exit(1) # 退出程序

# --- 全局常量 ---
DEFAULT_RESULTS_SUFFIX = '_api_results.txt' # 提取结果文件的默认后缀
DEFAULT_REPORT_SUFFIX = '.html'             # HTML 报告文件的默认后缀
MAX_FILENAME_LENGTH = 100                   # 生成文件名时的最大长度限制 (避免过长)

# --- 辅助函数 ---

def slugify(text: str) -> str:
    """
    将文本转换为适合用作文件名的 "slug" 格式 (安全、简短)。
    移除或替换特殊字符和空格。

    Args:
        text: 输入的文本字符串。

    Returns:
        转换后的 slug 字符串。
    """
    if not isinstance(text, str): # 防御性编程，确保输入是字符串
        return ""
    # 移除协议头 (http://, https://, ws://, wss://)
    text = re.sub(r'^(https?://|ws?://)', '', text)
    # 将常见的 URL 分隔符和空格替换为下划线
    text = re.sub(r'[/:?#\[\]@!$&\'()*+,;=\s]+', '_', text.strip())
    # 移除所有非字母、数字、点、下划线、连字符的字符
    text = re.sub(r'[^\w.\-]+', '', text)
    # 移除开头和结尾可能存在的点、下划线、连字符
    slug = text.strip('._-')
    # 限制最终长度
    return slug[:MAX_FILENAME_LENGTH]

def determine_output_filename(args: argparse.Namespace) -> Path:
    """
    根据输入参数自动确定提取结果的输出文件名。
    优先级：从输入文件/URL 生成 -> 默认名称。

    Args:
        args: 解析后的命令行参数对象。

    Returns:
        表示最终输出文件名的 Path 对象。
    """
    base_name = "api_extraction" # 默认基础文件名
    input_source = None # 用于记录输入源，方便调试

    try:
        # 根据不同的输入参数确定基础名称和输入源
        if args.file:
            input_source = args.file
            base_name = Path(input_source).stem # 使用输入文件的基本名 (无后缀)
        elif args.list:
            input_source = args.list
            base_name = Path(input_source).stem + "_pagelist" # 文件基本名 + 后缀
        elif args.extract_list:
            input_source = args.extract_list
            base_name = Path(input_source).stem + "_jslist" # 文件基本名 + 后缀
        elif args.url or args.extract_url:
            input_source = args.url or args.extract_url
            parsed_url = urlparse(input_source)
            domain = parsed_url.netloc or "local" # 获取域名，若无则为 local
            # 获取路径的最后一部分作为文件名参考，如果路径为空或只有'/'则忽略
            path_part = Path(parsed_url.path).name if parsed_url.path and Path(parsed_url.path).name else ''
            # 组合域名和路径部分
            combined = f"{domain}_{path_part}" if path_part else domain
            base_name = slugify(combined) # 生成安全的文件名部分
            if args.extract_url: # 如果是直接提取 JS URL，添加后缀
                base_name += "_js"
        else:
            # argparse 配置了 required=True，理论上不会到这里
            log.error("无法确定输入源类型以生成文件名。")

    except Exception as e:
        # 如果从输入源解析文件名时出错
        source_repr = str(input_source or "未知输入")
        log.warning(f"从输入 '{source_repr}' 解析基础文件名时出错: {e}。将尝试 slugify 输入或使用默认名称。", exc_info=True)
        # 尝试直接 slugify 原始输入作为后备
        try:
            if isinstance(input_source, str):
                base_name = slugify(input_source)
        except Exception:
            pass # 如果 slugify 也失败，则 base_name 保持默认值 "api_extraction"

    # 最终检查生成的基础文件名是否有效 (非空且只包含安全字符)
    if not base_name or not re.match(r'^[a-zA-Z0-9._-]+$', base_name):
        log.warning(f"生成的基础文件名 '{base_name}' 无效或为空，将使用默认名称 'api_extraction'。")
        base_name = "api_extraction"

    # 返回完整的输出文件路径 (Path 对象)
    return Path(f"{base_name}{DEFAULT_RESULTS_SUFFIX}")

def setup_logging(verbose: bool) -> None:
    """根据 verbose 参数设置全局日志级别。"""
    # 如果 verbose 为 True, 设置 DEBUG 级别，否则设置 INFO 级别
    level = logging.DEBUG if verbose else logging.INFO
    # 更新根日志记录器的级别
    logging.getLogger().setLevel(level)
    # 可以选择性地降低某些冗长库 (如 requests) 的日志级别，避免过多不相关的日志
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    log.info(f"日志级别已设置为: {logging.getLevelName(level)}")
    # 检查终端是否支持颜色，如果不支持则禁用 Colors 类中的颜色代码
    if not Colors._supports_color:
        log.warning("终端可能不支持颜色输出，将禁用颜色。")
        # print(f"{Colors.WARNING}警告：终端可能不支持颜色输出，将禁用颜色。{Colors.RESET}") # 移除这里的打印，由日志系统处理警告


def handle_exception(msg: str, e: Exception, exit_code: int = 1) -> NoReturn:
    """
    统一处理严重错误：记录日志，打印错误信息到 stderr，并退出程序。
    此函数用于程序无法继续执行的严重错误，不使用彩色打印以确保在任何终端都可见。

    Args:
        msg: 描述错误的自定义消息。
        e: 捕获到的异常对象。
        exit_code: 退出的状态码 (默认为 1，表示错误)。
    """
    log.critical(f"{msg}: {e}", exc_info=True) # 记录严重错误及堆栈跟踪
    # 打印错误信息到标准错误流 (不带颜色)
    print(f"错误：{msg}: {e}", file=sys.stderr)
    sys.exit(exit_code) # 退出程序

# --- 主函数 ---
def main():
    """程序的主入口点。"""
    global DEFAULT_RESULTS_SUFFIX, DEFAULT_REPORT_SUFFIX # 允许修改全局常量 (虽然本例中未修改)

    # --- 参数解析器设置 ---
    parser = argparse.ArgumentParser(
        description='从 JavaScript 代码或网页中提取 HTTP API 请求信息，并可选择生成 HTML 报告。',
        epilog='示例:\n' # 添加使用示例
               '  python %(prog)s -u https://example.com --report report.html\n'
               '  python %(prog)s -f script.js --report\n'
               '  python %(prog)s -l urls.txt -v',
        formatter_class=argparse.RawDescriptionHelpFormatter # 允许在 help 信息中使用换行符
    )
    # --- 输入参数组 (互斥且必需) ---
    input_group = parser.add_mutually_exclusive_group(required=True) # 定义互斥组，用户必须提供其中一个
    input_group.add_argument('-u', '--url', metavar='PAGE_URL', help='要分析的单个网页 URL。')
    input_group.add_argument('-eu', '--extract-url', metavar='JS_URL', help='要直接分析的单个 JS 文件 URL。')
    input_group.add_argument('-l', '--list', metavar='PAGE_URL_FILE', help='包含网页 URL 列表的文件路径。')
    input_group.add_argument('-el', '--extract-list', metavar='JS_URL_FILE', help='包含 JS 文件 URL 列表的文件路径。')
    input_group.add_argument('-f', '--file', metavar='JS_FILE_PATH', help='要直接分析的本地 JS 文件路径。')
    # --- 报告参数 (可选) ---
    parser.add_argument(
        '--report',
        nargs='?',        # 允许参数不带值 (const=True 生效) 或带一个值 (HTML_PATH)
        const=True,       # 如果提供了 --report 但没有值，则参数值为 True
        metavar='HTML_PATH', # 在帮助信息中显示的值的名称
        help=f'生成 HTML 报告。可选指定路径，否则自动生成 (后缀 {DEFAULT_REPORT_SUFFIX})。'
    )
    # --- 可选参数 ---
    parser.add_argument('-v', '--verbose', action='store_true', help='启用详细日志记录 (DEBUG 级别)。')

    # --- 解析命令行参数 ---
    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse 在显示帮助 (-h) 或参数错误时会调用 sys.exit()
        sys.exit(e.code) # 保持 argparse 的退出码
    except Exception as e:
        # 处理解析过程中可能出现的其他异常
        handle_exception("解析命令行参数时发生错误", e)

    # --- 设置日志级别 ---
    setup_logging(args.verbose)
    log.debug(f"命令行参数: {args}") # 记录解析后的参数 (DEBUG 级别)

    # --- 初始化 ---
    output_file_path = determine_output_filename(args) # 确定输出文件名
    # 恢复开始信息打印
    print(f"{Colors.HEADER}--- 开始 API 提取 ---{Colors.RESET}")
    print(f"{Colors.INFO}提取结果将保存到: {Colors.PATH}{output_file_path}{Colors.RESET}")
    log.info(f"提取结果将保存到: {output_file_path}") # 同时记录到日志

    # 创建/覆盖输出文件并写入文件头
    try:
        utils.create_output_header(output_file_path)
    except Exception as e:
        # 如果无法创建或写入输出文件，则无法继续
        handle_exception(f"无法初始化提取结果输出文件 {output_file_path}", e)

    # --- 执行提取 ---
    extraction_success = True # 标记提取过程是否成功
    exit_code = 0 # 最终退出码，0 表示成功
    try:
        output_path_str = str(output_file_path) # 转换为字符串路径，方便传递
        # 使用 Set 跟踪处理过的 JS URL，避免在处理网页或列表时重复下载和分析同一个 JS 文件
        js_cache: Set[str] = set()

        # 根据参数调用相应的处理函数
        if args.url:
            processor.process_web_page(args.url, output_path_str, js_cache)
        elif args.extract_url:
            processor.process_js_url(args.extract_url, output_path_str, js_cache)
        elif args.file:
            processor.process_js_file(args.file, output_path_str)
        elif args.list:
            processor.process_url_list_file(args.list, is_js_list=False, output_file=output_path_str)
        elif args.extract_list:
            processor.process_url_list_file(args.extract_list, is_js_list=True, output_file=output_path_str)

    except KeyboardInterrupt:
         # 处理用户按 Ctrl+C 中断操作
         log.warning("\n用户中断了提取操作。")
         # 恢复彩色中断打印到 stderr
         print(f"\n{Colors.WARNING}⚠️ 提取操作已被用户中断。{Colors.RESET}", file=sys.stderr)
         try:
             # 尝试在输出文件中记录中断信息
             utils.write_to_file(output_path_str, "\n\n# 提取操作已被用户中断。\n")
         except Exception as write_err:
             log.error(f"无法将中断信息写入输出文件: {write_err}")
         extraction_success = False # 标记提取未成功完成
         exit_code = 1 # 设置非零退出码
    except Exception as e:
        # 捕获提取过程中所有未被内部处理的异常
        log.critical(f"提取过程中发生意外错误: {e}", exc_info=True)
        # 恢复彩色错误打印到 stderr
        print(f"\n{Colors.FAIL}❌ 提取过程中发生意外错误: {e}{Colors.RESET}", file=sys.stderr)
        try:
             # 尝试在输出文件中记录错误信息
             utils.write_to_file(output_path_str, f"\n\n# 提取过程中发生意外错误: {e}\n")
        except Exception as write_err:
             log.error(f"无法将提取错误写入输出文件: {write_err}")
        extraction_success = False # 标记提取未成功完成
        exit_code = 1 # 设置非零退出码

    # --- 提取完成信息 (合并并修改格式) ---
    # 仅当提取成功时打印报告开始信息
    if extraction_success:
        log.info("提取完成，开始生成 HTML 报告...")
        # 恢复并修改提取完成和报告开始的打印格式
        print(f"✅ 提取完成---开始生成 HTML 报告...{Colors.RESET}") # 移除颜色代码，直接在字符串中添加

    # 最终处理完成横幅
    print(f"\n{Colors.HEADER}--- 处理完成 ---{Colors.RESET}")

    # 最终结果和报告路径打印 (修改格式并添加表情符号)
    if extraction_success: # 仅在提取成功时显示结果文件路径
        print(f"  🎮{Colors.INFO}提取结果: {Colors.PATH}{output_file_path}{Colors.RESET}")
    else: # 提取失败时，仍然显示可能不完整的结果文件路径 (如果已创建)
        print(f"  🎮{Colors.WARNING}提取结果 (可能不完整): {Colors.PATH}{output_file_path}{Colors.RESET}", file=sys.stderr)


    report_output_path_str = "" # 报告文件的最终路径字符串
    report_generated = False    # 标记报告是否成功生成
    report_output_path: Optional[Path] = None # 报告文件的 Path 对象

    # 仅当提取成功且用户请求了报告时才生成
    if args.report and extraction_success:
        log.info("开始生成 HTML 报告...") # 此日志保留
        # 确定报告输出路径
        if isinstance(args.report, str):
            report_output_path = Path(args.report)
        elif args.report is True:
            report_output_path = output_file_path.with_suffix(DEFAULT_REPORT_SUFFIX)
            log.info(f"未指定报告路径，将使用默认路径: {report_output_path}")

        if report_output_path:
            report_output_path_str = str(report_output_path)
            try:
                report_success = reporter.create_bg_report(str(output_file_path), report_output_path_str)
                if report_success:
                    log.info(f"HTML 报告已成功生成: {report_output_path_str}")
                    report_generated = True
                    # 恢复并修改报告成功消息打印 (添加表情符号)
                    print(f"  🎁{Colors.SUCCESS}HTML报告: {Colors.PATH}{report_output_path_str}{Colors.RESET}")
                else:
                    log.error("生成 HTML 报告失败。")
                    # 恢复失败打印到 stderr
                    print(f"  {Colors.FAIL}❌ 生成 HTML 报告失败。请检查日志。{Colors.RESET}", file=sys.stderr)
                    exit_code = 1 # 设置错误退出码
            except AttributeError:
                 handle_exception("报告模块 ('bg.py') 缺少 'create_bg_report' 函数", AttributeError())
            except Exception as report_err:
                 handle_exception(f"生成报告时发生意外错误", report_err)

    elif args.report and not extraction_success:
        log.warning("由于提取过程未成功完成，跳过报告生成。")
        # 恢复警告打印到 stderr
        print(f"{Colors.WARNING}⚠️ 由于提取过程未成功完成，跳过报告生成。{Colors.RESET}", file=sys.stderr)
        # 如果报告生成跳过，且用户请求了报告，打印报告跳过信息 (修改格式)
        if report_output_path: # 即使跳过，如果路径已确定，也显示
            print(f"  🎁{Colors.WARNING}HTML报告生成已跳过 (目标路径: {Colors.PATH}{report_output_path_str}{Colors.RESET}){Colors.RESET}", file=sys.stderr)
        else: # 如果路径都未确定，只打印跳过原因
             print(f"  🎁{Colors.WARNING}HTML报告生成已跳过 (因提取错误){Colors.RESET}", file=sys.stderr)


    sys.exit(exit_code) # 使用最终确定的退出码退出程序

# --- 脚本入口点 ---
if __name__ == "__main__":
    # 可选: 在 Windows 上设置控制台输出为 UTF-8 (如果遇到编码问题)
    # if sys.platform == "win32":
    #     try:
    #         import io
    #         sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    #         sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    #     except Exception as e:
    #         log.warning(f"设置控制台 UTF-8 输出失败: {e}")
    main() # 调用主函数
