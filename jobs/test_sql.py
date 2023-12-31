import pymysql

create_table_sql=f"""
CREATE TABLE `stock_zh_a_daily` (
	`symbol` VARCHAR(10) NOT NULL COLLATE 'utf8mb4_general_ci',
	`date` DATE NOT NULL,
	`open` DECIMAL(10,2) NULL DEFAULT NULL,
	`high` DECIMAL(10,2) NULL DEFAULT NULL,
	`low` DECIMAL(10,2) NULL DEFAULT NULL,
	`close` DECIMAL(10,2) NULL DEFAULT NULL,
	`volume` DECIMAL(20,4) NULL DEFAULT NULL,
	`turnover` DECIMAL(10,4) NULL DEFAULT NULL,
	`rise` INT(11) NULL DEFAULT NULL,
	`rise_continue` INT(11) NULL DEFAULT NULL,
	PRIMARY KEY (`symbol`, `date`) USING BTREE
)
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
"""
def save_to_mysql(data, host="mysqldb", port=3306, user="root", password="mysqldb", database="stock_data"):
    # 建立数据库连接
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    # 将数据写入mysql数据库
    cursor = conn.cursor()
    cursor.execute(create_table_sql)

    # 关闭数据库连接
    conn.close()
data = {"date":"eee"}
save_to_mysql(data)