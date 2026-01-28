#!/usr/bin/env python3
#
# Copyright 2023-2025 Enflame. All Rights Reserved.
#
from ntpath import isfile
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
# Get the directory containing this file (common directory)
COMMON_DIR = Path(__file__).resolve().parent
# Get the parent directory (workspace root)
REPO_DIR = COMMON_DIR.parent
import time
import codecs

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

CONFIG_FILE = str(REPO_DIR / 'config/sast.json')
JSON_DICT = dict()

class CommonUtil():
    def __init__(self):
        super().__init__()

    # func to load dict from json file
    def load_json(self, file_path):
        return_dict = dict()
        with open(file_path, mode='r', encoding='utf-8') as json_file:
            return_dict = json.load(json_file)

        return return_dict

JSON_DICT = CommonUtil().load_json(CONFIG_FILE)

custom_config = os.path.join(os.getcwd(),".sast_config.json")

if os.path.isfile(custom_config):
    JSON_DICT.update(CommonUtil().load_json(custom_config))

# all sast items info.
SAST_ITENS_DICT = JSON_DICT.get("sast_items_dict")

CHECKS_GROUP = JSON_DICT.get("checks_group") or {}


API_TYPE_LOCALGIT = "localgit"

DIFF_TYPE_FULL="full"
DIFF_TYPE_INCREMENT = "increment"
DIFF_TYPE_WORKSPACE = "workspace"

GIT_NULL_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

NO_COLOR = os.environ.get('NO_COLOR', 'false')

if NO_COLOR == 'true':
    CRED = ""
    CGREEN = ""
    CBLUE = ""
    CYELLOW = ""
    CLIGHT = ""
    CEND = ""
else:
    CEND    = "\033[0m"
    CRED    = "\033[31m"
    CGREEN  = "\033[32m"
    CBLUE   = "\033[34;01m"
    CYELLOW = "\033[93m"
    CLIGHT = "\033[2m"

SERIALIZED_FILE_NAME = ".static_check_cache"

FILE_CHANGE_TYPE_ADD = "add"
FILE_CHANGE_TYPE_DELETE = "delete"
FILE_CHANGE_TYPE_RENAME = "rename"
FILE_CHANGE_TYPE_MODIFY = "modify"

CHECK_LEVEL=os.getenv("CHECK_LEVEL","Fail")

LINES_LIMIT=int(os.getenv("LINES_LIMIT",2000))

CI_USER = os.getenv("CI_ARTIFACT_username")
CI_PWD = os.getenv("CI_ARTIFACT")