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
        # Check if any 300 stocks exist at all
        cursor.execute("SELECT COUNT(*) as count FROM stock_zh_a_minute_ol_4 WHERE name LIKE '300%'")
        print(f"Total 300 stocks records: {cursor.fetchone()['count']}")

        # Check for 300 stocks in the date range
        cursor.execute("SELECT COUNT(*) as count FROM stock_zh_a_minute_ol_4 WHERE name LIKE '300%' AND day BETWEEN '2026-04-11' AND '2026-04-21'")
        print(f"300 stocks records in range: {cursor.fetchone()['count']}")

        # Check if any 300 stocks meet the gain threshold
        cursor.execute("""
            SELECT name, COUNT(*) as count 
            FROM stock_zh_a_minute_ol_4 
            WHERE Gain_5 > 0.03 AND day BETWEEN '2026-04-11' AND '2026-04-21' AND name LIKE '300%'
            GROUP BY name 
            LIMIT 5
        """)
        results = cursor.fetchall()
        print(f"Sample 300 stocks meeting threshold: {results}")

finally:
    connection.close()
