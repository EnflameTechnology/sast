#!/usr/bin/env python3
#
# Copyright 2023-2025 Enflame. All Rights Reserved.
#
import subprocess
import os
import argparse
import re
import sys
import json
from io import StringIO
from contextlib import redirect_stdout
import getpass
from datetime import datetime
from pprint import pprint
from pathlib import Path
from xml.dom.minidom import parse
import pickle
import xml.dom.minidom
# Get the directory containing this file (common directory)
COMMON_DIR = Path(__file__).resolve().parent
# Get the parent directory (workspace root)
REPO_DIR = COMMON_DIR.parent
# Add the workspace root to Python path
sys.path.append(str(REPO_DIR))
from common.config_parser import *
from common import localgit

class DefaultArgs():
    def __init__(self,diff_type = DIFF_TYPE_INCREMENT,check_file = None):
        self.diff_type = diff_type
        self.check_file = check_file

class StaticCheck():
    '''
    1.Abstract away platform-specific details, such as code from localgit.
    2.Encapsulate common operations, such as getting the diff lines, getting the check lines, etc.
    3.Provide base information,like commit hash,change url,etc.
    '''
    def __init__(self, api_init, args, check_api_type, cache_file = SERIALIZED_FILE_NAME):
        self.timestamp = datetime.now()
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as load_file:
                self.cache = pickle.load(load_file, encoding='utf-8')
                self.cache.timestamp = datetime.now()
        else:
            if not api_init or not args or not check_api_type:
                api_init = localgit.Local()
                args = DefaultArgs(diff_type=DIFF_TYPE_INCREMENT)
                check_api_type = API_TYPE_LOCALGIT
            self.check_api_type = check_api_type
            self.default_check = False
            self.local_ci_check = True
            self.local_workspace_check = False
            self.pass_flag = True
            self.permission_flag = False
            self.diff_type = args.diff_type
            self.check_file = args.check_file
            self.api_init = api_init
            self.add_files = list()
            self.renamed_files = list()
            self.modified_files = list()
            self.add_or_changed_files = list()
            self.files_static_check_status = dict()
            self.hook_data = []
            self.tools_path = "{}/tools".format(REPO_DIR)
            self.default_config_path = "{}/config".format(REPO_DIR)
            if check_api_type == API_TYPE_LOCALGIT:
                self.patchset_revision = self.api_init.get_current_commit_id()
                self.patchset_revision_old = self.api_init.get_old_commit_id()
                self.change_url = self.api_init.get_local_path()
                self.branch = self.api_init.get_current_branch()
                self.project_name = self.api_init.get_current_project_name()
            else:
                print("Check type input error")
                exit(1)

            self._patchset_files()

            self.commit_message = self.get_last_commit_messages()
            self.commit_author = self.get_last_commit_owner()

            if self.check_api_type != API_TYPE_LOCALGIT:
                with open(SERIALIZED_FILE_NAME, 'wb') as dump_file:
                    pickle.dump(self, dump_file, protocol=pickle.DEFAULT_PROTOCOL)


    def _patchset_files(self):
        if  self.check_api_type == API_TYPE_LOCALGIT:
            if self.diff_type == DIFF_TYPE_WORKSPACE:
                pipe = subprocess.Popen("git status -s | grep -P '^\s*M' |awk '{print $2}'",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                self.changed_files = command_output.decode('utf-8').splitlines()
                pipe = subprocess.Popen("git status -s | grep -P '^\?\?' |awk '{print $2}'",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                self.add_files = command_output.decode('utf-8').splitlines()
                if self.check_file:
                    if self.check_file in self.add_files or any([self.check_file.startswith(x) for x in self.add_files]):
                        self.add_files = [self.check_file]
                        self.add_or_changed_files = [self.check_file]
                    elif self.check_file in self.changed_files:
                        self.add_files = []
                        self.add_or_changed_files = [self.check_file]
                    else:
                        self.add_files = []
                        self.add_or_changed_files = []
                else:
                    self.add_or_changed_files = self.changed_files
            elif self.diff_type == DIFF_TYPE_INCREMENT:
                # if git depth is 1, 'git diff' will not work,so we use 'git show' instead
                pipe = subprocess.Popen("git show --no-commit-id --name-only --diff-filter=ACMR HEAD",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                self.add_or_changed_files = command_output.decode('utf-8').splitlines()
                pipe = subprocess.Popen("git show --no-commit-id --name-only --diff-filter=A HEAD",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                self.add_files = command_output.decode('utf-8').splitlines()


    def ignore_checker(self, ignore_type, ignore_admin):
        '''
        skip check if the commit message contains the ignore keyword
        '''
        return False

    def is_binary(self, file_path):
        '''
        Check if the file is binary
        return False if file is directory or text file
        '''
        _TEXT_BOMS = (
            codecs.BOM_UTF16_BE,
            codecs.BOM_UTF16_LE,
            codecs.BOM_UTF32_BE,
            codecs.BOM_UTF32_LE,
            codecs.BOM_UTF8,
        )
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as source_file:
                initial_bytes = source_file.read(8192)
                return not any(initial_bytes.startswith(bom) for bom in _TEXT_BOMS) and b'\0' in initial_bytes
        else:
            return False

    def get_diff_lines_info(self):
        '''
        Get the deleted lines and added lines from the commit
        return:
        {
            "common_util/util_func.groovy": {
                "add":[(6822,"def epkgVerify1")],
                "del":[(6822,"def epkgVerify2")],
                "type":"modify",
                "old_path":"common_util/util_func.groovy"
            }
        }
        '''
        result = self.api_init.get_diff()
        return result

    def get_diff_lines_info_for_local(self, revision1=GIT_NULL_TREE, revision2="HEAD", directory = "./"):
        '''
        Use the diff between the current commit and an empty tree to obtain the full code
        '''
        if self.check_api_type != API_TYPE_LOCALGIT:
            print("get_diff_lines_info_for_local only support local git")
            exit(1)
        local = localgit.Local(directory)
        result = local.get_diff(revision1, revision2)
        return result

    def get_diff_lines_for_workspace(self,check_file):
        '''
        '''
        if check_file:
            if check_file in list(set(self.add_or_changed_files) - set(self.add_files)):
                return self.get_diff_lines_info_for_local(revision1=check_file,revision2="",directory = "./")
            else:
                add_info = []
                with open(check_file,'r',encoding='utf-8',errors='ignore') as f:
                    for index,content in enumerate(f.readlines()):
                         add_info.append((index+1, content))
                return {
                     check_file: {
                        "add":add_info,
                        "del":[],
                        "type":"add",
                        "old_path":""
                    }
                }
        else:
            return self.get_diff_lines_info_for_local(revision1="",revision2="HEAD",directory = "./")

    def get_diff_info(self,*args,**kwargs):
        '''
        Get the deleted lines and added lines
        '''
        if self.diff_type == DIFF_TYPE_FULL:
            return self.get_diff_lines_info_for_local(*args,**kwargs)
        elif self.diff_type == DIFF_TYPE_INCREMENT:
            return self.get_diff_lines_info()
        elif self.diff_type == DIFF_TYPE_WORKSPACE:
            return self.get_diff_lines_for_workspace(self.check_file)

    def upload_sonarqube(self):
        '''
        {
        "issues": [
            {
            "engineId":"slg",
            "type":"CODE_SMELL",
            "ruleId": "external_rule",
            "severity": "MAJOR",
            "primaryLocation": {
                "filePath":"main.cpp",
                "message": "this is slg test ",
                "textRange": {
                "startLine": 1,
                "endLine": 1,
                "endColumn": 8
                }
            }
            }
        ]
        }
        sonar-scanner -X  -Dsonar.externalIssuesReportPaths=report.json
        '''
        pass

    def get_last_commit_messages(self):
        '''
        return last commit message
        '''
        last_commit_messages = self.api_init.get_edit_commit_message()
        return last_commit_messages

    def get_last_commit_owner(self):
        '''
        return owner 
        '''
        last_commit_owner = self.api_init.get_current_author()
        return last_commit_owner


    def get_file_size(self):
        '''
        get change file size
        return such as:
        {
            "a.py":{
                "size":"1024000"
            }
        }
        '''
        result = {}
        result = self.api_init.get_changed_file_size()
        return result


    def get_lfs_status(self,file_path):
        flag = self.api_init.get_lfs_status(file_path)
        return flag

    def get_file_content(self, file_path ,left):
        '''
        get file content
        '''
        content = self.api_init.get_change_file_content(file_path, left = left)
        return content

class QualityCodexCommitee():
    def __init__(self):
        super().__init__()

    def FormatOutput(check_type):
        print(80 * "=")
        print(SAST_ITENS_DICT[check_type]["id"] + ": " + check_type)
        print("Quality Gate Spec:")
        print(80 * "=")

    def CommiteeRemind():
        msg =  " If you have any concern, please contact Codex Commitee | Quality Commitee. \
                \n   Codex: -->                              \
                \n Quality: --> "
        print(CYELLOW)
        print(80 * "=")
        print(msg)
        print(80 * "=")
        print(CEND)

    def FormatOutputSimple(check_name, result ,check_id, checked_files ,no_pass_tag = "Fail",cols = 120):
        if checked_files:
            checked_files_msg = ""
            pass_or_fail_msg = CGREEN+"Pass"+CEND if result else CRED+no_pass_tag+CRED
            pass_or_fail = "Pass" if result else no_pass_tag
        else:
            checked_files_msg = "(no files to check)"
            pass_or_fail_msg = CYELLOW+"Skip"+CEND
            pass_or_fail = "Skip"
        msg = str(check_id) + ":"+check_name  + "." * (cols - len(check_name) -len(check_id)- len(pass_or_fail) - len(checked_files_msg) -1 ) + checked_files_msg + pass_or_fail_msg
        print(msg)

class CICheckerCommon():
    def __init__(self,api_init = None, args = None, check_api_type = None, check_name = None, static_check = StaticCheck) -> None:
        # Use the proxy pattern instead of inheritance, so that caching can be utilized
        self.static_check = static_check(api_init, args, check_api_type)
        self.check_name = check_name
        if getattr(args, "config_path", ""):
            sast_config = CommonUtil().load_json(args.config_path).get("sast_items_dict")
        else:
            sast_config = SAST_ITENS_DICT
        for property in sast_config.get(check_name):
            setattr(self, property, sast_config.get(self.check_name).get(property))

    def check(self):
        try:
            captured_output = StringIO()
            with redirect_stdout(captured_output):
                if not self.ignore_checker(self.check_name, self.ignore_admin):
                    self.check_func()
                else:
                    cols = 120
                    pass_word = CYELLOW + "Ignore" + CEND
                    ignore_word = "(ignore)"
                    msg = str(self.id) + ":"+self.check_name  + "." * (cols - len(self.check_name) -len(self.id)- len(pass_word) - len(ignore_word) -1 ) + ignore_word + pass_word
                    print(msg)
        finally:
            sys.stdout = sys.__stdout__
            captured_output.seek(0)
            content = captured_output.read().strip()
            print(content)

    def __getattr__(self, item):
        '''
        If the attribute is not found in the current class, it will be found in the StaticCheck class.
        '''
        if getattr(self.static_check, "cache", None):
            return getattr(self.static_check.cache, item)
        return getattr(self.static_check, item)

    def get_filepaths(self, top, exclude_hidden_files = False):
        filepaths = []
        if exclude_hidden_files:
            for root, dirs, files in os.walk(top):
                for file in files:
                    if not file[0] == '.':
                        path = os.path.join(root, file)
                        filepaths.append(path)
                dirs[:] = [d for d in dirs if not d[0] == '.']
        else:
            for root, dirs, files in os.walk(top):
                for file in files:
                    path = os.path.join(root, file)
                    filepaths.append(path)
        return filepaths

    def remove_cpp_comments(self, content):
        """
        Remove C/C++ style comments from the given content.
        
        Args:
            content (str): The source code content
            
        Returns:
            str: Content with comments removed
        """
        lines = content.split('\n')
        result_lines = []
        in_multiline_comment = False
        
        for line in lines:
            processed_line = line
            original_line = line
            
            # Handle multi-line comments first
            if in_multiline_comment:
                # Look for end of multi-line comment
                end_pos = processed_line.find('*/')
                if end_pos != -1:
                    # Found end of comment, keep everything after */
                    processed_line = processed_line[end_pos + 2:]
                    in_multiline_comment = False
                else:
                    # Still in comment, make entire line empty if it was only comment/whitespace
                    if original_line.strip().startswith('*') or original_line.strip() == '':
                        processed_line = ''
                    else:
                        processed_line = ''
            
            # Look for start of multi-line comment
            if not in_multiline_comment:
                start_pos = processed_line.find('/*')
                while start_pos != -1:
                    # Found start of multi-line comment
                    end_pos = processed_line.find('*/', start_pos + 2)
                    if end_pos != -1:
                        # Comment ends on same line
                        processed_line = processed_line[:start_pos] + processed_line[end_pos + 2:]
                    else:
                        # Comment continues to next line
                        processed_line = processed_line[:start_pos]
                        in_multiline_comment = True
                        break
                    # Look for more comments on the same line
                    start_pos = processed_line.find('/*', start_pos)
            
            # Handle single-line comments if not in multi-line comment
            if not in_multiline_comment:
                comment_pos = processed_line.find('//')
                if comment_pos != -1:
                    # Found single-line comment
                    processed_line = processed_line[:comment_pos]
            
            # Check if the entire original line was only comments/whitespace
            if original_line.strip() and not processed_line.strip():
                # Original line had content but after removing comments it's empty
                # This means the entire line was comments, make it an empty line
                result_lines.append('')
            else:
                # Either line had code content remaining, or was originally empty
                result_lines.append(processed_line.rstrip())
        
        return '\n'.join(result_lines)