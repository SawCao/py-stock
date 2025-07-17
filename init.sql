-- 创建数据库和表结构
CREATE DATABASE IF NOT EXISTS stock_data;
USE stock_data;

-- 股票基本信息表
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code VARCHAR(20) PRIMARY KEY,
    symbol VARCHAR(10),
    name VARCHAR(50),
    area VARCHAR(20),
    industry VARCHAR(20),
    market VARCHAR(10),
    list_date DATE,
    is_hs VARCHAR(2)
);

-- 股票日线数据表
CREATE TABLE IF NOT EXISTS stock_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_date DATE,
    open_price DECIMAL(10,4),
    high_price DECIMAL(10,4),
    low_price DECIMAL(10,4),
    close_price DECIMAL(10,4),
    pre_close DECIMAL(10,4),
    change_amount DECIMAL(10,4),
    pct_chg DECIMAL(10,4),
    vol DECIMAL(20,0),
    amount DECIMAL(20,0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_daily (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_ts_code (ts_code)
);

-- 股票分钟线数据表
CREATE TABLE IF NOT EXISTS stock_minute (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_time DATETIME,
    open_price DECIMAL(10,4),
    high_price DECIMAL(10,4),
    low_price DECIMAL(10,4),
    close_price DECIMAL(10,4),
    vol DECIMAL(20,0),
    amount DECIMAL(20,0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_minute (ts_code, trade_time),
    INDEX idx_trade_time (trade_time),
    INDEX idx_ts_code (ts_code)
);

-- 股票实时数据表
CREATE TABLE IF NOT EXISTS stock_realtime (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    name VARCHAR(50),
    price DECIMAL(10,4),
    change_amount DECIMAL(10,4),
    pct_chg DECIMAL(10,4),
    volume DECIMAL(20,0),
    amount DECIMAL(20,0),
    open DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    pre_close DECIMAL(10,4),
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_realtime (ts_code),
    INDEX idx_update_time (update_time)
);

-- 任务执行日志表
CREATE TABLE IF NOT EXISTS job_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_name VARCHAR(50),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_name (job_name),
    INDEX idx_start_time (start_time)
);

-- 创建用户并授权
CREATE USER IF NOT EXISTS 'stock_user'@'%' IDENTIFIED BY 'stock_pass_2024';
GRANT ALL PRIVILEGES ON stock_data.* TO 'stock_user'@'%';
FLUSH PRIVILEGES;
