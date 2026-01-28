#!/usr/bin/env python3
#
# Copyright 2023-2025 Enflame. All Rights Reserved.
#

import subprocess
import os
import copy
import argparse
import re
import sys
import json
from datetime import datetime
from pprint import pprint
from pathlib import Path
from xml.dom.minidom import parse
from pathlib import Path
from typing import List, Tuple, Dict
CHECKERS_DIR = Path(__file__).resolve().parent
REPO_DIR = CHECKERS_DIR.parent
# Add the workspace root to Python path
sys.path.append(str(REPO_DIR))
from common.static_check_common import QualityCodexCommitee,CICheckerCommon,StaticCheck
from common.config_parser import *

def excepthook(exctype, value, traceback):
    '''
    cancel print AssertionError traceback
    '''
    if exctype == AssertionError:
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)

sys.excepthook = excepthook


class Cpp17Feature:
    """C++17 特性信息"""
    def __init__(self, name, line, column, code_snippet, in_cpp14_guard=False, guard_line=0):
        """
        Args:
            name: 特性名称
            line: 行号
            column: 列号
            code_snippet: 代码片段
            in_cpp14_guard: 是否在 #if __cplusplus >= 201402L 条件编译块中
            guard_line: 条件编译块开始的行号
        """
        self.name = name
        self.line = line
        self.column = column
        self.code_snippet = code_snippet
        self.in_cpp14_guard = in_cpp14_guard
        self.guard_line = guard_line 

class CIChecker(CICheckerCommon):
    '''
    checker class
    '''
    def __init__(self, api_init =None, args = None , check_api_type = None , static_check = StaticCheck):
        self.check_name = "cpp17 feature check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.local_ci_check = True
        self.command_output = {}
        self.files_static_check_status = {}
        self.error_message = ""
        self.pass_flag = True
        self.features = [
            {
                'name': '结构化绑定 (Structured Bindings)',
                'pattern': r'\[.*auto.*\]\s*=',
                'description': '例如: auto [a, b] = pair;'
            },
            {
                'name': 'if constexpr',
                'pattern': r'\bif\s+constexpr\s*\(',
                'description': '编译时条件判断'
            },
            {
                'name': '折叠表达式 (Fold Expressions)',
                'pattern': r'\(.*\.\.\.\s*[+\-*/%&|^<>=]|[\+\-*/%&|^<>=]\s*\.\.\.\)',
                'description': '例如: (args + ...)'
            },
            {
                'name': '类模板参数推导 (CTAD)',
                'pattern': r'\bstd::(optional|variant|any|string_view|filesystem::path|tuple|pair)\s*\{',
                'description': 'C++17 引入的标准库类型'
            },
            {
                'name': '内联变量 (Inline Variables)',
                'pattern': r'\binline\s+(const|static|constexpr)\s+\w+',
                'description': 'inline 变量声明'
            },
            {
                'name': 'constexpr lambda',
                'pattern': r'\bconstexpr\s*\[',
                'description': 'constexpr lambda 表达式'
            },
            {
                'name': '嵌套命名空间简写',
                'pattern': r'\bnamespace\s+\w+(::\w+)+\s*\{',
                'description': 'namespace A::B::C {}'
            },
            {
                'name': 'auto 非类型模板参数',
                'pattern': r'template\s*<\s*auto\s+',
                'description': 'template <auto N>'
            },
            {
                'name': 'noexcept 作为函数类型',
                'pattern': r'noexcept\s*\([^)]*\)\s*[=;]',
                'description': 'noexcept 作为函数类型的一部分'
            },
            {
                'name': 'lambda 捕获初始化',
                'pattern': r'\[.*\w+\s*=\s*\w+.*\]',
                'description': 'lambda 捕获时初始化变量'
            },
            {
                'name': 'std::optional',
                'pattern': r'\bstd::optional\s*<',
                'description': 'std::optional<T> 类型'
            },
            {
                'name': 'std::variant',
                'pattern': r'\bstd::variant\s*<',
                'description': 'std::variant<T...> 类型'
            },
            {
                'name': 'std::any',
                'pattern': r'\bstd::any\b',
                'description': 'std::any 类型'
            },
            {
                'name': 'std::string_view',
                'pattern': r'\bstd::string_view\b',
                'description': 'std::string_view 类型'
            },
            {
                'name': 'std::filesystem',
                'pattern': r'\bstd::filesystem::',
                'description': 'std::filesystem 文件系统库'
            },
            {
                'name': '并行算法 (std::execution)',
                'pattern': r'\bstd::execution::',
                'description': '使用 std::execution 的并行算法'
            },
            {
                'name': 'std::apply',
                'pattern': r'\bstd::apply\s*\(',
                'description': 'std::apply 函数'
            },
            {
                'name': 'std::invoke',
                'pattern': r'\bstd::invoke\s*\(',
                'description': 'std::invoke 函数'
            },
            {
                'name': 'std::make_from_tuple',
                'pattern': r'\bstd::make_from_tuple\s*\(',
                'description': 'std::make_from_tuple 函数'
            },
            {
                'name': 'std::not_fn',
                'pattern': r'\bstd::not_fn\s*\(',
                'description': 'std::not_fn 函数'
            },
            {
                'name': 'std::clamp',
                'pattern': r'\bstd::clamp\s*\(',
                'description': 'std::clamp 函数'
            },
            {
                'name': 'std::gcd',
                'pattern': r'\bstd::gcd\s*\(',
                'description': 'std::gcd 函数'
            },
            {
                'name': 'std::lcm',
                'pattern': r'\bstd::lcm\s*\(',
                'description': 'std::lcm 函数'
            },
            {
                'name': 'std::byte',
                'pattern': r'\bstd::byte\b',
                'description': 'std::byte 类型'
            },
            {
                'name': 'std::as_const',
                'pattern': r'\bstd::as_const\s*\(',
                'description': 'std::as_const 函数'
            },
            {
                'name': 'std::size (C++17)',
                'pattern': r'\bstd::size\s*\(',
                'description': 'std::size 函数'
            },
            {
                'name': 'std::empty (C++17)',
                'pattern': r'\bstd::empty\s*\(',
                'description': 'std::empty 函数'
            },
            {
                'name': 'std::data (C++17)',
                'pattern': r'\bstd::data\s*\(',
                'description': 'std::data 函数'
            },
        ]
        
        # C++17 标准库头文件
        self.cpp17_headers = {
            '<optional>': 'std::optional',
            '<variant>': 'std::variant',
            '<any>': 'std::any',
            '<string_view>': 'std::string_view',
            '<filesystem>': 'std::filesystem',
            '<execution>': '并行算法 (Parallel Algorithms)',
        }
        

    def remove_angle_brackets(self,line):
        stack = []
        ret = ""
        for char in line:
            if char == "<":
                stack.append(char)
            elif char == ">":
                if stack:
                    stack.pop()
                    continue
            if not stack:
                ret+=char
        return ret

    def remove_comments(self, code):
        # 匹配块注释 /* ... */
        block_comment_pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
        code = re.sub(block_comment_pattern, '', code)

        # 匹配行注释 //
        line_comment_pattern = re.compile(r'//.*')
        code = re.sub(line_comment_pattern, '', code)

        return code

    def _parse_preprocessor_directives(self, lines: List[str]) -> Dict[int, Tuple[bool, int, str]]:
        """
        解析预处理指令，跟踪条件编译块
        
        Args:
            lines: 文件的所有行
            
        Returns:
            Dict[int, Tuple[bool, int, str]]: 
                key: 行号（从1开始）
                value: (是否在条件编译块中, 条件编译块开始行号, 条件表达式)
        """
        result = {}
        stack = []  # 栈，用于跟踪嵌套的条件编译块
        # 每个元素是 (开始行号, 条件表达式, 是否激活)
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检查 #if, #ifdef, #ifndef
            if stripped.startswith('#if'):
                # 提取条件表达式
                if stripped.startswith('#ifdef'):
                    condition = stripped[7:].strip()
                    # 对于 #ifdef，我们只检查是否定义了宏，不检查值
                    # 这里简化处理，假设 #ifdef 不是我们要检查的
                    is_cpp14_guard = False
                elif stripped.startswith('#ifndef'):
                    condition = stripped[7:].strip()
                    is_cpp14_guard = False
                else:
                    # #if 指令
                    condition = stripped[3:].strip()
                    # 检查是否是 __cplusplus >= 201402L 或类似的条件
                    # 支持多种格式：
                    # __cplusplus >= 201402L
                    # __cplusplus >= 201703L (C++17)
                    # defined(__cplusplus) && __cplusplus >= 201402L
                    # 等等
                    cpp14_pattern = r'__cplusplus\s*>=\s*201402L'
                    cpp17_pattern = r'__cplusplus\s*>=\s*201703L'
                    is_cpp14_guard = bool(re.search(cpp14_pattern, condition) or 
                                         re.search(cpp17_pattern, condition))
                
                # 检查条件是否可能为真（简化处理）
                # 对于 #ifdef/#ifndef，我们无法确定，假设为 False
                is_active = is_cpp14_guard
                stack.append((line_num, condition, is_active, is_cpp14_guard))
                result[line_num] = (is_active, line_num, condition)
            
            # 检查 #elif
            elif stripped.startswith('#elif'):
                if stack:
                    condition = stripped[5:].strip()
                    cpp14_pattern = r'__cplusplus\s*>=\s*201402L'
                    cpp17_pattern = r'__cplusplus\s*>=\s*201703L'
                    is_cpp14_guard = bool(re.search(cpp14_pattern, condition) or 
                                         re.search(cpp17_pattern, condition))
                    # 更新栈顶元素
                    start_line, old_condition, old_active, old_is_cpp14_guard = stack[-1]
                    # 如果前面的 #if 已经激活，那么 #elif 不应该激活
                    # 否则，如果 #elif 的条件是 __cplusplus >= 201402L，则激活
                    is_active = is_cpp14_guard and not old_active
                    stack[-1] = (start_line, condition, is_active, is_cpp14_guard)
                    result[line_num] = (is_active, start_line, condition)
                else:
                    result[line_num] = (False, 0, condition)
            
            # 检查 #else
            elif stripped.startswith('#else'):
                if stack:
                    start_line, condition, _, is_cpp14_guard = stack[-1]
                    # #else 分支通常不是我们要检查的（除非前面的 #if 是）
                    is_active = False  # #else 分支通常不包含 C++17 特性
                    stack[-1] = (start_line, condition, is_active, is_cpp14_guard)
                    result[line_num] = (is_active, start_line, condition)
                else:
                    result[line_num] = (False, 0, '')
            
            # 检查 #endif
            elif stripped.startswith('#endif'):
                if stack:
                    start_line, condition, _, is_cpp14_guard = stack.pop()
                    result[line_num] = (False, start_line, condition)
                else:
                    result[line_num] = (False, 0, '')
            
            # 普通代码行
            else:
                # 检查当前是否在任何条件编译块中
                if stack:
                    # 检查栈中是否有激活的条件编译块
                    # 找到最内层的激活块
                    is_active = False
                    guard_start = 0
                    guard_condition = ''
                    for start_line, condition, active, is_cpp14_guard in reversed(stack):
                        if active and is_cpp14_guard:
                            is_active = True
                            guard_start = start_line
                            guard_condition = condition
                            break
                    result[line_num] = (is_active, guard_start, guard_condition)
                else:
                    result[line_num] = (False, 0, '')
        
        return result

    def _remove_string_literals(self, content: str) -> str:
        """移除字符串字面量（简化处理）"""
        # 移除双引号字符串
        content = re.sub(r'"[^"]*"', '""', content)
        # 移除单引号字符
        content = re.sub(r"'[^']*'", "''", content)
        return content

    def find_files_by_name(self, filename, search_dir=None):
        """
        在当前目录中递归查找同名文件
        
        Args:
            filename: 要查找的文件名
            search_dir: 搜索的根目录，默认为当前工作目录
            exclude_dirs: 要跳过的目录列表，默认为 ['.epkg', '.git', '__pycache__', 'build', 'log']
            
        Returns:
            List[str]: 找到的文件相对路径列表（相对于 search_dir）
        """
        if search_dir is None:
            search_dir = os.getcwd()
        
        found_files = []
        # 获取搜索目录的绝对路径作为基准
        search_dir_abs = os.path.abspath(search_dir)
        
        for root, _, files in os.walk(search_dir_abs):
            
            # 查找同名文件
            if filename in files:
                full_path = os.path.join(root, filename)
                # 计算相对于搜索目录的相对路径
                try:
                    rel_path = os.path.relpath(full_path, search_dir_abs)
                    # 统一使用正斜杠（跨平台兼容）
                    rel_path = rel_path.replace(os.sep, '/')
                    found_files.append(rel_path)
                except ValueError:
                    # 如果无法计算相对路径（例如在不同驱动器上），使用绝对路径
                    found_files.append(os.path.abspath(full_path))
        
        return found_files

    def get_export_header_files(self):
        """
        获取导出的头文件
        """
        export_header_files = []
        epkg_json_files = []
        
        # 遍历目录下的所有文件
        for root, _, files in os.walk(".epkg"):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    epkg_json_files.append(file_path)
        for epkg_json_file in epkg_json_files:
            # print(epkg_json_file)
            with open(epkg_json_file, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                headers = data.get("headers")
                if headers:
                    
                    for header in headers:
                        filename = os.path.basename(header)
                        # print(filename)
                        # 在当前目录中递归查找同名文件
                        found_files = self.find_files_by_name(filename)
                        
                        # 如果找到同名文件，添加到导出头文件列表
                        if found_files:
                            # print("found_files: ", found_files)
                            export_header_files.extend(found_files)
                        # else:
                        #     print(f"未找到同名文件: {filename}")
        return export_header_files

    def check_file(self, file_path: str) -> List[Cpp17Feature]:
        """
        检查文件中的 C++17 特性
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Cpp17Feature]: 发现的 C++17 特性列表
        """
        features_found = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"错误: 无法读取文件 {file_path}: {e}", file=sys.stderr)
            return features_found
        
        # 解析预处理指令，跟踪条件编译块
        preprocessor_info = self._parse_preprocessor_directives(lines)
        
        # 检查 C++17 头文件包含
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            for header, feature_name in self.cpp17_headers.items():
                if header in line_lower and '#include' in line_lower:
                    # 检查是否在条件编译块中
                    in_guard, guard_line, condition = preprocessor_info.get(line_num, (False, 0, ''))
                    features_found.append(Cpp17Feature(
                        name=f'包含 {feature_name} 头文件',
                        line=line_num,
                        column=1,
                        code_snippet=line.strip(),
                        in_cpp14_guard=in_guard,
                        guard_line=guard_line
                    ))
        
        # 移除注释以便更准确地检测
        content_no_comments = self.remove_cpp_comments(content)
        lines_no_comments = content_no_comments.split('\n')
        
        # 检查每种 C++17 特性
        for feature_info in self.features:
            pattern = feature_info['pattern']
            regex = re.compile(pattern)
            
            for line_num, line in enumerate(lines_no_comments, 1):
                # 移除字符串字面量以避免误报
                line_no_strings = self._remove_string_literals(line)
                
                matches = list(regex.finditer(line_no_strings))
                for match in matches:
                    # 获取匹配位置
                    start_col = match.start() + 1  # 列号从1开始
                    end_col = match.end()
                    
                    # 获取原始代码行（带注释的）
                    original_line = lines[line_num - 1] if line_num <= len(lines) else line
                    
                    # 检查是否在条件编译块中
                    in_guard, guard_line, condition = preprocessor_info.get(line_num, (False, 0, ''))
                    
                    features_found.append(Cpp17Feature(
                        name=feature_info['name'],
                        line=line_num,
                        column=start_col,
                        code_snippet=original_line.strip(),
                        in_cpp14_guard=in_guard,
                        guard_line=guard_line
                    ))
        
        # 去重：相同行和列的相同特性只保留一个
        seen = set()
        unique_features = []
        for feature in features_found:
            key = (feature.name, feature.line, feature.column)
            if key not in seen:
                seen.add(key)
                unique_features.append(feature)
        
        # 按行号排序
        unique_features.sort(key=lambda f: (f.line, f.column))
        
        return unique_features

    def check_func(self):
        '''
        check function
        '''
        export_header_files = self.get_export_header_files()
        # print(export_header_files)git 
        for check_file in self.add_or_changed_files:
            if check_file in export_header_files:
                self.files_static_check_status[check_file] = {"check_status": True}
        if self.files_static_check_status:
            self.diff_info = self.get_diff_info()
            for check_file in self.files_static_check_status:
                ret = self.check_file(check_file)
                add_line_info = [ x for x in self.diff_info.get(check_file, {}).get("add",[])]
                add_line_numbers = [x[0] for x in add_line_info]
                for item in ret:
                    if item.line in add_line_numbers:
                        if not item.in_cpp14_guard:
                            self.pass_flag = False
                            self.files_static_check_status[check_file]["check_status"] = False
                            message = f"C++17 feature: {item.name} (not in '#if __cplusplus >= 201402L' or '#if __cplusplus >= 201703L' guard block)"
                            if check_file not in self.command_output:
                                self.command_output[check_file] = "{}:{}:{}".format(check_file,item.line,message)
                            else:
                                self.command_output[check_file] = self.command_output[check_file] + "\n" + "{}:{}:{}".format(check_file,item.line,message)

        return self.check_report()

    def check_report(self):
        '''
        report check result
        '''
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if not check_status['check_status']:
                hook_data_item = {
                    "file":file_path,
                    "message":[],
                    "result":"fail"
                }
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                msg = self.command_output[file_path]
                for one_msg in msg.split("\n"):
                    if one_msg:
                        hook_data_item["message"].append(one_msg)
                        print("\t\t"+one_msg.replace("\n",""))
                self.hook_data.append(hook_data_item)
            else:
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"pass"
                })
        if not self.pass_flag:
            if self.error_message:
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(self.error_message))
                self.hook_data.append({
                    "file":"",
                    "message":[self.error_message],
                    "result":"fail"
                })
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)

    def get_dir_files(self, root_dir):
        '''
        Find all CheckArgs functions and their local variable assignments
        Args:
            root_dir: root directory to search
        Returns:
            dict: Dictionary with file paths as keys and analysis results as values
        '''
        results = []
        
        # 遍历目录下的所有文件
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith((".c", ".cc", ".h", ".hpp", ".cpp", ".tops")):
                    file_path = os.path.join(root, file)
                    results.append(file_path)
        return results


if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    all_files = checker.get_export_header_files()
    for file_path in all_files:
        result = checker.check_file(file_path)
        for feature in result:
            if not feature.in_cpp14_guard:
                message = f"使用 C++17 特性: {feature.name} (未在 #if __cplusplus >= 201402L 条件编译块中)"
                print("{}:{}:{}".format(file_path,feature.line,message))
            else:
                message = f"使用 C++17 特性: {feature.name} (在条件编译块中，第 {feature.guard_line} 行)"
                print("{}:{}:{}".format(file_path,feature.line,message))
