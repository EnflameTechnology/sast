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
    
    def __init__(self, api_init =None , args =None, check_api_type =None ,static_check = StaticCheck):
        self.check_name = "jsonlint check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.local_ci_check = False
        self.command_output = dict()
        self._jsonlint_file_filter()

    def _jsonlint_file_filter(self):
        ignore_file_name = self.ignorejsoncheck
        suffix = ".json"
        file_with_specific_suffix = []
        for file in self.add_or_changed_files:
            if file not in ignore_file_name and file.endswith(suffix):
                file_with_specific_suffix.append(file)
        self.add_or_changed_files = file_with_specific_suffix
        
    def check_func(self):
        def check_json_duplicate_key(key_pair):
            exist_key = []
            result = {}
            for k,v in key_pair:
                #print(k,v)
                if k not in exist_key:
                    exist_key.append(k)
                    #print(exist_key)
                    result[k] = v
                else:
                    raise Exception("duplicate key {}".format(k))
            return result
        if self.add_or_changed_files:
            for file in self.add_or_changed_files:
                self.files_static_check_status[file] = {"check_status":True}
                try:
                    f = open(file,"r",encoding='utf-8')
                    json_file_content = f.read()
                    json.loads(json_file_content, object_pairs_hook=check_json_duplicate_key)
                    self.files_static_check_status[file]["check_status"] = True
                except Exception as e:
                    self.command_output[file] = str(e)
                    self.pass_flag = False
                    self.files_static_check_status[file]["check_status"] = False
                finally:
                    f.close()
        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

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
                msg = self.command_output[file_path]
                for one_msg in msg.split("\n"):
                    if one_msg:
                        print("\t\t"+one_msg.replace("\n",""))
                        hook_data_item["message"].append(one_msg)
                self.hook_data.append(hook_data_item)
        if not self.pass_flag:
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)
        
if __name__ == "__main__":
    checker = CIChecker()
    checker.check()
