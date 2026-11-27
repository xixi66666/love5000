"""同步共享模型选择器到各静态站点，避免运行时跨域加载脚本。

唯一源码是 website/src/main/resources/static/model-picker/picker.js；脚本把它原样复制到四个独立
服务的静态目录（python-a、personal-agent、scrapling-ui、skill-finder），让各站点从自己的域名
同源加载同一份选择器，而不是跨端口 fetch 脚本。

参数：
    --check  只读模式，逐字节比较各副本与源码，不写入任何文件。

副作用：默认模式会创建缺失的父目录并覆盖四个目标副本；``--check`` 模式不写文件。

退出码：0 表示写入完成或检查通过；1 表示 ``--check`` 发现副本缺失或内容不一致；2 表示
``--check`` 时源码文件不存在（先修源码再同步）。默认模式遇到 IO 错误直接抛出，进程非 0 退出。
"""
import argparse
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
# 唯一源码：website 模块的静态资源目录，构建时随 classpath 一起打包。
source = root / "website/src/main/resources/static/model-picker/picker.js"
# 四个独立服务的静态目录；每份副本都按源文件原样覆盖，不保留服务侧改动。
targets = [
    "website/python-a/model-picker.js",
    "personal-agent/src/main/resources/static/model-picker.js",
    "website/scrapling-ui/frontend/public/model-picker.js",
    "website/skill-finder/frontend/public/model-picker.js",
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true", help="仅检查部署副本是否与源码一致，不写入")
args = parser.parse_args()

if args.check:
    if not source.is_file():
        parser.exit(2, "模型选择器源文件不存在：%s\n" % source)
    stale = [target for target in targets
             if not (root / target).is_file()
             or (root / target).read_bytes() != source.read_bytes()]
    if stale:
        parser.exit(1, "模型选择器副本未同步：\n" + "\n".join(stale) + "\n")
    print("模型选择器副本检查通过（%s 个服务）" % len(targets))
else:
    for target in targets:
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
    print("已同步模型选择器到 %s 个服务" % len(targets))
