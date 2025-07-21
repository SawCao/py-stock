#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云短信发送模块
支持中国大陆手机号短信发送
"""

import os
import sys
import json
import uuid
import hmac
import hashlib
import base64
import urllib.parse
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TencentSMS:
    """腾讯云短信服务类"""
    
    def __init__(self, secret_id=None, secret_key=None, app_id=None, sign_name=None, template_id=None):
        """
        初始化腾讯云短信服务
        
        Args:
            secret_id: 腾讯云SecretId
            secret_key: 腾讯云SecretKey
            app_id: 短信应用ID
            sign_name: 短信签名内容
            template_id: 短信模板ID
        """
        self.secret_id = secret_id or os.getenv('TENCENT_SECRET_ID', '')
        self.secret_key = secret_key or os.getenv('TENCENT_SECRET_KEY', '')
        self.app_id = app_id or os.getenv('TENCENT_SMS_APP_ID', '')
        self.sign_name = sign_name or os.getenv('TENCENT_SMS_SIGN_NAME', '')
        self.template_id = template_id or os.getenv('TENCENT_SMS_TEMPLATE_ID', '')
        self.domain = 'sms.tencentcloudapi.com'
        self.service = 'sms'
        self.version = '2021-01-11'
        self.region = 'ap-beijing'  # 默认北京区域
        
    def sign_request(self, params, headers):
        """计算腾讯云API签名"""
        # 腾讯云签名算法
        http_method = 'POST'
        canonical_uri = '/'
        canonical_querystring = ''
        
        # 构建规范头部
        canonical_headers = ''
        signed_headers = ''
        for key in sorted(headers.keys()):
            canonical_headers += key.lower() + ':' + headers[key] + '\n'
            signed_headers += key.lower() + ';'
        signed_headers = signed_headers[:-1]
        
        # 构建规范请求
        payload = json.dumps(params)
        hashed_request_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = (http_method + '\n' +
                           canonical_uri + '\n' +
                           canonical_querystring + '\n' +
                           canonical_headers + '\n' +
                           signed_headers + '\n' +
                           hashed_request_payload)
        
        # 构建待签名字符串
        algorithm = 'TC3-HMAC-SHA256'
        request_timestamp = str(int(datetime.now().timestamp()))
        credential_scope = request_timestamp[:8] + '/' + self.service + '/tc3_request'
        string_to_sign = (algorithm + '\n' +
                         request_timestamp + '\n' +
                         credential_scope + '\n' +
                         hashlib.sha256(canonical_request.encode('utf-8')).hexdigest())
        
        # 计算签名
        secret_date = hmac.new(('TC3' + self.secret_key).encode('utf-8'),
                              request_timestamp[:8].encode('utf-8'),
                              hashlib.sha256).digest()
        secret_service = hmac.new(secret_date, self.service.encode('utf-8'), hashlib.sha256).digest()
        secret_signing = hmac.new(secret_service, 'tc3_request'.encode('utf-8'), hashlib.sha256).digest()
        signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # 构建Authorization头部
        authorization = (algorithm + ' ' +
                        'Credential=' + self.secret_id + '/' + credential_scope + ', ' +
                        'SignedHeaders=' + signed_headers + ', ' +
                        'Signature=' + signature)
        
        return authorization, request_timestamp
    
    def send_sms(self, phone_numbers, template_param=None):
        """
        发送短信
        
        Args:
            phone_numbers: 手机号列表或单个手机号
            template_param: 模板参数，dict类型
            
        Returns:
            dict: 发送结果
        """
        if not self.secret_id or not self.secret_key or not self.app_id:
            logger.error("未配置腾讯云SMS密钥")
            return {'success': False, 'message': '未配置腾讯云SMS密钥'}
        
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]
        
        # 过滤中国大陆手机号格式
        formatted_phones = []
        for phone in phone_numbers:
            phone = phone.strip()
            if phone.startswith('86'):
                phone = '+' + phone
            elif not phone.startswith('+'):
                phone = '+86' + phone
            formatted_phones.append(phone)
        
        # 构建请求参数
        params = {
            "SmsSdkAppId": self.app_id,
            "SignName": self.sign_name,
            "TemplateId": self.template_id,
            "TemplateParamSet": [str(v) for v in template_param.values()] if template_param else [],
            "PhoneNumberSet": formatted_phones
        }
        
        # 构建请求头部
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Host': self.domain,
            'X-TC-Action': 'SendSms',
            'X-TC-Version': self.version,
            'X-TC-Region': self.region,
            'X-TC-Timestamp': str(int(datetime.now().timestamp()))
        }
        
        # 计算签名
        authorization, timestamp = self.sign_request(params, headers)
        headers['Authorization'] = authorization
        headers['X-TC-Timestamp'] = timestamp
        
        try:
            url = f"https://{self.domain}"
            response = requests.post(url, headers=headers, json=params, timeout=10)
            result = response.json()
            
            if 'Response' in result:
                response_data = result['Response']
                if 'SendStatusSet' in response_data:
                    send_status = response_data['SendStatusSet'][0]
                    if send_status.get('Code') == 'Ok':
                        logger.info(f"短信发送成功: {phone_numbers}")
                        return {'success': True, 'message': '发送成功', 'data': response_data}
                    else:
                        error_msg = send_status.get('Message', '发送失败')
                        logger.error(f"短信发送失败: {error_msg}")
                        return {'success': False, 'message': error_msg, 'data': response_data}
                else:
                    error_msg = response_data.get('Error', {}).get('Message', '发送失败')
                    logger.error(f"短信发送失败: {error_msg}")
                    return {'success': False, 'message': error_msg, 'data': response_data}
            else:
                logger.error(f"短信发送失败: {result}")
                return {'success': False, 'message': '接口返回异常', 'data': result}
                
        except Exception as e:
            logger.error(f"短信发送异常: {str(e)}")
            return {'success': False, 'message': str(e)}

class AliyunSMS:
    """阿里云短信服务类（保留向后兼容）"""
    
    def __init__(self, access_key_id=None, access_key_secret=None, sign_name=None, template_code=None):
        """
        初始化阿里云短信服务
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            sign_name: 短信签名名称
            template_code: 短信模板CODE
        """
        self.access_key_id = access_key_id or os.getenv('ALIYUN_ACCESS_KEY_ID', '')
        self.access_key_secret = access_key_secret or os.getenv('ALIYUN_ACCESS_KEY_SECRET', '')
        self.sign_name = sign_name or os.getenv('ALIYUN_SMS_SIGN_NAME', '阿里云短信测试')
        self.template_code = template_code or os.getenv('ALIYUN_SMS_TEMPLATE_CODE', 'SMS_154950909')
        self.domain = 'dysmsapi.aliyuncs.com'
        self.version = '2017-05-25'
        self.region_id = 'cn-hangzhou'
        
    def percent_encode(self, encode_str):
        """URL编码"""
        encode_str = str(encode_str)
        res = urllib.parse.quote(encode_str, '')
        res = res.replace('+', '%20')
        res = res.replace('*', '%2A')
        res = res.replace('%7E', '~')
        return res
    
    def sign_string(self, string_to_sign, access_key_secret):
        """计算签名"""
        h = hmac.new(access_key_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(h.digest()).decode('utf-8')
        return signature
    
    def build_common_params(self):
        """构建公共参数"""
        return {
            'Format': 'JSON',
            'Version': self.version,
            'AccessKeyId': self.access_key_id,
            'SignatureMethod': 'HMAC-SHA1',
            'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'SignatureVersion': '1.0',
            'SignatureNonce': str(uuid.uuid4()),
            'RegionId': self.region_id
        }
    
    def send_sms(self, phone_numbers, template_param=None):
        """
        发送短信
        
        Args:
            phone_numbers: 手机号列表或单个手机号
            template_param: 模板参数，dict类型
            
        Returns:
            dict: 发送结果
        """
        if not self.access_key_id or not self.secret_key:
            logger.error("未配置阿里云AccessKey")
            return {'success': False, 'message': '未配置阿里云AccessKey'}
        
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]
        
        # 构建请求参数
        params = self.build_common_params()
        params.update({
            'Action': 'SendSms',
            'PhoneNumbers': ','.join(phone_numbers),
            'SignName': self.sign_name,
            'TemplateCode': self.template_code
        })
        
        if template_param:
            params['TemplateParam'] = json.dumps(template_param)
        
        # 排序参数
        sorted_params = sorted(params.items(), key=lambda item: item[0])
        
        # 构建待签名字符串
        canonicalized_query_string = ''
        for k, v in sorted_params:
            canonicalized_query_string += '&' + self.percent_encode(k) + '=' + self.percent_encode(v)
        
        string_to_sign = 'GET&%2F&' + self.percent_encode(canonicalized_query_string[1:])
        
        # 计算签名
        signature = self.sign_string(string_to_sign, self.access_key_secret + '&')
        params['Signature'] = signature
        
        # 构建请求URL
        url = f"https://{self.domain}/?{urllib.parse.urlencode(params)}"
        
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if 'Code' in result and result['Code'] == 'OK':
                logger.info(f"短信发送成功: {phone_numbers}")
                return {'success': True, 'message': '发送成功', 'data': result}
            else:
                logger.error(f"短信发送失败: {result}")
                return {'success': False, 'message': result.get('Message', '发送失败'), 'data': result}
                
        except Exception as e:
            logger.error(f"短信发送异常: {str(e)}")
            return {'success': False, 'message': str(e)}

class SimpleSMS:
    """简化短信发送类 - 用于测试和演示"""
    
    def __init__(self):
        self.phone_numbers = os.getenv('SMS_PHONE_NUMBERS', '').split(',')
        
    def send(self, message, phone_numbers=None):
        """发送短信（简化版本）"""
        if phone_numbers is None:
            phone_numbers = self.phone_numbers
        
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]
        
        # 过滤空手机号
        phone_numbers = [phone for phone in phone_numbers if phone.strip()]
        
        if not phone_numbers:
            logger.warning("没有配置有效的手机号")
            return False
        
        # 模拟发送
        for phone in phone_numbers:
            logger.info(f"模拟发送短信到 {phone}: {message}")
        
        return True

# 全局短信发送实例
def get_sms_sender():
    """获取短信发送实例"""
    # 优先使用腾讯云SMS
    if os.getenv('TENCENT_SECRET_ID') and os.getenv('TENCENT_SECRET_KEY') and os.getenv('TENCENT_SMS_APP_ID'):
        return TencentSMS()
    # 回退到阿里云SMS
    elif os.getenv('ALIYUN_ACCESS_KEY_ID') and os.getenv('ALIYUN_ACCESS_KEY_SECRET'):
        return AliyunSMS()
    else:
        logger.warning("使用简化短信发送器，请配置腾讯云或阿里云SMS以使用真实短信服务")
        return SimpleSMS()

# 使用示例
if __name__ == '__main__':
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 测试短信发送
    sms = get_sms_sender()
    
    # 测试消息
    test_message = "测试短信发送功能 - 股票数据更新任务"
    
    # 获取手机号
    phone_numbers = os.getenv('SMS_PHONE_NUMBERS', '').split(',')
    if phone_numbers and phone_numbers[0]:
        # 腾讯云SMS使用模板参数
        if isinstance(sms, TencentSMS):
            template_param = {"code": "123456", "time": "10分钟"}
            result = sms.send_sms(phone_numbers, template_param)
        else:
            result = sms.send(test_message, phone_numbers)
        print(f"发送结果: {result}")
    else:
        print("请设置SMS_PHONE_NUMBERS环境变量")
