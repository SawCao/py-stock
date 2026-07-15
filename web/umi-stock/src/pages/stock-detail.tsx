import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Typography, Spin, message, Button, Space } from 'antd';
import { ArrowLeftOutlined, LineChartOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'umi';
import * as echarts from 'echarts';
import './stock-detail.less';

const { Title, Text } = Typography;

interface StockDetailData {
  stockCode: string;
  stockName: string;
  currentPrice: number;
  change: number;
  changePercent: number;
  volume: number;
  turnover: number;
  marketCap: number;
  pe: number;
  pb: number;
  high: number;
  low: number;
  open: number;
  close: number;
}

interface KLineData {
  date: string;
  open: number;
  close: number;
  low: number;
  high: number;
  volume: number;
}

const StockDetail: React.FC = () => {
  const { stockCode } = useParams<{ stockCode: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [stockData, setStockData] = useState<StockDetailData | null>(null);
  const [kLineData, setKLineData] = useState<KLineData[]>([]);
  const [chartInstance, setChartInstance] = useState<echarts.ECharts | null>(null);

  useEffect(() => {
    if (stockCode) {
      fetchStockDetail();
      fetchKLineData();
    }
  }, [stockCode]);

  useEffect(() => {
    if (kLineData.length > 0) {
      initChart();
    }
  }, [kLineData]);

  const fetchStockDetail = async () => {
    setLoading(true);
    try {
      // 模拟从东方财富获取股票基本信息
      const response = await fetch(`/api/stock_detail/${stockCode}`);
      const data = await response.json();
      setStockData(data);
    } catch (error) {
      message.error('获取股票详情失败');
      console.error('Error fetching stock detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchKLineData = async () => {
    try {
      // 模拟获取K线数据
      const response = await fetch(`/api/kline/${stockCode}?period=30`);
      const data = await response.json();
      setKLineData(data);
    } catch (error) {
      message.error('获取K线数据失败');
      console.error('Error fetching K-line data:', error);
    }
  };

  const initChart = () => {
    const chartDom = document.getElementById('kline-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);
    setChartInstance(myChart);

    const option = {
      title: {
        text: `${stockData?.stockName || stockCode} - K线图`,
        left: 'center',
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          animation: false,
          label: {
            backgroundColor: '#505765'
          }
        },
        backgroundColor: 'rgba(50, 50, 50, 0.9)',
        borderColor: '#ccc',
        borderWidth: 1,
        textStyle: {
          color: '#fff'
        },
        formatter: function (params: any) {
          const data = params[0].data;
          if (!data || data.length < 6) return '';
          
          const open = Number(data[1]);
          const close = Number(data[2]);
          const low = Number(data[3]);
          const high = Number(data[4]);
          const volume = Number(data[5]);
          
          const color = open <= close ? '#14b143' : '#ef232a';
          return `
            <div style="padding: 10px; font-size: 12px;">
              <div style="margin-bottom: 5px; font-weight: bold;">${params[0].axisValue}</div>
              <div style="color: ${color}">开盘: ${open.toFixed(2)}</div>
              <div style="color: ${color}">收盘: ${close.toFixed(2)}</div>
              <div style="color: ${color}">最低: ${low.toFixed(2)}</div>
              <div style="color: ${color}">最高: ${high.toFixed(2)}</div>
              <div style="margin-top: 5px;">成交量: ${(volume / 10000).toFixed(2)}万</div>
            </div>
          `;
        }
      },
      legend: {
        data: ['K线', 'MA5', 'MA10', 'MA20', '成交量'],
        top: 30,
        textStyle: {
          color: '#333'
        }
      },
      grid: [
        {
          left: '3%',
          right: '3%',
          top: '15%',
          height: '50%',
          containLabel: true
        },
        {
          left: '3%',
          right: '3%',
          top: '70%',
          height: '15%',
          containLabel: true
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: kLineData.map(item => item.date),
          boundaryGap: false,
          axisLine: { lineStyle: { color: '#8392A5' } },
          axisLabel: {
            formatter: function (value: string) {
              return value.substring(5); // 只显示月-日
            }
          },
          gridIndex: 0
        },
        {
          type: 'category',
          gridIndex: 1,
          data: kLineData.map(item => item.date),
          boundaryGap: false,
          axisLine: { lineStyle: { color: '#8392A5' } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true,
            areaStyle: {
              color: ['rgba(250,250,250,0.1)', 'rgba(200,200,200,0.1)']
            }
          },
          axisLine: { lineStyle: { color: '#8392A5' } },
          gridIndex: 0
        },
        {
          scale: true,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          gridIndex: 1
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 50,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          bottom: '3%',
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
          name: 'K线',
          type: 'candlestick',
          data: kLineData.map(item => [
            item.date,
            item.open,
            item.close,
            item.low,
            item.high,
            item.volume
          ]),
          itemStyle: {
            color: '#ef232a',      // 阳线边框颜色
            color0: '#14b143',     // 阴线边框颜色
            borderColor: '#ef232a',  // 阳线边框颜色
            borderColor0: '#14b143'  // 阴线边框颜色
          },
          emphasis: {
            itemStyle: {
              color: '#c23531',
              color0: '#314656',
              borderColor: '#c23531',
              borderColor0: '#314656'
            }
          }
        },
        {
          name: 'MA5',
          type: 'line',
          data: calculateMA(5, kLineData),
          smooth: true,
          lineStyle: {
            opacity: 0.7,
            width: 1
          }
        },
        {
          name: 'MA10',
          type: 'line',
          data: calculateMA(10, kLineData),
          smooth: true,
          lineStyle: {
            opacity: 0.7,
            width: 1
          }
        },
        {
          name: 'MA20',
          type: 'line',
          data: calculateMA(20, kLineData),
          smooth: true,
          lineStyle: {
            opacity: 0.7,
            width: 1
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: kLineData.map(item => ({
            value: item.volume,
            itemStyle: {
              color: item.close >= item.open ? '#ef232a' : '#14b143'
            }
          }))
        }
      ]
    };

    myChart.setOption(option);

    // 响应式调整
    window.addEventListener('resize', () => {
      myChart.resize();
    });

    return () => {
      window.removeEventListener('resize', () => {
        myChart.resize();
      });
      myChart.dispose();
    };
  };

  const calculateMA = (dayCount: number, data: KLineData[]) => {
    const result = [];
    for (let i = 0; i < data.length; i++) {
      if (i < dayCount - 1) {
        result.push('-');
        continue;
      }
      let sum = 0;
      for (let j = 0; j < dayCount; j++) {
        sum += data[i - j].close;
      }
      result.push(parseFloat((sum / dayCount).toFixed(2)));
    }
    return result;
  };

  const goBack = () => {
    navigate(-1);
  };

  const goToMoneyFlow = () => {
    navigate(`/money-flow/${stockCode}`);
  };

  if (!stockData) {
    return (
      <div className="stock-detail-container">
        <div className="system-banner">
          <h1>帮赛系统 - 股票详情</h1>
        </div>
        <div className="loading-container">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  return (
    <div className="stock-detail-container">
      <div className="system-banner">
        <h1>帮赛系统 - 股票详情</h1>
      </div>
      
      <div className="detail-content">
        <Space style={{ marginBottom: 16 }}>
          <Button 
            type="primary" 
            icon={<ArrowLeftOutlined />} 
            onClick={goBack}
          >
            返回列表
          </Button>
          <Button 
            type="default" 
            icon={<LineChartOutlined />} 
            onClick={goToMoneyFlow}
          >
            主力资金流向
          </Button>
        </Space>

        <Row gutter={16}>
          <Col span={24}>
            <Card>
              <div className="stock-header">
                <Title level={2}>
                  {stockData.stockName} ({stockData.stockCode})
                </Title>
                <Space>
                  <Statistic
                    title="当前价格"
                    value={stockData.currentPrice}
                    precision={2}
                    valueStyle={{ color: stockData.change >= 0 ? '#3f8600' : '#cf1322' }}
                  />
                  <Statistic
                    title="涨跌额"
                    value={stockData.change}
                    precision={2}
                    valueStyle={{ color: stockData.change >= 0 ? '#3f8600' : '#cf1322' }}
                  />
                  <Statistic
                    title="涨跌幅"
                    value={stockData.changePercent}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: stockData.changePercent >= 0 ? '#3f8600' : '#cf1322' }}
                  />
                </Space>
              </div>
            </Card>
          </Col>
        </Row>

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col span={24}>
            <Card>
              <div id="kline-chart" style={{ width: '100%', height: '500px' }}></div>
            </Card>
          </Col>
        </Row>

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="成交量" value={stockData.volume} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="成交额" value={stockData.turnover} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="市值" value={stockData.marketCap} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="换手率" value={stockData.turnover / stockData.marketCap * 100} precision={2} suffix="%" />
            </Card>
          </Col>
        </Row>

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="市盈率(PE)" value={stockData.pe} precision={2} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="市净率(PB)" value={stockData.pb} precision={2} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="今日最高" value={stockData.high} precision={2} />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="今日最低" value={stockData.low} precision={2} />
            </Card>
          </Col>
        </Row>
      </div>
    </div>
  );
};

export default StockDetail;
