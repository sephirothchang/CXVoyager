# 使用说明（Windows）

本说明用于在 Windows 平台上运行本程序。主入口脚本为 `start.ps1`，位于仓库根目录。

## 前提要求
- 操作系统：Windows 10 / 11。
- PowerShell：推荐 PowerShell 7+，也可使用系统自带的 Windows PowerShell（注意脚本执行策略）。
- Python：Python 3.10 或更高版本已安装并在 PATH 中可用 （非必须，可使用自带虚拟环境）。

## 快速开始
1. 克隆仓库到本地并进入项目根目录（已在根目录时可跳过）。
2. 建议使用虚拟环境：
```powershell
.venv\Scripts\Activate.ps1
.venv\Scripts\python.exe main.py
```

或者直接使用 PowerShell 启动脚本：
```powershell
.\start.ps1
```

1. 允许脚本执行（如果被阻止，可临时放宽执行策略）：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\start.ps1
```

或者直接以 PowerShell 启动脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

## 日志与输出
- 运行过程中产生日志，位于仓库根目录下的 `logs/` 文件夹，常见日志文件例如 `cxvoyager.log.*`。
- 构建后的部署载荷位于`artifacts/`目录下。
- 巡检报告（含clusters_server_data.json）位于根目录下。

## 故障排查
- 如果脚本无法执行，请检查 PowerShell 的执行策略（见上）。
- 如果缺少 Python 依赖，请确认已在正确的虚拟环境中运行并按 3 根据提示安装依赖。
- 如遇权限问题，请以管理员权限运行 PowerShell（右键 PowerShell → 以管理员身份运行）。

## 其他
- MACOS 或 Linux 用户请参阅 `USAGE_MACOS_Linux.md`。
