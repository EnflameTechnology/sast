#!/usr/bin/env python3
#
# Copyright 2025 Enflame. All Rights Reserved.
#

import subprocess
import os
import argparse
import re
import sys
import json
from datetime import datetime
from pprint import pprint
from pathlib import Path
import xml.dom.minidom
CHECKERS_DIR = Path(__file__).resolve().parent
# Get the parent directory (workspace root)
REPO_DIR = CHECKERS_DIR.parent
# Add the workspace root to Python path
sys.path.append(str(REPO_DIR))
from common.static_check_common import QualityCodexCommitee,CICheckerCommon,StaticCheck
from common.config_parser import *

def excepthook(exctype, value, traceback):
    if exctype == AssertionError:
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)

sys.excepthook = excepthook

class CIChecker(CICheckerCommon):

    def __init__(self, api_init = None, args = None, check_api_type = None, static_check = StaticCheck):
        self.check_name = "hardcode check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.files_static_check_status = {}
        self.command_output = {}
        self.local_workspace_check = True
    
    def is_skipped_files(self, file_path, check_file_regx):
        skip_flag = False
        if not any([file_path.endswith(x) for x in self.suffix]):
            skip_flag = True
            return skip_flag
        for skip_mode in self.skip_files:
            if re.findall(skip_mode,file_path):
                skip_flag = True
                break
        if check_file_regx:
            skip_flag = True
            for check_regex in check_file_regx:
                if re.findall(check_regex.strip(), file_path):
                    skip_flag = False
                    break
        return skip_flag
    
    def grep_hardcode(self, text):
        result = []
        absolute_path_pattern = r'("|\')(/[^"\'\s#]+)(?:"|\')'
        matches = re.findall(absolute_path_pattern, text)
        if matches:
            absolute_paths = [match[1] for match in matches]
            for aboslute_path in absolute_paths:
                if any([re.findall(x,aboslute_path) for x in self.hardcode_list]):
                    result.append(aboslute_path)
        return result

    def check_func(self):
        check_file_regx = []
        if os.path.isfile(self.repo_config_file):
            with open(self.repo_config_file, "r") as f:
                check_file_regx = f.readlines()
        for file_path in self.add_or_changed_files:
            if self.is_skipped_files(file_path, check_file_regx):
                continue
            self.files_static_check_status[file_path] = {"check_status":True}
        if self.files_static_check_status:
            self.diff_info = self.get_diff_info()
        for unchecked_file in self.files_static_check_status.keys():
            self.command_output[unchecked_file] = ""
            for line in self.diff_info.get(unchecked_file,{}).get("add",[]):
                if unchecked_file.endswith(".py") or unchecked_file.endswith(".sh"):
                    if line[1].strip().startswith("#"):
                        continue
                if any(unchecked_file.endswith(x) for x in [".hpp", ".h", ".cc", ".cpp", ".c",".go",".java"]):
                    if line[1].strip().startswith("//"):
                        continue
                hardcode = self.grep_hardcode(line[1])
                if hardcode:
                    self.files_static_check_status[unchecked_file]["check_status"] = False
                    self.pass_flag = False
                    self.command_output[unchecked_file] +=  "{}:{}:hardcode found, {} \n".format(unchecked_file,line[0],",".join(hardcode))

        return self.check_report()
    
    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status,CHECK_LEVEL)

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
            print("\tPlease avoid to use hardcode in code !")
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)

if __name__ == "__main__":
    checker = CIChecker()
    checker.check()
