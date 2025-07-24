# jobs/turnover_rise_baostock_v2.py

import baostock as bs
import pandas as pd
import pymysql
import os
import time
from datetime import datetime, timedelta

# Import get_stock_list from the existing module
try:
    import daily_job_baostock_5min
except ImportError:
    print("Could not import daily_job_baostock_5min. Make sure it's in the python path.")
    # As a fallback, define a placeholder function
    def get_stock_list_placeholder():
        print("Using placeholder for get_stock_list. This will not work.")
        return pd.DataFrame(columns=['code', 'name'])
    class MockDailyJob:
        get_stock_list = get_stock_list_placeholder
    daily_job_baostock_5min = MockDailyJob()


# --- Database Configuration ---
MYSQL_HOST = os.environ.get('MYSQL_HOST', "127.0.0.1")
MYSQL_USER = os.environ.get('MYSQL_USER', "root")
MYSQL_PWD = os.environ.get('MYSQL_PWD', "mysqldb")
MYSQL_DB = os.environ.get('MYSQL_DB', "stock_data")

def get_db_connection():
    """Establishes a database connection."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=3306,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB
    )

def fetch_basic_stock_data(stock_code, start_date, end_date, adjust="3"):
    """Fetches basic historical K-line data from Baostock."""
    print(f"Querying basic data for {stock_code} from {start_date} to {end_date}")
    rs = bs.query_history_k_data_plus(
        stock_code,
        "date,open,high,low,close,volume,turn,tradestatus",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag=adjust
    )

    if rs.error_code != '0':
        print(f"Baostock error for {stock_code}: {rs.error_msg}")
        return pd.DataFrame()

    data_list = [rs.get_row_data() for _ in iter(rs.next, False)]

    if not data_list:
        return pd.DataFrame()

    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df[df['tradestatus'] == '1'] # Filter for trading days

    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'turn']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.dropna(subset=numeric_cols, inplace=True)
    return df[['date', 'open', 'high', 'low', 'close', 'volume', 'turn']]


def save_basic_data_to_mysql(data, symbol, conn):
    """Saves basic stock data to the database using ON DUPLICATE KEY UPDATE."""
    if data.empty:
        return

    with conn.cursor() as cursor:
        insert_sql = """
            INSERT INTO stock_zh_a_daily (symbol, date, open, high, low, close, volume, turnover)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            open=VALUES(open), high=VALUES(high), low=VALUES(low),
            close=VALUES(close), volume=VALUES(volume), turnover=VALUES(turnover);
        """
        
        values_to_insert = []
        for _, row in data.iterrows():
            values = (
                symbol, row['date'], row['open'], row['high'], row['low'],
                row['close'], row['volume'], row['turn']
            )
            values_to_insert.append(values)
        
        try:
            if values_to_insert:
                cursor.executemany(insert_sql, values_to_insert)
                conn.commit()
        except pymysql.Error as e:
            print(f"DB Error on batch insert for {symbol}: {e}")
            conn.rollback()


def calculate_and_update_rise_continue_for_stock(symbol, conn):
    """Reads data from DB, calculates rise_continue, and updates the table for a single stock."""
    with conn.cursor() as cursor:
        try:
            # Fetch data with date as string to avoid timezone issues
            cursor.execute("SELECT date, open, close FROM stock_zh_a_daily WHERE symbol = %s ORDER BY date ASC", (symbol,))
            stock_data = cursor.fetchall()

            if not stock_data:
                # print(f"No data in DB for {symbol} to calculate rise_continue.")
                return

            df = pd.DataFrame(stock_data, columns=['date', 'open', 'close'])
            df['open'] = pd.to_numeric(df['open'])
            df['close'] = pd.to_numeric(df['close'])
            
            df['rise'] = df['close'] > df['open']
            df['rise_continue'] = 0
            
            continue_count = 0
            for i in df.index:
                if df.loc[i, 'rise']:
                    continue_count += 1
                else:
                    continue_count = 0
                df.loc[i, 'rise_continue'] = continue_count
            
            update_data = [(row['rise_continue'], symbol, row['date']) for _, row in df.iterrows()]

            if update_data:
                update_sql = "UPDATE stock_zh_a_daily SET rise_continue = %s WHERE symbol = %s AND date = %s"
                cursor.executemany(update_sql, update_data)
                conn.commit()
            # print(f"Successfully updated rise_continue for {symbol}")

        except pymysql.Error as e:
            print(f"DB Error during rise_continue calculation for {symbol}: {e}")
            conn.rollback()


def run_job():
    """Main function to run the entire job."""
    print("Starting the stock data processing job (v2)...")
    
    lg = bs.login()
    if lg.error_code != '0':
        print(f"Baostock login failed: {lg.error_msg}")
        return
    print("Baostock login successful.")

    try:
        stock_list_df = daily_job_baostock_5min.get_stock_list()
    except Exception as e:
        print(f"Failed to get stock list: {e}")
        bs.logout()
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90) # Fetch 90 days of data
    end_date_str = end_date.strftime('%Y-%m-%d')
    start_date_str = start_date.strftime('%Y-%m-%d')

    db_conn = get_db_connection()
    try:
        total_stocks = len(stock_list_df)
        
        # Part 1: Fetch and save basic data
        print(f"\n--- Part 1: Fetching and saving basic data for {total_stocks} stocks ---")
        for i, row in stock_list_df.iterrows():
            prefixed_code = row['code']
            symbol = prefixed_code.split('.')[1]
            
            print(f"Processing {prefixed_code} ({i + 1}/{total_stocks})")
            
            basic_data = fetch_basic_stock_data(prefixed_code, start_date_str, end_date_str)
            if not basic_data.empty:
                save_basic_data_to_mysql(basic_data, symbol, db_conn)
            time.sleep(0.1) # Be nice to the API

        # Part 2: Calculate and update rise_continue
        print(f"\n--- Part 2: Calculating and updating 'rise_continue' for {total_stocks} stocks ---")
        for i, row in stock_list_df.iterrows():
            symbol = row['code'].split('.')[1]
            print(f"Calculating for {symbol} ({i + 1}/{total_stocks})")
            calculate_and_update_rise_continue_for_stock(symbol, db_conn)
            
    finally:
        if db_conn:
            db_conn.close()
        bs.logout()
        print("Baostock logout successful.")
        print("Stock data processing job finished.")

if __name__ == "__main__":
    run_job()