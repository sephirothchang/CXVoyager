# 使用说明（Linux）

本说明用于在 Linux 平台运行本程序。主入口脚本：`start-linux.sh` 位于仓库根目录。

## 前提要求
- 操作系统：主流 Linux 发行版（如 Ubuntu/CentOS 等）。
- Shell：bash 可用。
- Python：推荐 Python 3.10+ 已安装并在 PATH 中（可用系统自带或虚拟环境）。

## 快速开始
1. 进入项目根目录。
2. 首次赋予脚本执行权限：
   ```bash
   chmod +x start-linux.sh
   ```
3. 运行：
   ```bash
   ./start-linux.sh
   ```

## 使用虚拟环境（推荐）
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

说明：若存在 `.venv/bin/python`，`start-linux.sh` 会自动激活并使用虚拟环境；否则回退系统 `python3` 执行 `main.py`。不同平台请各自维护虚拟环境目录，避免跨平台共用同一 `.venv`。

## 日志与输出
- 日志位于 `logs/`（如 `cxvoyager.log.*`）。
- 构建后的部署载荷位于 `artifacts/`。
- 巡检报告（含 clusters_server_data.json）位于仓库根目录。

## 故障排查
- 无执行权限：确认已执行 `chmod +x start-linux.sh`。
- 缺少依赖：确认已在虚拟环境中 `pip install -r requirements.txt`。
- Python 版本低：请升级或改用 3.10+。
- 跨平台行尾问题：如有需要，可运行 `dos2unix start-linux.sh` 修正为 LF。

## 其他
- Windows 用户参阅 `USAGE_WINDOWS.md`。
- macOS 用户参阅 `USAGE_MACOS.md`。