# 潜在改进项与演进路线

> **许可证**：本文档依据 [GNU GPLv3](../LICENSE) 授权发布。

> 本文档用于跟踪尚未实现或可优化的特性，按主题分组；已实现后在此标记完成或迁移到CHANGELOG。

## 解析与验证
- [x] prepare 阶段缓存原始 parsed 数据（含 `_derived_network`）避免重复解析。
- [x] CloudTower-only 模式允许集群 VIP 存活，并通过 Fisheye 登录验证现有集群服务状态。
- [ ] 严格模式：将若干 warnings 在 strict 模式下提升为 errors。
- [ ] 增加 IPv4/IPv6 混合下的网段冲突与跨段分布检查。
- [ ] VIP 与所有主机地址、存储地址、网络网关冲突全面校验。
- [ ] 根据“虚拟网络”sheet usage 推断（mgmt/storage/vm/backup/rdma）。

## 部署载荷构建
- [ ] 从 `_derived_network` 自动构建 vdses/networks 而不是当前占位默认。
- [ ] 增加 RDMA / LACP 条件字段推断。
- [ ] 磁盘角色区分：cache / data / journal / metadata 策略映射。
- [ ] SSD/NVMe 性能排序与缓存优先策略（加权容量/IOPS）。

## API 交互
- [ ] 真实 API 认证流程（Token刷新 / 会话保持 / TLS 校验）。
- [ ] 区分可重试与不可重试错误（HTTP 4xx vs 5xx）。
- [ ] 部署任务事件流订阅（WebSocket / SSE）替代轮询。
- [ ] 指数退避与抖动参数化配置。

## 日志与可观测性
- [ ] 结构化 JSON 日志输出与字段标准（stage, action, duration_ms, result）。
- [ ] 接入 OpenTelemetry（trace/span）串联阶段调度。
- [ ] 错误分类统计与最终总结报告生成。

## 扩展阶段逻辑
- [x] config_cluster 阶段真实实现（VIP/DNS/NTP/IPMI/业务 VDS/主机密码加固）。
- [ ] deploy_cloudtower 阶段实际安装包上传与进度跟踪。
- [ ] attach_cluster 阶段并行多集群关联（支持批量）。
- [ ] create_test_vms 基于模板并发克隆，支持全闪/混合差异化策略。
- [ ] perf_reliability 自动编排 FIO 场景 + 注入故障（拔盘/关机）。
- [ ] cleanup 分级清理策略（软删除 -> 彻底移除）。

## CLI / Web
- [ ] CLI 输出彩色阶段概览表 + 总结（OK/FAIL/WARN 数）。
- [ ] Web UI：任务列表、阶段甘特图、实时日志流、下载工件。
- [ ] Web 后端：持久化 (SQLite/PostgreSQL) 任务状态与上下文。

## 配置与安全
- [ ] 秘钥/密码使用环境变量或外部 Secret 管理（不直接写 YAML）。
- [ ] 密码字段检测与脱敏日志输出。
- [ ] 多环境配置层（default / staging / prod）。

## 测试与质量
- [ ] 引入 mypy + ruff 检查。
- [ ] 增加集成测试（模拟完整阶段链路）。
- [ ] 性能基准：并发 N=50 主机扫描耗时统计。

## 打包与分发
- [ ] 生成可执行 zipapp / 单文件分发。
- [ ] Docker 镜像（含最小运行时与健康检查）。

## 其他
- [ ] 国际化（i18n）中英文双语日志与输出。
- [ ] 时间度量与阶段耗时统计仪表盘。
- [ ] 插件化阶段注册机制（entry_points）。
