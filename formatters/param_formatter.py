#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
参数格式化器模块
功能：处理和格式化提取的API参数
"""

import re
import json

def clean_and_validate_json(params_str):
    """
    清理并尝试验证JSON格式，处理各种边缘情况
    
    参数:
        params_str: 原始参数字符串
    
    返回:
        清理后的参数字符串，尽可能符合JSON格式
    """
    if not params_str:
        return None
    
    # 移除首尾多余字符
    params_str = params_str.strip()
    if not params_str.startswith('{'):
        params_str = '{' + params_str
    if not params_str.endswith('}'):
        params_str = params_str + '}'
    
    # 保留原始的JavaScript表达式
    # 先用占位符替换所有的JavaScript表达式
    js_expressions = []
    
    # 匹配JavaScript变量和表达式
    def replace_js_expr(match):
        expr = match.group(1)
        js_expressions.append(expr)
        return f': "__JS_EXPR_{len(js_expressions)-1}__"'
    
    # 保存原始字符串以备还原
    original_params_str = params_str
    
    # 替换JavaScript表达式，但保留原始值用于后续恢复
    params_str = re.sub(r':\s*(localStorage\.\w+(?:\|\|[^,}]*)?|[a-zA-Z_$][a-zA-Z0-9_$]*\.[a-zA-Z_$][a-zA-Z0-9_$]*(?:\|\|[^,}]*)?)', replace_js_expr, params_str)
    
    # 处理没有引号的键名（将键名加上双引号）
    params_str = re.sub(r'([{,])\s*([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', params_str)
    
    # 处理没有值的键(例如 {key,} 或 {key})，设置为null
    params_str = re.sub(r'([{,])\s*"([^"]+)"\s*([,}])', r'\1"\2":null\3', params_str)
    
    # 处理JS中的单引号字符串（转换为双引号）
    params_str = re.sub(r':\s*\'([^\']*)\'', r':"\1"', params_str)
    
    # 处理布尔值和null
    params_str = re.sub(r':\s*true\s*([,}])', r':true\1', params_str)
    params_str = re.sub(r':\s*false\s*([,}])', r':false\1', params_str)
    params_str = re.sub(r':\s*null\s*([,}])', r':null\1', params_str)
    
    # 处理末尾多余的逗号
    params_str = re.sub(r',\s*}', '}', params_str)
    
    # 尝试解析JSON以验证格式是否正确
    try:
        json.loads(params_str)
    except json.JSONDecodeError:
        # 如果处理后的JSON格式不正确，还原为原始字符串
        params_str = original_params_str
    
    # 恢复原始的JavaScript表达式
    for i, expr in enumerate(js_expressions):
        params_str = params_str.replace(f'"__JS_EXPR_{i}__"', f'"{expr}"')
    
    return params_str

def format_params(params):
    """
    尝试格式化参数为可读的JSON格式
    
    参数:
        params: 原始参数字符串
    
    返回:
        格式化后的参数字符串，尽可能美观
    """
    if not params:
        return "无参数"
    
    # 先清理并验证JSON
    cleaned_params = clean_and_validate_json(params)
    
    try:
        # 尝试解析并格式化为标准JSON
        parsed = json.loads(cleaned_params)
        return json.dumps(parsed, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        # 如果仍然无法解析，尝试更宽松的格式化方法
        try:
            # 使用自定义格式化方法，按层次缩进
            level = 0
            result = []
            in_string = False
            escape_next = False
            i = 0
            
            while i < len(cleaned_params):
                char = cleaned_params[i]
                
                # 处理字符串（避免混淆字符串中的大括号和引号）
                if char == '"' and not escape_next:
                    in_string = not in_string
                    result.append(char)
                elif char == '\\' and in_string:
                    escape_next = True
                    result.append(char)
                elif escape_next:
                    escape_next = False
                    result.append(char)
                # 处理对象和数组的格式化
                elif not in_string:
                    if char == '{' or char == '[':
                        result.append(char)
                        result.append('\n')
                        level += 1
                        result.append('    ' * level)
                    elif char == '}' or char == ']':
                        result.append('\n')
                        level -= 1
                        if level < 0:  # 防止缩进级别为负数
                            level = 0
                        result.append('    ' * level)
                        result.append(char)
                    elif char == ',':
                        result.append(char)
                        result.append('\n')
                        result.append('    ' * level)
                    elif char == ':':
                        result.append(char)
                        result.append(' ')
                    else:
                        result.append(char)
                else:
                    result.append(char)
                    
                i += 1
                
            return ''.join(result)
        except Exception as e:
            # 如果所有尝试都失败，返回基本美化的字符串
            cleaned_params = params.replace("'", '"')
            # 基本美化尝试
            cleaned_params = cleaned_params.replace(",", ", ")
            cleaned_params = cleaned_params.replace(":", ": ")
            cleaned_params = cleaned_params.replace("{", "{\n  ")
            cleaned_params = cleaned_params.replace("}", "\n}")
            # 处理多余的空格
            cleaned_params = re.sub(r'\s+', ' ', cleaned_params)
            return cleaned_params
