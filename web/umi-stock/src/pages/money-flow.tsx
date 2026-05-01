import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Typography, Spin, message, Button, DatePicker, Space } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'umi';
import * as echarts from 'echarts';
import dayjs, { Dayjs } from 'dayjs';
import './money-flow.less';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

interface MoneyFlowData {
  time: string;
  inflow: number;
  outflow: number;
  netflow: number;
}

interface StockInfo {
  stockCode: string;
  stockName: string;
}

const MoneyFlow: React.FC = () => {
  const { stockCode } = useParams<{ stockCode: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [moneyFlowData, setMoneyFlowData] = useState<MoneyFlowData[]>([]);
  const [flowChartInstance, setFlowChartInstance] = useState<echarts.ECharts | null>(null);
  const [netflowChartInstance, setNetflowChartInstance] = useState<echarts.ECharts | null>(null);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(10, 'days'),
    dayjs()
  ]);

  useEffect(() => {
    if (stockCode) {
      fetchMoneyFlowData();
    }
  }, [stockCode, dateRange]);

  useEffect(() => {
    if (moneyFlowData.length > 0) {
      initFlowChart();
      initNetflowChart();
    }
  }, [moneyFlowData]);

  const fetchMoneyFlowData = async () => {
    setLoading(true);
    try {
      const startDate = dateRange[0].format('YYYY-MM-DD');
      const endDate = dateRange[1].format('YYYY-MM-DD');
      
      const response = await fetch(
        `/api/money_flow/${stockCode}?start_date=${startDate}&end_date=${endDate}`
      );
      const data = await response.json();
      
      if (data.error) {
        message.error(data.error);
      } else {
        setStockInfo({
          stockCode: data.stock_code,
          stockName: data.stock_name
        });
        setMoneyFlowData(data.money_flow);
      }
    } catch (error) {
      message.error('获取主力资金流向数据失败');
      console.error('Error fetching money flow data:', error);
    } finally {
      setLoading(false);
    }
  };

  // 初始化流入流出柱状图
  const initFlowChart = () => {
    const chartDom = document.getElementById('flow-chart');
    if (!chartDom) return;

    // 销毁旧实例
    if (flowChartInstance) {
      flowChartInstance.dispose();
    }

    const myChart = echarts.init(chartDom);
    setFlowChartInstance(myChart);

    const times = moneyFlowData.map(item => item.time);
    const inflowData = moneyFlowData.map(item => item.inflow);
    const outflowData = moneyFlowData.map(item => item.outflow);

    const option = {
      title: {
        text: `${stockInfo?.stockName || stockCode} - 资金流入/流出`,
        left: 'center',
        textStyle: {
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow',
          shadowStyle: {
            color: 'rgba(150,150,150,0.1)'
          }
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#ddd',
        borderWidth: 1,
        textStyle: {
          color: '#333'
        },
        padding: 15,
        formatter: function (params: any) {
          let result = `<div style="padding: 5px; font-size: 13px;">`;
          result += `<div style="margin-bottom: 10px; font-weight: bold; color: #333; border-bottom: 1px solid #eee; padding-bottom: 5px;">${params[0].axisValue}</div>`;
          params.forEach((param: any) => {
            const value = param.value;
            const name = param.seriesName;
            const marker = param.marker;
            result += `<div style="margin: 5px 0;">${marker} ${name}: <strong style="color: #ef232a;">${(value / 10000).toFixed(2)}万元</strong></div>`;
          });
          result += `</div>`;
          return result;
        }
      },
      legend: {
        data: ['流入主力资金', '流出主力资金'],
        top: 40,
        textStyle: {
          color: '#333'
        }
      },
      grid: {
        left: '3%',
        right: '3%',
        top: '20%',
        bottom: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: times,
        boundaryGap: true,
        axisLine: { 
          lineStyle: { 
            color: '#8392A5',
            width: 2
          } 
        },
        axisTick: {
          alignWithLabel: true
        },
        axisLabel: {
          formatter: function (value: string) {
            // 显示 月-日 时:分
            const parts = value.split(' ');
            if (parts.length === 2) {
              const datePart = parts[0].substring(5); // MM-DD
              const timePart = parts[1].substring(0, 5); // HH:mm
              return `${datePart}\n${timePart}`;
            }
            return value;
          },
          interval: 'auto',
          rotate: 0,
          color: '#666'
        }
      },
      yAxis: {
        type: 'value',
        name: '资金（万元）',
        nameTextStyle: {
          color: '#666',
          fontSize: 14
        },
        axisLine: { 
          lineStyle: { 
            color: '#8392A5',
            width: 2
          } 
        },
        splitLine: {
          lineStyle: {
            color: '#E0E6F1',
            type: 'dashed'
          }
        },
        splitArea: {
          show: true,
          areaStyle: {
            color: ['rgba(250,250,250,0.05)', 'rgba(200,200,200,0.02)']
          }
        },
        axisLabel: {
          formatter: function (value: number) {
            return (value / 10000).toFixed(0);
          },
          color: '#666'
        }
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100
        },
        {
          show: true,
          type: 'slider',
          bottom: '5%',
          height: 20,
          borderColor: '#8392A5',
          fillerColor: 'rgba(180,180,180,0.2)',
          handleStyle: {
            color: '#8392A5'
          }
        }
      ],
      series: [
        {
          name: '流入主力资金',
          type: 'bar',
          data: inflowData,
          barWidth: '30%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#ff6b6b' },
              { offset: 0.5, color: '#ef232a' },
              { offset: 1, color: '#c41a1f' }
            ]),
            borderRadius: [4, 4, 0, 0],
            shadowBlur: 10,
            shadowColor: 'rgba(239, 35, 42, 0.5)',
            shadowOffsetX: 3,
            shadowOffsetY: 3
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#ff8888' },
                { offset: 0.5, color: '#ff4444' },
                { offset: 1, color: '#ef232a' }
              ]),
              shadowBlur: 20,
              shadowColor: 'rgba(239, 35, 42, 0.8)'
            }
          }
        },
        {
          name: '流出主力资金',
          type: 'bar',
          data: outflowData,
          barWidth: '30%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#74c0fc' },
              { offset: 0.5, color: '#1890ff' },
              { offset: 1, color: '#0c5da5' }
            ]),
            borderRadius: [4, 4, 0, 0],
            shadowBlur: 10,
            shadowColor: 'rgba(24, 144, 255, 0.5)',
            shadowOffsetX: 3,
            shadowOffsetY: 3
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#a5d8ff' },
                { offset: 0.5, color: '#4dabf7' },
                { offset: 1, color: '#1890ff' }
              ]),
              shadowBlur: 20,
              shadowColor: 'rgba(24, 144, 255, 0.8)'
            }
          }
        }
      ]
    };

    myChart.setOption(option);

    // 响应式调整
    const resizeHandler = () => {
      myChart.resize();
    };
    window.addEventListener('resize', resizeHandler);
  };

  // 初始化净流入折线图
  const initNetflowChart = () => {
    const chartDom = document.getElementById('netflow-chart');
    if (!chartDom) return;

    // 销毁旧实例
    if (netflowChartInstance) {
      netflowChartInstance.dispose();
    }

    const myChart = echarts.init(chartDom);
    setNetflowChartInstance(myChart);

    const times = moneyFlowData.map(item => item.time);
    const netflowData = moneyFlowData.map(item => item.netflow);

    const option = {
      title: {
        text: `${stockInfo?.stockName || stockCode} - 净流入资金`,
        left: 'center',
        textStyle: {
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#ddd',
        borderWidth: 1,
        textStyle: {
          color: '#333'
        },
        padding: 15,
        formatter: function (params: any) {
          const param = params[0];
          const value = param.value;
          const color = value >= 0 ? '#14b143' : '#ef232a';
          return `
            <div style="padding: 5px; font-size: 13px;">
              <div style="margin-bottom: 10px; font-weight: bold; color: #333; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                ${param.axisValue}
              </div>
              <div style="margin: 5px 0;">
                ${param.marker} 净流入资金: <strong style="color: ${color};">${(value / 10000).toFixed(2)}万元</strong>
              </div>
            </div>
          `;
        }
      },
      legend: {
        data: ['净流入资金'],
        top: 40,
        textStyle: {
          color: '#333'
        }
      },
      grid: {
        left: '3%',
        right: '3%',
        top: '20%',
        bottom: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: times,
        boundaryGap: false,
        axisLine: { 
          lineStyle: { 
            color: '#8392A5',
            width: 2
          } 
        },
        axisLabel: {
          formatter: function (value: string) {
            // 显示 月-日 时:分
            const parts = value.split(' ');
            if (parts.length === 2) {
              const datePart = parts[0].substring(5); // MM-DD
              const timePart = parts[1].substring(0, 5); // HH:mm
              return `${datePart}\n${timePart}`;
            }
            return value;
          },
          interval: 'auto',
          rotate: 0,
          color: '#666'
        }
      },
      yAxis: {
        type: 'value',
        name: '资金（万元）',
        nameTextStyle: {
          color: '#666',
          fontSize: 14
        },
        axisLine: { 
          lineStyle: { 
            color: '#8392A5',
            width: 2
          } 
        },
        splitLine: {
          lineStyle: {
            color: '#E0E6F1',
            type: 'dashed'
          }
        },
        axisLabel: {
          formatter: function (value: number) {
            return (value / 10000).toFixed(0);
          },
          color: '#666'
        }
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100
        },
        {
          show: true,
          type: 'slider',
          bottom: '5%',
          height: 20,
          borderColor: '#8392A5',
          fillerColor: 'rgba(180,180,180,0.2)',
          handleStyle: {
            color: '#8392A5'
          }
        }
      ],
      series: [
        {
          name: '净流入资金',
          type: 'line',
          data: netflowData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: {
            width: 3
          },
          itemStyle: {
            color: function(params: any) {
              return params.value >= 0 ? '#14b143' : '#ef232a';
            }
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(20, 177, 67, 0.3)' },
              { offset: 1, color: 'rgba(239, 35, 42, 0.1)' }
            ])
          },
          markLine: {
            silent: true,
            data: [
              {
                yAxis: 0,
                lineStyle: {
                  color: '#999',
                  type: 'dashed',
                  width: 2
                },
                label: {
                  formatter: '零线',
                  position: 'end'
                }
              }
            ]
          }
        }
      ]
    };

    myChart.setOption(option);

    // 响应式调整
    const resizeHandler = () => {
      myChart.resize();
    };
    window.addEventListener('resize', resizeHandler);
  };

  const goBack = () => {
    navigate(-1);
  };

  const handleDateRangeChange = (dates: any) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange([dates[0], dates[1]]);
    }
  };

  const calculateSummary = () => {
    if (moneyFlowData.length === 0) {
      return { totalInflow: 0, totalOutflow: 0, totalNetflow: 0 };
    }

    const totalInflow = moneyFlowData.reduce((sum, item) => sum + item.inflow, 0);
    const totalOutflow = moneyFlowData.reduce((sum, item) => sum + item.outflow, 0);
    const totalNetflow = moneyFlowData.reduce((sum, item) => sum + item.netflow, 0);

    return { totalInflow, totalOutflow, totalNetflow };
  };

  const summary = calculateSummary();

  return (
    <div className="money-flow-container">
      <div className="system-banner">
        <h1>帮赛系统 - 资金流向分析（双图表）</h1>
      </div>

      <div className="money-flow-content">
        <Space style={{ marginBottom: 16 }}>
          <Button 
            type="primary" 
            icon={<ArrowLeftOutlined />} 
            onClick={goBack}
          >
            返回详情
          </Button>
          <RangePicker
            value={dateRange}
            onChange={handleDateRangeChange}
            format="YYYY-MM-DD"
          />
        </Space>

        {loading ? (
          <div className="loading-container">
            <Spin size="large" />
          </div>
        ) : (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={24}>
                <Card>
                  <Title level={3}>
                    {stockInfo?.stockName} ({stockInfo?.stockCode})
                  </Title>
                  <Text type="secondary">
                    数据时间范围: {dateRange[0].format('YYYY-MM-DD')} 至 {dateRange[1].format('YYYY-MM-DD')}
                  </Text>
                </Card>
              </Col>
            </Row>

            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={24} sm={8}>
                <Card>
                  <div className="summary-card">
                    <div className="summary-title">累计流入主力资金</div>
                    <div className="summary-value inflow">
                      {(summary.totalInflow / 10000).toFixed(2)} 万元
                    </div>
                  </div>
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card>
                  <div className="summary-card">
                    <div className="summary-title">累计流出主力资金</div>
                    <div className="summary-value outflow">
                      {(summary.totalOutflow / 10000).toFixed(2)} 万元
                    </div>
                  </div>
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card>
                  <div className="summary-card">
                    <div className="summary-title">累计净流入资金</div>
                    <div className={`summary-value ${summary.totalNetflow >= 0 ? 'netflow-positive' : 'netflow-negative'}`}>
                      {(summary.totalNetflow / 10000).toFixed(2)} 万元
                    </div>
                  </div>
                </Card>
              </Col>
            </Row>

            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={24}>
                <Card title="流入/流出资金对比">
                  <div id="flow-chart" style={{ width: '100%', height: '450px' }}></div>
                </Card>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={24}>
                <Card title="净流入资金走势">
                  <div id="netflow-chart" style={{ width: '100%', height: '450px' }}></div>
                </Card>
              </Col>
            </Row>

            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={24}>
                <Card title="计算说明">
                  <ul style={{ margin: 0, lineHeight: '2' }}>
                    {/* <li><strong>流入主力资金</strong>（红色柱）：当30分钟时间段的总涨幅大于5%时，计算该30分钟内总成交额/2×65%</li>
                    <li><strong>流出主力资金</strong>（蓝色柱）：当60分钟时间段的总跌幅大于5%时，计算该60分钟内总成交额/2×65%</li>
                    <li><strong>净流入资金</strong>（折线图）：流入主力资金 - 流出主力资金，正值为绿色，负值为红色，包含零线参考</li> */}
                    <li><strong>数据粒度</strong>：以30分钟和60分钟为单位展示，只显示满足涨跌幅条件的时间段</li>
                    {/* <li><strong>图表布局</strong>：上方为流入流出对比柱状图（3D效果），下方为净流入趋势折线图</li> */}
                  </ul>
                </Card>
              </Col>
            </Row>
          </>
        )}
      </div>
    </div>
  );
};

export default MoneyFlow;

