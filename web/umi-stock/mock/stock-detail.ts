export default {
  // 股票详情数据
  'GET /api/stock_detail/:stockCode': (req: any, res: any) => {
    const { stockCode } = req.params;
    
    // 模拟股票数据
    const mockStockData = {
      stockCode,
      stockName: `股票${stockCode}`,
      currentPrice: Math.random() * 100 + 10,
      change: (Math.random() - 0.5) * 10,
      changePercent: (Math.random() - 0.5) * 10,
      volume: Math.floor(Math.random() * 1000000),
      turnover: Math.floor(Math.random() * 100000000),
      marketCap: Math.floor(Math.random() * 10000000000),
      pe: Math.random() * 50 + 5,
      pb: Math.random() * 5 + 0.5,
      high: Math.random() * 100 + 50,
      low: Math.random() * 50 + 10,
      open: Math.random() * 100 + 20,
      close: Math.random() * 100 + 20,
    };
    
    mockStockData.change = mockStockData.currentPrice - mockStockData.close;
    mockStockData.changePercent = (mockStockData.change / mockStockData.close) * 100;
    
    res.json(mockStockData);
  },

  // K线数据
  'GET /api/kline/:stockCode': (req: any, res: any) => {
    const { stockCode } = req.params;
    const { period = 30 } = req.query;
    
    // 生成模拟K线数据
    const kLineData = [];
    const basePrice = Math.random() * 50 + 20;
    
    for (let i = 0; i < parseInt(period); i++) {
      const date = new Date();
      date.setDate(date.getDate() - (parseInt(period) - i));
      
      const volatility = 0.02;
      const trend = Math.sin(i / 5) * 0.01;
      
      const open = basePrice + (Math.random() - 0.5) * basePrice * volatility + trend * basePrice;
      const close = open + (Math.random() - 0.5) * basePrice * volatility;
      const high = Math.max(open, close) + Math.random() * basePrice * volatility;
      const low = Math.min(open, close) - Math.random() * basePrice * volatility;
      const volume = Math.floor(Math.random() * 1000000);
      
      kLineData.push({
        date: date.toISOString().split('T')[0],
        open: parseFloat(open.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        volume,
      });
    }
    
    res.json(kLineData);
  },
};
