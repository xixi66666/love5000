"""把公共客户端与统一模型配置读取器随独立 Python 服务打包。源码只在 website/model-routing 维护。"""
import argparse
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = [
    (root / "website/model-routing/model_routing.py", "_model_routing.py"),
    (root / "website/model-routing/model_properties.py", "_model_properties.py"),
]
services = [
    root / "website/python-a/services",
    root / "website/scrapling-ui/backend/services",
    root / "website/skill-finder/backend/app/services",
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true", help="仅检查部署副本是否与源码一致")
args = parser.parse_args()


def copies():
    for directory in services:
        for source, name in files:
            yield source, directory / name


if args.check:
    stale = [str(target.relative_to(root)) for source, target in copies()
             if not target.exists() or target.read_bytes() != source.read_bytes()]
    if stale:
        parser.exit(1, "客户端副本未同步：\n" + "\n".join(stale) + "\n")
else:
    for source, target in copies():
        shutil.copyfile(source, target)
print("模型公共源码副本检查通过" if args.check else "已同步 6 个模型公共源码部署副本")
