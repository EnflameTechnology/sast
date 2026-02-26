#!/usr/bin/env python3
#
# Copyright 2026 Enflame. All Rights Reserved.
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

CONFIG_PATH = REPO_DIR / 'config' / 'sast.json'

class CIChecker(CICheckerCommon):
    def __init__(self, api_init=None, args=None, check_api_type=None, static_check=StaticCheck):
        self.check_name = "external tools check"
        super().__init__(api_init, args, check_api_type, self.check_name, static_check)
        self.local_ci_check = True
        self.local_workspace_check = True
        self.pass_flag = True
        self.files_static_check_status = {}
        self.command_output = {}

    def _load_tools(self):
        try:
            with open(CONFIG_PATH, 'r') as f:
                cfg = json.load(f)
            return cfg.get('external_tools', [])
        except Exception:
            return []

    def check_func(self):
        tools = self._load_tools()
        # run each configured tool command; commands should be shell commands (bash)
        for tool in tools:
            name = tool.get('name')
            cmd = tool.get('command')
            guide = tool.get('guide_link','')
            if not cmd or not name:
                continue
            print("Running {}: {}".format(name, cmd))
            pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable='/bin/bash')
            stdout, _ = pipe.communicate()
            out = stdout.decode('utf-8', errors='ignore') if stdout else ''
            ret = pipe.returncode
            if ret != 0:
                self.pass_flag = False
                self.command_output[name] = out
            else:
                # still capture output for information
                self.command_output[name] = out

        return self.check_report()

    def check_report(self):
        # Prepare a synthetic files_static_check_status entry to integrate with existing output format
        self.files_static_check_status['external_tools'] = {"check_status": self.pass_flag}
        QualityCodexCommitee.FormatOutputSimple(self.check_name, self.pass_flag, self.id, self.files_static_check_status, CHECK_LEVEL)

        # Print outputs for failed tools
        for tool_name, output in self.command_output.items():
            if output:
                print('\t=== {} output ==='.format(tool_name))
                for line in output.splitlines():
                    print('\t\t' + line)

        if not self.pass_flag:
            print('\tPlease review guide links in config/sast.json for remediation.')
        assert self.pass_flag, "Failed {}".format(self.id)

if __name__ == '__main__':
    c = CIChecker(None, None, None)
    c.check()
