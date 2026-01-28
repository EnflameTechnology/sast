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

    def __init__(self, api_init = None, args = None, check_api_type = None, static_check = StaticCheck):
        self.check_name = "keyword check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_workspace_check = True

    def check_func(self):
        self.diff_info = self.get_diff_info()
        for file_need_check in self.add_or_changed_files:
            if all(item not in file_need_check for item in self.ignore_list):
                self.files_static_check_status[file_need_check] = {"check_status": True}
                self.files_static_check_status[file_need_check]['name_or_email_msg'] = set()
                self.files_static_check_status[file_need_check]['key_word'] = set()
                self.files_static_check_status[file_need_check]['add_string'] = set()
                change_line_list = [x for x in self.diff_info.get(file_need_check, {}).get("add", [])]
                for index,line in change_line_list:
                    for key_word in self.forbidden_string_dict.keys():
                        if key_word in line:
                            check_dirs = self.forbidden_string_dict[key_word].get("check_dirs",[])
                            if not check_dirs:
                                check_flag = True
                            else:
                                check_flag = False
                            for check_dir in check_dirs:
                                if re.findall(check_dir,file_need_check):
                                    check_flag = True
                            if check_flag:
                                self.pass_flag = False
                                self.files_static_check_status[file_need_check]['check_status'] = False
                                self.files_static_check_status[file_need_check]['key_word'].add((index,key_word))
                    check_name_msg = re.findall(self.judge_str,line)
                    if check_name_msg:
                        self.pass_flag = False
                        self.files_static_check_status[file_need_check]['check_status'] = False
                        for i in range(len(check_name_msg)):
                            name_msg = check_name_msg[i][0]
                            self.files_static_check_status[file_need_check]['name_or_email_msg'].add(name_msg)
                add_lines = [x[1] for x in self.diff_info.get(file_need_check, {}).get("add",[]) if  not x[1].lstrip().startswith('#')]
                delete_lines = [x[1] for x in self.diff_info.get(file_need_check, {}).get("del",[]) if  not x[1].lstrip().startswith('#')]
                for keyword in self.forbidden_add_string:
                    del_count = 0
                    add_count = 0
                    if self.forbidden_add_string[keyword].get("repo",[]):
                        if not self.project_name in self.forbidden_add_string[keyword]["repo"]:
                            continue
                    for add_line in add_lines:
                        ret = re.findall(keyword,add_line)
                        add_count += len(ret)
                    for del_line in delete_lines:
                        ret = re.findall(keyword,del_line)
                        del_count += len(ret)
                    if add_count > del_count:
                        self.pass_flag = False
                        self.files_static_check_status[file_need_check]["check_status"] = False
                        self.files_static_check_status[file_need_check]["msg"] = self.files_static_check_status[file_need_check].get("msg","") + "Add '{}' is not allowed!\n".format(keyword)
                        self.files_static_check_status[file_need_check]['add_string'].add(keyword)
                add_line_info = [x for x in self.diff_info.get(file_need_check, {}).get("add",[]) ]
                for check_mode in self.forbidden_string_mode:
                    flag = False
                    for repo in self.forbidden_string_mode[check_mode].get("repo",[]):
                        if re.match(repo,self.project_name):
                            flag = True
                    if flag:
                        for add_line in add_line_info:
                            if re.match(check_mode,add_line[1]):
                                self.pass_flag = False
                                if file_need_check not in self.files_static_check_status:
                                    self.files_static_check_status[file_need_check] = {"check_status":False}
                                else:
                                    self.files_static_check_status[file_need_check]['check_status'] = False
                                msg = file_need_check + ":"+str(add_line[0])+ ":"+self.forbidden_string_mode[check_mode]["msg"]
                                if msg not in self.files_static_check_status[file_need_check].get("msg",""):
                                    self.files_static_check_status[file_need_check]["msg"] = self.files_static_check_status[file_need_check].get("msg","") + "\n\t" + msg

        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)

        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if check_status['check_status']:
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
                msg=""
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                if check_status.get('name_or_email_msg'):
                    for name in check_status['name_or_email_msg']:
                        for name_check in check_status['name_or_email_msg']:
                            if name_check.endswith(name) and name != name_check:
                                check_status['name_or_email_msg'].remove(name)
                if check_status.get('name_or_email_msg'):
                    msg += "\n\tPersonal name or email address are found: {}\n\n".format(CRED + '\n\t' + ('\n\t').join(check_status['name_or_email_msg']) + CEND)
                    hook_data_item["message"].append("\n\tPersonal name or email address are found: {}\n\n".format(CRED + '\n\t' + ('\n\t').join(check_status['name_or_email_msg']) + CEND))
                    msg += "\tReason: The code contains names and email addresses, which expose employee information when the software is released to the outside.\n\n"
                    msg += "\tSuggestion: Disable Personal names and email addresses. Replace them with 'Enflame'\n\n"
                if check_status.get('key_word'):
                    msg += "\n\tThose words are not allowed to appear in newly created files.\n"
                    for index,key_word in check_status['key_word']:
                        msg += "\t{}:{}:'{}' is not allowed to appear in newly created files\n\n".format(file_path,index,key_word)
                        hook_data_item["message"].append("Those words are not allowed to appear in newly created files: {}\n\n".format(CRED+key_word+CEND))
                        msg += "\tReason: {}\n\n".format(self.forbidden_string_dict[key_word]["reason"])
                        msg += "\tSuggestion: {}\n\n".format(self.forbidden_string_dict[key_word]["suggestion"])
                if check_status.get('add_string'):
                    msg += "\n\tThose words are not allowed to add in newly created files.\n"
                    for add_string in check_status['add_string']:
                        msg += "\t{}\n\n".format(add_string)
                        hook_data_item["message"].append("Those words are not allowed to add in newly created files: {}\n\n".format(CRED+add_string+CEND))
                        msg += "\tReason: {}\n\n".format("Add '{}' is not allowed!".format(self.forbidden_add_string[add_string]["reason"]))
                        msg += "\tSuggestion: {}\n\n".format("Delete '{}'".format(self.forbidden_add_string[add_string]["suggestion"]))
                if check_status.get('msg'):
                    msg += "\t{}".format(check_status['msg'])
                    hook_data_item["message"].append("\n\t{}\n\n".format(check_status['msg']))

                self.hook_data.append(hook_data_item)
                print(msg)
        if not self.pass_flag:
            print("\tPlease review guide link:{}".format(self.guide_link))
        assert self.pass_flag, "Failed {}".format(self.id)
        
if __name__ == "__main__":
    checker = CIChecker()
    checker.check()