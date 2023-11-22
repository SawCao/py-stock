import tushare as ts

pro = ts.pro_api('0a42c03559605acecb58cca7218b5f6736f1ea878e20a090b2077bdf')


df = pro.stock_basic()
data_dict = df.set_index('symbol').to_dict('index')  # 将df转换为字典
result = []
symbols = ['000001', '000002']  # 示例symbol的列表
for symbol in symbols:
    temp_dict = {"market": data_dict[symbol]['market'], 
                 "industry": data_dict[symbol]['industry']}
    result.append(temp_dict)
print(result)