# STEP 09 - DEPLOY_BAK

目标
- 上传并部署备份服务（BAK），并将实例关联到目标集群。

输入
- 本地 BAK 安装包，命名模式：`smtx-backup-dr-(x86_64|aarch64)-<version>.tar.gz`
- 规划表：管理网、存储网、备份网信息（IP/mask/VLAN/VDS）
- API 配置：`api.bak_base_url`（优先）或 `api.base_url`，CloudTower 登录凭据
- 上下文：`ctx.extra['parsed_plan']`、`ctx.plan`

输出
- `ctx.extra['deploy_results']['bak']`：上传、部署、关联结果摘要

实现要点（handler `deploy_bak`）
- 登录 CloudTower，获取 token + cookie 以满足上传与业务 API。
- 版本判断：若远端已有同架构且版本 ≥ 本地包，则跳过上传，直接使用已有版本。
- 上传：GraphQL 初始化 upload task，分片 multipart 上传，再提交 commit/verify。
- 网络准备：
	- 优先使用规划表存储网掩码，否则回退 /24。
	- 若缺少存储 IP，则复用管理网第一节点 IP。
	- 根据 VDS/VLAN 创建备份存储网络（/v2/api/create-vm-vlan）。
- 部署：调用 `/api` 创建/更新 backup service，并轮询状态直至完成或超时。
- 任务轮询：`/v2/api/get-tasks` 观察后台任务完成状态。
- 关联集群：GraphQL mutation 将 backup instance 绑定到集群。

操作步骤（运行器视角）
1) 确认本地包路径与版本（遵循命名模式）。
2) 运行 prepare/前置阶段获取规划表解析结果。
3) 执行 deploy_bak 阶段；若 `--dry-run` 仅打印流程。
4) 部署成功后在 CloudTower 验证实例状态与网络。

故障排查
- 上传失败：检查 HTTP 日志、分片重试信息，确认包名与架构匹配。
- 网络创建失败：核对存储 VLAN/VDS/掩码配置；必要时手工创建再重试部署。
- 部署/任务超时：查看 CloudTower 任务中心与服务状态，确认包版本是否匹配目标平台。

日志与可观测
- 上传进度、分片状态、部署轮询记录。

操作提示
- 确保 BAK 包文件名匹配模式；当前为占位实现。