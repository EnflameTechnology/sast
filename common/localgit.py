#!/usr/bin/env python3
#
# Copyright 2022-2025 Enflame. All Rights Reserved.
#

import subprocess
import re
import json
import os

class Local(object):
    def __init__(self, root_dir="./"):
        self.root_dir = root_dir

    def get_diff(self, revision1="HEAD~", revision2="HEAD"):
        '''
        Get changed lines information
        return:
        {
            "common_util/util_func.groovy": {
                "add":[(6822,"def epkgVerify1")],
                "del":[(6822,"def epkgVerify2")]
            }
        }
        '''
        result = {}
        del_lines = []
        add_lines = []
        try:
            if "{}~".format(revision2) ==  revision1 or "{}^".format(revision2) ==  revision1:
                output=subprocess.check_output("cd {root_dir};git show --no-commit-id {revision2}".format(root_dir=self.root_dir,revision2=revision2),shell=True)
            else:
                output=subprocess.check_output("cd {root_dir};git diff {revision1} {revision2}".format(root_dir=self.root_dir, revision1=revision1,revision2=revision2),shell=True)
            status = 0
        except Exception as e:
            print(e)
            status = 1
        if status == 0:
            flag = False
            git_diff_lines = output.decode("utf-8",errors="ignore").split("\n")
            for index,line in enumerate(git_diff_lines):
                if not flag and re.findall("diff --git a/.* b/.*",line):
                    flag = True
                    continue
                if not flag:
                    continue
                ret1 = re.findall("\+\+\+\s+b/(.*)",line)
                if ret1:
                    file_path = ret1[0]
                    ret_ = re.findall("---\s+/dev/null",git_diff_lines[index-1])
                    if ret_:
                        result[file_path] = {"add":[],"del":[],"type":"add","old_path":""}
                    else:
                        old_path_ret= re.findall("---\s+a/(.*)",git_diff_lines[index-1])
                        old_path = old_path_ret[0]
                        if old_path == file_path:
                            result[file_path] = {"add":[],"del":[],"type":"modify","old_path":old_path}
                        else:
                            result[file_path] = {"add":[],"del":[],"type":"rename","old_path":old_path}
                ret1 = re.findall("\+\+\+\s+/dev/null",line)
                if ret1:
                    ret3 = re.findall("---\s+a/(.*)",git_diff_lines[index-1])
                    if ret3:
                        file_path = ret3[0]
                        result[file_path] = {"add":[],"del":[],"type":"delete","old_path":file_path}
                ret2 = re.findall("@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@",line)
                if ret2:
                    status = True
                    del_number = int(ret2[0][0]) - 1
                    add_number = int(ret2[0][1]) - 1
                if not status:
                    continue
                if line.startswith("+++ ") or line.startswith("--- "):
                    continue
                if line.startswith("-"):
                    del_lines.append((del_number,line))
                    result[file_path]["del"].append((del_number,line[1:]))
                    del_number += 1
                elif line.startswith("+"):
                    add_lines.append((add_number,line))
                    result[file_path]["add"].append((add_number,line[1:]))
                    add_number += 1
                else:
                    add_number += 1
                    del_number += 1
        else:
            raise Exception("git diff error")
        return result

    def get_current_author(self):
        '''
        return current user.email
        '''
        pipe = subprocess.Popen("git config --get user.email||git log -1 --pretty=format:\"%ae\" ||echo",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8",errors="ignore").strip()

    def get_edit_commit_message(self):
        '''
        return edit commit message
        '''
        if os.path.exists(".git/COMMIT_EDITMSG"):
            pipe = subprocess.Popen("cat .git/COMMIT_EDITMSG",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
            command_output = pipe.communicate()[0]
            return command_output.decode("utf-8",errors="ignore").strip()
        else:
            if os.path.isfile(".git"):
                pipe = subprocess.Popen("cat .git|sed 's/gitdir: //g'|xargs -I {} cat {}/COMMIT_EDITMSG",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                return command_output.decode("utf-8",errors="ignore").strip()
            else:
                pipe = subprocess.Popen("git log -1 --pretty=format:%B",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
                command_output = pipe.communicate()[0]
                return command_output.decode("utf-8",errors="ignore").strip()

    def get_local_path(self):
        '''
        return local path
        '''
        pipe = subprocess.Popen("pwd",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8",errors="ignore").strip()

    def get_current_branch(self):
        '''
        return current branch
        '''
        pipe = subprocess.Popen("git branch|grep '*'|awk '{print $2}'",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8",errors="ignore").strip()

    def update_submodule(self):
        pipe = subprocess.Popen("git submodule update --init --recursive --depth=2 > /dev/null 2>&1",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8", errors="ignore").strip()

    def get_changed_file_size(self, revision1="HEAD~", revision2="HEAD"):
        '''
        return changed file size
        {
            "a.txt":{
                "size":8773
            }
        }
        '''
        result = {}
        pipe = subprocess.Popen('git diff {} {} --diff-filter=ACMR --name-only'.format(revision1,revision2),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        for changed_file in command_output.decode("utf-8", errors="ignore").strip().split("\n"):
            if changed_file.strip():
                result[changed_file.strip()] = {"size":int(os.path.getsize(changed_file))}
        return result

    def check_out(self, commit_id):
        pipe = subprocess.Popen('''git checkout {}
                                git submodule foreach --recursive git reset --hard
                                git submodule foreach --recursive git clean -fdx
                                git submodule sync --recursive
                                git submodule update --init --recursive'''.format(commit_id),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8", errors="ignore").strip()

    def get_current_commit_id(self):
        pipe = subprocess.Popen("git rev-parse HEAD",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8", errors="ignore").strip()

    def get_old_commit_id(self):
        pipe = subprocess.Popen("git rev-parse HEAD~",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8", errors="ignore").strip()

    def get_current_project_name(self):
        pipe = subprocess.Popen("git config --get remote.origin.url",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        repo_name = ""
        clone_url = command_output.decode("utf-8", errors="ignore").strip()
        if re.findall("git@",clone_url):
            repo_name = clone_url.split("/")[-1].split(".")[0]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name

    def get_lfs_status(self,file_path):
        '''
        return lfs status
        '''
        pipe = subprocess.Popen("git show --no-commit-id {} | grep 'version https://git-lfs.github.com/'".format(file_path),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        if command_output.decode("utf-8", errors="ignore").strip():
            return True
        else:
            return False

    def get_change_file_content(self,file_path, left = False):
        '''
        return file content
        '''
        if left:
            pipe = subprocess.Popen("git show HEAD^:{}".format(file_path),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        else:
            pipe = subprocess.Popen("git show HEAD:{}".format(file_path),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable="/bin/bash")
        command_output = pipe.communicate()[0]
        return command_output.decode("utf-8", errors="ignore").strip()

if __name__ == "__main__":
    local = Local()
    ret = local.get_current_project_name()
    print(ret)
