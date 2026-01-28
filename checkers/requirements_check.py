#!/usr/bin/env python3
#
# Copyright 2023-2024 Enflame. All Rights Reserved.
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

    def __init__(self, api_init =None, args = None , check_api_type = None , static_check = StaticCheck):
        self.check_name = "requirements check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)

    def get_check_files(self):
        check_files = []
        for file_path in self.add_or_changed_files:
            if any([re.match(x, file_path) for x in self.check_files_regex]):
                check_files.append(file_path)
        return check_files

    def check_func(self):
        check_files = self.get_check_files()
        if check_files:
            self.diff_info = self.get_diff_info()
            for check_file in check_files:
                add_lines = [x[1] for x in self.diff_info.get(check_file,{}).get("add",[])]
                self.files_static_check_status[check_file] = {"check_status":True,"content":[]}
                for add_line in add_lines:
                    if not add_line.strip():
                        continue
                    if any([x for x in self.ignore_list if x in add_line ]):
                        continue
                    if any(self.project_name in self.specific_version_regex[x] for x in self.specific_version_regex):
                        for x in self.specific_version_regex:
                            if self.project_name in self.specific_version_regex[x]:
                                if not re.findall(x,add_line) and not '==' in add_line:
                                    self.pass_flag = False
                                    self.files_static_check_status[check_file]["check_status"] = False
                                    self.files_static_check_status[check_file]["content"].append(add_line)
                                break
                        continue
                    if '==' not in add_line :
                        self.pass_flag = False
                        self.files_static_check_status[check_file]["check_status"] = False
                        self.files_static_check_status[check_file]["content"].append(add_line)
                    elif '==' in add_line and (not add_line.strip().split('==')[1] or not add_line.strip().split('==')[0]):
                        self.pass_flag = False
                        self.files_static_check_status[check_file]["check_status"] = False
                        self.files_static_check_status[check_file]["content"].append(add_line)
                
                        
        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

        # each file summary check result print
        for package, check_status in self.files_static_check_status.items():
            if not check_status['check_status']:
                self.hook_data.append({
                    "file":package,
                    "message":check_status['content'],
                    "result":"fail"
                })
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(package))
                print("\t\t{}".format(",".join(check_status['content'])))
            else:
                self.hook_data.append({
                    "file":package,
                    "message":[],
                    "result":"pass"
                })
        if not self.pass_flag:
            print("\t{}".format(self.message))
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)

if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()