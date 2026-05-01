FROM node:18-alpine AS builder

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 设置淘宝NPM镜像并安装依赖
RUN npm config set registry https://registry.npmmirror.com/ && \
    npm ci

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产环境阶段保持不变
FROM nginx:alpine
COPY --from=builder /app/dist /etc/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 9090
CMD ["nginx", "-g", "daemon off;"]