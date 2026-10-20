"""同步共享模型选择器到各静态站点，避免运行时跨域加载脚本。"""
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
for target in targets:
    path = root / target
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, path)
print("已同步模型选择器到 %s 个服务" % len(targets))
