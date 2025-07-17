# 使用官方Python基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 使用国内镜像源并安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y gcc default-libmysqlclient-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    pandas \
    numpy \
    sqlalchemy \
    mysqlclient \
    akshare \
    pytest

# 设置环境变量
ENV MYSQL_HOST=mysql
ENV MYSQL_USER=test
ENV MYSQL_PWD=test
ENV MYSQL_DB=test_db

# 运行测试
CMD ["pytest", "test_insert_minute.py"]
