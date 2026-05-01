import pymysql

connection = pymysql.connect(
    host='stock-mysql',
    user='stock_user',
    password='stock_pass_2024_sawtt',
    database='stock_data',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with connection.cursor() as cursor:
        # Check for 600 stocks in the date range
        cursor.execute("SELECT COUNT(*) as count FROM stock_zh_a_minute_ol_4 WHERE name LIKE '600%' AND day BETWEEN '2026-04-11' AND '2026-04-21'")
        print(f"600 stocks records in range: {cursor.fetchone()['count']}")

        # Check for 000 stocks in the date range
        cursor.execute("SELECT COUNT(*) as count FROM stock_zh_a_minute_ol_4 WHERE name LIKE '000%' AND day BETWEEN '2026-04-11' AND '2026-04-21'")
        print(f"000 stocks records in range: {cursor.fetchone()['count']}")
        
        # Check what is the latest date in the database for 300 stocks
        cursor.execute("SELECT MAX(day) as max_day FROM stock_zh_a_minute_ol_4 WHERE name LIKE '300%'")
        print(f"Latest date for 300 stocks: {cursor.fetchone()['max_day']}")

finally:
    connection.close()
