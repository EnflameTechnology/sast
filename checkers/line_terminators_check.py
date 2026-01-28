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

    def __init__(self, api_init, args, check_api_type):
        self.check_name = "line terminators check"
        super().__init__(api_init, args, check_api_type, self.check_name)
        self.fail_list = []
        
    def check_func(self):
        for filetype in self.lineTerminatorsCheckFileType:
            for file_path in self.add_or_changed_files:
                if file_path.endswith(filetype):
                    out = subprocess.Popen("file {}".format(file_path), shell=True, stdout=subprocess.PIPE).communicate()[0].decode('utf-8',errors="ignore")
                    self.files_static_check_status[file_path]={"check_status":True}
                    self.files_static_check_status[file_path]['file_info']=out
                    if "with CRLF line terminators" in out or "No such file or directory"  in out:
                        self.files_static_check_status[file_path]['check_status']=False
                        self.pass_flag=False
        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, True, CHECK_LEVEL)
        terminators_fail=False
        for file_path, check_status in self.files_static_check_status.items():
            if check_status['check_status']:
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"pass"
                })
                print("\t"+CGREEN + "Pass"+ CEND + " : " + file_path)
            elif "No such file or directory" in check_status['file_info']:
                print("\t"+CRED + CHECK_LEVEL+ CEND + " : " + file_path)
                print("\t"+check_status['file_info'])
                self.hook_data.append({
                    "file":file_path,
                    "message":[check_status['file_info']],
                    "result":"fail"
                })
                assert False,"error file {} No such file or directory, please check.".format(file_path)
            else:
                self.hook_data.append({
                    "file":file_path,
                    "message":[check_status['file_info']],
                    "result":"fail"
                })
                terminators_fail=True
                print("\t"+CRED + CHECK_LEVEL+ CEND + " : " + file_path)
                print("\t"+check_status['file_info'])
        if terminators_fail:
            self.hook_data.append({
                    "file":file_path,
                    "message":["file must be unix style, please check the file."],
                    "result":"fail"
                })
            print("\t"+"file must be unix style, please check the file.")
            print("\tplease run "+CRED+"\"dos2unix FileName\""+CEND+"to resolve this issue.")

        if not self.pass_flag:
            print("\n\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)


if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()