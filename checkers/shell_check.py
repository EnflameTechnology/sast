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
        self.check_name = "shell check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.error_file = list()
        self.strict_mode=False
        self.pass_flag_strict=True

    def _shell_file_filter(self):
        for file_path in self.add_or_changed_files:
            # only in the scope for scripts/code_format_check_list which will be checked:
            if file_path.endswith(self.end_filter) and not file_path.startswith(self.start_filter):
                self.files_static_check_status[file_path] = {"check_status":True}
                self.files_static_check_status[file_path]['command_output']=""

    def _ignore_strict_check(self,file_path):
        for path in self.shell_strict_mode_check['ignoreshellstrictmodecheckPath']:
            if file_path.startswith(path):
                return True
        if file_path in self.shell_strict_mode_check['ignoreshellstrictmodecheck']:
            return True      
        return False

    def shell_check(self):
        if self.add_or_changed_files:
            self._shell_file_filter()
            self.diff_info = self.get_diff_info()
        for unchecked_file in self.files_static_check_status:
            pipe_shell_check = subprocess.Popen("shellcheck --severity=error {}".format(unchecked_file),stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
            stdout, _stderr = pipe_shell_check.communicate()
            out=stdout.decode('utf-8', errors="ignore").rsplit('\n')
            if pipe_shell_check.returncode:
                add_lines_number = [x[0] for x in self.diff_info.get(unchecked_file,{}).get("add",[])]
                new_line=False
                for line in out:
                    # returncode not zero which means code have lint errors
                    # False means failed to pass which code have lint errors
                    rets=re.findall(r'In\s.*\sline\s(\d+):',line)
                    if rets:
                        new_line=False
                        line_number = int(rets[0])
                        if line_number and line_number in add_lines_number:
                            new_line=True
                            self.pass_flag = False
                            self.files_static_check_status[unchecked_file]["check_status"] = False
                            self.files_static_check_status[unchecked_file]['command_output'] +="\n"+line
                    elif new_line:
                        self.files_static_check_status[unchecked_file]['command_output'] +="\n"+line
                    else:
                        continue

    def shell_strict_check(self):
        for unchecked_file in self.files_static_check_status:
            if not self._ignore_strict_check(unchecked_file):
                self.strict_mode=True
                self.files_static_check_status[unchecked_file]['need_shell_strict_check'] = True
                self.files_static_check_status[unchecked_file]['shell_strict_check_status'] = True
                if 'need_shell_strict_check' in self.files_static_check_status[unchecked_file].keys() and self.files_static_check_status[unchecked_file]['need_shell_strict_check']:
                    command  = "echo {} | xargs egrep -l '^((#!((\/usr\/bin\/env\s)|(\/bin\/))bash)|\s*set)\s(\s?\-?[abfhkmnptuvxBCEHPT]*e[abfhkmnptuvxBCEHPT]*)' \
                                | xargs egrep -l  '^((#!((\/usr\/bin\/env\s)|(\/bin\/))bash)|\s*set)\s(\s?\-?[abefhkmnptvxBCEHPT]*u[abefhkmnptvxBCEHPT]*)' \
                                | xargs egrep -l '^\s*set.*o pipefail'".format(unchecked_file)

                    pipe_shell_strict_check = subprocess.run(command,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf-8")
                    # current code function well
                    # True means pass which code is clean
                    self.files_static_check_status[unchecked_file]["shell_strict_check_status"] = True
                    if pipe_shell_strict_check.returncode != 0:
                        # Any bash or shell script that does not use 'set-eu-o pipefail' will fail
                        self.files_static_check_status[unchecked_file]["shell_strict_check_status"] = False
                        self.pass_flag_strict = False
                        self.error_file.append(unchecked_file)
        return self.check_report()

    def check_func(self):
        self.shell_check()
        self.shell_strict_check()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, self.files_static_check_status, CHECK_LEVEL)
        # each file summary check result print
        for file_path, check_status in self.files_static_check_status.items():
            if check_status["check_status"]:
                self.hook_data.append({
                    "file":file_path,
                    "message":[],
                    "result":"pass"
                })
                print("\t"+CGREEN + "Pass" + CEND + ": {}".format(file_path))
            else:
                self.hook_data.append({
                    "file":file_path,
                    "message":[self.files_static_check_status[file_path]['command_output']],
                    "result":"fail"
                })
                print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                # failed detailed description
                print("{}".format(self.files_static_check_status[file_path]['command_output']))
        if not self.pass_flag:
            print("\tPlease review guide link:{}\n".format(self.guide_link))

        QualityCodexCommitee.FormatOutputSimple('shell_strict_mode_check',self.pass_flag_strict,self.shell_strict_mode_check['id'], self.error_file)
        for file_path, check_status in self.files_static_check_status.items():
            if 'need_shell_strict_check' in check_status.keys() and check_status['need_shell_strict_check']:
                if check_status["shell_strict_check_status"]:
                    self.hook_data.append({
                        "file":file_path,
                        "message":[],
                        "result":"pass"
                    })
                    print("\t"+CGREEN + "Pass" + CEND + ": {}".format(file_path))
                else:
                    self.hook_data.append({
                        "file":file_path,
                        "message":[],
                        "result":"fail"
                    })
                    print("\t"+CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                    # failed detailed description      
        if self.error_file:
            for file_path in self.error_file:
                self.hook_data.append({
                    "file":file_path,
                    "message":["\nIn {}: \ndid not use 'set -eu -o pipefail' in file header;".format(file_path)],
                    "result":"fail"
                })
                print("\nIn {}: \ndid not use 'set -eu -o pipefail' in file header;".format(file_path))
            print("\n\tPlease review guide link:{}\n".format(self.shell_strict_mode_check['guide_link']))
    
        assert self.pass_flag, "Failed {}".format(self.id)



if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()