CREATE DATABASE IF NOT EXISTS stock_data;
USE stock_data;

-- Create table for daily stock data
CREATE TABLE IF NOT EXISTS stock_zh_a_daily (
    symbol VARCHAR(20),
    date DATE,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    amount DECIMAL(15,2),
    amplitude DECIMAL(10,2),
    quote_change DECIMAL(10,2),
    ups_downs DECIMAL(10,2),
    turnover DECIMAL(10,4),
    rise_continue INT,
    PRIMARY KEY (symbol, date)
);

-- Create table for stock minute data optimized
CREATE TABLE IF NOT EXISTS stock_zh_a_minute_ol_4 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20),
    day DATETIME,
    open DECIMAL(10,2),
    close DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    volume BIGINT,
    Gain_5 DECIMAL(10,4),
    Gain_6 DECIMAL(10,4),
    Gain_7 DECIMAL(10,4),
    Gain_8 DECIMAL(10,4),
    Gain_9 DECIMAL(10,4),
    Gain_10 DECIMAL(10,4),
    Gain_15 DECIMAL(10,4),
    Gain_20 DECIMAL(10,4),
    Gain_30 DECIMAL(10,4),
    Gain_60 DECIMAL(10,4),
    rname VARCHAR(100),
    price_change_5d DECIMAL(10,4) DEFAULT 0.0,
    volume_ratio_10d DECIMAL(10,4) DEFAULT 0.0,
    consecutive_up_5d BOOLEAN DEFAULT FALSE,
    high_turnover_10d BOOLEAN DEFAULT FALSE,
    high_turnover_5d BOOLEAN DEFAULT FALSE,
    volume_increase_5d_pct DECIMAL(10,4) DEFAULT 0.0,
    volume_increase_10d_pct DECIMAL(10,4) DEFAULT 0.0
);

-- Create indexes for better performance
CREATE INDEX idx_name_day ON stock_zh_a_minute_ol_4(name, day);
CREATE INDEX idx_gain_5 ON stock_zh_a_minute_ol_4(Gain_5);
CREATE INDEX idx_gain_6 ON stock_zh_a_minute_ol_4(Gain_6);
CREATE INDEX idx_gain_7 ON stock_zh_a_minute_ol_4(Gain_7);
CREATE INDEX idx_gain_8 ON stock_zh_a_minute_ol_4(Gain_8);
CREATE INDEX idx_gain_9 ON stock_zh_a_minute_ol_4(Gain_9);
CREATE INDEX idx_gain_10 ON stock_zh_a_minute_ol_4(Gain_10);
CREATE INDEX idx_gain_15 ON stock_zh_a_minute_ol_4(Gain_15);
CREATE INDEX idx_gain_20 ON stock_zh_a_minute_ol_4(Gain_20);
CREATE INDEX idx_gain_30 ON stock_zh_a_minute_ol_4(Gain_30);
CREATE INDEX idx_gain_60 ON stock_zh_a_minute_ol_4(Gain_60);

-- Create indexes for new indicators
CREATE INDEX idx_price_change_5d ON stock_zh_a_minute_ol_4(price_change_5d);
CREATE INDEX idx_volume_ratio_10d ON stock_zh_a_minute_ol_4(volume_ratio_10d);
CREATE INDEX idx_consecutive_up_5d ON stock_zh_a_minute_ol_4(consecutive_up_5d);
CREATE INDEX idx_high_turnover_10d ON stock_zh_a_minute_ol_4(high_turnover_10d);
CREATE INDEX idx_high_turnover_5d ON stock_zh_a_minute_ol_4(high_turnover_5d);
CREATE INDEX idx_volume_increase_5d_pct ON stock_zh_a_minute_ol_4(volume_increase_5d_pct);
CREATE INDEX idx_volume_increase_10d_pct ON stock_zh_a_minute_ol_4(volume_increase_10d_pct);

-- 创建用户并授权
CREATE USER IF NOT EXISTS 'stock_user'@'%' IDENTIFIED BY 'stock_pass_2024';
GRANT ALL PRIVILEGES ON stock_data.* TO 'stock_user'@'%';
FLUSH PRIVILEGES;
