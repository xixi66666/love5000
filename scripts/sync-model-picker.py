"""同步共享模型选择器到各静态站点，避免运行时跨域加载脚本。"""
import argparse
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "website/src/main/resources/static/model-picker/picker.js"
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
