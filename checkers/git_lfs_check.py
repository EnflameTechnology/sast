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

    def __init__(self, api_init =None, args = None , check_api_type = None , static_check = StaticCheck):
        self.check_name = "git lfs check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.local_ci_check = False

    def get_lfs_file_list(self):
        check_files = [ x for x in self.add_or_changed_files if any([x.endswith(y) for y in self.need_lfs_list])]
        return check_files

    def get_gitattributes_list(self):
        gitattributes_list = []
        if os.path.isfile(self.attributes_file):
            with open(self.attributes_file, mode='r', encoding='utf-8',errors="ignore") as f:
                gitattributes_list = f.readlines()
        return gitattributes_list

    def check_func(self):
        if self.add_or_changed_files:
            self.gitattributes_list = self.get_gitattributes_list()
            for file_path in self.add_or_changed_files:
                self.files_static_check_status[file_path] = {"check_status":True}
                if self.attributes_file in file_path:
                    if file_path != self.attributes_file:
                        self.pass_flag = False
                        self.files_static_check_status[file_path] = {"check_status":False,"check_msg":".gitattributes file should be in root dir , please do not commit .gitattributes in subdir."}
                    else:
                        self.diff_info = self.get_diff_info()
                        for add_line_item in self.diff_info.get(self.attributes_file,{}).get("add",[]):
                            add_line = add_line_item[1]
                            if add_line == "" :
                                continue
                            add_lines = add_line.split(' ')
                            addpath = os.path.dirname(add_lines[0])
                            filename = add_lines[0].replace(addpath,'').replace('/','')
                            if "." in filename :
                                fixname = filename.split('.')
                                extension = fixname[-1]
                                typename = "*." + extension
                                if fixname[0] != '*':
                                    replace_line = add_line.replace(filename,typename)
                                    if not any([replace_line.strip() == x.strip() for x in self.gitattributes_list]):
                                        self.pass_flag = False
                                        self.files_static_check_status[file_path]["check_status"] = False
                                        if self.files_static_check_status.get(file_path,{}).get("check_msg",""):
                                            self.files_static_check_status[file_path]["check_msg"] =  self.files_static_check_status.get(file_path,{}).get("check_msg","") + "\n\t\t" + add_line + CRED + " should be " + replace_line + CEND
                                        else:
                                            self.files_static_check_status[file_path]["check_msg"] =  add_line + CRED + " should be " + replace_line + CEND
                            else:
                                extension = ""
                                typename ="*"
                            right_line = add_line.replace(filename,typename)
                            if add_line == right_line:
                                continue
                            for line in self.gitattributes_list:
                                if line.strip() == right_line.strip():
                                    self.pass_flag = False
                                    self.files_static_check_status[file_path]["check_status"] = False
                                    if self.files_static_check_status.get(file_path,{}).get("check_msg",""):
                                        self.files_static_check_status[file_path]["check_msg"] = self.files_static_check_status.get(file_path,{}).get("check_msg","")  + "\n\t\t" + add_line + CRED + " is unnecessary! you should delete this line." + CEND
                                    else:
                                        self.files_static_check_status[file_path]["check_msg"] = add_line + CRED + " is unnecessary! you should delete this line." + CEND
                                    break
        self.check_files = self.get_lfs_file_list()
        if self.check_files:
            self.diff_info = self.get_diff_info()
            total_lfs_size = 0
            for check_file in self.check_files:
                if not self.get_lfs_status(check_file) and not os.path.islink(check_file):
                    self.pass_flag = False
                    self.files_static_check_status[check_file] = {"check_status":False,"check_msg":"Those types of file are not allowed push to this repo. Please push these files to lfs"}
                else:
                    add_lines = [ x[1] for x in self.diff_info.get(check_file,{}).get("add",[]) ]
                    for add_line in add_lines:
                        ret = re.findall("size\s+(\d+)",add_line)
                        if ret:
                            total_lfs_size += int(ret[0])
                            if int(ret[0]) > self.file_size_limit:
                                self.files_static_check_status[check_file] = {"check_status":False,"check_msg":"The max size of single lfs file is 50M, this file shouldn't push to git"}
                                self.pass_flag = False
            if total_lfs_size > self.total_size_limit:
                self.files_static_check_status["patch"] = {"check_status":False,"check_msg":"Total size of the patch lfs files must be less than 200Mb."}
                self.pass_flag = False
        if self.lfs_config_path in self.add_or_changed_files and os.path.isfile(self.lfs_config_path):
            flag = False
            with open(self.lfs_config_path, mode='r', encoding='utf-8',errors="ignore") as f:
                lfs_config = f.read()
                if re.findall("\[remote\s+\"origin\"\]\n\s*lfsurl\s*=",lfs_config,re.S):
                    flag = True
            if not flag:
                self.files_static_check_status[self.lfs_config_path] = {"check_status":False,"check_msg":"lfs config file should be format like lfs server:{}".format(self.lfsconfig_sample)}
                self.pass_flag = False
        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if not check_status['check_status']:
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"fail"
                })
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                print("\t\t{}".format(check_status['check_msg']))
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