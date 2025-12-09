# 关于cloudtower镜像文档的处理

## 修改的文件
isolinux.cfg
修改默认启动项label linux
修改默认超时时间从600改为100（单位是1/10秒）

ks.cfg
增加了自动安装SVT的脚本

SMTX_VM_TOOLS_INSTALL.sh
提取自SVT 4.0.0镜像的SVT工具

## 目录
/
- isolinux.cfg
- ks.cfg
- SMTX_VM_TOOLS_INSTALL.sh
  
/isolinux
- isolinux.cfg
- ks.cfg