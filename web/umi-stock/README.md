# 股票数据查询系统 (Umi重构版)

这是一个使用Umi + Ant Design重构的股票数据查询系统，保持了原有系统的所有功能，并提供了更现代化的用户界面。

## 功能特性

- ✅ 密码验证登录系统
- ✅ 股票数据筛选查询
- ✅ 多种时间区间选择（5分钟-60分钟）
- ✅ 实时数据展示
- ✅ 表格排序和筛选
- ✅ 响应式设计
- ✅ 外部链接跳转（东方财富、同花顺）

## 技术栈

- **前端框架**: Umi 4
- **UI组件库**: Ant Design 5.x
- **样式**: Less
- **路由**: React Router
- **构建工具**: Webpack/Vite
- **语言**: TypeScript

## 快速开始

### 安装依赖

```bash
cd web/umi-stock
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:8000

### 构建生产版本

```bash
npm run build
```

## 项目结构

```
web/umi-stock/
├── src/
│   └── pages/
│       ├── login.tsx          # 登录页面
│       ├── login.less         # 登录页面样式
│       ├── index.tsx          # 主页面
│       └── index.less         # 主页面样式
├── .umirc.ts                  # Umi配置文件
├── package.json               # 项目依赖
└── README.md                  # 项目说明
```

## 与原系统对比

| 特性 | 原系统 | Umi重构版 |
|------|--------|-----------|
| UI框架 | Bootstrap 3 | Ant Design 5 |
| 样式 | 传统CSS | Less + 现代化样式 |
| 交互 | jQuery | React Hooks |
| 响应式 | 基础响应式 | 完善的移动端适配 |
| 性能 | 一般 | 优化后的现代构建 |
| 开发体验 | 传统方式 | 现代化开发流程 |

## 使用说明

1. **登录**: 输入密码 `110548` 登录系统
2. **查询**: 设置筛选率、时间范围和筛选区间
3. **筛选**: 使用表格的筛选功能按概念板块或行业筛选
4. **排序**: 点击表头进行排序
5. **跳转**: 点击"东财"或"同花顺"按钮跳转到对应股票页面

## API接口

系统通过以下接口获取数据：
- GET `/api/stock_data?gain_threshold=0.03&start_date=...&end_date=...&gain_type=Gain_5`

## 开发指南

### 添加新功能

1. 在 `src/pages/` 目录下创建新的页面组件
2. 在 `.umirc.ts` 中配置路由
3. 使用 Ant Design 组件构建界面

### 样式定制

- 使用 Less 编写样式
- 遵循 Ant Design 设计规范
- 支持主题定制

## 注意事项

- 确保后端API服务已启动
- 开发时默认代理到 `http://localhost:5000`
- 生产环境需要配置正确的API地址
