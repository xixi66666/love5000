"""把公共客户端随独立 Python 服务打包。源码只在 website/model-routing 维护。"""
import argparse
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "website/model-routing/model_routing.py"
targets = [
    root / "website/python-a/services/_model_routing.py",
    root / "website/scrapling-ui/backend/services/_model_routing.py",
    root / "website/skill-finder/backend/app/services/_model_routing.py",
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true", help="仅检查部署副本是否与源码一致")
args = parser.parse_args()
if args.check:
    stale = [str(p.relative_to(root)) for p in targets
             if not p.exists() or p.read_bytes() != source.read_bytes()]
    if stale:
        parser.exit(1, "客户端副本未同步：\n" + "\n".join(stale) + "\n")
else:
    for path in targets:
        shutil.copyfile(source, path)
print("模型公共客户端副本检查通过" if args.check else "已同步 3 个模型公共客户端部署副本")
