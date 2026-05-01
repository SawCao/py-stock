import React, { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import './login.less';

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = (values: { password: string }) => {
    setLoading(true);
    
    // 模拟验证密码
    if (values.password === '110548') {
      message.success('登录成功！');
      // 清除登录失败标识
      localStorage.setItem('loginFailed', 'false');
      navigate('/index');
    } else {
      // 密码错误也跳转到index页面，但设置登录失败标识
      localStorage.setItem('loginFailed', 'true');
      navigate('/index');
    }
    
    setLoading(false);
  };

  return (
    <div className="login-container">
      <Card className="login-card" title="帮赛系统登录">
        <Form
          name="login"
          onFinish={onFinish}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
            />
          </Form.Item>
          
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login;
