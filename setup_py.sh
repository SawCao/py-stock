#!/bin/bash
set -e

# 1. 确保系统有 venv 和 pip
sudo apt update
sudo apt install -y python3-full python3-venv

# 2. 如果已有 venv，先删除
if [ -d "venv" ]; then
  echo "已有 venv，删除旧环境..."
  rm -rf venv
fi

# 3. 创建新的虚拟环境
python3 -m venv venv

# 4. 激活虚拟环境并升级 pip
source venv/bin/activate
pip install --upgrade pip

# 5. 安装 requirements.txt 中的依赖
pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

echo ""
echo "✅ 环境创建完成！"
echo "使用方法："
echo "   source venv/bin/activate"
echo "退出环境："
echo "   deactivate"
