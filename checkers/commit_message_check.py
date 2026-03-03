#!/usr/bin/env python3
#
# Copyright 2023-2026 Enflame. All Rights Reserved.
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
        self.static_check = static_check(api_init, args, check_api_type)
        self.check_name = "commit message check"
        super().__init__(api_init, args, check_api_type, self.check_name,static_check)
        self.pass_flag = True
        self.local_ci_check = False
        self.fail_message = []

    def check_func(self):
        if any(x in self.commit_author for x in self.bypass_commit_author):
            return self.check_report()
        if re.findall("This reverts commit", self.commit_message):
            return self.check_report()
        #subject = self.commit_message.split("\n")[0]
        #ret=re.findall("\[.*?\]\(.*?\)(.*)",subject)
        # if ret:
        #     check_title = ret[0].strip()
        #     if len(check_title) < 10:
        #         self.pass_flag = False
        #         self.fail_message.append("After removing '[type](jira id)' in the title, the remaining content must have at least 10 valid characters.")
        for template_field in self.template_fields:
            template_field_reg_find = re.findall(template_field + ":\s*\n(.*?)",self.commit_message)
            if not template_field_reg_find:
                self.pass_flag = False
                self.fail_message.append("There must be {},please fill in it".format(template_field))
            # else:
            #     template_field_content = template_field_reg_find[0]
            #     if any([ template_field_content.lower().strip() == x for x in self.forbidden_single_string ]):
            #         self.pass_flag = False
            #         self.fail_message.append("{} cannot be {},please update it ".format(template_field, self.forbidden_single_string))
        return self.check_report()
    

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, True,CHECK_LEVEL)

        # each file summary check result print
        if not self.pass_flag:
            for message in self.fail_message:
                print("\t"+ CRED + CHECK_LEVEL + CEND + ": {}".format(message))

        if not self.pass_flag:
            print("\tDetail info please refer to:" + " {}".format(self.guide_link))
        assert self.pass_flag, "Failed {}".format(self.id)


if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()