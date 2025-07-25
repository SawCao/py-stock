#!/bin/bash

# 脚本: 构建 umi-stock-ui 镜像并推送到 Docker Hub
# 用法: ./build_and_push_ui.sh

# --- 配置 ---
DOCKER_USERNAME="sawcao"
IMAGE_NAME="umi-stock-ui"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

DOCKERFILE_PATH="web/umi-stock/Dockerfile"
CONTEXT_PATH="web/umi-stock/"

# --- 脚本开始 ---
set -e # 如果任何命令失败，则立即退出

echo "=================================================="
echo "开始构建 Docker 镜像: ${FULL_IMAGE_NAME}"
echo "=================================================="

docker build --no-cache --pull -t "${FULL_IMAGE_NAME}" -f "${DOCKERFILE_PATH}" "${CONTEXT_PATH}"

if [ $? -ne 0 ]; then
    echo "❌ Docker 镜像构建失败。"
    exit 1
fi

echo "✅ Docker 镜像构建成功: ${FULL_IMAGE_NAME}"

echo "=================================================="
echo "开始推送镜像到 Docker Hub..."
echo "=================================================="

docker push "${FULL_IMAGE_NAME}"

if [ $? -ne 0 ]; then
    echo "❌ 镜像推送失败。"
    exit 1
fi

echo "✅ 镜像成功推送到 Docker Hub: ${FULL_IMAGE_NAME}"
echo "=================================================="