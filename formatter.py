# -*- coding: utf-8 -*-
"""
用于 JavaScript API 提取器的参数格式化模块。
包含清理、尝试验证和美化参数字符串的功能，使其更接近标准 JSON 格式以便阅读。
"""

import re
import json
import logging
# 导入所需的类型提示
from typing import Optional, List, Dict, Any, Union, Tuple

# --- 配置日志 ---
# 获取当前模块的日志记录器
log = logging.getLogger(__name__)

# --- 常量与预编译正则表达式 ---

# 匹配 JavaScript 表达式作为值的模式。
# 旨在识别那些看起来不像标准 JSON 值 (字符串、数字、布尔、null) 的值，
# 例如函数调用、变量、包含 JS 运算符的表达式等。
JS_EXPR_PATTERN = re.compile(
    r':\s*' # 匹配冒号和其后的空白字符
    r'('    # 开始捕获组 1: JS 表达式值本身
        # 优先匹配明显的非 JSON 值
        # 1. 函数调用 (可能包含嵌套括号)
        r'(?:[a-zA-Z_$][a-zA-Z0-9_$.]*\s*\(.*?\))' # 匹配标识符后跟括号，非贪婪匹配括号内容
        # 2. 包含常见 JS 运算符的表达式 (||, &&, +, -, *, /, %, ?, :)
        r'|' # 或
        r'(?:.*(?:\|\||&&|\*|\/|%|\?|:).*)' # 匹配包含这些运算符的任意内容
        # 3. 变量名 / 属性访问 (不是加引号的字符串、数字、布尔或 null)
        r'|' # 或
        r'(?:[a-zA-Z_$][a-zA-Z0-9_$.]+)' # 匹配标识符和属性访问，例如 localStorage.SchoolId
        # 4. 排除简单的 JSON 值 (字符串、数字、布尔、null) 的逻辑主要依赖于前面的模式未匹配到它们
    r')' # 结束捕获组 1
    # 后向肯定断言：确保表达式后是逗号、闭合花括号/方括号，或字符串结束
    r'(?=\s*[,}\]]|$)'
)


# 匹配未加引号的 JSON 键。例如 `{ key: "value" }` 中的 `key`
UNQUOTED_KEY_PATTERN = re.compile(r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', re.DOTALL)
# 匹配单引号包围的值。例如 `: 'value'` 中的 `'value'`
SINGLE_QUOTED_VALUE_PATTERN = re.compile(r":\s*'((?:\\.|[^'])*)'", re.DOTALL)
# 匹配反引号包围的值。例如 `: `value`` 中的 ``value``
BACKTICK_QUOTED_VALUE_PATTERN = re.compile(r":\s*`((?:\\.|[^`])*)`", re.DOTALL)
# 匹配对象或数组末尾可能存在的逗号。例如 `{ "key": "value", }` 中的 `,`
TRAILING_COMMA_PATTERN = re.compile(r',\s*([}\]])')
# 验证是否是有效的 JS 变量名 (用于参数去重时的键)
VALID_JS_VARIABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_$][a-zA-Z0-9_$.]*$')


# --- 清理与验证函数 ---

def _apply_basic_cleaning(params_str: str) -> str:
    """
    应用基本的 JSON 格式清理，包括给未加引号的键加引号、转换单引号和反引号值、移除末尾逗号。
    此函数不会替换 JS 表达式。
    """
    if not params_str: return ""
    temp_params = params_str.strip()
    log.debug(f"Applying basic cleaning to: {temp_params[:100]}...")

    # 1. 给未加引号的键加引号
    # 使用 lambda 函数处理匹配，将捕获组 2 (键名) 用双引号包围
    temp_params = UNQUOTED_KEY_PATTERN.sub(r'\1"\2":', temp_params)

    # 2. 转换单引号值到双引号值
    # 使用 lambda 函数处理匹配，将捕获组 1 (单引号内的内容) 用双引号包围，并处理转义字符
    temp_params = re.sub(r":\s*'((?:\\.|[^'])*)'", lambda m: ': "{}"'.format(m.group(1).replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")), temp_params)

    # 3. 转换反引号值到双引号值
    # 注意：反引号可能包含模板字符串 (${...})，这里的简单转换可能不完全准确。
    # 但对于简单的反引号字符串，这个转换是有效的。
    temp_params = re.sub(r":\s*`((?:\\.|[^`])*)`", lambda m: ': "{}"'.format(m.group(1).replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")), temp_params)

    # 4. 移除对象或数组末尾的逗号
    # 使用 lambda 函数处理匹配，只保留闭合的花括号或方括号
    temp_params = TRAILING_COMMA_PATTERN.sub(r'\1', temp_params)

    log.debug(f"After basic cleaning: {temp_params[:100]}...")
    return temp_params.strip()

def clean_and_validate_json(params_str: Optional[str]) -> Tuple[Optional[str], Dict[str, str]]:
    """
    清理参数字符串，使其更接近标准 JSON 格式，以便尝试解析。
    主要处理未加引号的键、不同类型的引号，并将 JS 表达式替换为占位符。

    Args:
        params_str: 原始参数字符串。

    Returns:
        一个元组：(清理后带占位符的字符串, 占位符与原始表达式的映射字典)。
        如果输入无效，返回 (None, {})。
    """
    if not params_str or not isinstance(params_str, str):
        return None, {}

    cleaned_params = params_str.strip()
    if not cleaned_params:
        return "", {}

    log.debug(f"Starting JSON cleaning process for: {cleaned_params[:100]}...")

    # --- Step 1: 应用基本的 JSON 格式清理 (引号、逗号) ---
    # 先进行基本清理，处理引号和末尾逗号
    temp_params = _apply_basic_cleaning(cleaned_params)

    # --- Step 2: 将可能的 JS 表达式替换为占位符 ---
    expr_placeholders: Dict[str, str] = {} # 存储 JS 表达式和其对应的占位符
    placeholder_counter = 0 # 占位符计数器

    def replace_expr_simple(match):
        """用于 re.sub 的回调函数，将匹配到的 JS 表达式替换为占位符字符串。"""
        nonlocal placeholder_counter
        # match.group(1) 是 JS 表达式的值部分
        expr = match.group(1).strip()

        # 启发式检查：如果表达式看起来已经是 JSON 基本类型 (加引号字符串、数字、布尔、null)，则不替换
        # 避免将有效的 JSON 值误判为 JS 表达式
        if re.fullmatch(r'"(?:\\.|[^"])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null', expr, re.IGNORECASE):
             log.debug(f"Expression '{expr}' looks like JSON primitive, not replacing.")
             return match.group(0) # 返回原始匹配的完整字符串 (包括冒号和值)

        log.debug(f"Identified potential JS expression to replace: {expr[:100]}...")
        # 如果这个表达式之前没有遇到过，创建一个新的占位符
        if expr not in expr_placeholders:
            placeholder = f"__JS_EXPR_{placeholder_counter}__" # 定义占位符格式
            expr_placeholders[expr] = placeholder
            placeholder_counter += 1
        # 返回替换后的字符串：原始的键值分隔部分 (冒号和空格) 加上用双引号包围的占位符
        # 这样在 JSON 解析时，占位符会被当作一个普通的字符串值
        original_full_match = match.group(0) # 完整的匹配字符串 (例如 ': JS表达式')
        original_value_part = match.group(1) # JS 表达式值部分
        # 找到值部分在完整匹配中的起始索引
        start_index_value = original_full_match.find(original_value_part)
        # 提取键值分隔部分 (从完整匹配的开始到值部分的开始)
        key_part = original_full_match[:start_index_value] # 例如 ': '
        # 返回重构的字符串：分隔部分 + 双引号 + 占位符 + 双引号
        return f'{key_part}"{expr_placeholders[expr]}"'

    # 使用 JS_EXPR_PATTERN 查找并替换所有可能的 JS 表达式
    params_with_placeholders = JS_EXPR_PATTERN.sub(replace_expr_simple, temp_params)
    log.debug(f"After replacing JS expressions: {params_with_placeholders[:100]}...")

    final_cleaned_params = params_with_placeholders.strip()
    log.debug(f"JSON cleaning finished. Result: {final_cleaned_params[:100]}...")
    return final_cleaned_params, expr_placeholders


# --- 格式化函数 ---

def format_params(params_str: Optional[str]) -> str:
    """
    尝试格式化提取到的参数字符串。
    首先尝试将字符串清理并解析为 JSON (替换 JS 表达式为占位符)。
    如果 JSON 解析成功，则对 JSON 进行美化，并将占位符恢复为原始 JS 表达式。
    如果 JSON 解析失败，则对原始字符串应用基本的清理和缩进。

    Args:
        params_str: 原始参数字符串。

    Returns:
        格式化后的字符串，如果输入无效则返回 "无参数"。
    """
    if not params_str or not isinstance(params_str, str):
        return "无参数"

    original_params_str = params_str.strip()
    if not original_params_str:
        return "无参数"

    # 1. 清理字符串并获取 JS 表达式占位符，以便尝试 JSON 解析
    cleaned_params_for_json, expr_placeholders = clean_and_validate_json(original_params_str)

    # 如果清理后的字符串为空，可能是原始输入有问题，回退到基本格式化
    if not cleaned_params_for_json:
        log.warning("Cleaning for JSON attempt resulted in empty string, formatting original.")
        return _basic_pretty_print(original_params_str)

    log.debug(f"Attempting JSON parse on: {cleaned_params_for_json[:100]}...")

    # 2. 尝试解析清理后的字符串 (包含占位符) 作为 JSON
    try:
        # 只有当清理后的字符串看起来像 JSON 对象或数组时才尝试解析
        if (cleaned_params_for_json.startswith('{') and cleaned_params_for_json.endswith('}')) or \
           (cleaned_params_for_json.startswith('[') and cleaned_params_for_json.endswith(']')):

            # 尝试加载为 JSON 对象
            parsed_json = json.loads(cleaned_params_for_json)
            # 如果成功解析，使用 json.dumps 进行美化 (缩进、排序键、不转义非 ASCII 字符)
            formatted_json_str = json.dumps(parsed_json, indent=2, sort_keys=True, ensure_ascii=False)
            log.debug("Successfully parsed as JSON (with placeholders). Restoring expressions.")

            # 恢复原始 JS 表达式
            final_formatted_str = formatted_json_str
            # 为了避免替换字符串中包含其他占位符的情况 (虽然不常见)，按占位符长度倒序排序进行替换
            sorted_placeholders = sorted(expr_placeholders.items(), key=lambda item: len(item[1]), reverse=True)
            for expr, placeholder in sorted_placeholders:
                 # 在格式化后的 JSON 字符串中，占位符是被双引号包围的字符串值。
                 # 将 '"__JS_EXPR_X__"' 替换回原始的 JS 表达式字符串。
                 # 注意：这里直接替换，不加引号，因为原始表达式可能不是字符串。
                 final_formatted_str = final_formatted_str.replace(f'"{placeholder}"', expr)

            log.debug("Expressions restored. Final formatted output.")
            # 对最终结果再应用一次基本缩进，确保格式一致性 (可选，json.dumps 已缩进)
            # return _basic_pretty_print(final_formatted_str)
            return final_formatted_str.strip() # 返回去除首尾空白的最终字符串

        else:
             # 清理后的字符串不像 JSON 对象/数组，回退到基本格式化
             log.debug("Cleaned string does not resemble JSON object/array. Formatting original.")
             # 对原始字符串应用基本清理和缩进
             partially_cleaned_original = _apply_basic_cleaning(original_params_str)
             return _basic_pretty_print(partially_cleaned_original)

    except (json.JSONDecodeError, TypeError) as e:
        # JSON 解析失败 (即使有占位符也未能成功解析)
        log.warning(f"Could not parse as JSON ({e}). Formatting original with basic cleaning. Input: {cleaned_params_for_json[:100]}...")
        # 回退：对原始字符串应用基本清理和缩进
        partially_cleaned_original = _apply_basic_cleaning(original_params_str)
        return _basic_pretty_print(partially_cleaned_original)

    except Exception as e:
        # 捕获格式化过程中的其他意外错误
        log.error(f"Unexpected error during parameter formatting: {e}. Input: {original_params_str[:100]}...", exc_info=True)
        # 作为最后的回退，返回原始字符串
        return original_params_str.strip()


def _basic_pretty_print(params_str: str, indent_char: str = '  ') -> str:
    """
    一个简单的基本缩进函数，用于处理对象/数组结构的字符串，即使其中包含 JS 表达式。
    它不会尝试解析 JSON，只根据花括号、方括号和逗号进行缩进。

    Args:
        params_str: 需要格式化的字符串 (可能包含 JS 表达式)。
        indent_char: 用于缩进的字符 (默认为两个空格)。

    Returns:
        应用基本缩进后的字符串。
    """
    log.debug(f"Applying basic pretty print to: {params_str[:100]}...")
    result: List[str] = [] # 存储格式化后的行或字符
    level = 0 # 当前缩进级别
    in_string = False # 标记是否在字符串内部
    string_char = '' # 当前字符串的引号类型 ('"', "'", '`')
    i = 0 # 当前处理的字符索引
    n = len(params_str) # 字符串总长度

    try:
        while i < n:
            char = params_str[i] # 当前字符

            # 如果不在字符串内部
            if not in_string:
                if char in ('{', '['):
                    # 遇到开花括号或开方括号，添加到结果，换行，增加缩进级别，添加缩进
                    result.append(char)
                    result.append('\n')
                    level += 1
                    result.append(indent_char * level)
                elif char in ('}', ']'):
                    # 遇到闭花括号或闭方括号，换行，减少缩进级别，添加缩进，添加到结果
                    result.append('\n')
                    level = max(0, level - 1) # 确保缩进级别不小于 0
                    result.append(indent_char * level)
                    result.append(char)
                elif char == ',':
                    # 遇到逗号，添加到结果，换行，添加当前级别的缩进
                    result.append(char)
                    result.append('\n')
                    result.append(indent_char * level)
                elif char == ':':
                    # 遇到冒号，添加到结果，并在后面加一个空格
                    result.append(char)
                    result.append(' ')
                elif char in ('"', "'", "`"):
                    # 遇到引号，添加到结果，进入字符串内部状态，记录引号类型
                    result.append(char)
                    in_string = True
                    string_char = char
                elif char.isspace():
                     # 遇到空白字符，如果不在字符串内部，且不是在行首或冒号后，则添加到结果
                     # 这个逻辑可以进一步优化，只保留必要的空格
                     # 简单的处理是：如果前一个字符不是空白，则添加一个空格
                     if not result or not result[-1].isspace():
                         result.append(' ')
                else:
                    # 遇到其他字符，添加到结果
                    result.append(char)
            else:
                # 如果在字符串内部，直接添加字符
                result.append(char)
                # 检查是否遇到字符串结束引号，并处理转义引号
                if char == string_char and (i == 0 or params_str[i-1] != '\\' or (i > 1 and params_str[i-2:i] == '\\\\')):
                   in_string = False # 退出字符串内部状态
                   string_char = '' # 清空引号类型
                elif char == '\\' and i + 1 < n: # 处理转义字符，例如 \" 或 \'
                    result.append(params_str[i+1]) # 添加转义字符的下一位
                    i += 1 # 跳过转义字符的下一位

            i += 1 # 移动到下一个字符

        # 将结果列表合并为字符串
        formatted_string = "".join(result)
        # 清理多余的空白行或行末空白
        formatted_string = re.sub(r'\s*\n', '\n', formatted_string) # 移除换行符前的空白
        formatted_string = re.sub(r'\n\s*\n', '\n\n', formatted_string) # 合并连续空行
        log.debug("Basic pretty print finished.")
        # 返回去除首尾空白的最终字符串
        return formatted_string.strip()

    except Exception as e:
         # 捕获基本格式化过程中的意外错误
         log.error(f"Error during basic pretty print: {e}. Input: {params_str[:100]}...", exc_info=True)
         # 回退：返回原始字符串去除首尾空白
         return params_str.strip()

# --- 独立执行入口 (通常不会直接运行 formatter.py) ---
# 保留此部分以防需要独立测试，但在主程序中不会执行
if __name__ == '__main__':
    # 确保独立运行时日志有基本配置
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    # 示例用法
    test_params_js = """
    {
        userId: 123,
        userName: 'testUser',
        isActive: true,
        settings: {
            theme: "dark",
            pageSize: 10
        },
        roles: ['admin', 'editor'],
        lastLogin: new Date(), // JS expression
        data: someVariable, // JS variable
        status: checkStatus(user) // JS function call
    }
    """
    test_params_json = """
    {
        "id": "abc",
        "value": 456,
        "enabled": false,
        "list": [1, 2, 3]
    }
    """
    test_params_invalid = "just a string"
    test_params_empty = ""
    test_params_none = None
    test_params_no_params = "无参数"

    print("--- Testing format_params ---")
    print("\nOriginal JS-like:")
    print(test_params_js)
    print("\nFormatted:")
    print(format_params(test_params_js))

    print("\nOriginal JSON:")
    print(test_params_json)
    print("\nFormatted:")
    print(format_params(test_params_json))

    print("\nOriginal Invalid:")
    print(test_params_invalid)
    print("\nFormatted:")
    print(format_params(test_params_invalid))

    print("\nOriginal Empty:")
    print(f"'{test_params_empty}'")
    print("\nFormatted:")
    print(f"'{format_params(test_params_empty)}'")

    print("\nOriginal None:")
    print(test_params_none)
    print("\nFormatted:")
    print(f"'{format_params(test_params_none)}'")

    print("\nOriginal '无参数':")
    print(test_params_no_params)
    print("\nFormatted:")
    print(f"'{format_params(test_params_no_params)}'")
