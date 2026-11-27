"""python-a 单元测试包的标记文件。

存在这个文件，``python -m unittest discover -s tests`` 才会把 tests 当包导入，测试模块内部
也才能直接 ``import server`` 与 ``from services.storage_service import JsonStore``（工作目录为
website/python-a）。不包含测试用例，也不产生任何副作用。
"""
