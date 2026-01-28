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
        self.check_name = "lines check"
        super().__init__(api_init, args, check_api_type, self.check_name)

    def check_func(self):
        self.diff_info = self.get_diff_info()
        self.change_add_lines = 0
        for file_path in self.diff_info:
            if any([re.match(x, file_path) for x in self.check_file_type]) and not any(re.match(x, file_path) for x in self.skip_files):
                self.change_add_lines += len(self.diff_info[file_path]["add"])
        lines_limit = max(self.lines_limit,LINES_LIMIT)
        if self.change_add_lines > lines_limit:
            self.pass_flag = False

        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(self.check_name,self.pass_flag,self.id, True, CHECK_LEVEL)

        if not self.pass_flag:
            print("\tcode size: {}".format(self.change_add_lines))
            lines_limit = max(self.lines_limit,LINES_LIMIT)
            print("\t{}".format(self.error_message.format(lines_limit)))
            print("\tPlease review guide link:{}".format(self.guide_link))
            self.hook_data.append({
                "file":"",
                "message":[self.error_message.format(lines_limit)],
                "result":"fail"
            })

        assert self.pass_flag, "Failed {}".format(self.id)

if __name__ == "__main__":
    checker = CIChecker(None,None,None)
    checker.check()