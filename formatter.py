# -*- coding: utf-8 -*-
"""
用于 JavaScript API 提取器的参数格式化函数。
包含清理、验证和美化参数字符串的功能。
(优化版本)
"""

import re
import json
import logging

# --- 配置日志 ---
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# --- 预编译用于清理和验证的正则表达式 ---

# 匹配潜在的 JS 表达式/变量作为值的模式
# 查找 : 后跟潜在的 JS 代码（未被引号包围）
# 处理标识符、点表示法、简单函数调用、localStorage、布尔值、null 等
# 注意：这个模式是为了在 JSON 清理前识别非字符串值，可能无法覆盖所有 JS 语法
js_expr_pattern = re.compile(
    r':\s*'
    r'('
        # 变量名或属性访问: variable, obj.prop, obj.prop.sub
        r'(?:[a-zA-Z_$][a-zA-Z0-9_$]*\.)*[a-zA-Z_$][a-zA-Z0-9_$]*'
        # 简单函数调用: func()
        r'(?:\s*\(\))?'
        # localStorage: localStorage.getItem(...) - 简化匹配
        r'|localStorage\.\w+'
        # 布尔值和 null
        r'|true|false|null'
    r')'
    # 负向断言：确保后面不是引号或另一个点/括号（避免匹配对象内部）
    r'\b(?!\s*["\'`.(])'
)

# 匹配未加引号的键名，并在其前后加上双引号
# (?<=...) 正向后行断言，确保前面是 { 或 ,
# (?!...) 负向先行断言，确保后面不是 : (避免重复添加引号)
unquoted_key_pattern = re.compile(r'(?<=[{,]\s*)([a-zA-Z0-9_$]+)\s*(?=:)(?!")')

# 匹配单引号字符串值，并将其转换为双引号 (简单情况)
# 注意：无法处理转义的单引号
single_quoted_value_pattern = re.compile(r":\s*'((?:\\.|[^'])*)'")

# 匹配单引号键名，并将其转换为双引号 (简单情况)
single_quoted_key_pattern = re.compile(r"'((?:\\.|[^'])*)'\s*:")

# 匹配对象或数组末尾多余的逗号
trailing_comma_pattern = re.compile(r',\s*([}\]])')

# --- 清理与验证函数 ---

def clean_and_validate_json(params_str):
    """
    清理并尝试将参数字符串验证为 JSON 格式，处理常见的 JS 对象字面量差异。
    此函数尝试将类似 JSON 的 JavaScript 对象转换为更标准的 JSON 格式，
    同时尝试保留原始的 JavaScript 表达式（如变量名、函数调用）作为特殊标记的字符串。

    参数:
        params_str (str): 原始参数字符串。

    返回:
        str: 清理后的参数字符串，更接近有效的 JSON 格式。如果清理失败或输入无效，则返回原始字符串。
             如果输入为 None 或空，则返回 None。
    """
    if not params_str or not isinstance(params_str, str):
        return params_str # 返回 None 或非字符串输入

    params_str = params_str.strip() # 去除首尾空格

    # 基本结构检查 - 如果看起来不像对象或数组，可能直接返回
    # (可以根据需要调整此逻辑)
    if not (params_str.startswith('{') and params_str.endswith('}')) and \
       not (params_str.startswith('[') and params_str.endswith(']')):
        # 对于非对象/数组的参数（如简单字符串或变量名），直接返回
        # logging.debug(f"参数不是对象或数组字面量: {params_str}")
        return params_str

    # --- 用于存储 JS 表达式的占位符逻辑 ---
    js_expressions = [] # 存储提取出的 JS 表达式
    placeholder_prefix = "__JS_EXPR_PLACEHOLDER_" # 占位符前缀
    placeholder_suffix = "__"       # 占位符后缀

    def replace_js_expr(match):
        """正则表达式替换函数：将匹配到的 JS 表达式替换为占位符字符串"""
        nonlocal js_expressions
        expr = match.group(1).strip()
        # 检查是否已经是字符串的一部分（避免误替换）
        # 这是一个简化检查，可能不够完美
        start_index = match.start(1)
        if start_index > 0 and params_str[start_index-1] in ['"', "'", "`"]:
             return match.group(0) # 在引号内，不替换

        js_expressions.append(expr)
        placeholder = f'"{placeholder_prefix}{len(js_expressions)-1}{placeholder_suffix}"' # 创建带引号的占位符
        # 返回带冒号和占位符的替换结果，确保占位符是有效的 JSON 字符串值
        return f': {placeholder}'

    # --- 执行清理步骤 ---
    original_params_str = params_str # 保留原始字符串以备回退
    try:
        # 1. 替换 JS 表达式为占位符字符串
        #    注意：这可能会错误地替换某些看起来像表达式的字符串值
        #    这是一个启发式方法，目标是让后续的 JSON 清理更容易进行
        try:
            params_str = js_expr_pattern.sub(replace_js_expr, params_str)
        except Exception as e:
            logging.warning(f"替换 JS 表达式时出错: {e}. Params: {original_params_str[:100]}...")
            # 替换失败时，继续尝试后续清理，但结果可能不准确
            pass

        # 2. 为未加引号的键名添加双引号
        #    使用循环确保所有匹配都被替换
        while True:
            new_params_str = unquoted_key_pattern.sub(r'"\1"', params_str)
            if new_params_str == params_str:
                break
            params_str = new_params_str

        # 3. 将单引号转换为双引号 (键和值)
        #    注意：这可能无法处理所有情况，例如嵌套或转义的单引号
        params_str = single_quoted_key_pattern.sub(r'"\1":', params_str)
        params_str = single_quoted_value_pattern.sub(r':"\1"', params_str)


        # 4. 处理末尾多余的逗号
        params_str = trailing_comma_pattern.sub(r'\1', params_str)

        # --- 恢复 JS 表达式 (将占位符字符串变回原始表达式，不带引号) ---
        # 这一步使得最终结果不是严格的 JSON，但保留了原始信息
        for i, expr in enumerate(js_expressions):
             placeholder = f'"{placeholder_prefix}{i}{placeholder_suffix}"'
             # 恢复时不带引号，因为原始表达式不是字符串
             # 使用 replace 可能替换掉字符串内部的占位符，这是一个潜在问题
             # 更安全的方式是只替换独立的占位符值
             # 简化处理：直接替换
             params_str = params_str.replace(placeholder, expr)

    except Exception as e:
        logging.error(f"JSON 清理过程中发生意外错误: {e}. Params: {original_params_str[:100]}...")
        # 如果清理步骤失败，返回原始字符串
        return original_params_str.strip()

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
    if not params or not isinstance(params, str):
        return "无参数" # 输入为空或非字符串

    # 步骤 1: 清理参数字符串，尝试处理 JS 对象字面量的常见差异
    cleaned_params = clean_and_validate_json(params)
    if not cleaned_params:
        return "无参数" # 清理后为空

    # 步骤 2: 尝试使用标准 JSON 库解析和格式化
    # 这只在 cleaned_params 是严格有效的 JSON 时才会成功
    try:
        parsed = json.loads(cleaned_params)
        # 如果成功，使用 json.dumps 进行标准格式化
        return json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=False) # sort_keys=False 保留原始顺序
    except json.JSONDecodeError:
        # 如果标准解析失败（可能因为包含 JS 表达式或清理不彻底），进入备用格式化流程
        logging.debug(f"标准 JSON 解析失败，尝试基本美化: {cleaned_params[:100]}...")
        pass # 继续尝试其他方法

    # 步骤 3: 备用 - 基本的美化（如果 JSON 解析失败）
    # 这是一个简单的基于字符的缩进逻辑，尝试提高可读性
    # 对包含 JS 表达式的清理后字符串进行格式化
    try:
        level = 0         # 当前缩进级别
        result = []       # 存储格式化后的字符列表
        in_string = False # 是否在字符串内部 ('"' 或 "'")
        string_char = None # 当前字符串使用的引号类型
        escape_next = False # 下一个字符是否是转义字符
        indent_char = '    ' # 使用 4 个空格进行缩进

        for char in cleaned_params:
            # 处理字符串引号
            if char in ['"', "'"] and not escape_next:
                if not in_string:
                    in_string = True
                    string_char = char
                    result.append(char)
                elif in_string and char == string_char:
                    in_string = False
                    string_char = None
                    result.append(char)
                else: # 字符串内部的其他引号
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
                # （忽略非字符串中的空白字符，除非是换行符，可能需要保留）
            # 处理字符串内部的字符：直接添加
            else:
                result.append(char)

        # 组合格式化后的字符列表为字符串
        formatted_string = "".join(result)
        # 简单的后处理：去除可能由格式化引入的连续空行
        formatted_string = re.sub(r'\n\s*\n', '\n', formatted_string)
        return formatted_string.strip()

    except Exception as e:
         logging.error(f"基本美化过程中出错: {e}. Params: {cleaned_params[:100]}...")
         # 如果所有尝试都失败，返回清理后的（但未美化的）原始字符串作为最终回退
         return cleaned_params

# --- 示例 ---
if __name__ == '__main__':
    test_params = [
        '{key: "value", num: 123, bool: true, arr: [1, \'two\'], obj: { nested: null }}',
        '{\'key\': "value", unquoted: value, func: call(), local: localStorage.item}',
        '[1, 2, {id: variableName}]',
        'data: { query: `query MyQuery { posts { id title } }`, variables: { limit: 10 } }',
        'JSON.stringify({a:1, b:"str"})',
        'someVariable',
        'null',
        '{a:1,b:2,}', # Trailing comma
        '{\'single_key\': \'single_value\'}'
    ]
    for p in test_params:
        print("-" * 20)
        print(f"Original: {p}")
        formatted = format_params(p)
        print(f"Formatted:\n{formatted}")

