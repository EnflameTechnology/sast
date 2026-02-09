#!/usr/bin/env python3
#
# Copyright 2022-2025 Enflame. All Rights Reserved.
#
# Version 1.0.0
# Date 2025年8月19日

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
import importlib
REPO_DIR = Path(sys.argv[0]).resolve().parent
sys.path.append(str(REPO_DIR / 'common'))
sys.path.append(str('{}/sast'.format(REPO_DIR)))
sys.path.append('{}/checkers'.format(REPO_DIR))
from common import localgit
import time
import codecs

from common.config_parser import DIFF_TYPE_INCREMENT,DIFF_TYPE_FULL,DIFF_TYPE_WORKSPACE, CHECKS_GROUP

try:
    import requests
except ImportError as e:
    ORANGE = '\033[38;5;172m'
    RED = '\033[31m'
    ENDC = '\033[0m'
    print(RED+str(e)+ENDC)
    matchObj = re.match( r'No module named \'(.*)\'', str(e))
    if matchObj:
        print (RED+"may you install with command:"+ENDC)
        print (ORANGE+"\tpython3 -m pip install {}".format(matchObj.group(1))+ENDC)
    exit(1)



class AllCICheck():
    def __init__(self, api_init, args, check_api_type):
        self.api_init = api_init
        self.args = args
        self.check_api_type = check_api_type

    def fully_check(self):
        exit_flag = 0
        for sast_file in os.listdir("{}/checkers".format(REPO_DIR)):
            if re.match(".*_check.py",sast_file):
                sast_checker = sast_file.replace(".py","")
                module = importlib.import_module(sast_checker)
                if getattr(module, "CIChecker", None):
                    checker = module.CIChecker(self.api_init, self.args, self.check_api_type)
                    if checker.local_ci_check:
                        try:
                            checker.check()
                        except Exception as e:
                            print(sast_checker,e)
                            exit_flag = 1
        sys.exit(exit_flag)

class AllWorkspaceCheck():
    def __init__(self, api_init, args, check_api_type):
        self.api_init = api_init
        self.args = args
        self.check_api_type = check_api_type

    def fully_check(self):
        for sast_file in os.listdir("{}/checkers".format(REPO_DIR)):
            if re.match(".*_check.py",sast_file):
                sast_checker = sast_file.replace(".py","")
                module = importlib.import_module(sast_checker)
                if getattr(module, "CIChecker", None):
                    checker = module.CIChecker(self.api_init, self.args, self.check_api_type)
                    if checker.local_workspace_check:
                        try:
                            checker.check()
                        except Exception as e:
                            pass

class ChecksGroupCheck():
    def __init__(self, api_init, args, check_api_type, checks_group):
        self.api_init = api_init
        self.args = args
        self.check_api_type = check_api_type
        self.checks_group = CHECKS_GROUP.get(checks_group,[])
        if not self.checks_group:
            raise Exception("There is no checks in checks group {}".format(checks_group))

    def fully_check(self):
        exit_flag = 0
        for sast_file in os.listdir("{}/checkers".format(REPO_DIR)):
            if re.match(".*_check.py",sast_file):
                sast_checker = sast_file.replace(".py","")
                if sast_checker not in self.checks_group:
                    continue
                module = importlib.import_module(sast_checker)
                if getattr(module, "CIChecker", None):
                    checker = module.CIChecker(self.api_init, self.args, self.check_api_type)
                    if checker.local_ci_check:
                        try:
                            checker.check()
                        except Exception as e:
                            exit_flag = 1
        sys.exit(exit_flag)

def script_parse_args():
    parser = argparse.ArgumentParser(
        description='script command line interface description')
    parser.add_argument("--all_ci_check", dest="all_ci_check", action='store_true',
                        required=False, help="This option is to do fully ci check.")
    parser.add_argument("--all_workspace_check", dest="all_workspace_check", action='store_true',
                        required=False, help="This option is to do fully workspace check such as check for vscode extension")
    parser.add_argument("--checks_group", dest="checks_group", type=str,
                        required=False, help="Run a set of checks defined in the configuration file")
    parser.add_argument("--api-type",  type=str, dest="api_type",
                        required=False, help="What api you use? localgit.")
    parser.add_argument("--diff-type",  type=str, dest="diff_type",default=DIFF_TYPE_INCREMENT, choices=[DIFF_TYPE_INCREMENT,DIFF_TYPE_FULL,DIFF_TYPE_WORKSPACE],
                        required=False, help="What content you check? increment or full.")
    parser.add_argument("--check-file",  type=str, dest="check_file",
                        required=False, help="What file you check?")
    parser.add_argument("--root-path", type=str, dest="root_path",
                        required=False, help="workspace")
    parser.add_argument("-c", "--config" ,type=str, dest="config_path",
                        required=False, help="config_path")
    for sast_check in os.listdir("{}/checkers".format(REPO_DIR)):
        if re.match(".*_check.py",sast_check):
            sast_check = sast_check.replace(".py","")
            parser.add_argument("--{}".format(sast_check), dest=sast_check, action='store_true',
                    default=False, help='This option is to do {}'.format(sast_check))

    args = parser.parse_args()
    if args.root_path:
        os.chdir(args.root_path)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    return args

def get_project_name_local():
    project_name = ''
    cmd = 'git ls-remote --get-url | xargs basename -s .git'
    pipe = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
    stdout, _stderr = pipe.communicate()
    project_name = stdout
    return project_name.decode('utf-8').strip("\n")

def parse_args_check(args):
    api_init = None
    check_api_type = 'localgit'
    api_init = localgit.Local()

    return check_api_type, api_init

def main():
    args = script_parse_args()

    check_api_type, api_init = parse_args_check(args)
    if args.all_ci_check:
        fully_checker = AllCICheck(api_init, args, check_api_type)
        fully_checker.fully_check()
    elif args.all_workspace_check:
        fully_checker = AllWorkspaceCheck(api_init, args, check_api_type)
        fully_checker.fully_check()
    elif args.checks_group:
        checks_group = ChecksGroupCheck(api_init, args, check_api_type, args.checks_group)
        checks_group.fully_check()
    else:
        exit_flag = 0
        for sast_file in os.listdir("{}/checkers".format(REPO_DIR)):
            if re.match(".*_check.py",sast_file):
                sast_checker = sast_file.replace(".py","")
                if getattr(args, sast_checker):
                    module = importlib.import_module(sast_checker)
                    if getattr(module, "CIChecker", None):
                        checker = module.CIChecker(api_init, args, check_api_type)
                        try:
                            checker.check()
                        except Exception as e:
                            exit_flag = 1
        sys.exit(exit_flag)
                        
if __name__ == '__main__':
    main()
