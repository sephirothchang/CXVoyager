# SMTXOS 使用说明

> 适用于通过 `start-smtxos.sh` 启动的场景，使用内置便携 Python 与独立虚拟环境 `.venv-smtxos`，默认英文界面。

## 启动步骤
1) 授权脚本：`chmod +x start-smtxos.sh`
2) 运行：`./start-smtxos.sh`
   - 自动解压便携 Python 到 `smtxos-python/` 并优先使用；版本低于 3.10 会直接退出提示。
   - 创建/复用虚拟环境 `.venv-smtxos`，优先用离线包安装依赖，失败时尝试联网安装。
   - 设置 `CXVOYAGER_LANG=en_US`，CLI/Web 提示为英文。
   - 进入 `main.py` 交互菜单。

## 交互菜单
- **CLI 模式**：选择 `1`，进入 `cli>` 提示；常用命令：
  - `help` 查看命令
  - `parse` / `check --no-scan` 验证规划表(可选跳过扫描，一般用不到，除非你想先扫描一下主机看看信息)
  - `deploy` 交互式选择阶段进行部署
  - `run --stages <stage1,stage2,...> [--dry-run] [--debug] [--strict-validation]` 直接按阶段执行部署（不推荐日常使用）
- **Web UI 模式**：选择 `2`，默认监听 `0.0.0.0:8080`，可用 `CXVOYAGER_WEB_HOST`、`CXVOYAGER_WEB_PORT` 覆盖。
- **离线依赖安装**：选择 `3`，需预先准备 `offline_packages`。

## 路径与目录
- 便携 Python 解压：`smtxos-python/bin/python`
- 虚拟环境：`.venv-smtxos/`
- 离线包目录：`cxvoyager/common/resources/offline_packages/`

## 常见问题
- **缺少 PyYAML 或其他包**：离线目录未包含匹配 wheel，补齐后重试；或在可联网环境让脚本自动联网安装。
- **显示方块**：终端字体不含中文；建议使用支持 CJK 的 SSH 客户端（UTF-8）或图形终端。纯文本控制台难以完全避免方块。
- **Python 版本不足**：确保压缩包完整放在 `python-smtxos` 目录；必要时删除旧的 `smtxos-python/` 后重跑脚本。
