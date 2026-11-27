"""把公共客户端与统一模型配置读取器随独立 Python 服务打包。

源码只在 website/model-routing 维护两份文件（model_routing.py、model_properties.py），脚本把它们
复制成以 ``_`` 开头的部署副本（_model_routing.py、_model_properties.py）放进三个独立服务的
services 目录，避免各服务重复实现模型网关调用与 model.properties 读取。

参数：
    --check  只读模式，逐字节比较六个副本，不写入任何文件。

副作用：默认模式覆盖 3 个服务目录下的 6 个副本文件；目录必须已存在，脚本不创建，源码也不被修改。

退出码：0 表示写入完成或检查通过；1 表示 ``--check`` 发现副本缺失或内容不一致。默认模式遇到
IO 错误直接抛出，进程非 0 退出。
"""
import argparse
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
# (源码路径, 部署副本文件名)：下划线前缀表示这是生成文件，不要手工编辑。
files = [
    (root / "website/model-routing/model_routing.py", "_model_routing.py"),
    (root / "website/model-routing/model_properties.py", "_model_properties.py"),
]
# 需要完整模型公共源码的三个独立 Python 服务，副本落在各自 services 目录内。
services = [
    root / "website/python-a/services",
    root / "website/scrapling-ui/backend/services",
    root / "website/skill-finder/backend/app/services",
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true", help="仅检查部署副本是否与源码一致")
args = parser.parse_args()


def copies():
    """逐个产出 (源码, 目标副本) 组合，供检查与写入共用一个真值来源。

    服务目录不存在时，写入阶段会由 ``shutil.copyfile`` 抛 FileNotFoundError，
    这比静默跳过更安全：漏掉一个服务的副本会在运行时才暴露导入失败。
    """
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
