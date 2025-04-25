# -*- coding: utf-8 -*-
"""
AST 解析器模块
功能：调用外部 Node.js Esprima 解析器获取 JavaScript AST
"""
import subprocess
import json
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Node.js 脚本路径 (假设与此文件在同一目录下)
NODE_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'esprima_parser.js')

def create_node_script():
    """如果 Node.js 解析脚本不存在，则创建它"""
    if not os.path.exists(NODE_SCRIPT_PATH):
        script_content = r"""
const esprima = require('esprima');
const fs = require('fs');

const inputFile = process.argv[2]; // 输入 JS 文件路径
const outputFile = process.argv[3]; // 输出 AST JSON 文件路径

try {
    const jsCode = fs.readFileSync(inputFile, 'utf8');
    // 解析选项：包括位置信息和范围信息，容忍一些错误
    const ast = esprima.parseScript(jsCode, { range: true, loc: true, tolerant: true });
    fs.writeFileSync(outputFile, JSON.stringify(ast, null, 2)); // 输出格式化的 JSON
    // console.log(`AST successfully generated for ${inputFile}`); // 用于调试
    process.exit(0); // 成功退出
} catch (e) {
    console.error(`Error parsing ${inputFile}:`, e.message);
    // 尝试输出错误信息到文件，以便 Python 捕获
    fs.writeFileSync(outputFile, JSON.stringify({ error: e.message, stack: e.stack }));
    process.exit(1); // 失败退出
}
"""
        try:
            with open(NODE_SCRIPT_PATH, 'w', encoding='utf-8') as f:
                f.write(script_content)
            logger.info(f"Node.js parser script created at {NODE_SCRIPT_PATH}")
        except IOError as e:
            logger.error(f"Failed to create Node.js parser script: {e}")
            raise

def parse_js_to_ast(js_code):
    """
    使用 Node.js Esprima 解析 JavaScript 代码字符串并返回 AST JSON 对象。

    参数:
        js_code: JavaScript 代码字符串

    返回:
        解析得到的 AST (dict)，如果解析失败则返回 None
    """
    # 确保 Node.js 脚本存在
    create_node_script()

    # 使用临时文件传递代码和接收 AST，避免命令行长度限制和编码问题
    temp_input_file = None
    temp_output_file = None
    try:
        # 创建临时输入文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.js', encoding='utf-8') as infile:
            infile.write(js_code)
            temp_input_file = infile.name
        # 创建临时输出文件路径
        with tempfile.NamedTemporaryFile(mode='r', delete=False, suffix='.json', encoding='utf-8') as outfile:
            temp_output_file = outfile.name

        # 构建 Node.js 命令
        # 确保 node 命令在 PATH 中，或者提供完整路径
        command = ['node', NODE_SCRIPT_PATH, temp_input_file, temp_output_file]

        # 执行 Node.js 脚本
        # 设置超时以防止脚本挂起
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=15) # 15秒超时

        # 检查执行结果
        if process.returncode != 0:
            logger.error(f"Node.js Esprima parser failed (return code {process.returncode}).")
            logger.error(f"Stderr: {process.stderr.strip()}")
            # 尝试读取输出文件中的错误信息
            try:
                with open(temp_output_file, 'r', encoding='utf-8') as f:
                    error_data = json.load(f)
                    logger.error(f"Parser error details: {error_data.get('error', 'Unknown error')}")
            except Exception:
                 logger.error("Could not read error details from output file.")
            return None

        # 读取并解析输出的 AST JSON 文件
        with open(temp_output_file, 'r', encoding='utf-8') as f:
            ast_data = json.load(f)
            # 检查是否包含解析器返回的错误
            if isinstance(ast_data, dict) and 'error' in ast_data:
                 logger.error(f"Esprima parsing error reported in output: {ast_data['error']}")
                 return None
            return ast_data

    except FileNotFoundError:
        logger.error("Error: 'node' command not found. Please ensure Node.js is installed and in your PATH.")
        return None
    except subprocess.TimeoutExpired:
        logger.error("Error: Node.js parser script timed out.")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding AST JSON output: {e}")
        # 可以尝试打印原始输出用于调试
        # try:
        #     with open(temp_output_file, 'r', encoding='utf-8') as f:
        #         logger.debug(f"Raw output: {f.read()}")
        # except Exception: pass
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during AST parsing: {e}")
        return None
    finally:
        # 清理临时文件
        if temp_input_file and os.path.exists(temp_input_file):
            os.remove(temp_input_file)
        if temp_output_file and os.path.exists(temp_output_file):
            os.remove(temp_output_file)

if __name__ == '__main__':
    # 测试代码
    test_js = """
    function greet(name) {
        console.log('Hello, ' + name + '!');
        axios.get('/api/users', { params: { id: 123 } });
        fetch('/api/data', { method: 'POST', body: JSON.stringify({ value: dataVar }) });
    }
    const dataVar = "test";
    greet('World');
    """
    ast = parse_js_to_ast(test_js)
    if ast:
        print("AST parsing successful!")
        # print(json.dumps(ast, indent=2)) # 打印部分 AST 结构
    else:
        print("AST parsing failed.")
