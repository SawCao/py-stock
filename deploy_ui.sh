#!/bin/bash

# 如果任何命令失败，则立即退出
set -e

# 定义镜像名称
IMAGE_NAME="sawcao/umi-stock-ui:latest"

echo "正在停止并移除现有的容器..."
docker-compose down

echo "正在强制移除旧的UI镜像: $IMAGE_NAME"
# 如果镜像不存在，`|| true`可以防止脚本失败
docker rmi -f $IMAGE_NAME || true

echo "正在拉取最新的UI镜像: $IMAGE_NAME"
docker pull $IMAGE_NAME

echo "正在使用新镜像启动所有服务..."
docker-compose up -d

echo "部署完成."

echo "正在清理悬空的镜像..."
docker image prune -f

echo "完成."