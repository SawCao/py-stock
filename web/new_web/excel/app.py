from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_excel import init_excel, make_response_from_array
import pandas as pd
import security
import onCall
import json
from flask import Markup
import ast
import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) # Secret key
init_excel(app)

data = {
    "当前时间": "2023-01-01 00:00:00",  
    
    "正式提交": "否", 
    
    "排班开始时间": "2021-01-01",
    
    "排班结束时间": "2021-01-31",
    
    "请假表":{},
    
    "带班领导":["文伟钿", "蔡应谦", "范锦炎", "丁银才", "马立光", "宗广荣"],
    
    "值班领导":["杨伟", "李伟嘉", "林国胜", "吴钦辉", "林经智", "林瑞锋", "郑康弟"],
    
    "主班民警":["林奕兵", "周文迅", "洪永海", "王彪", "林少程", "许夏阳", "邱华先", "徐卓辉", "林建辉", "张少卫", "郑文斌", "高泽波", "肖建全", "李耘", "陈旭彬", "许小刚", "杨少鸿", "林静山", "张仲凯", "陈敬斌", "马少雄", "陈雄文", "吕俊伟", "林敬钦", "朱少辉", "郑桂峰", "吴贤才", "黄献忠", "李业雄", "陈佳建", "王江勇"],
    
    "副班民警":["王江勇", "陈佳建", "李业雄", "黄献忠", "吴贤才", "郑桂峰", "朱少辉", "林敬钦", "吕俊伟", "陈雄文", "马少雄", "陈敬斌", "张仲凯", "林静山", "杨少鸿", "陈旭彬", "李耘", "许小刚", "肖建全", "高泽波", "郑文斌", "张少卫", "林建辉", "徐卓辉", "邱华先", "许夏阳", "林少程", "王彪", "洪永海", "周文迅", "林奕兵"],

    "第一中队（辅警）": [
    "李楷锋13068998802", "杨坚凯15817930211", 
    "王育彬13342740810", "黄春山13924789065",
    "翁培嘉18823991992", "陈汉强15876154500", 
    "林荣毅15876172597", "刘涛13719921969",
    "林烁13025224218", "罗松滨15817942205", 
    "陈祺涛18998249232", "连益民15916647050",
    "赵嘉诺13288001655", "林晓丹13192370536"],
    
    "第二中队（辅警）": [
    "余昌元15815015018", "张锦杰15815091983",
    "张海斌16607549896", "林怡荣15815102866",
    "余斌强16626101117", "赖栋15816617195",
    "许荣腾13682882743", "廖继乾13546824415",
    "谢振涛13428333019", "林喜镇15889213774",
    "林源15989845432", "翁建平15019725014",
    "余泽斌15916622787", "陈鳅洋13501414442"],
    
    "第三中队（辅警）": [
    "胡煜15815068798", "林少伟15019706212",
    "唐惟识13531163344", "吴烨源15019778688",
    "林泽佳15992281749", "吴承焓13433828298",
    "陈少伟13415198944", "范玮欣15875464046",
    "黄钦峰13016660014", "黄腾13428302081",
    "许晓章13825889679", "吴坤宏13411931755",
    "陈泽斌13414073644"],
    
    "第五中队（辅警）": [
    "翁介南18029558755", "陈程鹏15113117722",
    "詹世鑫13226816365", "谢思凯13539656383",
    "陈杰彬13794104401", "朱延鑫13682875298",
    "林俊鑫17607549713", "陈华佳13226827920",
    "蔡国森13682877737", "陈佳豪13433854018"],
    
    "骑警中队（辅警）": [
    "陈胜洲13502997495", "庄锦坤15815000994", 
    "谢燕彬13028187978", "王金湖13556450433", 
    "郑裕亮13829691586", "邱源18675455859", 
    "方捷15816615469", "方鸿18664464272",
    "高涛18811125186", "刘灵驱15889251774", 
    "陈宇泓13113491860", "高塬辉13246082668",
    "黄少涵13428314449", "吴绍吉13428319568", 
    "刘拥军15626170755"],  
}

oncall_points = {
    "time":"",
    "main_leader_point":0,
    "deputy_leader_point":0,
    "deputy_leader_emptypoint":0,
    "sub_police_points":[0,0,0,0,0],
    "sub_police_curr_team": 0, 
    "main_police_point":0, 
    "deputy_police_point":0,
}

securityObject_points = {
    "time":"",
    "main_police_point":0,
    "security_points":[0,0,0,0,0],
    "security_curr_team":0,
    "security_next_team": 1,
}

# Set your password here
EDIT_PASS = "ct855"
SHOW_PASS = "091161"
DOWNLOAD_FOLDER = "./static/spreadsheets/"

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form["password"] == EDIT_PASS:
            session["logged_in_edit"] = True
            return redirect(url_for("index"))
        if request.form["password"] == SHOW_PASS:
            session["logged_in_show"] = True
            return redirect(url_for("show"))
        else:
            error = "密码错误"
    return render_template("login.html", error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route("/")
def index():
    if not session.get("logged_in_edit") and session.get("logged_in_show"):
        return redirect(url_for("show"))
    if not session.get("logged_in_edit") and not session.get("logged_in_show"):
        return redirect(url_for("login"))
    else:
        with open('data.json') as f:
            lines = f.readlines()
        data = json.loads(lines[-1].strip())
        return render_template("index.html", data=data)

@app.route("/show")
def show():
    if not session.get("logged_in_show"):
        return redirect(url_for("login"))
    else:
        with open('data.json') as f:
            lines = f.readlines()
        data = json.loads(lines[-1].strip())
        return render_template("just_show.html", data=data)
    
@app.route("/sheet/<sheet>")
def get_sheet(sheet):
    if sheet == "one": df = pd.read_excel("one.xlsx") 
    elif sheet == "two": df = pd.read_excel("two.xlsx") 
    else: return "无法找到该表格", 404
    sheet_name = 'Sheet1'
    return make_response_from_array(df.values, file_type='html', status=200, sheet_name=sheet_name)

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route("/update-data", methods=["POST"])
def update_data(): 
    global data
    
    new_data = request.form.to_dict()
    now = datetime.datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
    new_data["当前时间"] = formatted_date
    
    start_date = new_data["排班开始时间"]
    end_date = new_data["排班结束时间"]
    vacation_dict = ast.literal_eval(new_data["请假表"])
    main_leaders = ast.literal_eval(new_data["带班领导"])
    deputy_leaders = ast.literal_eval(new_data["值班领导"])
    main_police = ast.literal_eval(new_data["主班民警"])
    deputy_police = ast.literal_eval(new_data["副班民警"])
    leadership = [main_leaders, deputy_leaders, main_police, deputy_police]
    zhongdui1 = ast.literal_eval(new_data["第一中队（辅警）"])
    zhongdui2 = ast.literal_eval(new_data["第二中队（辅警）"])
    zhongdui3 = ast.literal_eval(new_data["第三中队（辅警）"])
    zhongdui5 = ast.literal_eval(new_data["第五中队（辅警）"])
    zhongdui6 = ast.literal_eval(new_data["骑警中队（辅警）"])
    sub_teams_asc = [zhongdui1, zhongdui2, zhongdui3, zhongdui5, zhongdui6]
    sub_teams_desc = [zhongdui6, zhongdui5, zhongdui3, zhongdui2, zhongdui1]
    print(new_data)
    
    # 读取历史的打点记录
    with open('data_oncall_point.json') as f:
        lines = f.readlines()
    oncall_points = json.loads(lines[-1].strip())
    with open('data_security_point.json') as f:
        lines = f.readlines()
    securityObject_points = json.loads(lines[-1].strip())

    oncall = onCall.onCallExcel(start_date, end_date, leadership, sub_teams_asc, 
                                vacation_dict, oncall_points["main_leader_point"], oncall_points["deputy_leader_point"], oncall_points["deputy_leader_emptypoint"],
                                oncall_points["sub_police_points"], oncall_points["sub_police_curr_team"], oncall_points["main_police_point"], oncall_points["deputy_police_point"])
    oncall.RUN()
    oncall_points["main_leader_point"] = oncall.main_leader_point
    oncall_points["deputy_leader_point"] = oncall.deputy_leader_point
    oncall_points["deputy_leader_emptypoint"] = oncall.deputy_leader_emptypoint
    oncall_points["sub_police_points"] = oncall.sub_police_points
    oncall_points["sub_police_curr_team"] = oncall.sub_police_curr_team 
    oncall_points["main_police_point"] = oncall.main_police_point 
    oncall_points["deputy_police_point"] = oncall.deputy_police_point
    oncall_points["time"] = formatted_date
    
    securityObject = security.securityExcel(start_date, end_date, leadership, sub_teams_desc, vacation_dict, securityObject_points["main_police_point"], 
                                            securityObject_points["security_points"], securityObject_points["security_curr_team"], securityObject_points["security_next_team"])
    securityObject.RUN()
    securityObject_points["main_police_point"] = securityObject.main_police_point 
    securityObject_points["security_points"] = securityObject.security_points
    securityObject_points["security_curr_team"] = securityObject.security_curr_team
    securityObject_points["security_next_team"] = securityObject.security_next_team
    securityObject_points["time"] = formatted_date
    
    
    
    if new_data["正式提交"] != "否":
        # 将Python对象序列化为JSON格式，并追加到文件末尾（使用UTF-8编码）
        with open('data_oncall_point.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(oncall_points, ensure_ascii=False) + '\n')
        with open('data_security_point.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(securityObject_points, ensure_ascii=False) + '\n')
        with open('data.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_data, ensure_ascii=False) + '\n')
            
    for key, value in new_data.items():
        # 可根据需要模拟操作进行数据转换
        data[key] = value
    return jsonify(data), 200