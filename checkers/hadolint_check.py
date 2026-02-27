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
        self.check_name = "hadolint check"
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

        for file_path in self.check_files_list:
            cmd = "hadolint -f json {} 2>/dev/null || true".format(repr(file_path))
            pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   shell=True, executable="/bin/bash")
            stdout, _ = pipe.communicate()
            out = stdout.decode('utf-8', errors='ignore').strip()
            add_lines_number = [x[0] for x in self.diff_info.get(file_path, {}).get("add", [])]
            if not out:
                continue
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                continue
            # hadolint JSON: array of { "line": N, "message": "...", "code": "..." } or similar
            if isinstance(data, list):
                issues = data
            elif isinstance(data, dict):
                issues = data.get("", data.get("result", []))
                if not isinstance(issues, list):
                    issues = []
            else:
                issues = []
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                line_number = issue.get("line") or issue.get("lineNumber") or issue.get("startLine")
                if line_number is None:
                    continue
                try:
                    line_number = int(line_number)
                except (ValueError, TypeError):
                    continue
                if (line_number == 0 and file_path in self.add_files) or (line_number in add_lines_number):
                    self.files_static_check_status[file_path]["check_status"] = False
                    self.pass_flag = False
                    msg = "{}:{}: {} [{}]".format(
                        file_path, line_number,
                        issue.get("message", issue.get("description", "")),
                        issue.get("code", "")
                    )
                    self.command_output[file_path] = self.command_output.get(file_path, "") + msg + "\n"

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
