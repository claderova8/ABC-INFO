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
    尝试将JavaScript对象字面量转换为有效的JSON字符串
    """
    if not params_str:
        return None

    # 移除首尾多余字符和可能的函数调用包裹
    params_str = params_str.strip()
    if params_str.startswith('JSON.stringify(') and params_str.endswith(')'):
        params_str = params_str[len('JSON.stringify('):-1].strip()

    # 确保字符串以大括号包裹
    if not params_str.startswith('{'):
        params_str = '{' + params_str
    if not params_str.endswith('}'):
        params_str = params_str + '}'

    # 尝试更智能地处理JavaScript对象字面量
    # 1. 处理没有引号的键名
    # 使用更精确的模式，只在对象内部和逗号后查找没有引号的键名
    params_str = re.sub(r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', params_str)

    # 2. 处理单引号字符串（转换为双引号）
    # 确保只替换值中的单引号字符串，不影响键名或JSON结构
    params_str = re.sub(r':\s*\'([^\']*)\'', r':"\1"', params_str)

    # 3. 处理没有值的键(例如 {key,} 或 {key})，设置为null
    # 查找后面紧跟逗号或结束大括号的键名
    params_str = re.sub(r'([{,]\s*"[^"]*"\s*)([,}])', r'\1:null\2', params_str)
    # 查找对象末尾没有值的键
    params_str = re.sub(r'([{,]\s*"[^"]*"\s*)\}$', r'\1:null}', params_str)


    # 4. 处理布尔值和null（确保是独立的单词）
    params_str = re.sub(r':\s*\b(true)\b', r':true', params_str)
    params_str = re.sub(r':\s*\b(false)\b', r':false', params_str)
    params_str = re.sub(r':\s*\b(null)\b', r':null', params_str)
    params_str = re.sub(r':\s*\b(undefined)\b', r':null', params_str) # 将 undefined 视为 null

    # 5. 处理末尾多余的逗号
    params_str = re.sub(r',\s*\}', '}', params_str)
    params_str = re.sub(r',\s*\]', ']', params_str)


    # 6. 尝试处理简单的JavaScript变量或表达式作为值
    # 这部分仍然是启发式的，难以完全准确解析复杂的JS表达式
    # 替换 localStorage.getItem('key') 为 "localStorage.getItem('key')"
    params_str = re.sub(r':\s*(localStorage\.getItem\s*\([\'"]([^\'"]*)[\'"]\))', r':"\1"', params_str)
    # 替换简单的变量名或属性访问为字符串形式
    params_str = re.sub(r':\s*([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)\s*([,}]|$)', r':"\1"\2', params_str)


    # 尝试解析为JSON以验证和标准化
    try:
        # 使用 json.loads 尝试解析，如果成功则返回标准的JSON字符串
        parsed_json = json.loads(params_str)
        # 使用 json.dumps 重新生成字符串，确保格式一致且处理了转义
        return json.dumps(parsed_json, ensure_ascii=False)
    except json.JSONDecodeError:
        # 如果解析失败，说明清理后的字符串仍然不是严格的JSON格式
        # 此时，返回原始的（经过初步清理的）字符串，并在格式化时尝试宽松处理
        return params_str


def format_params(params):
    """
    尝试格式化参数为可读的JSON格式，如果失败则进行基本美化
    """
    if not params:
        return "无参数"

    # 先清理并尝试转换为标准JSON
    cleaned_params = clean_and_validate_json(params)

    if cleaned_params is None:
        return "无参数"

    try:
        # 尝试解析并格式化为标准JSON，使用 indent=4 进行缩进
        parsed = json.loads(cleaned_params)
        return json.dumps(parsed, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        # 如果仍然无法解析为标准JSON，进行基本的美化处理
        # 这种情况下，cleaned_params 可能是经过 clean_and_validate_json 初步处理但非严格JSON的字符串
        try:
            # 尝试自定义格式化方法，按层次缩进（对非标准JSON结构可能有效）
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
        except Exception:
            # 如果自定义格式化也失败，返回原始清理后的字符串
            return cleaned_params

