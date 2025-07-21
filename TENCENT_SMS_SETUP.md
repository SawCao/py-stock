# 腾讯云短信服务配置指南

本文档介绍如何将SMSNotifier从阿里云短信服务切换到腾讯云短信服务。

## 1. 腾讯云短信服务配置

### 1.1 获取腾讯云API密钥

1. 登录[腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入[访问管理](https://console.cloud.tencent.com/cam/overview)
3. 创建或获取SecretId和SecretKey
4. 确保账号有短信服务权限

### 1.2 创建短信应用

1. 进入[短信服务控制台](https://console.cloud.tencent.com/smsv2)
2. 创建短信应用，获取应用ID（SmsSdkAppId）
3. 申请短信签名
4. 创建短信模板，获取模板ID

### 1.3 环境变量配置

在`.env`文件中添加以下配置：

```bash
# 腾讯云短信配置（推荐）
TENCENT_SECRET_ID=你的SecretId
TENCENT_SECRET_KEY=你的SecretKey
TENCENT_SMS_APP_ID=你的短信应用ID
TENCENT_SMS_SIGN_NAME=你的短信签名
TENCENT_SMS_TEMPLATE_ID=你的短信模板ID

# 短信通知手机号（多个用逗号分隔）
SMS_PHONE_NUMBERS=13800138000,13900139000
```

## 2. 短信模板配置

### 2.1 模板内容示例

**模板名称**: 股票数据更新通知
**模板内容**: `您的股票数据更新任务{message}，请关注系统状态。`
**模板参数**: message（字符串类型）

### 2.2 模板审核

提交模板后，需要等待腾讯云审核通过才能使用。

## 3. 使用方法

### 3.1 在代码中使用

```python
from sms_sender import get_sms_sender

# 获取短信发送实例
sms = get_sms_sender()

# 发送短信
phone_numbers = ["13800138000"]
template_param = {"message": "已完成更新"}
result = sms.send_sms(phone_numbers, template_param)

if result.get('success'):
    print("短信发送成功")
else:
    print(f"发送失败: {result.get('message')}")
```

### 3.2 在定时任务中使用

系统会自动检测环境变量配置：
- 优先使用腾讯云SMS（如果配置了TENCENT_SECRET_ID等）
- 回退到阿里云SMS（如果配置了ALIYUN_ACCESS_KEY_ID等）
- 最后使用简化SMS（仅日志记录）

## 4. 测试短信发送

运行测试命令：

```bash
# 设置环境变量
export TENCENT_SECRET_ID=your-secret-id
export TENCENT_SECRET_KEY=your-secret-key
export TENCENT_SMS_APP_ID=your-app-id
export TENCENT_SMS_SIGN_NAME=your-sign-name
export TENCENT_SMS_TEMPLATE_ID=your-template-id
export SMS_PHONE_NUMBERS=your-phone-number

# 测试短信发送
python sms_sender.py
```

## 5. 常见问题

### 5.1 签名失败
- 检查SecretId和SecretKey是否正确
- 确认账号有短信服务权限
- 检查时间同步（腾讯云API对时间敏感）

### 5.2 模板参数错误
- 确保模板参数与模板内容匹配
- 检查参数类型是否正确
- 确认模板已通过审核

### 5.3 手机号格式
- 支持中国大陆手机号（11位数字）
- 支持带国际区号的格式（如+8613800138000）
- 支持86开头的格式（如8613800138000）

## 6. 阿里云SMS向后兼容

为了向后兼容，系统仍然支持阿里云SMS配置：

```bash
# 阿里云短信配置（可选）
ALIYUN_ACCESS_KEY_ID=your-access-key-id
ALIYUN_ACCESS_KEY_SECRET=your-access-key-secret
ALIYUN_SMS_SIGN_NAME=阿里云短信测试
ALIYUN_SMS_TEMPLATE_CODE=SMS_154950909
```

## 7. 注意事项

1. **费用**: 腾讯云短信按条计费，请确保账户余额充足
2. **频率限制**: 注意短信发送频率限制，避免触发风控
3. **模板审核**: 新模板需要审核，建议提前准备
4. **测试环境**: 建议先在测试环境验证配置正确性

## 8. 技术支持

- [腾讯云短信文档](https://cloud.tencent.com/document/product/382)
- [腾讯云API Explorer](https://console.cloud.tencent.com/api/explorer)
- [错误码查询](https://cloud.tencent.com/document/product/382/38778)
