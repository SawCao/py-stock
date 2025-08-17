#!/bin/bash

#
# 通过第一个入参控制需要执行docker compose yml中的每个service的强制重新build重新deploy
#

# 从 docker-compose.yml 文件中动态获取服务列表
SERVICES=$(grep -E '^\s{2,4}[a-zA-Z0-9_-]+:' docker-compose.yml | sed 's/://' | sed 's/^\s*//' | grep -v 'services')

# 获取用户传入的第一个参数作为服务名
SERVICE=$1

# 检查用户是否传入了服务名
if [ -z "$SERVICE" ]; then
  echo "错误：请输入需要重新部署的服务名。"
  echo "用法: $0 [service_name]"
  echo "可用服务:"
  echo "$SERVICES"
  exit 1
fi

# 检查用户输入的服务名是否在服务列表中
if ! echo "$SERVICES" | grep -w -q "$SERVICE"; then
  echo "错误：服务 '$SERVICE' 不存在。"
  echo "可用服务:"
  echo "$SERVICES"
  exit 1
fi

# 执行 docker-compose 命令来强制重新构建和部署指定的服务
echo "正在重新构建和部署服务: $SERVICE"
docker compose up -d --force-recreate --no-deps --build "$SERVICE"

if [ $? -eq 0 ]; then
  echo "服务 '$SERVICE' 已成功重新部署。"
else
  echo "服务 '$SERVICE' 重新部署失败。"
fi