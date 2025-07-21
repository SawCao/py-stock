#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云短信服务测试脚本
"""

import os
import sys
import logging
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_tencent_sms():
    """测试腾讯云短信服务"""
    print("=" * 60)
    print("腾讯云短信服务测试")
    print("=" * 60)
    
    # 检查环境变量
    required_vars = [
        'TENCENT_SECRET_ID',
        'TENCENT_SECRET_KEY', 
        'TENCENT_SMS_APP_ID',
        'TENCENT_SMS_SIGN_NAME',
        'TENCENT_SMS_TEMPLATE_ID',
        'SMS_PHONE_NUMBERS'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            print(f"{var}: {value}")
    
    if missing_vars:
        print(f"\n❌ 缺少环境变量: {', '.join(missing_vars)}")
        print("\n请设置以下环境变量:")
        for var in missing_vars:
            print(f"export {var}=your-value")
        return False
    
    print("\n✅ 环境变量配置完整")
    
    try:
        # 测试短信发送
        from sms_sender import get_sms_sender
        sms = get_sms_sender()
        
        # 获取手机号
        phone_numbers = os.getenv('SMS_PHONE_NUMBERS', '').split(',')
        phone_numbers = [p.strip() for p in phone_numbers if p.strip()]
        
        if not phone_numbers:
            print("❌ 没有配置有效的手机号")
            return False
        
        print(f"\n📱 测试手机号: {phone_numbers}")
        
        # 发送测试短信
        test_message = f"腾讯云SMS测试 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        template_param = {"message": test_message}
        
        print(f"\n📤 发送测试短信...")
        result = sms.send_sms(phone_numbers, template_param)
        
        if result.get('success'):
            print("✅ 短信发送成功!")
            print(f"响应: {result.get('data')}")
        else:
            print("❌ 短信发送失败!")
            print(f"错误: {result.get('message')}")
            print(f"详情: {result.get('data')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_tencent_sms()
    sys.exit(0 if success else 1)
