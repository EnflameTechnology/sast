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

    def __init__(self, api_init = None, args =None, check_api_type = None, static_check = StaticCheck):
        self.check_name = "gitleaks check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_ci_check = True
        self.command_output = {}
        self.files_static_check_status = {}
        self.error_message = ""
        self.pass_flag = True
        self.local_workspace_check = True

    def check_func(self):
        if self.add_or_changed_files:
            self.diff_info = self.get_diff_info()
            for check_file in self.add_or_changed_files:
                self.files_static_check_status[check_file] = {"check_status": True}
                pipe = subprocess.Popen("gitleaks detect --no-git --source {} --report-format json --report-path leaks.json".format(self.tools_path, check_file),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                stdout, _stderr = pipe.communicate()
                if os.path.isfile("leaks.json"):
                    with open("leaks.json", "r") as f:
                        leaks_data = json.load(f)
                    for leak in leaks_data:
                        if leak["File"] in self.add_or_changed_files:
                            add_lines_number = [x[0] for x in self.diff_info.get(leak["File"],{}).get("add",[])]
                            if leak["StartLine"] in add_lines_number:
                                self.files_static_check_status[leak["File"]]["check_status"] = False
                                self.pass_flag = False
                                if leak["File"] not in self.command_output:
                                    self.command_output[leak["File"]] = "{}:{}:secret {} found, please check it".format(leak["File"], leak["StartLine"], leak["Secret"])
                                else:
                                    self.command_output[leak["File"]] = self.command_output[leak["File"]] + "\n{}:{}:secret {} found, please check it".format(leak["File"], leak["StartLine"], leak["Secret"])
                    os.remove("leaks.json")
        return self.check_report()
    
    def check_report(self):
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

if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()