#!/usr/bin/env python3
#
# Copyright 2023-2025 Enflame. All Rights Reserved.
#

import subprocess
import os
import re
import sys
import json
from pathlib import Path

CHECKERS_DIR = Path(__file__).resolve().parent
REPO_DIR = CHECKERS_DIR.parent
sys.path.append(str(REPO_DIR))
from common.static_check_common import QualityCodexCommitee, CICheckerCommon, StaticCheck
from common.config_parser import *


def excepthook(exctype, value, traceback):
    if exctype == AssertionError:
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)


sys.excepthook = excepthook


class CIChecker(CICheckerCommon):
    def __init__(self, api_init=None, args=None, check_api_type=None, static_check=StaticCheck):
        self.check_name = "mypy check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_ci_check = True
        self.local_workspace_check = True
        self.command_output = {}

    def filter_file(self):
        return [
            x for x in self.add_or_changed_files
            if re.match(self.check_files, x) and os.path.isfile(x)
            and not any(re.match(y, x) for y in self.exclude_files)
        ]

    def check_func(self):
        self.check_files_list = self.filter_file()
        if not self.check_files_list:
            return self.check_report()
        self.diff_info = self.get_diff_info()
        for file_path in self.check_files_list:
            self.files_static_check_status[file_path] = {"check_status": True}
            self.command_output[file_path] = ""

        cmd = "mypy --ignore-missing-imports --disable-error-code=import-untyped --show-error-codes {} 2>&1".format(
            " ".join(repr(p) for p in self.check_files_list)
        )
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               shell=True, executable="/bin/bash")
        stdout, _ = pipe.communicate()
        out = stdout.decode('utf-8', errors='ignore')
        # mypy format: file:line: error: message  or  file:line:column: error: message
        for line in out.split("\n"):
            if not line.strip():
                continue
            m = re.match(r"^(.+?):(\d+)(?::(\d+))?:\s*error:", line)
            if m:
                fpath = m.group(1).strip().lstrip("./")
                try:
                    line_number = int(m.group(2))
                except ValueError:
                    continue
                if fpath not in self.files_static_check_status:
                    continue
                add_lines = [x[0] for x in self.diff_info.get(fpath, {}).get("add", [])]
                if (line_number == 0 and fpath in self.add_files) or (line_number and line_number in add_lines):
                    self.files_static_check_status[fpath]["check_status"] = False
                    self.pass_flag = False
                    self.command_output[fpath] = self.command_output.get(fpath, "") + line + "\n"

        return self.check_report()

    def check_report(self):
        QualityCodexCommitee.FormatOutputSimple(
            self.check_name, self.pass_flag, self.id,
            self.files_static_check_status, CHECK_LEVEL
        )
        for file_path, check_status in self.files_static_check_status.items():
            if not check_status['check_status']:
                hook_data_item = {"file": file_path, "message": [], "result": "fail"}
                print("\t" + CRED + CHECK_LEVEL + CEND + ": {}".format(file_path))
                msg = self.command_output.get(file_path, "")
                for one_msg in msg.split("\n"):
                    if one_msg:
                        hook_data_item["message"].append(one_msg)
                        print("\t\t" + one_msg.replace("\n", ""))
                self.hook_data.append(hook_data_item)
            else:
                self.hook_data.append({"file": file_path, "message": [], "result": "pass"})
        if not self.pass_flag:
            print("\tPlease review guide link:{}".format(self.guide_link))
        assert self.pass_flag, "Failed {}".format(self.id)


if __name__ == "__main__":
    checker = CIChecker(None, None, None)
    checker.check()
