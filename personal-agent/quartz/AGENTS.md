# Quartz 私人资料展示层

- 上游 `jackyzha0/quartz` v5.1.0（tag 对象 `8b587c674cf82a924f5abe805090fcf42600dd28`），MIT 许可证见 LICENSE.txt。核心源码随项目提交；node_modules 和私人产物禁止提交。
- 该目录负责真正的 Quartz 静态构建，不实现另一套资料数据库。Java 先复制经过根目录校验的文件到私人快照，再调用 Node 构建。
- 本地适配：quartz.config.yaml 禁用统计、外部字体、CDN 数学/Mermaid、社交嵌入；quartz.ts 为 Markdown 与虚拟页面加 HTML 清理；styles/custom.scss 设置中文系统字体；util/glob.ts 允许读取 Git 排除目录中的私人快照；Head.tsx 移除外部预连接；componentResources.ts 将图谱地址改为本地；prepare-private-assets.mjs 构建 D3 与 Pixi CSP 资源；explorer 不序列化运行时自定义函数。
- 不运行 `quartz sync`、不推送内容、不添加公开托管部署。私人 Vault 和搜索索引仅由5178的登录会话访问。
- Node.js 22+；`npm ci` 安装锁定依赖。`node ../scripts/check-quartz.mjs` 使用构造资料验证实际构建，不能替换为仅检查空站构建成功。
