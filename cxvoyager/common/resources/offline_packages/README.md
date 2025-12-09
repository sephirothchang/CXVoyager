# 离线依赖包目录

> **许可证**：本文档依据 [GNU GPLv3](../../../LICENSE) 授权发布。

将所有 Python 依赖的安装包（`.whl` 或 `.tar.gz`）放置在此目录，以便在无外网环境下完成部署。

## 准备方式

在联网环境中执行以下命令即可将 `requirements.txt` 中的所有依赖下载到本目录：

```bash
python -m pip download -r requirements.txt -d utils/resources/offline_packages
```

如需兼容不同平台/架构，可在相应环境下各自运行上述命令，以收集完整的离线包集合。

## 使用方式

在运行 `python main.py` 后，选择菜单中的 “安装依赖（离线包）”，工具会自动执行：

```bash
python -m pip install --no-index --find-links utils/resources/offline_packages -r requirements.txt
```

确保当前解释器指向目标运行环境（推荐使用项目根目录下的 `.venv` 虚拟环境）。如安装过程中出现缺包提示，请重新下载对应包并放入该目录后再试。
