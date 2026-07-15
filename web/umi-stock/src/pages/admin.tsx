import React, { useEffect, useState } from 'react';
import { Button, Card, Col, DatePicker, Descriptions, Input, List, message, Modal, Row, Select, Space, Table, Tag, Typography, InputNumber, Spin } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { Dayjs } from 'dayjs';
import './admin.less';

const { Paragraph, Text } = Typography;

interface CronJobStatus {
  job_name: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  log_file: string | null;
  pid: number | null;
  command: string | null;
}

const jobSupportsDays = (jobName: string) => jobName === 'daily_job_baostock' || jobName === 'turnover_rise_baostock';

interface LogFileItem {
  name: string;
  size: number;
  updated_at: string;
  run_mode: string;
  job_name: string | null;
  date: string | null;
}

interface CompletenessSummaryItem {
  trade_date: string;
  stock_count: number;
  expected_rows_per_stock: number;
  complete_stock_count: number;
  incomplete_stock_count: number;
  total_rows: number;
  expected_total_rows: number;
  missing_rows: number;
  completion_rate: number;
}

interface CompletenessDetailItem {
  trade_date: string;
  stock_code: string;
  stock_name: string;
  row_count: number;
  expected_rows: number;
  missing_rows: number;
}

interface StockBasicInfo {
  stockCode: string;
  symbol: string;
  stockName: string;
  exchangeBoard: string;
  industry: string;
  industryBoards: string;
  latestPrice: number;
  isActive: boolean;
  latestTradeDate: string | null;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnoverRate: number;
  tables: {
    stock_list_cache: Record<string, unknown> | null;
    stock_industry: Record<string, unknown> | null;
    stock_board_membership: Array<Record<string, unknown>>;
    stock_zh_a_daily_latest: Record<string, unknown> | null;
  };
}

const renderFieldRows = (row: Record<string, unknown> | null) => {
  if (!row) {
    return <Paragraph className="stock-query-empty" type="secondary">当前表没有查到记录。</Paragraph>;
  }

  return (
    <Descriptions column={1} size="small" bordered>
      {Object.entries(row).map(([key, value]) => (
        <Descriptions.Item key={key} label={key}>
          {value === null || value === undefined || value === '' ? '-' : String(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
};

const renderFieldList = (rows: Array<Record<string, unknown>>) => {
  if (!rows.length) {
    return <Paragraph className="stock-query-empty" type="secondary">当前表没有查到记录。</Paragraph>;
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {rows.map((row, index) => (
        <Descriptions key={`${String(row.board_type || 'row')}-${String(row.board_code || index)}`} column={1} size="small" bordered>
          {Object.entries(row).map(([key, value]) => (
            <Descriptions.Item key={key} label={key}>
              {value === null || value === undefined || value === '' ? '-' : String(value)}
            </Descriptions.Item>
          ))}
        </Descriptions>
      ))}
    </Space>
  );
};

const statusColorMap: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  unknown: 'default',
  invalid_status_file: 'orange',
  started: 'blue',
};

const AdminPage: React.FC = () => {
  const [jobs, setJobs] = useState<CronJobStatus[]>([]);
  const [logFiles, setLogFiles] = useState<LogFileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [clearingCache, setClearingCache] = useState(false);
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);
  const [logModalOpen, setLogModalOpen] = useState(false);
  const [logLoading, setLogLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<string>('');
  const [logContent, setLogContent] = useState('');
  const [logLines, setLogLines] = useState(200);
  const [triggerDays, setTriggerDays] = useState<Record<string, number>>({
    daily_job_baostock: 2,
    turnover_rise_baostock: 2,
    stock_board_sync: 2,
  });
  const [completenessDays, setCompletenessDays] = useState(5);
  const [completenessLoading, setCompletenessLoading] = useState(false);
  const [completenessSummary, setCompletenessSummary] = useState<CompletenessSummaryItem[]>([]);
  const [completenessDetails, setCompletenessDetails] = useState<CompletenessDetailItem[]>([]);
  const [logDateFilter, setLogDateFilter] = useState<Dayjs | null>(dayjs());
  const [logRunModeFilter, setLogRunModeFilter] = useState<string>('');
  const [logJobFilter, setLogJobFilter] = useState<string>('');
  const [stockQuery, setStockQuery] = useState('');
  const [stockInfoLoading, setStockInfoLoading] = useState(false);
  const [stockInfo, setStockInfo] = useState<StockBasicInfo | null>(null);

  const fetchCronStatus = async () => {
    const response = await fetch('/api/admin/cron_status');
    if (!response.ok) {
      throw new Error('获取 cron 状态失败');
    }
    const result = await response.json();
    setJobs(result.jobs || []);
  };

  const fetchLogFiles = async () => {
    const params = new URLSearchParams();
    if (logDateFilter) {
      params.set('date', logDateFilter.format('YYYYMMDD'));
    }
    if (logRunModeFilter) {
      params.set('run_mode', logRunModeFilter);
    }
    if (logJobFilter) {
      params.set('job_name', logJobFilter);
    }
    const response = await fetch(`/api/admin/log_files?${params.toString()}`);
    if (!response.ok) {
      throw new Error('获取日志列表失败');
    }
    const result = await response.json();
    setLogFiles(result.files || []);
  };

  const refreshAll = async () => {
    setLoading(true);
    try {
      await Promise.all([fetchCronStatus(), fetchLogFiles()]);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '刷新失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchCompleteness = async (days: number) => {
    setCompletenessLoading(true);
    try {
      const response = await fetch(`/api/admin/minute_data_completeness?days=${days}`);
      if (!response.ok) {
        throw new Error('获取分钟数据完整性失败');
      }
      const result = await response.json();
      setCompletenessSummary(result.summary || []);
      setCompletenessDetails(result.incomplete_details || []);
    } finally {
      setCompletenessLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    fetchLogFiles().catch(() => undefined);
  }, [logDateFilter, logRunModeFilter, logJobFilter]);

  const handleClearCache = async () => {
    setClearingCache(true);
    try {
      const response = await fetch('/api/admin/stock_search_cache/clear', { method: 'POST' });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || '清缓存失败');
      }
      message.success(`已清理 ${result.removed} 个缓存文件`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '清缓存失败');
    } finally {
      setClearingCache(false);
    }
  };

  const handleTriggerJob = async (jobName: string) => {
    setTriggeringJob(jobName);
    try {
      const days = triggerDays[jobName] || 2;
      const payload = jobSupportsDays(jobName) ? { days } : {};
      const response = await fetch(`/api/admin/cron_trigger/${jobName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || '触发任务失败');
      }
      message.success(jobSupportsDays(jobName) ? `任务 ${jobName} 已启动，范围 ${result.days} 天` : `任务 ${jobName} 已启动`);
      await fetchCronStatus();
      await fetchLogFiles();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '触发任务失败');
    } finally {
      setTriggeringJob(null);
    }
  };

  const handleOpenLog = async (logName: string) => {
    setSelectedLog(logName);
    setLogModalOpen(true);
    setLogLoading(true);
    try {
      const response = await fetch(`/api/admin/logs?name=${encodeURIComponent(logName)}&lines=${logLines}`);
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || '读取日志失败');
      }
      setLogContent(result.content || '');
    } catch (error) {
      setLogContent('');
      message.error(error instanceof Error ? error.message : '读取日志失败');
    } finally {
      setLogLoading(false);
    }
  };

  const handleQueryStockInfo = async () => {
    const keyword = stockQuery.trim();
    if (!keyword) {
      message.warning('请输入股票代码');
      return;
    }

    setStockInfoLoading(true);
    try {
      const response = await fetch(`/api/admin/stock_basic_info?stock_code=${encodeURIComponent(keyword)}`);
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || '查询股票基础信息失败');
      }
      setStockInfo(result);
    } catch (error) {
      setStockInfo(null);
      message.error(error instanceof Error ? error.message : '查询股票基础信息失败');
    } finally {
      setStockInfoLoading(false);
    }
  };

  const cronColumns: ColumnsType<CronJobStatus> = [
    {
      title: '任务名',
      dataIndex: 'job_name',
      key: 'job_name',
      width: 180,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => <Tag color={statusColorMap[status] || 'default'}>{status}</Tag>,
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (value: string | null) => value || '-',
    },
    {
      title: '结束时间',
      dataIndex: 'finished_at',
      key: 'finished_at',
      width: 180,
      render: (value: string | null) => value || '-',
    },
    {
      title: '退出码',
      dataIndex: 'exit_code',
      key: 'exit_code',
      width: 100,
      render: (value: number | null) => (value === null ? '-' : value),
    },
    {
      title: '日志',
      dataIndex: 'log_file',
      key: 'log_file',
      width: 220,
      render: (value: string | null) => value || '-',
    },
    {
      title: '执行范围',
      key: 'trigger_days',
      width: 150,
      render: (_, record) =>
        jobSupportsDays(record.job_name) ? (
          <InputNumber
            min={1}
            max={60}
            value={triggerDays[record.job_name] || 2}
            onChange={(value) =>
              setTriggerDays((prev) => ({
                ...prev,
                [record.job_name]: value || 2,
              }))
            }
          />
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_, record) => {
        const logName = record.log_file ? record.log_file.split('/').pop() || '' : '';
        return (
          <Space wrap>
            <Button
              type="primary"
              onClick={() => handleTriggerJob(record.job_name)}
              loading={triggeringJob === record.job_name}
              disabled={record.status === 'running'}
            >
              立即执行
            </Button>
            <Button
              onClick={() => logName && handleOpenLog(logName)}
              disabled={!logName}
            >
              查看日志
            </Button>
          </Space>
        );
      },
    },
  ];

  const completenessColumns: ColumnsType<CompletenessSummaryItem> = [
    { title: '交易日', dataIndex: 'trade_date', key: 'trade_date', width: 120 },
    { title: '股票数', dataIndex: 'stock_count', key: 'stock_count', width: 100 },
    { title: '理论每股条数', dataIndex: 'expected_rows_per_stock', key: 'expected_rows_per_stock', width: 140 },
    { title: '完整股票数', dataIndex: 'complete_stock_count', key: 'complete_stock_count', width: 120 },
    { title: '不完整股票数', dataIndex: 'incomplete_stock_count', key: 'incomplete_stock_count', width: 130 },
    { title: '实际总条数', dataIndex: 'total_rows', key: 'total_rows', width: 120 },
    { title: '理论总条数', dataIndex: 'expected_total_rows', key: 'expected_total_rows', width: 130 },
    { title: '缺失条数', dataIndex: 'missing_rows', key: 'missing_rows', width: 110 },
    {
      title: '完整率',
      dataIndex: 'completion_rate',
      key: 'completion_rate',
      width: 100,
      render: (value: number) => <Tag color={value >= 99 ? 'green' : value >= 95 ? 'orange' : 'red'}>{value}%</Tag>,
    },
  ];

  const completenessDetailColumns: ColumnsType<CompletenessDetailItem> = [
    { title: '交易日', dataIndex: 'trade_date', key: 'trade_date', width: 120 },
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 120 },
    { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name', width: 140 },
    { title: '实际条数', dataIndex: 'row_count', key: 'row_count', width: 100 },
    { title: '理论条数', dataIndex: 'expected_rows', key: 'expected_rows', width: 100 },
    { title: '缺失条数', dataIndex: 'missing_rows', key: 'missing_rows', width: 100 },
  ];

  return (
    <div className="admin-container">
      <div className="admin-banner">
        <h1>帮赛系统管理台</h1>
        <Paragraph>
          统一查看 cron 任务状态、手动清理 stock_search 缓存、触发任务执行并查看日志。
        </Paragraph>
      </div>

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card
              title="Cron 状态"
              extra={
                <Space>
                  <Button onClick={refreshAll}>刷新</Button>
                  <Button type="primary" danger onClick={handleClearCache} loading={clearingCache}>
                    清空 stock_search 缓存
                  </Button>
                </Space>
              }
            >
              <Table
                rowKey="job_name"
                columns={cronColumns}
                dataSource={jobs}
                pagination={false}
                scroll={{ x: 1200 }}
              />
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card title="股票基础信息查询">
              <Space className="stock-query-toolbar" wrap>
                <Input
                  placeholder="输入股票代码，如 600519 或 sh.600519"
                  value={stockQuery}
                  onChange={(event) => setStockQuery(event.target.value)}
                  onPressEnter={handleQueryStockInfo}
                  allowClear
                  style={{ width: 260 }}
                />
                <Button type="primary" onClick={handleQueryStockInfo} loading={stockInfoLoading}>
                  查询
                </Button>
              </Space>
              <Paragraph type="secondary">
                返回当前数据库里该股票的基础资料和板块/行业信息，不返回详细 K 线。
              </Paragraph>
              {stockInfo ? (
                <Descriptions className="stock-basic-info" column={1} size="small" bordered>
                  <Descriptions.Item label="股票代码">{stockInfo.stockCode}</Descriptions.Item>
                  <Descriptions.Item label="交易所代码">{stockInfo.symbol}</Descriptions.Item>
                  <Descriptions.Item label="股票名称">{stockInfo.stockName}</Descriptions.Item>
                  <Descriptions.Item label="交易板块">{stockInfo.exchangeBoard}</Descriptions.Item>
                  <Descriptions.Item label="行业代码/名称">{stockInfo.industry}</Descriptions.Item>
                  <Descriptions.Item label="行业板块">{stockInfo.industryBoards || '-'}</Descriptions.Item>
                  <Descriptions.Item label="最新交易日">{stockInfo.latestTradeDate || '-'}</Descriptions.Item>
                  <Descriptions.Item label="最新价格">{stockInfo.latestPrice || 0}</Descriptions.Item>
                  <Descriptions.Item label="开盘价">{stockInfo.open || 0}</Descriptions.Item>
                  <Descriptions.Item label="最高价">{stockInfo.high || 0}</Descriptions.Item>
                  <Descriptions.Item label="最低价">{stockInfo.low || 0}</Descriptions.Item>
                  <Descriptions.Item label="收盘价">{stockInfo.close || 0}</Descriptions.Item>
                  <Descriptions.Item label="成交量">{stockInfo.volume || 0}</Descriptions.Item>
                  <Descriptions.Item label="换手率">{stockInfo.turnoverRate || 0}%</Descriptions.Item>
                  <Descriptions.Item label="是否活跃">
                    <Tag color={stockInfo.isActive ? 'green' : 'default'}>
                      {stockInfo.isActive ? '是' : '否'}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>
              ) : null}
              {stockInfo ? (
                <div className="stock-db-sections">
                  <Card size="small" title="stock_list_cache 全字段">
                    {renderFieldRows(stockInfo.tables.stock_list_cache)}
                  </Card>
                  <Card size="small" title="stock_industry 全字段">
                    {renderFieldRows(stockInfo.tables.stock_industry)}
                  </Card>
                  <Card size="small" title="stock_board_membership 全字段">
                    {renderFieldList(stockInfo.tables.stock_board_membership || [])}
                  </Card>
                  <Card size="small" title="stock_zh_a_daily 最新一条全字段">
                    {renderFieldRows(stockInfo.tables.stock_zh_a_daily_latest)}
                  </Card>
                </div>
              ) : (
                <Paragraph className="stock-query-empty" type="secondary">
                  输入股票代码后可查看数据库中的基础信息。
                </Paragraph>
              )}
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card title="日志文件">
              <Space className="log-toolbar" wrap>
                <Text>行数</Text>
                <InputNumber min={50} max={2000} step={50} value={logLines} onChange={(value) => setLogLines(value || 200)} />
                <DatePicker value={logDateFilter} format="YYYY-MM-DD" onChange={(value) => setLogDateFilter(value)} />
                <Select
                  value={logRunModeFilter}
                  onChange={setLogRunModeFilter}
                  style={{ width: 120 }}
                  options={[
                    { value: '', label: '全部方式' },
                    { value: 'scheduled', label: '定时任务' },
                    { value: 'manual', label: '手动触发' },
                    { value: 'other', label: '其他日志' },
                  ]}
                />
                <Select
                  value={logJobFilter}
                  onChange={setLogJobFilter}
                  style={{ width: 180 }}
                  options={[
                    { value: '', label: '全部任务' },
                    { value: 'daily_job_baostock', label: 'daily_job_baostock' },
                    { value: 'turnover_rise_baostock', label: 'turnover_rise_baostock' },
                    { value: 'stock_board_sync', label: 'stock_board_sync' },
                  ]}
                />
                <Button onClick={fetchLogFiles}>刷新日志列表</Button>
              </Space>
              <List
                className="log-list"
                dataSource={logFiles}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button key="view" type="link" onClick={() => handleOpenLog(item.name)}>
                        查看
                      </Button>,
                    ]}
                    >
                    <List.Item.Meta
                      title={item.name}
                      description={`方式: ${item.run_mode || '-'} | 任务: ${item.job_name || '-'} | 日期: ${item.date || '-'} | 大小: ${item.size} bytes | 更新: ${item.updated_at}`}
                    />
                  </List.Item>
                )}
              />
            </Card>
          </Col>

          <Col xs={24}>
            <Card
              title="分钟数据完整性"
              extra={
                <Space wrap>
                  <Text>统计近</Text>
                  <InputNumber min={1} max={30} value={completenessDays} onChange={(value) => setCompletenessDays(value || 5)} />
                  <Text>天</Text>
                  <Button onClick={() => fetchCompleteness(completenessDays)} loading={completenessLoading}>
                    刷新完整性统计
                  </Button>
                </Space>
              }
            >
              <Paragraph>
                理论上 A 股 5 分钟数据在一个完整交易日应为 <Text strong>48 条/股票</Text>。
                计算口径：上午 9:30-11:30 共 24 条，下午 13:00-15:00 共 24 条。
              </Paragraph>
              <Table
                rowKey="trade_date"
                columns={completenessColumns}
                dataSource={completenessSummary}
                pagination={false}
                scroll={{ x: 1200 }}
                loading={completenessLoading}
              />

              <div style={{ marginTop: 24 }}>
                <Text strong>缺失明细</Text>
              </div>
              <Table
                rowKey={(record) => `${record.trade_date}-${record.stock_code}`}
                columns={completenessDetailColumns}
                dataSource={completenessDetails}
                pagination={{ pageSize: 20, showSizeChanger: true }}
                scroll={{ x: 900 }}
                loading={completenessLoading}
                style={{ marginTop: 12 }}
              />
            </Card>
          </Col>
        </Row>
      </Spin>

      <Modal
        title={`日志预览: ${selectedLog}`}
        open={logModalOpen}
        onCancel={() => setLogModalOpen(false)}
        footer={[
          <Button key="refresh" onClick={() => selectedLog && handleOpenLog(selectedLog)}>
            刷新日志
          </Button>,
          <Button key="close" type="primary" onClick={() => setLogModalOpen(false)}>
            关闭
          </Button>,
        ]}
        width={1000}
      >
        <Spin spinning={logLoading}>
          <pre className="log-content">{logContent || '暂无日志内容'}</pre>
        </Spin>
      </Modal>
    </div>
  );
};

export default AdminPage;
