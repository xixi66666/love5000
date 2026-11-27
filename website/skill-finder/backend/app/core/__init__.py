"""配置与定时调度。

``config`` 汇总运行配置（数据库连接、GitHub Token、采集与日报参数）并提供唯一实例
``settings``；``scheduler`` 负责 MySQL 命名锁与 APScheduler 的装配。
两者都在导入期完成只读初始化，不做网络请求，也不打印任何密钥。
"""
