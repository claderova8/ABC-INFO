# -*- coding: utf-8 -*-
"""
参数格式化器模块 (适配 AST 提取结果)
功能：格式化提取的API参数字典
"""
import json
import logging

logger = logging.getLogger(__name__)

def format_params(params_data):
    """
    格式化从 AST 提取的参数数据 (通常是字典) 为可读的 JSON 格式。
    对于无法静态解析的值 (标记为 "[Dynamic ...]", "[Variable: ...]" 等)，
    会保留这些标记。

    参数:
        params_data: 从 extract_object_literal 返回的字典, 字符串标记, 或 None

    返回:
        格式化后的字符串，或者 "无参数"
    """
    if params_data is None:
        return "无参数"

    # 处理 AST 提取器直接返回的字符串标记 (如 "[Variable: data]")
    if isinstance(params_data, str) and params_data.startswith('['):
         return params_data # 直接返回标记字符串

    # 处理 AST 提取器返回的字典
    if isinstance(params_data, dict):
        if not params_data: # 空字典
            return "无参数 (空对象)"
        try:
            # 直接将字典格式化为 JSON
            return json.dumps(params_data, indent=4, ensure_ascii=False, sort_keys=True)
        except TypeError as e:
            # --- BUG 修复: 更具体的异常处理 ---
            logger.error(f"格式化参数字典为 JSON 时发生 TypeError: {e}. 参数: {params_data}", exc_info=True)
            # 如果序列化失败，返回原始字典的字符串表示形式
            return str(params_data)

    # --- 处理可能的旧格式或意外输入 ---
    # 如果输入是字符串但不是标记格式，尝试解析为 JSON (可能是旧 regex 提取的?)
    if isinstance(params_data, str):
        logger.debug(f"参数数据是字符串，尝试解析为 JSON: {params_data[:100]}...") # Log a preview
        try:
            # 尝试去除可能的 JavaScript 对象字面量引号问题 (谨慎使用)
            # cleaned_str = params_data.replace("'", '"') # 这可能破坏字符串内部的单引号
            parsed = json.loads(params_data) # 直接尝试解析
            return json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True)
        except json.JSONDecodeError:
             logger.warning(f"参数字符串不是有效的 JSON，按原样返回: {params_data[:100]}...")
             # 如果是旧格式的清理后字符串，直接返回
             return params_data.strip()
        except Exception as e:
             # --- BUG 修复: 捕获其他解析错误 ---
             logger.error(f"解析参数字符串时发生意外错误: {e}", exc_info=True)
             return "[参数字符串解析错误]"

    # 其他未知类型
    logger.warning(f"未知的参数数据类型: {type(params_data)}，值: {params_data}")
    return "参数格式未知"

if __name__ == '__main__':
    # 测试
    test_params_1 = {'key': 'value', 'num': 123, 'bool': True, 'arr': '[Array]', 'dyn': '[Variable: config]'}
    test_params_2 = None
    test_params_3 = {}
    test_params_4 = "[Variable: bodyData]" # 来自 AST 的标记
    test_params_5 = "{key: 'old style string'}" # 格式错误的 JSON 字符串
    test_params_6 = '{"valid": "json string"}' # 有效的 JSON 字符串
    test_params_7 = 123 # 意外类型

    print("Test 1 (Dict):")
    print(format_params(test_params_1))
    print("\nTest 2 (None):")
    print(format_params(test_params_2))
    print("\nTest 3 (Empty Dict):")
    print(format_params(test_params_3))
    print("\nTest 4 (AST Marker String):")
    print(format_params(test_params_4))
    print("\nTest 5 (Malformed JSON String):")
    print(format_params(test_params_5))
    print("\nTest 6 (Valid JSON String):")
    print(format_params(test_params_6))
    print("\nTest 7 (Unexpected Type):")
    print(format_params(test_params_7))
