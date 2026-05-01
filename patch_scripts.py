import pymysql
import time
import logging
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_connection():
    return pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='stock_root_2024_sawtt',
        database='stock_data',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def wait_for_locks():
    logging.info("Waiting for locks to clear...")
    while True:
        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SHOW FULL PROCESSLIST;")
                processes = cursor.fetchall()
                is_locked = False
                for p in processes:
                    if p['Info'] and 'DELETE FROM stock_zh_a_minute_ol_4' in p['Info'] and p['Id'] != conn.thread_id():
                        logging.info(f"Lock detected from PID {p['Id']}, State: {p['State']}")
                        is_locked = True
                
                if not is_locked:
                    logging.info("No locks detected.")
                    conn.close()
                    return
            conn.close()
        except Exception as e:
            logging.error(f"Error checking locks: {e}")
        
        time.sleep(10)

def add_index():
    logging.info("Adding composite index...")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if index exists
            cursor.execute("SHOW INDEX FROM stock_zh_a_minute_ol_4 WHERE Key_name = 'idx_day_gain5_name';")
            if cursor.fetchone():
                logging.info("Index already exists.")
                return
            
            cursor.execute("ALTER TABLE stock_zh_a_minute_ol_4 ADD INDEX idx_day_gain5_name (day, Gain_5, name);")
            logging.info("Composite index added successfully.")
    except Exception as e:
        logging.error(f"Failed to add index: {e}")
    finally:
        conn.close()

def delete_old_data():
    logging.info("Deleting data before 2026-03-20 in batches...")
    conn = get_connection()
    total_deleted = 0
    try:
        with conn.cursor() as cursor:
            while True:
                cursor.execute("DELETE FROM stock_zh_a_minute_ol_4 WHERE day < '2026-03-20' LIMIT 50000;")
                deleted_rows = cursor.rowcount
                total_deleted += deleted_rows
                logging.info(f"Deleted {deleted_rows} rows. Total deleted: {total_deleted}")
                if deleted_rows == 0:
                    break
                time.sleep(0.5)
        logging.info("Finished deleting old data.")
    except Exception as e:
        logging.error(f"Failed to delete old data: {e}")
        logging.error(traceback.format_exc())
    finally:
        conn.close()

if __name__ == '__main__':
    wait_for_locks()
    add_index()
    delete_old_data()
