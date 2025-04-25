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
        params_data: 从 extract_object_literal 返回的字典或 None

    返回:
        格式化后的字符串，或者 "无参数"
    """
    if params_data is None:
        return "无参数"

    if not isinstance(params_data, dict):
        # 如果输入不是预期的字典 (可能是旧 regex 提取的字符串)，尝试基本处理
        if isinstance(params_data, str):
             # 尝试直接解析为 JSON
             try:
                 parsed = json.loads(params_data)
                 return json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True)
             except json.JSONDecodeError:
                 # 如果是旧格式的清理后字符串，直接返回
                 return params_data.strip()
        return "参数格式未知" # 其他意外类型

    if not params_data: # 空字典
        return "无参数 (空对象)"

    try:
        # 直接将字典格式化为 JSON
        # ensure_ascii=False 保留非 ASCII 字符
        # sort_keys=True 使输出顺序稳定
        # indent=4 提供缩进
        return json.dumps(params_data, indent=4, ensure_ascii=False, sort_keys=True)
    except TypeError as e:
        logger.error(f"Error formatting parameters to JSON: {e}. Params: {params_data}")
        # 如果序列化失败（理论上不应发生，因为我们处理的是基本类型和字符串标记），返回原始表示
        return str(params_data)
    except Exception as e:
         logger.error(f"Unexpected error during parameter formatting: {e}")
         return "[参数格式化错误]"

if __name__ == '__main__':
    # 测试
    test_params_1 = {'key': 'value', 'num': 123, 'bool': True, 'arr': '[Array]', 'dyn': '[Variable: config]'}
    test_params_2 = None
    test_params_3 = {}
    test_params_4 = "[Variable: bodyData]" # 来自 AST 的标记
    test_params_5 = "{key: 'old style string'}" # 旧格式字符串

    print("Test 1:")
    print(format_params(test_params_1))
    print("\nTest 2:")
    print(format_params(test_params_2))
    print("\nTest 3:")
    print(format_params(test_params_3))
    print("\nTest 4:")
    print(format_params(test_params_4))
    print("\nTest 5:")
    print(format_params(test_params_5))

