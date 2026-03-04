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
        self.check_name = "safety check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_ci_check = True
        self.local_workspace_check = True
        self.command_output = {}

    def get_check_files(self):
        return [
            x for x in self.add_or_changed_files
            if any(re.match(r, x) for r in self.check_files_regex) and os.path.isfile(x)
        ]

    def _package_from_line(self, line):
        """Parse package name from requirements line (e.g. 'foo==1.0' or 'foo>=1.0')."""
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            return None
        for sep in ["==", ">=", "<=", ">", "<", "~=", "!="]:
            if sep in line:
                return line.split(sep)[0].strip().lower()
        return line.split()[0].strip().lower() if line else None

    def check_func(self):
        self.check_files_list = self.get_check_files()
        if not self.check_files_list:
            return self.check_report()
        self.diff_info = self.get_diff_info()
        for file_path in self.check_files_list:
            self.files_static_check_status[file_path] = {"check_status": True}
            self.command_output[file_path] = ""

        for req_file in self.check_files_list:
            add_lines_with_num = self.diff_info.get(req_file, {}).get("add", [])
            added_packages = set()
            for line_no, content in add_lines_with_num:
                pkg = self._package_from_line(content)
                if pkg:
                    added_packages.add((line_no, pkg))

            # Build (line_no, pkg) from file so report has correct line numbers (safety JSON has no line numbers)
            file_packages = []
            try:
                with open(req_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        pkg = self._package_from_line(line)
                        if pkg:
                            file_packages.append((line_no, pkg))
            except (OSError, IOError):
                file_packages = list(added_packages)  # fallback to diff line numbers

            if not added_packages:
                continue

            pipe = subprocess.Popen(
                "safety check -r {} --json 2>/dev/null || true".format(repr(req_file)),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash"
            )
            stdout, _ = pipe.communicate()
            out = stdout.decode('utf-8', errors='ignore').strip()
            if not out:
                continue
            # safety output may include banner + DEPRECATED text + JSON; extract JSON only
            start = out.find("{")
            end = out.rfind("}")
            if start < 0 or end <= start:
                continue
            try:
                data = json.loads(out[start : end + 1])
            except json.JSONDecodeError:
                continue
            # safety JSON: list of vuln or {"vulnerabilities": [...]} (safety 3.x uses package_name)
            vulns = data if isinstance(data, list) else data.get("vulnerabilities", data.get("affected_packages", []))
            if not isinstance(vulns, list):
                continue
            added_pkg_names = {pkg for _, pkg in added_packages}
            for v in vulns:
                if isinstance(v, dict):
                    # safety 3.x: package_name; older: package or name
                    pkg_name = (v.get("package_name") or v.get("package") or v.get("name") or "").lower()
                    cve = v.get("CVE") or v.get("cve") or ""
                    advisory = (v.get("advisory") or "").strip().replace("\r", " ").replace("\n", " ")
                else:
                    continue
                # Only fail when this vulnerable package was newly added (in diff)
                if not any(pkg in pkg_name or pkg_name in pkg for pkg in added_pkg_names):
                    continue
                self.files_static_check_status[req_file]["check_status"] = False
                self.pass_flag = False
                # Report with line numbers from file (safety JSON has no line numbers)
                for line_no, pkg in file_packages:
                    if pkg in pkg_name or pkg_name in pkg:
                        msg = "{}:{}: vulnerable package '{}'".format(req_file, line_no, pkg_name)
                        if cve:
                            msg += " ({})".format(cve)
                        if advisory:
                            msg += " | advisory: {}".format(advisory[:500] + "..." if len(advisory) > 500 else advisory)
                        msg += "\n"
                        self.command_output[req_file] = self.command_output.get(req_file, "") + msg

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
