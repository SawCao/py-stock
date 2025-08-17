import pymysql
from flask import Flask, jsonify, request, render_template
import logging
import tushare as ts
import time
import json
import os
import pickle
import traceback

app = Flask(__name__, static_folder='static')
app.config['DEBUG'] = True
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.route('/', methods=['GET','POST'])
def login():
    return app.send_static_file('login.html')

@app.route('/index', methods=['GET','POST'])
def index():
    return app.send_static_file('index.html')


@app.route('/stock_search', methods=['GET'])
def search_stock_data():
    search_string = request.args.get('search', default='', type=str)
    gain_threshold = request.args.get('gain_threshold', default=0.03, type=float)
    start_date = request.args.get('start_date', default='2023-01-31 00:00:00')
    end_date = request.args.get('end_date', default='2023-01-31 00:00:00')
    gain_type = request.args.get('gain_type', default='Gain_5')
    return get_stock_from_db_with_search(search_string, gain_threshold, start_date, end_date, gain_type)

def _normalize_code(code: str) -> str:
    """
    统一代码为纯6位：如 'sh.600000' / 'sz000001' / '600000' -> '600000'
    """
    if not code:
        return ""
    c = code.strip().lower().replace(".", "")
    if c.startswith("sh") or c.startswith("sz"):
        c = c[2:]
    return c

def get_stock_data():
    connection = pymysql.connect(
        host='127.0.0.1',
        user='stock_user',
        password='stock_pass_2024_sawtt',
        database='stock_data',
        cursorclass=pymysql.cursors.DictCursor,
        charset='utf8mb4',
        autocommit=True
    )
    try:
        with connection.cursor() as cursor:
            query = "SELECT id, name, code, code_name, industry, industry_classification FROM stock_industry"
            cursor.execute(query)
            rows = cursor.fetchall()  # list[dict]
    finally:
        connection.close()

    # 构造成 dict，key=纯6位代码
    result = {}
    for r in rows:
        k = _normalize_code(r.get("code") or r.get("code_name") or r.get("name") or "")
        if not k:
            continue
        result[k] = {
            "name": r.get("name"),
            "code": k,
            "code_name": r.get("code_name"),
            "industry": r.get("industry"),
            "industry_classification": r.get("industry_classification"),
        }
    return result

def get_stock_from_db_with_search(search_string, gain_threshold, start_date, end_date, gain_type):
    logging.info('Performing fuzzy search with string: %s', search_string)
# Please enter the commit message for your changes. Lines starting
# with '#' will be ignored, and an empty message aborts the commit.
#
# On branch dev
# Your branch is up to date with 'origin/dev'.
#
# Changes to be committed:
#	modified:   web/new_web/app.py
#

    # Connect to the database
    connection = pymysql.connect(
        host='127.0.0.1',
        user='stock_user',
        password='stock_pass_2024_sawtt',
        database='stock_data',
        cursorclass=pymysql.cursors.DictCursor
    )
    pro = ts.pro_api('0a42c03559605acecb58cca7218b5f6736f1ea878e20a090b2077bdf')
    try:
        with connection.cursor() as cursor:
            # Get parameters from request
            start_time = time.time()
            
            if gain_threshold == 1:
                # 读取本地文件
                with open('fake_result.json', 'r') as f:
                    result  = json.load(f) 
                return result
            
            # Query database with fuzzy search on rname and code
            query = """
                SELECT name as t2name, count(*) as gain_Amplitude_num
                FROM stock_zh_a_minute_ol_4
                WHERE {} > %s and `day` > %s and `day` < %s
                AND (rname LIKE %s OR name LIKE %s)
                GROUP BY name
                ORDER BY gain_Amplitude_num DESC
                LIMIT 100
            """.format(str(gain_type))
            
            search_pattern = f"%{search_string}%"
            cursor.execute(query, (gain_threshold, start_date, end_date, search_pattern, search_pattern))
            logging.info(cursor.mogrify(query))
            results = cursor.fetchall()
            response_dict = {}  # 存储结果的字典
            response = []
            end_time = time.time()
            logging.info(f"查询震荡，执行时间为 {end_time - start_time:.6f} 秒")
            try:
                all_stock_info = get_stock_data()
                
                logging.info("all_stock_info！")
            except Exception as e:
                logging.error("读取 tushare 数据失败，使用本地缓存数据！")
                logging.error("错误类型: %s", type(e).__name__)
                logging.error("错误详情: %s", str(e))
                logging.error("堆栈信息:\n%s", traceback.format_exc())
                all_stock_info = {}
            else:
                logging.info("读取成功！")
            # Load all stock data from tushare into a dictionary
            # data_dict = pro.stock_basic().set_index('symbol').to_dict('index')  # 将df转换为字典
            for result in results:
                # Perform second query
                second_query = """
                    SELECT day, low, volume, high
                    FROM stock_zh_a_minute_ol_4
                    WHERE {} > %s AND `name` = %s and `day` > %s and `day` < %s
                    ORDER BY `day` ASC 
                    LIMIT 1
                """.format(str(gain_type))

                cursor.execute(second_query, (gain_threshold, result['t2name'], start_date, end_date))
                second_result = cursor.fetchone()

                third_query = """
                    SELECT day, low, volume, high, rname
                    FROM stock_zh_a_minute_ol_4 
                    WHERE {} > %s AND `name` = %s and `day` > %s and `day` < %s
                    ORDER BY `day` DESC 
                    LIMIT 1
                """.format(str(gain_type))
                cursor.execute(third_query, (gain_threshold, result['t2name'], start_date, end_date))
                third_result = cursor.fetchone()
                
                forth_query = """
                    SELECT 
                        COUNT(CASE WHEN rise_continue = 1 THEN 1 END) AS num_rise_continue,
                        COUNT(CASE WHEN turnover > 15 THEN 1 END) AS num_turnover_rate_gt_015
                    FROM 
                        stock_zh_a_daily
                    WHERE 
                        code = %s
                        AND date BETWEEN %s AND %s;
                """
                cursor.execute(forth_query, (result['t2name'], start_date, end_date))
                forth_result = cursor.fetchone()
                
                code_tmp = result["t2name"]

                stock_info = all_stock_info.get(code_tmp)
                # 判断上海还是 深圳，东方财富 接口要求。
                if code_tmp.startswith("6"):
                    code_tmp = "sh" + code_tmp
                else:
                    code_tmp = "sz" + code_tmp
                
            
                url_1 = 'http://quote.eastmoney.com/%s.html' % code_tmp
                #url_2 = 'http://finance.sina.com.cn/realstock/company/%s/nc.shtml' % code_tmp
                url_2 = 'http://stockpage.10jqka.com.cn/%s/' % code_tmp[2:]
                result['rname'] = third_result['rname']
                # Add second query results to first query results
                if float(second_result['low']) == 0:
                    result['price_diff'] = "100%"
                else:
                    result['price_diff'] = str(round((float(third_result['high']) - float(second_result['low']))/float(second_result['low'])*100, 2)) + "%"
                
                if float(second_result['volume']) == 0:
                    result['volume_diff'] = "100%"
                else:
                    result['volume_diff'] = str(round((float(third_result['volume']) - float(second_result['volume']))/float(second_result['volume'])*100, 2)) + "%"
                result['gain_start_date'] = str(second_result['day'])
                result['gain_end_date'] = str(third_result['day'])
                result['url_1'] = url_1
                result['url_2'] = url_2
                result['url_3'] = "/login"
                result['num_rise_continue_5day'] = forth_result['num_rise_continue']
                result['num_turnover_rate_gt_015'] = forth_result['num_turnover_rate_gt_015']
                if stock_info is not None:
                    # Add stock concept and industry to result
                    result['market'] = stock_info.get('market', '')
                    result['industry'] = stock_info.get('industry', '')
                else:
                    result['market'] = '未知'
                    result['industry'] = '未知'
                # 将结果添加到字典中
                response_dict[result['t2name']] = result

            # 按照t2name排序
            results_sorted = sorted(results, key=lambda x: x['t2name'])
            response_sorted = sorted(response_dict.values(), key=lambda x: x['t2name'])
            end_time = time.time()
            logging.info(f"总查询时间，执行时间为 {end_time - start_time:.6f} 秒")
            # 将两个列表合并为一个列表
            response = [dict(r.items()) for r in response_sorted]

            return jsonify(response)

    finally:
        connection.close()
if __name__ == '__main__':
    app.run(debug=True)
