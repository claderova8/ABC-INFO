# -*- coding: utf-8 -*-
"""
用于 JavaScript API 提取器的参数格式化函数。
包含清理、验证和美化参数字符串的功能。
(优化版本 v2)
"""

import re
import json
import logging

# --- 配置日志 ---
log = logging.getLogger(__name__)

# --- 预编译用于清理和验证的正则表达式 ---
js_expr_pattern = re.compile(
    r':\s*'
    r'('
        r'(?:[a-zA-Z_$][a-zA-Z0-9_$]*\.)*[a-zA-Z_$][a-zA-Z0-9_$]*'
        r'(?:\s*\(\))?'
        r'|localStorage\.\w+'
        r'|true|false|null'
    r')'
    r'\b(?!\s*["\'`.(])'
)
unquoted_key_pattern = re.compile(r'(?<=[{,]\s*)([a-zA-Z0-9_$]+)\s*(?=:)(?!")')
single_quoted_value_pattern = re.compile(r":\s*'((?:\\.|[^'])*)'")
single_quoted_key_pattern = re.compile(r"'((?:\\.|[^'])*)'\s*:")
trailing_comma_pattern = re.compile(r',\s*([}\]])')

# --- 清理与验证函数 ---

def clean_and_validate_json(params_str):
    """清理并尝试将参数字符串验证为 JSON 格式，处理常见的 JS 对象字面量差异"""
    if not params_str or not isinstance(params_str, str):
        return params_str

    params_str = params_str.strip()

    if not (params_str.startswith('{') and params_str.endswith('}')) and \
       not (params_str.startswith('[') and params_str.endswith(']')):
        return params_str # 对于非对象/数组的参数，直接返回

    js_expressions = []
    placeholder_prefix = "__JS_EXPR_PLACEHOLDER_"
    placeholder_suffix = "__"

    def replace_js_expr(match):
        nonlocal js_expressions
        expr = match.group(1).strip()
        start_index = match.start(1)
        if start_index > 0 and params_str[start_index-1] in ['"', "'", "`"]:
             return match.group(0)
        js_expressions.append(expr)
        placeholder = f'"{placeholder_prefix}{len(js_expressions)-1}{placeholder_suffix}"'
        return f': {placeholder}'

    original_params_str = params_str
    try:
        # 1. 替换 JS 表达式
        try:
            params_str = js_expr_pattern.sub(replace_js_expr, params_str)
        except Exception as e:
            log.warning(f"替换 JS 表达式时出错: {e}. Params: {original_params_str[:100]}...")

        # 2. 添加键名引号
        while True:
            new_params_str = unquoted_key_pattern.sub(r'"\1"', params_str)
            if new_params_str == params_str: break
            params_str = new_params_str

        # 3. 转换单引号
        params_str = single_quoted_key_pattern.sub(r'"\1":', params_str)
        params_str = single_quoted_value_pattern.sub(r':"\1"', params_str)

        # 4. 移除末尾逗号
        params_str = trailing_comma_pattern.sub(r'\1', params_str)

        # 5. 恢复 JS 表达式 (结果非严格 JSON)
        for i, expr in enumerate(js_expressions):
             placeholder = f'"{placeholder_prefix}{i}{placeholder_suffix}"'
             params_str = params_str.replace(placeholder, expr)

    except Exception as e:
        log.error(f"JSON 清理过程中发生意外错误: {e}. Params: {original_params_str[:100]}...")
        return original_params_str.strip()

    return params_str.strip()

# --- 格式化函数 ---

def format_params(params):
    """尝试将参数字符串格式化为可读的 JSON 或类似 JSON 的格式"""
    if not params or not isinstance(params, str):
        return "无参数"

    cleaned_params = clean_and_validate_json(params)
    if not cleaned_params:
        return "无参数"

    # 尝试标准 JSON 格式化
    try:
        parsed = json.loads(cleaned_params)
        return json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=False)
    except json.JSONDecodeError:
        log.debug(f"标准 JSON 解析失败，尝试基本美化: {cleaned_params[:100]}...")
        pass # 继续备用格式化

    # 备用美化逻辑
    try:
        level = 0
        result = []
        in_string = False
        string_char = None
        escape_next = False
        indent_char = '    '

        for char in cleaned_params:
            if char in ['"', "'"] and not escape_next:
                if not in_string:
                    in_string = True
                    string_char = char
                    result.append(char)
                elif in_string and char == string_char:
                    in_string = False
                    string_char = None
                    result.append(char)
                else: result.append(char)
            elif char == '\\' and in_string and not escape_next:
                escape_next = True
                result.append(char)
            elif escape_next:
                escape_next = False
                result.append(char)
            elif not in_string:
                if char in '{[':
                    result.append(char)
                    result.append('\n')
                    level += 1
                    result.append(indent_char * level)
                elif char in '}]':
                    result.append('\n')
                    level = max(0, level - 1)
                    result.append(indent_char * level)
                    result.append(char)
                elif char == ',':
                    result.append(char)
                    result.append('\n')
                    result.append(indent_char * level)
                elif char == ':':
                    result.append(char)
                    result.append(' ')
                elif not char.isspace():
                    result.append(char)
            else:
                result.append(char)

        formatted_string = "".join(result)
        formatted_string = re.sub(r'\n\s*\n', '\n', formatted_string)
        return formatted_string.strip()

    except Exception as e:
         log.error(f"基本美化过程中出错: {e}. Params: {cleaned_params[:100]}...")
         return cleaned_params # 返回清理后但未美化的字符串
