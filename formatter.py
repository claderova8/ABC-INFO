# -*- coding: utf-8 -*-
"""
用于 JavaScript API 提取器的参数格式化函数。
包含清理、验证和美化参数字符串的功能。
"""

import re
import json

# --- 预编译用于清理和验证的正则表达式 ---

# 匹配潜在的 JS 表达式/变量作为值的模式
# 查找 : 后跟潜在的 JS 代码（未被引号包围）
# 处理标识符、点表示法、简单函数调用、localStorage 等
# 注意：这个模式比较复杂，可能需要根据实际遇到的 JS 代码进行调整
js_expr_pattern = re.compile(
    r':\s*((?:[a-zA-Z_$][a-zA-Z0-9_$]*\.)*[a-zA-Z_$][a-zA-Z0-9_$]*(?:\s*\(\))?|localStorage\.\w+|true|false|null)\b(?!\s*["\'])'
)

# 匹配未加引号的键名，并在其前后加上双引号
unquoted_key_pattern = re.compile(r'([{,])\s*([a-zA-Z0-9_$]+)\s*:')

# 匹配单引号字符串值，并将其转换为双引号 (简单情况)
single_quoted_value_pattern = re.compile(r":\s*'([^']*)'")

# 匹配单引号键名，并将其转换为双引号 (简单情况)
single_quoted_key_pattern = re.compile(r"'([^']*)'\s*:")

# 匹配对象或数组末尾多余的逗号
trailing_comma_pattern = re.compile(r',\s*([}\]])')

# --- 清理与验证函数 ---

def clean_and_validate_json(params_str):
    """
    清理并尝试将参数字符串验证为 JSON 格式，处理各种边缘情况。
    此函数尝试将类似 JSON 的 JavaScript 对象转换为更标准的 JSON 格式，
    同时保留原始的 JavaScript 表达式（如变量名、函数调用）。

    参数:
        params_str (str): 原始参数字符串。

    返回:
        str: 清理后的参数字符串，更接近有效的 JSON 格式，如果清理失败则返回原始字符串。
             如果输入为 None 或空，则返回 None。
    """
    if not params_str:
        return None

    params_str = params_str.strip() # 去除首尾空格

    # 基本结构检查 - 如果看起来不像对象或数组，则提前返回
    # (可以根据需要调整此逻辑，例如允许非对象/数组的参数)
    # if not (params_str.startswith('{') and params_str.endswith('}')) and \
    #    not (params_str.startswith('[') and params_str.endswith(']')):
    #      return params_str # 或者返回 None，如果只想要 JSON 对象/数组

    # --- 用于存储 JS 表达式的占位符逻辑 ---
    js_expressions = [] # 存储提取出的 JS 表达式
    placeholder_prefix = "__JS_EXPR_" # 占位符前缀
    placeholder_suffix = "__"       # 占位符后缀

    def replace_js_expr(match):
        """正则表达式替换函数：将匹配到的 JS 表达式替换为占位符"""
        nonlocal js_expressions # 允许修改外部函数的变量
        expr = match.group(1) # 获取匹配到的表达式
        # 简单的检查，避免替换字符串内部看起来像表达式的部分
        # 检查匹配项前后的字符是否是引号
        pre_char_index = match.start(1) - 2 # 检查冒号前的字符
        pre_char = params_str[pre_char_index:pre_char_index+1] if pre_char_index >= 0 else ''

        # 只有当表达式不是被引号包围时才进行替换
        if pre_char not in ['"', "'", "`"]:
             js_expressions.append(expr) # 存储表达式
             placeholder = f'"{placeholder_prefix}{len(js_expressions)-1}{placeholder_suffix}"' # 创建占位符字符串 (带引号)
             return f': {placeholder}' # 返回带冒号和占位符的替换结果
        else:
            # 如果在引号内，则不替换
            return match.group(0)

    # --- 执行清理步骤 ---
    try:
        # 1. 替换 JS 表达式为占位符
        #    使用 try-except 块防止正则表达式错误中断整个过程
        try:
            params_str = js_expr_pattern.sub(replace_js_expr, params_str)
        except Exception as e:
            # print(f"调试信息：替换 JS 表达式时正则错误: {e}") # 可选调试信息
            pass # 即使替换失败也继续

        # 2. 为未加引号的键名添加双引号
        params_str = unquoted_key_pattern.sub(r'\1"\2":', params_str)

        # 3. 将单引号转换为双引号 (简单情况)
        #    注意：这可能无法处理所有情况，例如嵌套或转义的单引号
        params_str = single_quoted_value_pattern.sub(r':"\1"', params_str)
        params_str = single_quoted_key_pattern.sub(r'"\1":', params_str)

        # 4. 处理末尾多余的逗号
        params_str = trailing_comma_pattern.sub(r'\1', params_str)

        # --- 恢复 JS 表达式 ---
        # 将占位符替换回原始的 JS 表达式 (不带引号)
        for i, expr in enumerate(js_expressions):
             placeholder = f'"{placeholder_prefix}{i}{placeholder_suffix}"'
             # 恢复时不带引号，因为原始表达式不是字符串
             params_str = params_str.replace(placeholder, expr)

    except Exception as e:
        # print(f"调试信息：JSON 清理过程中出错: {e}") # 可选调试信息
        # 如果清理步骤失败，返回经过部分清理的字符串
        return params_str.strip()

    return params_str.strip() # 返回最终清理后的字符串

# --- 格式化函数 ---

def format_params(params):
    """
    尝试将参数字符串格式化为可读的 JSON 或类似 JSON 的格式。

    参数:
        params (str): 原始参数字符串。

    返回:
        str: 格式化后的参数字符串，如果无法格式化则返回清理后的原始字符串，
             如果输入为 None 或空，则返回 "无参数"。
    """
    if not params:
        return "无参数" # 输入为空

    # 步骤 1: 清理参数字符串
    cleaned_params = clean_and_validate_json(params)
    if not cleaned_params:
        return "无参数" # 清理后为空

    # 步骤 2: 尝试使用标准 JSON 库解析和格式化
    try:
        # 直接尝试解析清理后的字符串
        parsed = json.loads(cleaned_params)
        # 如果成功，使用 json.dumps 进行标准格式化
        return json.dumps(parsed, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        # 如果标准解析失败（可能因为包含 JS 表达式），进入备用格式化流程
        pass # 继续尝试其他方法

    # 步骤 3: 备用 - 基本的美化（如果 JSON 解析失败）
    # 这是一个简单的基于字符的缩进逻辑，尝试提高可读性
    try:
        level = 0         # 当前缩进级别
        result = []       # 存储格式化后的字符列表
        in_string = False # 是否在字符串内部
        escape_next = False # 下一个字符是否是转义字符
        indent_char = '    ' # 使用 4 个空格进行缩进

        for char in cleaned_params:
            # 处理字符串引号，避免错误处理字符串内部的特殊字符
            if char == '"' and not escape_next:
                in_string = not in_string
                result.append(char)
            # 处理转义字符
            elif char == '\\' and in_string and not escape_next:
                escape_next = True
                result.append(char)
            elif escape_next:
                escape_next = False
                result.append(char)
            # 处理非字符串部分的格式化
            elif not in_string:
                # 处理左大括号和左方括号：换行，增加缩进级别，添加缩进
                if char in '{[':
                    result.append(char)
                    result.append('\n')
                    level += 1
                    result.append(indent_char * level)
                # 处理右大括号和右方括号：换行，减少缩进级别，添加缩进，添加字符
                elif char in '}]':
                    result.append('\n')
                    level = max(0, level - 1) # 防止缩进级别为负
                    result.append(indent_char * level)
                    result.append(char)
                # 处理逗号：添加逗号，换行，添加缩进
                elif char == ',':
                    result.append(char)
                    result.append('\n')
                    result.append(indent_char * level)
                # 处理冒号：添加冒号和空格
                elif char == ':':
                    result.append(char)
                    result.append(' ')
                # 处理非空白字符：直接添加
                elif not char.isspace():
                    result.append(char)
                # （忽略非字符串中的空白字符）
            # 处理字符串内部的字符：直接添加
            else:
                result.append(char)

        # 组合格式化后的字符列表为字符串
        formatted_string = "".join(result)
        # 简单的后处理：去除可能由格式化引入的空行
        formatted_string = re.sub(r'\n\s*\n', '\n', formatted_string)
        return formatted_string.strip()

    except Exception as e:
         # print(f"调试信息：基本美化过程中出错: {e}") # 可选调试信息
         # 如果所有尝试都失败，返回清理后的原始字符串作为最终回退
         return cleaned_params

