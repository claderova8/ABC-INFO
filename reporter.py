# -*- coding: utf-8 -*-
"""
HTML报告生成工具 (重构优化版 v4)
功能：读取 API 提取结果文件，解析并生成结构化 HTML 报告。
"""
import re
import sys
import html
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

# --- 配置日志 ---
log = logging.getLogger(__name__)

# --- 正则表达式 ---
SECTION_HEADER_REGEX = re.compile(r'^--- 来源: (.+) ---$')
REQUEST_LINE_REGEX = re.compile(r'^类型: (\w+), 请求: "(\w+)\s+(.+?)"$')
PARAMS_START_REGEX = re.compile(r'^请求参数:\s*(.*)$')
SEPARATOR_REGEX = re.compile(r'^[=-]{3,}$')

@dataclass
class RequestInfo:
    """存储单个 API 请求的信息"""
    type: str
    method: str
    url: str
    params: Optional[str] = None

@dataclass
class ReportSection:
    """存储报告中一个章节（来源）的信息"""
    source_name: str
    requests: List[RequestInfo] = field(default_factory=list)


def slugify(text: str) -> str:
    """将文本转换为适合用作 HTML ID 的 slug 格式"""
    text = re.sub(r'^(https?://|ws?://)', '', text)
    slug = re.sub(r'[^\w\-]+', '_', text.strip())
    return slug.strip('_')[:100] # 限制长度


def parse_extraction_output(input_path: Path) -> List[ReportSection]:
    """解析 API 提取工具的输出文件"""
    if not input_path.exists():
        log.error(f"报告生成失败：输入文件不存在: {input_path}")
        return []
    try:
        lines = input_path.read_text(encoding='utf-8').splitlines()
    except Exception as e:
        log.error(f"读取输入文件失败 {input_path}: {e}")
        return []

    sections: List[ReportSection] = []
    current_section: Optional[ReportSection] = None
    current_request: Optional[RequestInfo] = None
    is_reading_params = False
    params_buffer: List[str] = []

    log.info(f"开始解析文件: {input_path}")
    line_num = 0
    while line_num < len(lines):
        line = lines[line_num].strip()
        line_num += 1

        if not line or SEPARATOR_REGEX.match(line): continue

        header_match = SECTION_HEADER_REGEX.match(line)
        if header_match:
            if is_reading_params and current_request:
                current_request.params = '\n'.join(params_buffer).strip() or None
            is_reading_params = False
            params_buffer = []
            source_name = header_match.group(1).strip()
            current_section = ReportSection(source_name=source_name)
            sections.append(current_section)
            current_request = None
            log.debug(f"找到新章节: {source_name}")
            continue

        if not current_section: continue

        request_match = REQUEST_LINE_REGEX.match(line)
        if request_match:
            if is_reading_params and current_request:
                current_request.params = '\n'.join(params_buffer).strip() or None
            is_reading_params = False
            params_buffer = []
            req_type, req_method, req_url = request_match.groups()
            current_request = RequestInfo(
                type=req_type.strip(),
                method=req_method.strip().upper(),
                url=req_url.strip()
            )
            current_section.requests.append(current_request)
            log.debug(f"找到请求: {current_request.method} {current_request.url}")
            continue

        params_match = PARAMS_START_REGEX.match(line)
        if params_match and current_request:
            if is_reading_params: # 保存上一个参数块（理论上不应连续出现）
                 current_request.params = '\n'.join(params_buffer).strip() or None
            is_reading_params = True
            params_buffer = [params_match.group(1).strip()]
            log.debug("开始读取参数...")
            continue

        if is_reading_params:
            # 检查是否是下一个请求或章节的开始，以确定参数块结束
            next_line_peek = lines[line_num].strip() if line_num < len(lines) else None
            if next_line_peek and (SECTION_HEADER_REGEX.match(next_line_peek) or REQUEST_LINE_REGEX.match(next_line_peek)):
                 # 当前行是参数块的最后一行
                 params_buffer.append(line)
                 current_request.params = '\n'.join(params_buffer).strip() or None
                 is_reading_params = False
                 params_buffer = []
                 log.debug("参数块结束（检测到下一请求/章节）")
            else:
                 params_buffer.append(line) # 参数内容继续

    # 文件结束，保存最后的参数块
    if is_reading_params and current_request:
        current_request.params = '\n'.join(params_buffer).strip() or None
        log.debug("文件结束，保存最后的参数块。")

    log.info(f"文件解析完成，共找到 {len(sections)} 个章节。")
    # 过滤掉没有请求的章节
    valid_sections = [sec for sec in sections if sec.requests]
    if len(valid_sections) < len(sections):
         log.info(f"过滤掉 {len(sections) - len(valid_sections)} 个空章节。")
    return valid_sections


def generate_html_report(sections: List[ReportSection], title: str = "API 提取报告") -> str:
    """根据解析的数据生成 HTML 报告内容"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    css = '''
:root{--primary-color:#4a90e2;--secondary-color:#f0f2f5;--content-bg:#fff;--text-color:#333;--border-color:#d9d9d9;--code-bg:#f5f5f5;--badge-get-bg:#52c41a;--badge-post-bg:#1890ff;--badge-put-bg:#faad14;--badge-delete-bg:#f5222d;--badge-ws-bg:#722ed1;--badge-gql-bg:#eb2f96;--link-color:#1890ff;--link-hover-color:#40a9ff}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:14px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans',sans-serif,'Apple Color Emoji','Segoe UI Emoji','Segoe UI Symbol','Noto Color Emoji';background-color:var(--secondary-color);color:var(--text-color);line-height:1.6}
.report-header{background:linear-gradient(90deg,var(--primary-color),#357ab8);color:#fff;padding:20px 30px;text-align:center;position:sticky;top:0;z-index:1000;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.report-header h1{margin-bottom:5px;font-size:1.8em}
.report-header p{font-size:.9em;opacity:.9}
.report-container{display:flex;flex-wrap:wrap;gap:20px;padding:20px;max-width:1600px;margin:20px auto}
.toc-container{flex:0 0 280px;position:sticky;top:100px;max-height:calc(100vh - 120px);overflow-y:auto;background:var(--content-bg);border:1px solid var(--border-color);border-radius:6px;padding:15px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.toc-container h2{font-size:1.3em;margin-bottom:15px;color:var(--primary-color);border-bottom:1px solid var(--border-color);padding-bottom:8px}
.toc-container #toc-search{width:100%;padding:8px 10px;margin-bottom:10px;border:1px solid var(--border-color);border-radius:4px;font-size:.95em}
.toc-container ul{list-style:none;counter-reset:toc-counter}
.toc-container li{padding:5px 0;border-bottom:1px dashed #eee}
.toc-container li:last-child{border-bottom:none}
.toc-container li::before{counter-increment:toc-counter;content:counter(toc-counter) ". ";color:var(--primary-color);font-weight:700;margin-right:5px}
.toc-container a{text-decoration:none;color:var(--link-color);word-break:break-all;transition:color .2s}
.toc-container a:hover{color:var(--link-hover-color);text-decoration:underline}
.toc-container li.active>a{font-weight:700;color:var(--primary-color)}
.content-container{flex:1 1 auto;min-width:0;background:var(--content-bg);padding:25px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.content-section{margin-bottom:40px;border-bottom:1px solid #eee;padding-bottom:20px}
.content-section:last-child{border-bottom:none}
.content-section h2{font-size:1.6em;margin-bottom:15px;color:#333;word-break:break-all}
.table-wrapper{overflow-x:auto;margin-top:15px;border:1px solid var(--border-color);border-radius:4px}
table{width:100%;border-collapse:collapse;word-break:break-word}
th,td{padding:12px 15px;border:1px solid var(--border-color);vertical-align:top;text-align:left}
th{background-color:#fafafa;font-weight:600;position:sticky;top:0;z-index:10}
tbody tr:nth-child(even){background-color:#f9f9f9}
tbody tr:hover{background-color:#e6f7ff}
code,.code{background-color:var(--code-bg);padding:.2em .4em;border-radius:3px;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,Courier,monospace;font-size:.9em;word-break:break-all}
pre{background-color:var(--code-bg);padding:15px;border-radius:4px;overflow:auto;white-space:pre-wrap;word-wrap:break-word;font-size:.9em;line-height:1.5;max-height:400px}
details{margin-top:8px}
summary{background-color:#e6f7ff;padding:8px 12px;border-radius:4px;cursor:pointer;display:inline-block;transition:background-color .2s;font-weight:500}
summary:hover{background-color:#bae7ff}
.badge{display:inline-block;padding:3px 8px;border-radius:4px;color:#fff;font-size:.85em;font-weight:700;text-align:center;min-width:50px}
.badge-GET{background-color:var(--badge-get-bg)}
.badge-POST{background-color:var(--badge-post-bg)}
.badge-PUT{background-color:var(--badge-put-bg)}
.badge-DELETE{background-color:var(--badge-delete-bg)}
.badge-WS{background-color:var(--badge-ws-bg)}
.badge-GRAPHQL{background-color:var(--badge-gql-bg)}
.badge-RESTFUL{background-color:#595959}
.badge-default{background-color:#8c8c8c}
.back-to-top{text-align:right;margin-top:15px}
.back-to-top a{color:var(--link-color);text-decoration:none;font-size:.9em}
.back-to-top a:hover{text-decoration:underline}
@media (max-width:992px){.report-container{flex-direction:column;padding:15px}.toc-container{position:relative;top:auto;width:100%;max-height:300px;margin-bottom:20px}.report-header{padding:15px}.report-header h1{font-size:1.6em}.content-container{padding:20px}.content-section h2{font-size:1.4em}}
@media (max-width:576px){th,td{padding:8px 10px}.report-header h1{font-size:1.4em}.content-section h2{font-size:1.3em}}
'''
    html_parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>{html.escape(title)}</title><style>{css}</style></head><body id="page-top">',
        f'<header class="report-header"><h1>{html.escape(title)}</h1><p>生成时间：{timestamp}</p></header>',
        '<div class="report-container"><nav class="toc-container"><h2>目录</h2><input type="text" id="toc-search" placeholder="搜索章节..." aria-label="搜索目录章节"><ul id="toc-list">'
    ]
    if not sections:
         html_parts.append('<li><em>未解析到任何章节</em></li>')
    else:
        for section in sections:
            section_id = slugify(section.source_name)
            html_parts.append(f'<li data-target-id="{section_id}"><a href="#{section_id}">{html.escape(section.source_name)}</a></li>')
    html_parts.append('</ul></nav><main class="content-container">')
    if not sections:
        html_parts.append('<p>未能从输入文件中解析出任何有效的 API 信息。</p>')
    else:
        for section in sections:
            section_id = slugify(section.source_name)
            html_parts.append(f'<section id="{section_id}" class="content-section"><h2>{html.escape(section.source_name)}</h2>')
            if not section.requests:
                html_parts.append('<p><em>未在此来源中找到有效的请求信息。</em></p>')
            else:
                html_parts.append('<div class="table-wrapper"><table><thead><tr><th>序号</th><th>类型</th><th>方法</th><th>URL</th><th>参数</th></tr></thead><tbody>')
                for idx, req in enumerate(section.requests, 1):
                    badge_class = f"badge-{req.method}" if req.method in ['GET','POST','PUT','DELETE'] else f"badge-{req.type.upper()}" if req.type.upper() in ['WS','GRAPHQL'] else 'badge-default'
                    method_badge = f'<span class="badge {badge_class}">{html.escape(req.method)}</span>'
                    type_badge_class = f"badge-{req.type.upper()}" if req.type.upper() in ['WS','GRAPHQL','RESTFUL'] else 'badge-default'
                    type_badge = f'<span class="badge {type_badge_class}">{html.escape(req.type)}</span>'
                    url_code = f'<code>{html.escape(req.url)}</code>'
                    params_html = '<em>无</em>'
                    if req.params:
                        escaped_params = html.escape(req.params)
                        # 尝试美化 JSON 参数显示
                        try:
                            parsed_params = json.loads(req.params)
                            pretty_params = json.dumps(parsed_params, indent=2, ensure_ascii=False)
                            escaped_params = html.escape(pretty_params)
                        except json.JSONDecodeError:
                            pass # 保持原始转义格式
                        params_html = f'<details><summary>查看/隐藏</summary><pre>{escaped_params}</pre></details>'
                    html_parts.append(f'<tr><td>{idx}</td><td>{type_badge}</td><td>{method_badge}</td><td>{url_code}</td><td>{params_html}</td></tr>')
                html_parts.append('</tbody></table></div>')
            html_parts.append('<p class="back-to-top"><a href="#page-top">返回顶部</a></p></section>')
    html_parts.append('</main></div><script>')
    html_parts.append('''
const searchInput=document.getElementById("toc-search"),tocListItems=document.querySelectorAll("#toc-list li");searchInput&&tocListItems.length>0&&searchInput.addEventListener("input",(function(){const t=this.value.toLowerCase().trim();tocListItems.forEach((e=>{const o=e.querySelector("a")?.textContent?.toLowerCase()||"";e.style.display=o.includes(t)?"":"none"}))}));const tocLinks=document.querySelectorAll("#toc-list li[data-target-id]"),contentSections=Array.from(tocLinks).map((e=>{const t=e.getAttribute("data-target-id");return t?document.getElementById(t):null})).filter((e=>null!==e));if(tocLinks.length>0&&contentSections.length>0){const observerOptions={rootMargin:"-80px 0px -40% 0px"},observer=new IntersectionObserver((entries=>{entries.forEach((entry=>{const id=entry.target.getAttribute("id"),correspondingLink=document.querySelector(`#toc-list li[data-target-id="${id}"]`);correspondingLink&&(entry.isIntersecting&&entry.intersectionRatio>.1?(document.querySelectorAll("#toc-list li.active").forEach((active=>active.classList.remove("active"))),correspondingLink.classList.add("active")):correspondingLink.classList.remove("active"))}))}),observerOptions);contentSections.forEach((section=>observer.observe(section)))}
    ''')
    html_parts.append('</script></body></html>')
    return '\n'.join(html_parts)


def create_report(input_filepath: str, output_filepath: str) -> bool:
    """主函数：解析输入文件并生成 HTML 报告"""
    input_path = Path(input_filepath)
    output_path = Path(output_filepath)
    log.info(f"开始生成报告，输入: {input_path}, 输出: {output_path}")
    sections = parse_extraction_output(input_path)
    if not sections:
        log.warning("未能从输入文件中解析出任何章节，将生成空报告。")
        # 生成包含提示信息的报告
        html_content = generate_html_report([], title=f"API 提取报告 (未找到有效内容: {input_path.name})")
    else:
        html_content = generate_html_report(sections, title=f"API 提取报告: {input_path.name}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')
        log.info(f"HTML 报告已成功生成: {output_path}")
        return True
    except Exception as e:
        log.error(f"写入 HTML 文件失败 {output_path}: {e}")
        return False

# --- 如果直接运行此脚本的示例 ---
if __name__ == '__main__':
    default_input = 'api_extraction_results.txt'
    default_output = 'generated_report.html'
    input_arg = sys.argv[1] if len(sys.argv) > 1 else default_input
    output_arg = sys.argv[2] if len(sys.argv) > 2 else default_output
    if not Path(input_arg).exists():
         print(f"错误：输入文件 '{input_arg}' 不存在。请先运行提取脚本。", file=sys.stderr)
         sys.exit(1)
    print(f"正在使用输入文件 '{input_arg}' 生成报告 '{output_arg}'...")
    success = create_report(input_arg, output_arg)
    if success: print("报告生成成功。")
    else: print("报告生成失败。"); sys.exit(1)
