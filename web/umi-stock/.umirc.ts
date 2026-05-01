import { defineConfig } from 'umi';

export default defineConfig({
  npmClient: 'npm',
  routes: [
    { path: '/', component: 'login' },
    { path: '/index', component: 'index' },
    { path: '/stock/:stockCode', component: 'stock-detail' },
    { path: '/money-flow/:stockCode', component: 'money-flow' },
  ],
  plugins: ['@umijs/plugins/dist/antd'],
  antd: {},
  proxy: {
    '/api': {
      'target': 'http://192.168.1.2:5000',
      'changeOrigin': true,
      'pathRewrite': { '^/api': '' },
    },
  },
});
