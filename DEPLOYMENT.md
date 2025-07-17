# 股票系统完整部署指南

## 系统架构

本系统包含以下服务：
- **MySQL**: 数据库存储
- **Redis**: 缓存服务
- **Web Backend**: Flask后端API服务
- **Web UI**: UmiJS前端界面
- **Job Scheduler**: 定时任务服务
- **Nginx**: 反向代理

## 部署步骤

### 1. 环境准备

确保已安装：
- Docker 20.10+
- Docker Compose 2.0+
- Git

### 2. 获取代码

```bash
git clone https://github.com/SawCao/py-stock.git
cd py-stock
```

### 3. 配置环境变量

创建 `.env` 文件：
```bash
# 数据库配置
MYSQL_ROOT_PASSWORD=stock_root_2024
MYSQL_DATABASE=stock_data
MYSQL_USER=stock_user
MYSQL_PASSWORD=stock_pass_2024

# Redis配置
REDIS_URL=redis://redis:6379/0

# Flask配置
FLASK_ENV=production
FLASK_DEBUG=false
```

### 4. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service-name]
```

### 5. 服务访问

- **前端界面**: http://localhost
- **后端API**: http://localhost/api
- **MySQL**: localhost:3306
- **Redis**: localhost:6379

## 服务管理

### 常用命令

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart [service-name]

# 查看日志
docker-compose logs -f [service-name]

# 进入容器
docker-compose exec [service-name] bash

# 重新构建
docker-compose build [service-name]
```

### 数据持久化

数据卷：
- `mysql_data`: MySQL数据
- `redis_data`: Redis数据

### 日志查看

日志文件：
- 应用日志: `./logs/`
- 容器日志: `docker-compose logs`

## 开发环境

### 本地开发

```bash
# 启动数据库和Redis
docker-compose up -d mysql redis

# 启动后端开发服务器
cd web/new_web
python app.py

# 启动前端开发服务器
cd web/umi-stock
npm install
npm start
```

### 调试模式

```bash
# 以调试模式启动
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up
```

## 监控和维护

### 健康检查

访问健康检查端点：
- http://localhost/health

### 数据库备份

```bash
# 备份数据库
docker-compose exec mysql mysqldump -u root -p stock_data > backup.sql

# 恢复数据库
docker-compose exec -i mysql mysql -u root -p stock_data < backup.sql
```

### 日志轮转

使用logrotate或配置Docker日志驱动进行日志轮转。

## 故障排除

### 常见问题

1. **端口冲突**
   - 修改docker-compose.yml中的端口映射

2. **内存不足**
   - 调整Docker资源限制
   - 减少worker数量

3. **数据库连接失败**
   - 检查MySQL容器状态
   - 验证数据库配置

4. **前端无法访问API**
   - 检查Nginx配置
   - 验证后端服务状态

### 调试技巧

```bash
# 查看容器详细信息
docker inspect [container-name]

# 进入容器调试
docker-compose exec [service-name] bash

# 查看网络
docker network ls
docker network inspect stock-network
```

## 性能优化

### 数据库优化

- 添加适当的索引
- 配置连接池
- 定期清理历史数据

### 缓存策略

- Redis缓存热点数据
- CDN缓存静态资源
- 浏览器缓存策略

### 负载均衡

- 使用Nginx负载均衡
- 水平扩展服务实例
- 数据库读写分离

## 安全配置

### 生产环境建议

1. **HTTPS配置**
   - 配置SSL证书
   - 强制HTTPS重定向

2. **访问控制**
   - 配置防火墙
   - 限制IP访问

3. **数据安全**
   - 定期备份
   - 敏感数据加密

4. **容器安全**
   - 使用非root用户
   - 定期更新镜像

## 扩展功能

### 监控集成

- Prometheus + Grafana
- ELK日志收集
- 应用性能监控

### 消息队列

- RabbitMQ/Apache Kafka
- 异步任务处理
- 实时数据推送

## 支持

如有问题，请提交Issue或联系维护人员。
