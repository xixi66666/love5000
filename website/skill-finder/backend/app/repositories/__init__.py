"""数据访问层：每张业务表一个 Store。

五个 Store 分别对应 ``repositories``、``star_snapshots``、``trending_entries``、
``collection_runs``、``last30days_reports``，只做 SQLAlchemy 语句组装，不写裸 SQL
字符串（命名锁等少数语句除外）。

事务约定：所有方法最多 ``flush``，**从不 ``commit``**。会话由调用方打开并关闭，
提交时机由业务层决定（采集服务按阶段提交，API 只读不提交），这样一次业务动作里的
多次写入可以落在同一个事务里。
"""
