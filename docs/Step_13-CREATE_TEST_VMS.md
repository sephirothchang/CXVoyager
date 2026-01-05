# STEP 13 - CREATE_TEST_VMS

目的
- 在已部署的集群上创建用于验收测试的虚拟机（基于模板或 ISO），用于功能验证与资源验证场景。

输入
- `ctx.plan`（包含测试虚机相关信息）
- 平台 API 访问凭据（CloudTower session token）

输出
- `ctx.extra['create_test_vms']`：创建结果（vm id 列表、IP、登录凭证等）

关键模块
- `cxvoyager.core.deployment.handlers.create_test_vms`：包含 VM 创建与初始化步骤。
- SmartX / CloudTower API 客户端

主要流程
1. 根据规划表或默认模板选择镜像/模板并组装虚机参数。
2. 并发创建虚机并等待 guest OS 就绪（轮询 IP/SSH 可达性）。
3. 执行简单验证脚本（如 ping、磁盘挂载检查、网络连通性测试）。
4. 收集结果并写入阶段输出。

容错与注意事项
- 创建 VM 可能因资源配额或镜像缺失失败，需返回清晰的错误并建议修复步骤。
- 并发创建时需限制并发度以避免对平台触发过多瞬时请求。

日志与可观测
- VM 创建进度、IP 分配、验证结果记录。

操作提示
- 使用 --mock 模式跳过实际创建；检查规划表中的测试 VM 配置。