
# 静态检查

## 环境要求

```
python >= 3.8
```

## 目录结构说明

```sh
├── checkers # 各种检查项脚本
│   ├── cpplint_check.py
|   ...
├── common
│   ├── config_parser.py # 通用参数解析，主要是解析配置文件，以及获取环境变量
│   ├── __init__.py
│   ├── localgit.py # 适配本地git相关操作
│   └── static_check_common.py # 通用检查项功能，比如初始化以及各类hook
├── config
│   └── sast.json # 各项检查项配置及通用配置
├── run.py # 入口脚本
└── tools # 各种检查项需要的工具
    ├── autopep8.py 
    ├── checkpatch.pl
    ...
```

## 使用说明

### 使用源码检查

需要在本地仓库的根目录里面，执行命令如下,检查的内容是最新的一个commit的增量修改内容是否有报错
```shell
python3 ${REPO_APTH}/sast/run.py --cpplint_check # 具体的检查项名称
python3 ${REPO_APTH}/sast/run.py --cpplint_check --shell_check  # 一次性检查多个检查项
python3 ${REPO_APTH}/sast/run.py --checks_group external_checks # 执行检查组,需要预先在配置文件中定义检查组名称和组内的检查项名
python3 ${REPO_APTH}/sast/run.py --all_ci_check # 执行全部的检查项
... ...
```

### 使用镜像检查

使用镜像检查,假设镜像名称是sast:release

```shell
# 进入git仓库的根目录
cd git_repo
# 执行一项检查
docker run --rm -it -v $(pwd):/app -u $(id -u):$(id -g) -w /app  sast:release bash -c 'python3 /sast/run.py --cpplint_check'
# 执行多个检查项
docker run --rm -it -v $(pwd):/app -u $(id -u):$(id -g) -w /app  sast:release bash -c 'python3 /sast/run.py --cpplint_check --shell_check'
# 执行检查组，需要预先在配置文件中定义检查组名称和组内的检查项名
docker run --rm -it -v $(pwd):/app -u $(id -u):$(id -g) -w /app  sast:release bash -c 'python3 /sast/run.py --checks_group external_checks'
```

### 使用指定配置文件

默认情况下使用仓库里面的config/sast.json文件做配置文件，如果想使用自定义的配置文件，在执行的目录下自定义文件名`.sast_config.json`

目前只支持如下内容配置

```json
{
    "checks_group":{ // 自定义检查组
        "external_checks":[ // 检查组的名称
            "codespell_check","copyright_check","cpplint_check","gitleaks_check","hardcode_check","jsonlint_check","line_terminators_check" // 检查组的检查项
        ],
        "my_checks":[
            "codespell_check","cpplint_check"
        ]
    }
}
```