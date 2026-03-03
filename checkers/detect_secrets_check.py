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


def _norm_path(path):
    return path.lstrip("./").replace("//", "/") if path else path


class CIChecker(CICheckerCommon):
    def __init__(self, api_init=None, args=None, check_api_type=None, static_check=StaticCheck):
        self.check_name = "detect-secrets check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_ci_check = True
        self.local_workspace_check = True
        self.command_output = {}

    def check_func(self):
        if not self.add_or_changed_files:
            return self.check_report()
        self.diff_info = self.get_diff_info()
        for file_path in self.add_or_changed_files:
            if not os.path.isfile(file_path):
                continue
            self.files_static_check_status[file_path] = {"check_status": True}
            self.command_output[file_path] = ""

        files_arg = " ".join(repr(p) for p in self.add_or_changed_files if os.path.isfile(p))
        if not files_arg:
            return self.check_report()
        cmd = "detect-secrets scan {} 2>/dev/null".format(files_arg)
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               shell=True, executable="/bin/bash")
        stdout, _ = pipe.communicate()
        out = stdout.decode('utf-8', errors='ignore').strip()
        if not out:
            return self.check_report()
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return self.check_report()
        results = data.get("results", {})
        for fpath, secrets in results.items():
            fpath_norm = _norm_path(fpath)
            if fpath_norm not in self.files_static_check_status:
                continue
            add_lines = [x[0] for x in self.diff_info.get(fpath_norm, {}).get("add", [])]
            for s in secrets:
                if not isinstance(s, dict):
                    continue
                line_number = s.get("line_number")
                if line_number is None:
                    line_number = s.get("line")
                if (line_number == 0 and fpath_norm in self.add_files) or (line_number and line_number in add_lines):
                    self.files_static_check_status[fpath_norm]["check_status"] = False
                    self.pass_flag = False
                    msg = "{}:{}: potential secret (type: {})".format(
                        fpath_norm, line_number, s.get("type", "unknown")
                    )
                    self.command_output[fpath_norm] = self.command_output.get(fpath_norm, "") + msg + "\n"
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
