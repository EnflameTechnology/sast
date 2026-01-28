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
from datetime import datetime
from pprint import pprint
from pathlib import Path
from xml.dom.minidom import parse
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

    def __init__(self, api_init = None, args = None, check_api_type = None):
        self.check_name = "cpplint check"
        super().__init__(api_init, args, check_api_type, self.check_name)
        self.files_static_check_status = {}
        self.local_workspace_check = True
        self.command_output = {}
    
    def is_skipped_files(self, file_path, check_file_regx):
        skip_flag = False
        if not any([file_path.endswith(x) for x in self.suffix]):
            skip_flag = True
            return skip_flag
        for skip_mode in self.skip_files:
            if re.findall(skip_mode,file_path):
                skip_flag = True
                return skip_flag
        if check_file_regx:
            skip_flag = True
            for check_regex in check_file_regx:
                if re.findall(check_regex.strip(), file_path):
                    skip_flag = False
                    break
        return skip_flag

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
            cmd = "python3 -W ignore {}/cpplint.py --filter=-whitespace/indent,-whitespace/comments {}".format(self.tools_path, unchecked_file)
            pipe = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
            stdout, _stderr = pipe.communicate()
            self.command_output[unchecked_file] = "\n"
            add_lines_number = [x[0] for x in self.diff_info.get(unchecked_file,{}).get("add",[])]
            for line in stdout.decode('utf-8',errors="ignore").split("\n"):
                rets = re.findall(":(\d+):",line)
                if rets:
                    line_number = int(rets[0])
                    if (line_number == 0 and unchecked_file in self.add_files ) or line_number in add_lines_number:
                        self.files_static_check_status[unchecked_file]["check_status"] = False
                        self.pass_flag = False
                        self.command_output[unchecked_file] +=  line + "\n"

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
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)

if __name__ == "__main__":
    checker = CIChecker()
    checker.check()