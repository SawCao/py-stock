import pymysql
from flask import Flask, jsonify, request, render_template
import logging
import tushare as ts
import time
import json
import os
import pickle
app = Flask(__name__, static_folder='static')
app.config['DEBUG'] = True
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.route('/', methods=['GET','POST'])
def login():
    return app.send_static_file('login.html')

@app.route('/index', methods=['GET','POST'])
def index():
    return app.send_static_file('index.html')

@app.route('/stock_data', methods=['GET'])
def get_stock_data():
    gain_threshold = request.args.get('gain_threshold', default=0.03, type=float)
    start_date = request.args.get('start_date', default='2023-01-31 00:00:00')
    end_date = request.args.get('end_date', default='2023-01-31 00:00:00')
    gain_type =  request.args.get('gain_type', default='Gain_5')
    return get_stock_resdata(gain_threshold, start_date, end_date, gain_type)


# 缓存tushare的板块数据，这个接口一个小时只能访问一次，坑爹
def save_data_to_file(data_dict):
    with open("data_cache.pickle", "wb") as f:
        pickle.dump(data_dict, f)
    os.utime("data_cache.pickle", (time.time(), time.time()))

def load_data_from_file():
    with open("data_cache.pickle", "rb") as f:
        data_dict = pickle.load(f)
    return data_dict

def get_stock_data():
    if os.path.isfile("data_cache.pickle"):
        file_age_seconds = time.time() - os.path.getmtime("data_cache.pickle")
        if file_age_seconds < 60 * 60 * 24:  # 24 hours
            data_dict = load_data_from_file()
            print("Cache file data is still fresh.")
            return data_dict
    pro = ts.pro_api('0a42c03559605acecb58cca7218b5f6736f1ea878e20a090b2077bdf')
    data_dict = pro.stock_basic().set_index("symbol").to_dict("index")
    save_data_to_file(data_dict)
    print("Data has been fetched and saved to cache.")
    return data_dict

# 缓存每日结果数据
def save_resdata_to_file(gain_threshold, start_date, end_date, gain_type, res):
    file_name = str(gain_threshold) + "_" + str(start_date[:10]) + "_" + str(end_date[:10]) + "_" + str(gain_type) + "_data.pickle"
    with open(file_name, "wb") as f:
        pickle.dump(res, f)
    os.utime(file_name, (time.time(), time.time()))

def load_resdata_from_file(gain_threshold, start_date, end_date, gain_type):
    file_name = str(gain_threshold) + "_" + str(start_date[:10]) + "_" + str(end_date[:10]) + "_" + str(gain_type) + "_data.pickle"
    with open(file_name, "rb") as f:
        data_dict = pickle.load(f)
    return data_dict

def get_stock_resdata(gain_threshold, start_date, end_date, gain_type):
    file_name = str(gain_threshold) + "_" + str(start_date[:10]) + "_" + str(end_date[:10]) + "_" + str(gain_type) + "_data.pickle"
    print("file_name" + file_name)
    if os.path.isfile(file_name):
        file_age_seconds = time.time() - os.path.getmtime(file_name)
        if file_age_seconds < 60 * 60 * 24:  # 24 hours
            data_dict = load_resdata_from_file(gain_threshold, start_date, end_date, gain_type)
            print("Cache file data is still fresh.")
            return data_dict
    res = get_stock_from_db(gain_threshold, start_date, end_date, gain_type)
    save_resdata_to_file(gain_threshold, start_date, end_date, gain_type,res)
    print("Data has been fetched and saved to cache.")
    return res


def get_stock_from_db(gain_threshold, start_date, end_date, gain_type):
    logging.info('ffff')
    # Connect to the database
    connection = pymysql.connect(
        host='mysqldb',
        user='root',
        password='mysqldb',
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
            # Query database
            query = """
                SELECT name as t2name, count(*) as gain_Amplitude_num
                FROM stock_zh_a_minute_ol_2
                WHERE %s > %s and `day` > '%s' and `day` < '%s'
                GROUP BY name
                ORDER BY gain_Amplitude_num DESC
                LIMIT 1000
            """ % (str(gain_type), str(gain_threshold), start_date, end_date)
            
            cursor.execute(query)
            print(cursor.mogrify(query))
            results = cursor.fetchall()
            response_dict = {}  # 存储结果的字典
            print("TEST", results)
            response = []
            end_time = time.time()
            print(f"查询震荡，执行时间为 {end_time - start_time:.6f} 秒")
            try:
                all_stock_info = get_stock_data()
            except:
                all_stock_info = {}
            else:
                print("读取成功！")
            # Load all stock data from tushare into a dictionary
            # data_dict = pro.stock_basic().set_index('symbol').to_dict('index')  # 将df转换为字典
            for result in results:
                # Perform second query
                second_query = """
                    SELECT day, low, volume, high
                
                    FROM stock_zh_a_minute_ol_2 
                    WHERE %s > %s AND `name` = '%s' and `day` > '%s' and `day` < '%s'
                    ORDER BY `day` ASC 
                    LIMIT 1
                """ % (str(gain_type), str(gain_threshold), result['t2name'],start_date, end_date)

                cursor.execute(second_query)
                second_result = cursor.fetchone()

                third_query = """
                    SELECT day, low, volume, high, rname
                    FROM stock_zh_a_minute_ol_2 
                    WHERE %s > %s AND `name` = '%s' and `day` > '%s' and `day` < '%s'
                    ORDER BY `day` DESC 
                    LIMIT 1
                """ % (str(gain_type), str(gain_threshold), result['t2name'],start_date, end_date)
                cursor.execute(third_query)
                third_result = cursor.fetchone()
                
                forth_query = """
                    SELECT 
                        
                        COUNT(CASE WHEN rise_continue = 1 THEN 1 END) AS num_rise_continue,
                        COUNT(CASE WHEN turnover > 0.15 THEN 1 END) AS num_turnover_rate_gt_015
                    FROM 
                        stock_zh_a_daily
                    WHERE 
                        symbol = '%s'
                        AND date BETWEEN '%s' AND '%s';
                """ % (result['t2name'], start_date, end_date)
                cursor.execute(forth_query)
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
            print(f"总查询时间，执行时间为 {end_time - start_time:.6f} 秒")
            # 将两个列表合并为一个列表
            response = [dict(r.items()) for r in response_sorted]

            return jsonify(response)

    finally:
        connection.close()
if __name__ == '__main__':
    app.run(debug=true)
