# Stages Index

此文档为每个阶段提供一行式摘要，便于快速浏览每个阶段的目的、关键输入与输出。详细设计请参见 `docs/Step_01-...` 对应文件。

- STEP 01 - PREPARE_PLAN_SHEET: 解析规划表并做验证与网络预检。 输入：规划表、CLI 选项；输出：`ctx.plan`, `ctx.extra['parsed_plan']`, `ctx.extra['precheck']`。
- STEP 02 - INIT_CLUSTER: 主机扫描、构建部署载荷并触发集群部署。 输入：`ctx.plan`、host_scan 配置；输出：`ctx.extra['deploy_payload']`, `ctx.extra['deploy_response']`。
- STEP 03 - CONFIG_CLUSTER: Fisheye 登录并配置集群 VIP/DNS/NTP 等。 输入：`deploy_verify`, `host_scan`; 输出：配置结果摘要。
- STEP 04 - DEPLOY_CLOUDTOWER: 上传 ISO、创建 CloudTower VM 并安装。 输入：CloudTower ISO、parsed_plan；输出：`ctx.extra['deploy_cloudtower']`。
- STEP 05 - ATTACH_CLUSTER: 将集群接入 CloudTower（创建数据中心并关联）。 输入：`deploy_cloudtower` 或探测到的 CloudTower；输出：`ctx.extra['attach_cluster']`。
- STEP 06 - CLOUDTOWER_CONFIG: CloudTower 高阶配置（NTP/DNS/策略/镜像）。 输入：attach 输出、parsed_plan；输出：配置变更摘要。
- STEP 07 - CHECK_CLUSTER_HEALTHY: 调用巡检接口生成健康报告。 输入：CloudTower/cluster 标识；输出：巡检报告。
- STEP 08 - DEPLOY_OBS: 上传 Observability 包（chunkedUploads 接口）。 输入：包文件、CloudTower base_url；输出：`ctx.extra['deploy_results']['OBS']`。
- STEP 09 - DEPLOY_BAK: 上传 Backup 包。 输入：包文件；输出：`ctx.extra['deploy_results']['BAK']`。
- STEP 10 - DEPLOY_ER: 上传 ER 包。 输入：包文件；输出：`ctx.extra['deploy_results']['ER']`。
- STEP 11 - DEPLOY_SFS: 上传 SFS 包（需同步存储策略）。 输入：包文件；输出：`ctx.extra['deploy_results']['SFS']`。
- STEP 12 - DEPLOY_SKS: 上传 SKS 包。 输入：包文件；输出：`ctx.extra['deploy_results']['SKS']`。
- STEP 13 - CREATE_TEST_VMS: 在集群上创建测试虚机并验证基本连通性。 输入：模板/镜像、cluster info；输出：测试 VM 列表与验证结果。
- STEP 14 - PERF_RELIABILITY: 执行性能基准与故障注入测试并生成报告。 输入：测试场景配置、host_info；输出：性能报告与指标。
- STEP 15 - CLEANUP: 清理临时资源、归档日志与移除敏感凭据。 输入：artifact、session token；输出：清理摘要。

快速定位：
- 详细文档目录：
  - `docs/Step_01-PREPARE_PLAN_SHEET.md`
  - `docs/Step_02-INIT_CLUSTER.md`
  - ...
  - `docs/Step_15-CLEANUP.md`

要点提醒：
- 上下文关键字段：`ctx.plan`, `ctx.extra['parsed_plan']`, `ctx.extra['host_scan']`, `ctx.extra['deploy_cloudtower']`, `ctx.extra['deploy_results']`。
- 建议在 `USAGE.md` 或项目 README 中放置此索引的快捷链接，方便运维人员查阅。
