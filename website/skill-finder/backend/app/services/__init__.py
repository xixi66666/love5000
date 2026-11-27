"""业务服务层。

``repository_service`` 组装榜单与详情查询，``stats_service`` 提供统计聚合并把采集
失败翻译成固定用户提示，``trend`` 是纯函数式的增长计算，``introduction_service``
负责调用模型生成中文简介并落库，``model_hub`` / ``model_settings`` 是统一模型入口与
``model.properties`` 的薄适配层。

约定：服务接收调用方传入的 ``AsyncSession``，只读服务不提交；写服务（简介补全）
在自己的事务边界提交。模型密钥一律从私有配置读取，不写日志、不进响应。
"""
