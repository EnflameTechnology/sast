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
        self.check_name = "file type check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.local_ci_check = False

    def check_func(self):
        if self.add_files:
            for file_path in self.add_files:
                self.files_static_check_status[file_path] = {"check_status":True}
                file_name = file_path.split("/")[-1]
                if  any([ re.match(x, file_name) for x in self.forbidden_file_type_list]):
                    self.pass_flag = False
                    self.files_static_check_status[file_path]["check_status"] = False

        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if not check_status['check_status']:
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"fail"
                })
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
    checker = CIChecker(None,None,None)
    checker.check()