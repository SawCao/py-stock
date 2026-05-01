import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Form, 
  Input, 
  Select, 
  DatePicker, 
  Button, 
  Table, 
  Space, 
  Tag,
  Spin,
  Row,
  Col,
  message 
} from 'antd';
import { SearchOutlined, ExportOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'umi';
import dayjs from 'dayjs';
import './index.less';

const { RangePicker } = DatePicker;
const { Option } = Select;

interface StockData {
  t2name: string;
  rname: string;
  gain_Amplitude_num: number;
  price_diff: string;
  volume_diff: string;
  gain_start_date: string;
  gain_end_date: string;
  market: string;
  industry: string;
  num_rise_continue_5day: number;
  num_turnover_rate_gt_015: number;
  url_1: string;
  url_2: string;
}

const Index: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<StockData[]>([]);
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();
  

  const gainTypeOptions = [
    { value: 'Gain_5', label: '5分钟' },
    { value: 'Gain_6', label: '6分钟' },
    { value: 'Gain_7', label: '7分钟' },
    { value: 'Gain_8', label: '8分钟' },
    { value: 'Gain_9', label: '9分钟' },
    { value: 'Gain_10', label: '10分钟' },
    { value: 'Gain_15', label: '15分钟' },
    { value: 'Gain_20', label: '20分钟' },
    { value: 'Gain_30', label: '30分钟' },
    { value: 'Gain_60', label: '60分钟' },
  ];

  const columns: ColumnsType<StockData> = [
    {
      title: '股票',
      dataIndex: 'rname',
      key: 'rname',
      fixed: 'left',
      width: 60,
      render: (text: string, record: StockData) => (
        <div
          onClick={() => navigate(`/money-flow/${record.t2name}`)}
          style={{ cursor: 'pointer', color: '#1890ff' }}
        >
          {text}
          <br />
          ({record.t2name})
        </div>
      ),
    },
    {
      title: '筛选次数',
      dataIndex: 'gain_Amplitude_num',
      key: 'gain_Amplitude_num',
      sorter: (a, b) => a.gain_Amplitude_num - b.gain_Amplitude_num,
      defaultSortOrder: 'descend',
      width: 50,
      fixed: 'left',
    },
        {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
      width: 60,
      filters: Array.from(new Set(data.map(item => item.industry))).map(industry => ({
        text: industry,
        value: industry,
      })),
      onFilter: (value, record) => record.industry === value,
    },

        {
      title: '跳转',
      key: 'action',
      width: 75,
      render: (_, record) => (
        <Space direction="vertical">
          <Button
            type="primary"
            size="small"
            icon={<ExportOutlined />}
            href={record.url_1}
            target="_blank"
          >
            东财
          </Button>
          <Button
            type="default"
            size="small"
            icon={<ExportOutlined />}
            href={record.url_2}
            target="_blank"
          >
            同花顺
          </Button>
        </Space>
      ),
    },
    {
      title: '价格差值比例',
      dataIndex: 'price_diff',
      key: 'price_diff',
      render: (text) => (
        <Tag color={text.startsWith('-') ? 'green' : 'red'}>{text}</Tag>
      ),
      width: 60,
    },
    {
      title: '成交量差值比例',
      dataIndex: 'volume_diff',
      key: 'volume_diff',
      render: (text) => (
        <Tag color={text.startsWith('-') ? 'green' : 'red'}>{text}</Tag>
      ),
      width: 60,
    },
    {
      title: '最早筛选时间',
      dataIndex: 'gain_start_date',
      key: 'gain_start_date',
      width: 120,
    },
    {
      title: '最晚筛选时间',
      dataIndex: 'gain_end_date',
      key: 'gain_end_date',
      width: 120,
    },
    {
      title: '连续5天上涨天数',
      dataIndex: 'num_rise_continue_5day',
      key: 'num_rise_continue_5day',
      sorter: (a, b) => a.num_rise_continue_5day - b.num_rise_continue_5day,
      width: 40,
    },
    {
      title: '换手率>15%天数',
      dataIndex: 'num_turnover_rate_gt_015',
      key: 'num_turnover_rate_gt_015',
      sorter: (a, b) => a.num_turnover_rate_gt_015 - b.num_turnover_rate_gt_015,
      width: 40,
    },
        {
      title: '概念板块',
      dataIndex: 'market',
      key: 'market',
      width: 60,
      filters: Array.from(new Set(data.map(item => item.market))).map(market => ({
        text: market,
        value: market,
      })),
      onFilter: (value, record) => record.market === value,
    },

  ];

  const fetchData = async (params: any) => {
    setLoading(true);
    
    // 检查是否有登录失败标识
    const loginFailed = localStorage.getItem('loginFailed');
    if (loginFailed === 'true' || loginFailed === null) {
      // 如果有登录失败标识，直接返回500错误
      message.error('服务器错误，无法获取数据');
      setData([]);
      setLoading(false);
      return;
    }
    
    try {
      const queryParams = new URLSearchParams({
        gain_threshold: params.gain_threshold || '0.03',
        start_date: params.start_date || dayjs().subtract(10, 'days').format('YYYY-MM-DD'),
        end_date: params.end_date || dayjs().format('YYYY-MM-DD'),
        gain_type: params.gain_type || 'Gain_5',
        search: params.search || '',
      });

      const response = await fetch(`/api/stock_search?${queryParams}`);
      const result = await response.json();
      
      setData(result);
    } catch (error) {
      message.error('获取数据失败，请稍后重试');
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const onFinish = (values: any) => {
    const params = {
      gain_threshold: values.gain_threshold,
      start_date: values.dateRange[0].format('YYYY-MM-DD'),
      end_date: values.dateRange[1].format('YYYY-MM-DD'),
      gain_type: values.gain_type,
      search: values.stock_filter,
    };
    
    fetchData(params);
  };

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchText(value);
  };

  useEffect(() => {
    // 初始加载数据
    const initialParams = {
      gain_threshold: '0.03',
      start_date: dayjs().subtract(10, 'days').format('YYYY-MM-DD'),
      end_date: dayjs().format('YYYY-MM-DD'),
      gain_type: 'Gain_5',
      search: '',
    };
    fetchData(initialParams);
    
    // 设置表单初始值
    form.setFieldsValue({
      gain_threshold: '0.03',
      dateRange: [dayjs().subtract(10, 'days'), dayjs()],
      gain_type: 'Gain_5',
    });
  }, []);

  return (
    <div className="stock-container">
      <div className="system-banner">
        <h1>帮赛系统</h1>
      </div>
      <Card className="search-card">
        <Form form={form} onFinish={onFinish} layout="inline">
          <Row gutter={16} style={{ width: '100%' }}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="stock_filter" label="股票名称/代码">
                <Input
                  placeholder="请输入名称或代码"
                  onChange={handleSearch}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="gain_threshold" label="筛选率">
                <Input placeholder="请输入筛选率" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={8}>
              <Form.Item name="dateRange" label="时间段">
                <RangePicker
                  format="YYYY-MM-DD"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="gain_type" label="筛选区间">
                <Select placeholder="请选择筛选区间">
                  {gainTypeOptions.map(option => (
                    <Option key={option.value} value={option.value}>
                      {option.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={4}>
              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
                  查询
                </Button>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>

      <Card className="table-card">
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={data}
            rowKey="t2name"
            scroll={{ x: 1500 }}
            pagination={{
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条记录`,
              pageSizeOptions: [10, 20, 50, 100],
              defaultPageSize: 50,
            }}
          />
        </Spin>
      </Card>
    </div>
  );
};

export default Index;
