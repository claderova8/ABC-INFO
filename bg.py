#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 报告生成工具 (优化版本)
功能：读取 API 提取结果文件，解析并生成结构化、交互式的 HTML 报告。
"""
import re
import sys
import html
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

# --- 配置日志 ---
log = logging.getLogger(__name__)
# 确保即使主模块未配置，这里也有基础配置
# 检查当前 logger 是否有 handlers，如果没有，则检查根 logger
if not log.handlers:
    # 检查根 logger 是否有 handlers
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # 如果根 logger 也未配置，则进行基础配置
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    # 如果根 logger 已配置，则当前 logger 会继承配置，无需额外配置

# --- 常量与预编译正则表达式 ---
# 匹配章节头，例如 '--- 来源: xxx ---'
SECTION_HEADER_REGEX = re.compile(r'^--- 来源: (.+) ---$')
# 匹配请求行，例如 '类型: RESTful, 请求: "GET /api/users"'
REQUEST_LINE_REGEX = re.compile(r'^类型: (\w+), 请求: "(\w+)\s+(.+?)"$')
# 匹配参数开始行，例如 '请求参数: {"key": "value"}' 或 '请求参数:'
PARAMS_START_REGEX = re.compile(r'^请求参数:\s*(.*)$')
# 匹配分隔符行，例如 '---' 或 '==='
SEPARATOR_REGEX = re.compile(r'^[=-]{3,}$')

# --- 数据结构 ---
@dataclass
class Request:
    """存储单个 API 请求的详细信息。"""
    type: str    # 请求类型 (例如 RESTful, GraphQL, WebSocket)
    method: str  # HTTP 方法 (例如 GET, POST) 或 WS/GRAPHQL
    url: str     # 请求 URL
    params: Optional[str] = None # 请求参数字符串，可选

@dataclass
class Section:
    """存储报告中一个章节（来源，如 JS 文件或 URL）的信息。"""
    source_name: str            # 来源名称
    requests: List[Request] = field(default_factory=list) # 该来源下的请求列表

# --- 辅助函数 ---
def slugify(text: str) -> str:
    """
    将文本转换为适合用作 HTML ID 的 slug 格式。
    移除协议、替换特殊字符，确保 ID 的有效性。
    """
    if not isinstance(text, str):
        return ""
    # 移除常见的协议头
    text = re.sub(r'^(https?://|ws?://)', '', text)
    # 将常见的 URL 分隔符和点替换为下划线
    text = text.replace('/', '_').replace('.', '_')
    # 替换所有非单词字符、下划线、连字符为下划线
    slug = re.sub(r'[^\w\-]+', '_', text.strip())
    # 合并连续的下划线为一个
    slug = re.sub(r'_+', '_', slug)
    # 移除开头和结尾的下划线，并限制总长度
    return slug.strip('_')[:100]

def _try_format_json(params_str: str) -> str:
    """
    尝试将参数字符串格式化为美观的 JSON，失败则返回原始转义字符串。
    处理 "无参数" 特殊情况，并对非字符串或 None 输入进行转义。
    """
    # 处理非字符串或 None 输入
    if not params_str or not isinstance(params_str, str):
        return html.escape(str(params_str))

    params_str = params_str.strip()
    # 如果是 "无参数"，直接返回特定的 HTML 标记
    if params_str == "无参数":
         return "<em>无参数</em>"

    # 尝试进行基本的 JSON 清理和解析
    cleaned_param = params_str

    # 只有当字符串看起来像 JSON 对象或数组时，才尝试清理和解析
    is_obj_arr = cleaned_param.startswith(('{', '[')) and cleaned_param.endswith(('}', ']'))

    if is_obj_arr:
        try:
            # 尝试对未加引号的键加引号 (仅在对象或数组内部)
            # 使用 lambda 函数处理匹配，确保只替换键部分
            cleaned_param = re.sub(r'([{,]\s*)([a-zA-Z0-9_$]+)\s*:', lambda m: m.group(1) + '"' + m.group(2) + '"' + ':', cleaned_param)
            # 尝试将单引号值转为双引号值
            cleaned_param = re.sub(r":\s*'((?:\\.|[^'])*)'", r':"\1"', cleaned_param)
            # 尝试移除末尾逗号 (在对象或数组内部)
            cleaned_param = re.sub(r',\s*([}\]])', r'\1', cleaned_param)

            # 尝试解析为 JSON
            parsed = json.loads(cleaned_param)
            # 如果解析成功，格式化为美观的 JSON 字符串
            pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)
            # 对格式化后的 JSON 进行 HTML 转义
            return html.escape(pretty_json)
        except (json.JSONDecodeError, TypeError) as e:
             # JSON 解析失败或类型错误，记录调试信息并返回原始转义字符串
             log.debug(f"参数无法格式化为 JSON (解析失败: {e}), 将显示原始转义值: {params_str[:100]}...")
             return html.escape(params_str) # JSON 错误时返回原始转义字符串
        except Exception as e:
            # 捕获其他意外错误
            log.warning(f"格式化参数为 JSON 时发生意外错误 (清理/解析阶段): {e}", exc_info=True)
            return html.escape(params_str) # 其他错误时返回原始转义字符串

    else:
        # 对于不像 JSON 对象/数组的结构 (如变量名或简单字符串)，直接进行 HTML 转义
        log.debug(f"参数不像是 JSON 对象/数组，直接转义: {params_str[:100]}...")
        return html.escape(params_str)


# --- 解析函数 ---
def parse_log(path: Path) -> List[Section]:
    """
    解析 API 提取结果文件。
    文件格式要求：
    --- 来源: [来源名称] ---
    类型: [类型], 请求: "[方法] [URL]"
    请求参数: [参数内容]
    ---
    ... (下一个请求或来源)

    Args:
        path: 输入文件的 Path 对象。
    Returns:
        包含 Section 对象的列表。如果文件不存在或读取失败，返回空列表。
    """
    # 检查文件是否存在且是有效文件
    if not path.is_file():
        log.error(f"报告生成失败：输入文件不存在或不是有效文件: {path}")
        return []

    try:
        # 读取文件内容，使用 utf-8 编码，忽略无法解码的字符
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except IOError as e:
        log.error(f"读取输入文件时发生 IO 错误 {path}: {e}")
        return []
    except Exception as e:
        log.error(f"读取输入文件失败 {path}: {e}", exc_info=True)
        return []

    sections: List[Section] = [] # 存储所有解析出的章节
    current_section: Optional[Section] = None # 当前正在处理的章节
    current_request: Optional[Request] = None # 当前正在处理的请求
    is_reading_params = False     # 标记是否正在读取参数内容 (参数可能跨行)
    params_buffer: List[str] = [] # 存储多行参数内容的缓冲区

    log.info(f"开始解析提取结果文件: {path} (共 {len(lines)} 行)")
    line_num = 0
    while line_num < len(lines):
        line = lines[line_num].strip() # 读取当前行并去除首尾空白
        line_num += 1 # 移动到下一行

        # 跳过空行和分隔符行
        # 如果遇到分隔符且正在读取参数，则结束参数块
        if not line or SEPARATOR_REGEX.match(line):
            if SEPARATOR_REGEX.match(line) and is_reading_params and current_request:
                 # 将参数缓冲区的内容合并，去除首尾空白，如果为空则设为 None
                 current_request.params = '\n'.join(params_buffer).strip() or None
                 log.debug(f"结束参数读取 (遇到分隔符): {current_request.params[:100] if current_request.params else 'None'}...")
                 is_reading_params = False
                 params_buffer = []
            continue # 继续处理下一行

        # --- 状态机逻辑：根据当前行类型转换状态 ---
        header_match = SECTION_HEADER_REGEX.match(line)
        request_match = REQUEST_LINE_REGEX.match(line)
        params_match = PARAMS_START_REGEX.match(line)

        # 结束上一参数块的条件：遇到新章节、新请求或新的参数开始行
        # 只有当 is_reading_params 为 True 时才需要检查
        should_finalize_params = is_reading_params and (header_match or request_match or params_match)

        if should_finalize_params and current_request:
            # 将参数缓冲区的内容合并，去除首尾空白，如果为空则设为 None
            current_request.params = '\n'.join(params_buffer).strip() or None
            log.debug(f"结束参数读取 (遇到新块): {current_request.params[:100] if current_request.params else 'None'}...")
            is_reading_params = False
            params_buffer = []
            # 注意：这里不能 continue，因为当前行可能是新块的开始，需要继续处理

        # 处理新章节开始行
        if header_match:
            source_name = header_match.group(1).strip() # 提取来源名称
            current_section = Section(source_name=source_name) # 创建新章节对象
            sections.append(current_section) # 添加到章节列表
            current_request = None # 重置当前请求，因为新章节开始了
            is_reading_params = False # 确保新章节开始时不在读参数状态
            params_buffer = [] # 清空参数缓冲区
            log.debug(f"进入新章节: {source_name}")
            continue # 处理下一行

        # 如果当前不在任何章节内 (例如文件开头没有章节头)，跳过该行
        if not current_section:
             log.debug(f"跳过无章节归属的行: {line[:100]}...")
             continue # 处理下一行

        # 处理新请求行
        if request_match:
            req_type, req_method, req_url = request_match.groups() # 提取类型、方法、URL
            current_request = Request(
                type=req_type.strip(),
                method=req_method.strip().upper(), # 方法转为大写
                url=req_url.strip()
            )
            current_section.requests.append(current_request) # 将新请求添加到当前章节
            is_reading_params = False # 确保新请求开始时不在读参数状态
            params_buffer = [] # 清空参数缓冲区
            log.debug(f"找到新请求: {current_request.method} {current_request.url}")
            continue # 处理下一行

        # 处理参数开始行
        if params_match and current_request: # 确保有当前请求可以附加参数
            is_reading_params = True # 进入读取参数状态
            # 获取参数开始行中可能包含的第一部分参数内容
            first_param_line = params_match.group(1).strip()
            # 如果第一部分内容非空，则添加到缓冲区
            params_buffer = [first_param_line] if first_param_line else []
            log.debug(f"开始读取参数 (首行: {first_param_line[:100]}...)")
            continue # 处理下一行

        # 处理参数内容行 (如果正在读取参数)
        if is_reading_params and current_request: # 确保有当前请求且处于读取参数状态
            params_buffer.append(line) # 添加当前行到缓冲区
            # 不需要 continue，因为下一行可能还是参数内容

    # 文件结束，处理可能遗留的最后一个参数块
    if is_reading_params and current_request:
        # 将参数缓冲区的内容合并，去除首尾空白，如果为空则设为 None
        current_request.params = '\n'.join(params_buffer).strip() or None
        log.debug(f"文件结束，保存最后参数块: {current_request.params[:100] if current_request.params else 'None'}...")

    log.info(f"文件解析完成，共找到 {len(sections)} 个章节。")
    # 过滤掉没有请求的空章节
    valid_sections = [sec for sec in sections if sec.requests]
    if len(valid_sections) < len(sections):
         log.info(f"已过滤掉 {len(sections) - len(valid_sections)} 个空章节。")
    return valid_sections

# --- HTML 生成函数 ---
def generate_html(sections: List[Section], title: str = "API 提取报告") -> str:
    """
    生成完整的 HTML 报告字符串。
    包含 CSS 样式、目录、内容区域和 JavaScript 交互。

    Args:
        sections: 包含 Section 对象的列表。
        title: 报告的标题。

    Returns:
        完整的 HTML 字符串。
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # 获取报告生成时间

    # --- CSS 样式 ---
    # 嵌入式 CSS 样式，控制报告的布局和外观
    css = '''
:root {
  --primary-color: #4a90e2; --secondary-color: #f0f2f5; --content-bg: #fff;
  --text-color: #333; --border-color: #d9d9d9; --code-bg: #f5f5f5;
  --badge-get-bg: #52c41a; --badge-post-bg: #1890ff; --badge-put-bg: #faad14;
  --badge-delete-bg: #f5222d; --badge-patch-bg: #fa8c16; /* Added Patch */
  --badge-ws-bg: #722ed1; --badge-gql-bg: #eb2f96;
  --badge-rest-bg: #595959; --badge-default-bg: #8c8c8c;
  --link-color: #1890ff; --link-hover-color: #40a9ff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; font-size: 14px; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif; background-color: var(--secondary-color); color: var(--text-color); line-height: 1.6; }
.report-header { background: linear-gradient(90deg, var(--primary-color), #357ab8); color: #fff; padding: 20px 30px; text-align: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.report-header h1 { margin-bottom: 5px; font-size: 1.8em; }
.report-header p { font-size: .9em; opacity: .9; }
.report-container { display: flex; flex-wrap: wrap; gap: 20px; padding: 20px; max-width: 1600px; margin: 20px auto; }
.toc-container { flex: 0 0 280px; position: sticky; top: 100px; max-height: calc(100vh - 120px); overflow-y: auto; background: var(--content-bg); border: 1px solid var(--border-color); border-radius: 6px; padding: 15px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.toc-container h2 { font-size: 1.3em; margin-bottom: 15px; color: var(--primary-color); border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
.toc-container #toc-search { width: 100%; padding: 8px 10px; margin-bottom: 10px; border: 1px solid var(--border-color); border-radius: 4px; font-size: .95em; }
.toc-container ul { list-style: none; counter-reset: toc-counter; }
.toc-container li { padding: 5px 0; border-bottom: 1px dashed #eee; }
.toc-container li:last-child { border-bottom: none; }
.toc-container li::before { counter-increment: toc-counter; content: counter(toc-counter) ". "; color: var(--primary-color); font-weight: 700; margin-right: 5px; }
.toc-container a { text-decoration: none; color: var(--link-color); word-break: break-all; transition: color .2s; display: block; padding: 2px 0;} /* Make link easier to click */
.toc-container a:hover { color: var(--link-hover-color); text-decoration: underline; }
.toc-container li.active > a { font-weight: 700; color: var(--primary-color); }
.toc-container li.hidden { display: none; } /* For search filtering */
.content-container { flex: 1 1 auto; min-width: 0; background: var(--content-bg); padding: 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.content-section { margin-bottom: 40px; border-bottom: 1px solid #eee; padding-bottom: 20px; }
.content-section:last-child { border-bottom: none; }
.content-section h2 { font-size: 1.6em; margin-bottom: 15px; color: #333; word-break: break-all; }
.table-wrapper { overflow-x: auto; margin-top: 15px; border: 1px solid var(--border-color); border-radius: 4px; }
table { width: 100%; border-collapse: collapse; word-break: break-word; table-layout: fixed; } /* Fixed layout helps */
th, td { padding: 12px 15px; border: 1px solid var(--border-color); vertical-align: top; text-align: left; }
th { background-color: #fafafa; font-weight: 600; position: sticky; top: 0; z-index: 10; } /* Make table header sticky */
th:nth-child(1) { width: 5%; } /* Seq */
th:nth-child(2) { width: 10%; } /* Type */
th:nth-child(3) { width: 10%; } /* Method */
th:nth-child(4) { width: 40%; } /* URL */
th:nth-child(5) { width: 35%; } /* Params */
tbody tr:nth-child(even) { background-color: #f9f9f9; }
tbody tr:hover { background-color: #e6f7ff; }
code, .code { background-color: var(--code-bg); padding: .2em .4em; border-radius: 3px; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: .9em; word-break: break-all; }
pre { background-color: var(--code-bg); padding: 15px; border-radius: 4px; overflow: auto; white-space: pre-wrap; word-wrap: break-word; font-size: .9em; line-height: 1.5; max-height: 400px; border: 1px solid #eee; margin-top: 5px;}
details { margin-top: 8px; }
summary { background-color: #f0f0f0; padding: 6px 10px; border-radius: 4px; cursor: pointer; display: inline-block; transition: background-color .2s; font-weight: 500; border: 1px solid #ddd; }
summary:hover { background-color: #e0e0e0; }
details[open] > summary { background-color: #d9d9d9; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 4px; color: #fff; font-size: .85em; font-weight: 700; text-align: center; min-width: 50px; text-transform: uppercase;}
.badge-GET { background-color: var(--badge-get-bg); }
.badge-POST { background-color: var(--badge-post-bg); }
.badge-PUT { background-color: var(--badge-put-bg); }
.badge-DELETE { background-color: var(--badge-delete-bg); }
.badge-PATCH { background-color: var(--badge-patch-bg); }
.badge-WS { background-color: var(--badge-ws-bg); }
.badge-GRAPHQL { background-color: var(--badge-gql-bg); }
.badge-RESTFUL { background-color: var(--badge-rest-bg); }
.badge-default { background-color: var(--badge-default-bg); }
.back-to-top { text-align: right; margin-top: 15px; }
.back-to-top a { color: var(--link-color); text-decoration: none; font-size: .9em; }
.back-to-top a:hover { text-decoration: underline; }
@media (max-width: 992px) {
  .report-container { flex-direction: column; padding: 15px; }
  .toc-container { position: relative; top: auto; width: 100%; max-height: 300px; margin-bottom: 20px; }
  .report-header { padding: 15px; }
  .report-header h1 { font-size: 1.6em; }
  .content-container { padding: 20px; }
  .content-section h2 { font-size: 1.4em; }
  th { position: static; } /* Disable sticky header on smaller screens if needed */
  table { table-layout: auto; } /* Revert layout */
  th:nth-child(1), th:nth-child(2), th:nth-child(3) { width: auto; }
  th:nth-child(4), th:nth-child(5) { width: auto; }
}
@media (max-width: 576px) {
  th, td { padding: 8px 10px; font-size: 0.9em; }
  .report-header h1 { font-size: 1.4em; }
  .content-section h2 { font-size: 1.3em; }
  .badge { font-size: 0.8em; padding: 2px 6px;}
  pre { font-size: 0.85em; padding: 10px;}
  summary {padding: 4px 8px;}
}
'''

    # --- HTML 结构构建 ---
    # 构建 HTML 文件的各个部分
    html_parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>{html.escape(title)}</title><style>{css}</style></head><body id="page-top">',
        f'<header class="report-header"><h1>{html.escape(title)}</h1><p>生成时间：{timestamp}</p></header>',
        '<div class="report-container"><nav class="toc-container"><h2>目录</h2><input type="text" id="toc-search" placeholder="搜索章节..." aria-label="搜索目录章节"><ul id="toc-list">'
    ]

    # 生成目录 (Table of Contents)
    if not sections:
         # 如果没有解析到章节，目录显示提示信息
         html_parts.append('<li><em>未解析到任何章节</em></li>')
    else:
        # 遍历每个章节，生成目录项
        for section in sections:
            section_id = slugify(section.source_name) # 为章节名称生成安全的 HTML ID
            # 添加 data-text 属性用于 JavaScript 搜索过滤
            html_parts.append(f'<li data-target-id="{section_id}" data-text="{html.escape(section.source_name.lower())}"><a href="#{section_id}">{html.escape(section.source_name)}</a></li>')

    # 关闭目录列表和导航标签，开始内容区域
    html_parts.append('</ul></nav><main class="content-container">')

    # 生成内容区域
    if not sections:
        # 如果没有解析到章节，内容区域显示提示信息
        html_parts.append('<p>未能从输入文件中解析出任何有效的 API 信息。</p>')
    else:
        # 遍历每个章节，生成内容块
        for section in sections:
            section_id = slugify(section.source_name) # 获取章节对应的 HTML ID
            # 生成章节标题
            html_parts.append(f'<section id="{section_id}" class="content-section"><h2>{html.escape(section.source_name)}</h2>')
            if not section.requests:
                # 如果章节内没有请求，显示提示信息
                html_parts.append('<p><em>未在此来源中找到有效的请求信息。</em></p>')
            else:
                # 如果有请求，生成表格
                html_parts.append('<div class="table-wrapper"><table><thead><tr><th>序号</th><th>类型</th><th>方法</th><th>URL</th><th>参数</th></tr></thead><tbody>')
                # 遍历章节内的每个请求
                for idx, req in enumerate(section.requests, 1):
                    # 确定请求方法和类型的徽章样式
                    method_upper = req.method.upper()
                    type_upper = req.type.upper()
                    # 根据方法确定徽章颜色类
                    method_badge_class = f"badge-{method_upper}" if method_upper in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] else 'badge-default'
                    # 根据类型确定徽章颜色类
                    type_badge_class = f"badge-{type_upper}" if type_upper in ['WS', 'GRAPHQL', 'RESTFUL'] else 'badge-default'
                    # 生成方法和类型的徽章 HTML
                    method_badge = f'<span class="badge {method_badge_class}">{html.escape(req.method)}</span>'
                    type_badge = f'<span class="badge {type_badge_class}">{html.escape(req.type)}</span>'
                    # 生成 URL 的代码块 HTML
                    url_code = f'<code>{html.escape(req.url)}</code>'
                    # 处理参数显示
                    params_html = '<em>无参数</em>' # 参数默认显示为 "无参数"
                    if req.params:
                        # 尝试格式化参数为 JSON，失败则显示原始转义值
                        formatted_params = _try_format_json(req.params)
                        # 如果格式化后的参数非空且不是 "无参数"，则使用 <details>/<pre> 结构显示
                        if formatted_params and formatted_params != "<em>无参数</em>":
                            params_html = f'<details><summary>查看/隐藏</summary><pre>{formatted_params}</pre></details>'
                    # 添加表格行 HTML
                    html_parts.append(f'<tr><td>{idx}</td><td>{type_badge}</td><td>{method_badge}</td><td>{url_code}</td><td>{params_html}</td></tr>')
                # 关闭表格
                html_parts.append('</tbody></table></div>')
            # 添加返回顶部链接
            html_parts.append('<p class="back-to-top"><a href="#page-top">返回顶部</a></p></section>')

    # 关闭内容区域和主容器
    html_parts.append('</main></div>')

    # --- JavaScript ---
    # 嵌入式 JavaScript，用于目录搜索和滚动时高亮当前章节
    js_code = '''
// 获取搜索输入框和目录列表项
const searchInput = document.getElementById("toc-search");
const tocList = document.getElementById("toc-list");
// 仅选择带有 data-target-id 属性的列表项 (即章节目录项)
const tocListItems = tocList ? tocList.querySelectorAll("li[data-target-id]") : [];

// 目录搜索功能
if (searchInput && tocListItems.length > 0) {
    searchInput.addEventListener("input", function() {
        const searchTerm = this.value.toLowerCase().trim(); // 获取搜索词并转为小写
        tocListItems.forEach(item => {
            // 获取用于搜索的文本 (data-text 属性)
            const itemText = item.getAttribute("data-text") || "";
            // 判断章节是否包含搜索词
            const isVisible = itemText.includes(searchTerm);
            // 根据是否包含搜索词来显示或隐藏列表项
            item.classList.toggle("hidden", !isVisible);
        });
    });
} else {
    // 如果元素未找到，记录警告 (仅在调试时有用)
    if (!searchInput) console.warn("TOC Search input not found.");
    if (tocListItems.length === 0) console.warn("No TOC list items with data-target-id found.");
}

// --- 滚动时高亮当前章节目录项 ---
// 将目录列表项转换为数组
const tocLinks = Array.from(tocListItems);
// 获取所有内容章节元素 (通过目录项的 data-target-id 关联)
const contentSections = tocLinks
    .map(link => {
        const targetId = link.getAttribute("data-target-id");
        return targetId ? document.getElementById(targetId) : null;
    })
    .filter(section => section !== null); // 过滤掉未找到对应元素的章节

if (tocLinks.length > 0 && contentSections.length > 0) {
    let currentActiveId = null; // 跟踪当前高亮的章节 ID

    // 配置 Intersection Observer 选项
    const observerOptions = {
        root: null, // 相对视口进行观察
        rootMargin: "-20% 0px -60% 0px", // 调整上下边距，使得章节在视口中间区域时更容易被激活
        threshold: 0 // 只要目标元素有一部分进入视口即可触发回调
    };

    // Intersection Observer 回调函数
    const intersectionCallback = (entries) => {
        let bestVisibleEntry = null; // 存储当前视口中最靠前的相交章节

        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // 如果元素正在相交，检查它是否是目前最靠前的
                if (!bestVisibleEntry || entry.boundingClientRect.top < bestVisibleEntry.boundingClientRect.top) {
                    bestVisibleEntry = entry;
                }
            }
        });

        // 特殊情况：如果滚动到页面底部，强制激活最后一个章节
        const scrollPosition = window.scrollY + window.innerHeight; // 当前滚动位置 (视口底部)
        const bodyHeight = document.body.scrollHeight; // 整个页面的高度
        if (scrollPosition >= bodyHeight - 50 && contentSections.length > 0) { // 留 50px 缓冲
             // 创建一个模拟的 entry 对象指向最后一个章节
             bestVisibleEntry = { target: contentSections[contentSections.length - 1] };
        }

        // 确定新的活动章节 ID
        const newActiveId = bestVisibleEntry ? bestVisibleEntry.target.id : null;

        // 如果活动章节发生变化
        if (newActiveId !== currentActiveId) {
            currentActiveId = newActiveId; // 更新当前活动 ID

            // 更新目录链接的 active 类
            tocLinks.forEach(link => {
                // 如果目录项的 data-target-id 与当前活动 ID 匹配，则添加 active 类，否则移除
                link.classList.toggle("active", link.getAttribute("data-target-id") === currentActiveId);
            });
        }
    };

    // 创建 Intersection Observer 实例
    const observer = new IntersectionObserver(intersectionCallback, observerOptions);

    // 观察每个内容章节
    contentSections.forEach(section => {
        if (section) { // 确保章节元素存在
             observer.observe(section);
        }
    });

} else {
     // 如果没有找到目录链接或内容章节，记录警告
     if (tocLinks.length === 0) console.warn("No TOC links found for scroll spying.");
     if (contentSections.length === 0) console.warn("No content sections found for scroll spying.");
}
    '''
    # 将 JavaScript 代码添加到 HTML 结束标签之前
    html_parts.append(f'<script>{js_code}</script></body></html>')

    # 将所有 HTML 部分合并为一个字符串并返回
    return '\n'.join(html_parts)


# --- 主函数 ---
def create_bg_report(input_filepath: str, output_filepath: str) -> bool:
    """
    主函数：解析输入文件并生成 HTML 报告。

    Args:
        input_filepath: 提取结果文件的路径字符串。
        output_filepath: 要生成的 HTML 报告文件的路径字符串。

    Returns:
        报告生成成功返回 True，否则返回 False。
    """
    input_path = Path(input_filepath)   # 输入文件路径 Path 对象
    output_path = Path(output_filepath) # 输出文件路径 Path 对象
    log.info(f"开始生成报告。输入: {input_path}, 输出: {output_path}")

    # 解析输入文件
    # parse_log 函数内部会处理文件不存在、读取错误等情况
    sections = parse_log(input_path)

    # 生成 HTML 内容
    html_content = ""
    report_title = f"API 提取报告: {input_path.name}" # 默认报告标题
    try:
        if not sections:
            # 如果没有解析到有效章节，记录警告并修改报告标题
            log.warning("未能从输入文件中解析出任何章节，将生成提示性空报告。")
            report_title = f"API 提取报告 (无有效内容): {input_path.name}"
        # 调用 generate_html 函数生成 HTML 内容
        html_content = generate_html(sections, title=report_title)
    except Exception as gen_err:
        # 捕获 HTML 内容生成过程中的错误
        log.error(f"生成 HTML 内容时发生错误: {gen_err}", exc_info=True)
        return False # 内容生成失败，返回 False

    # 写入 HTML 文件
    try:
        # 确保输出文件所在的目录存在，如果不存在则递归创建
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 将生成的 HTML 内容写入文件，使用 utf-8 编码
        output_path.write_text(html_content, encoding='utf-8')
        log.info(f"HTML 报告已成功生成: {output_path}")
        return True # 写入成功，返回 True
    except IOError as e:
         # 捕获文件写入的 IO 错误
         log.error(f"写入 HTML 文件时发生 IO 错误 {output_path}: {e}")
         return False # 写入失败，返回 False
    except Exception as e:
        # 捕获其他意外的写入错误
        log.error(f"写入 HTML 文件失败 {output_path}: {e}", exc_info=True)
        return False # 写入失败，返回 False

# --- 独立执行入口 ---
# 当脚本作为主程序运行时执行以下代码
if __name__ == '__main__':
    # 确保独立运行时日志有基本配置，避免没有日志输出
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    # 定义默认的输入和输出文件路径
    default_input = 'api_extraction_results.txt'
    default_output = 'bg_generated_report.html'

    # 从命令行参数获取输入和输出文件路径，如果没有提供则使用默认值
    input_arg = sys.argv[1] if len(sys.argv) > 1 else default_input
    output_arg = sys.argv[2] if len(sys.argv) > 2 else default_output

    print(f"正在独立运行 bg.py...")
    print(f"从 '{input_arg}' 生成报告到 '{output_arg}'...")

    # 调用主函数生成报告
    # create_bg_report 内部会处理文件检查和错误记录
    success = create_bg_report(input_arg, output_arg)

    # 根据生成结果打印最终消息并设置退出码
    if success:
        print("报告生成成功。")
        sys.exit(0) # 成功退出
    else:
        print("报告生成失败。请检查日志获取详细信息。")
        sys.exit(1) # 失败退出
