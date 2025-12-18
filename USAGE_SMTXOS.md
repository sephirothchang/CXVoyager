# SMTXOS 使用说明

> 适用于通过 `start-smtxos.sh` 启动的场景，使用内置便携 Python 与独立虚拟环境 `.venv-smtxos`，默认英文界面。

## 准备工作
- 将便携 Python 压缩包放到 `cxvoyager/common/resources/python-smtxos/`（示例：`cpython-3.10.19+...tar.gz`）。
- 如需中文字体，放置 `SourceHanSansSC-Normal.otf` 到 `cxvoyager/common/resources/fonts/`（仅对图形终端/SSH 有效，纯文本控制台仍可能显示方块）。
- 离线依赖请放入 `cxvoyager/common/resources/offline_packages/`（需包含与 Python 版本匹配的 wheel，例如 PyYAML、requests 等）。

## 启动步骤
1) 授权脚本：`chmod +x start-smtxos.sh`
2) 运行：`./start-smtxos.sh`
   - 自动解压便携 Python 到 `smtxos-python/` 并优先使用；版本低于 3.9 会直接退出提示。
   - 创建/复用虚拟环境 `.venv-smtxos`，优先用离线包安装依赖，失败时尝试联网安装。
   - 设置 `CXVOYAGER_LANG=en_US`，CLI/Web 提示为英文；复制字体并刷新 `fc-cache`（如存在字体）。
   - 进入 `main.py` 交互菜单。

## 交互菜单
- **CLI 模式**：选择 `1`，进入 `cli>` 提示；常用命令：
  - `help` 查看命令
  - `parse` / `check --no-scan` 验证规划表(可选跳过扫描)
  - `deploy` 交互式选择阶段
- **Web UI 模式**：选择 `2`，默认监听 `0.0.0.0:8080`，可用 `CXVOYAGER_WEB_HOST`、`CXVOYAGER_WEB_PORT` 覆盖。
- **离线依赖安装**：选择 `3`，需预先准备 `offline_packages`。

## 路径与目录
- 便携 Python 解压：`smtxos-python/bin/python`
- 虚拟环境：`.venv-smtxos/`
- 离线包目录：`cxvoyager/common/resources/offline_packages/`
- 字体目录：`cxvoyager/common/resources/fonts/`

## 常见问题
- **缺少 PyYAML 或其他包**：离线目录未包含匹配 wheel，补齐后重试；或在可联网环境让脚本自动联网安装。
- **显示方块**：终端字体不含中文；建议使用支持 CJK 的 SSH 客户端（UTF-8）或图形终端。纯文本控制台难以完全避免方块。
- **Python 版本不足**：确保压缩包完整放在 `python-smtxos` 目录；必要时删除旧的 `smtxos-python/` 后重跑脚本。
