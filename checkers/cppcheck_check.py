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
        self.check_name = "cppcheck"
        super().__init__(api_init, args, check_api_type, self.check_name)
        self.cppcheck_suppressions_list_file = '{}/config/cppcheck_suppressions_list'.format(REPO_DIR)
        self.command_output = {}

    def is_skipped_files(self, file_path):
        skip_flag = False
        for skip_mode in self.skip_files:
            if re.findall(skip_mode,file_path):
                skip_flag = True
                break
        if not any([file_path.endswith(x) for x in self.suffix]):
            skip_flag = True
        return skip_flag

    def check_func(self):
        for file_path in self.add_or_changed_files:
            if self.is_skipped_files(file_path):
                continue
            self.files_static_check_status[file_path] = {"check_status":True}
        if self.files_static_check_status:
            self.diff_info = self.get_diff_info()
        else:
            return self.check_report()
        add_file_list = ''
        modify_file_list = ''
        file_list = ''
        this_flag = True
        for file_path in self.files_static_check_status.keys():
            # if file_path in self.add_files:
            #     add_file_list += ' ./{}'.format(file_path)
            # else:
            #     modify_file_list += ' ./{}'.format(file_path)
            file_list += ' ./{}'.format(file_path)
        cppcheck_cmd = 'cppcheck --xml --xml-version=2 --suppressions-list={} --output-file={} --file-list={}'.format(self.cppcheck_suppressions_list_file, self.cppcheck_result_file, file_list)
        pipe = subprocess.Popen(cppcheck_cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        stdout, _stderr = pipe.communicate()
        DOMTree = xml.dom.minidom.parse(self.cppcheck_result_file)
        results = DOMTree.documentElement
        errors = results.getElementsByTagName("errors")[0]
        error_list = errors.getElementsByTagName("error")
        for error in error_list:
            remove_flag = True
            error_file_locations = error.getElementsByTagName("location")
            for error_file_location in error_file_locations:
                error_file_path = error_file_location.getAttribute("file")
                error_file_line_number = error_file_location.getAttribute("line")
                add_lines_number = [x[0] for x in self.diff_info.get(error_file_path,{}).get("add",[])]
                if int(error_file_line_number) in add_lines_number:
                    remove_flag = False
                    this_flag = False
            if remove_flag:
                errors.removeChild(error)
        if not this_flag:
            self.pass_flag = False
            with open(self.cppcheck_result_file,"w") as f:
                DOMTree.writexml(f,encoding="utf-8")
            DOMTree = xml.dom.minidom.parse(self.cppcheck_result_file)
            results = DOMTree.documentElement
            errors = results.getElementsByTagName("errors")[0]
            error_list = errors.getElementsByTagName("error")
            error_file_name_list = ""
            error_file_name_output_file = "cppcheck_error_file_list"
            for error in error_list:
                error_file_name = error.getElementsByTagName("location")[0].getAttribute('file')
                error_file_line_number = error.getElementsByTagName("location")[0].getAttribute('line')
                error_file_name_list += '{},'.format(error_file_name)
                self.files_static_check_status[error_file_name]["check_status"] = False
                self.command_output[error_file_name] = "line {},{}".format(error_file_line_number,error.getAttribute("msg"))
            error_file_name_list = error_file_name_list[:-1]
            with open(error_file_name_output_file, mode='w', encoding='utf-8') as f:
                f.write(error_file_name_list)

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
            print("\tPlease review guide link:{}".format(self.guide_link))

        assert self.pass_flag, "Failed {}".format(self.id)