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

import sys


def excepthook(exctype, value, traceback):
    if exctype == AssertionError:
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)

sys.excepthook = excepthook   



class CIChecker(CICheckerCommon):
    def __init__(self, api_init = None, args = None, check_api_type =None,static_check = StaticCheck):
        self.check_name = "codespell check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.command_output = {}
        self.local_workspace_check = True
        
    def filter_files(self, file_path):
        if any([file_path.endswith(x) for x in self.check_files_suffix]):
                return True
        return False

    def codespell_check(self):
        if self.add_or_changed_files:
            self.diff_info = self.get_diff_info()
        for unchecked_file in self.add_or_changed_files:
            if not self.filter_files(unchecked_file):
                continue
            self.files_static_check_status[unchecked_file]= {"check_status":True}
            if os.path.isfile(self.default_config):
                config_path = self.default_config
            else:
                config_path = self.remote_config
            command = "python3 {}/codespell.py --config {} {}".format(self.tools_path,config_path,unchecked_file)
            pipe = subprocess.Popen(command,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
            stdout, _stderr = pipe.communicate()
            self.command_output[unchecked_file] = "\n"
            add_lines_number = [x[0] for x in self.diff_info.get(unchecked_file,{}).get("add",[])]
            for line in stdout.decode('utf-8',errors="ignore").split("\n"):
                #print(line)
                rets = re.findall(":(\d+):",line)
                if rets:
                    line_number = int(rets[0])
                    if  line_number in add_lines_number:
                        self.files_static_check_status[unchecked_file]["check_status"] = False
                        self.pass_flag = False
                        self.command_output[unchecked_file] +=  line + " (codespell error)\n"
        return self.check_report()

    def check_func(self):
        if not self.ignore_checker(self.check_name,self.ignore_admin):
            return self.codespell_check()
        else:
            print("ignore {}".format(self.check_name))

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id,self.files_static_check_status,CHECK_LEVEL)

        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if check_status["check_status"]:
                print("\t"+CGREEN + "Pass" + CEND + ": {}".format(file_path))
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"pass"
                })
            else:
                hook_data_item = {
                    "file":file_path,
                    "message":[],
                    "result":"fail"
                }
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                # failed detailed description
                msg = self.command_output[file_path]
                for one_msg in msg.split("\n"):
                    if one_msg:
                        print("\t\t"+one_msg.replace("\n",""))
                        hook_data_item["message"].append(one_msg)
                self.hook_data.append(hook_data_item)
        if not self.pass_flag:
            print("\tDetail info please refer to:" + " {}".format(self.guide_link))
        assert self.pass_flag, "Failed {}".format(self.id)

    def __getattr__(self, item):
        '''
        If the attribute is not found in the current class, it will be found in the StaticCheck class.
        '''
        if getattr(self.static_check, "cache", None):
            return getattr(self.static_check.cache, item)
        return getattr(self.static_check, item)

if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()

