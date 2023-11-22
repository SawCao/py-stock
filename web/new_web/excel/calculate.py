import random
from typing import List, Dict
from datetime import datetime, timedelta

def random_name_assignment(start_date: str, end_date: str, names: List[str], name_dict: Dict[str, List[str]], start_index: int):

    # 将日期字符串转换成datetime格式
    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
    end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
    
    # 计算日期差
    num_days = (end_datetime - start_datetime).days + 1
    
    assigned_names = {date: [] for date in [(start_datetime + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]}
    
    #打乱排序
    # random.shuffle(names)
    index = start_index
    for date in assigned_names:
        if date not in name_dict or (date in name_dict and names[index] not in name_dict[date]):
            assigned_names[date].append(names[index])
        else:
            if index == len(names) - 1:
                index = 0
            else:
                index += 1
            assigned_names[date].append(names[index])
        if index == len(names) - 1:
            index = 0
        else:
            index += 1
    start_index = index
    return assigned_names, index
    
names = ['Alice', 'Bob', 'Charlie', 'David']
name_dict = {'2021-01-02': ['Bob', 'David'], '2021-01-01': ['David']}
num_names_per_day = 0

assigned_names, index = random_name_assignment('2021-01-01', '2021-01-10', names, name_dict, num_names_per_day)
print(assigned_names)