# 家账 Web 前端原型

这是基于产品文档和微信小程序现有页面整理的响应式 Web 仪表盘原型，覆盖家庭财务概览、收支趋势、分类占比、最近账单与预算使用情况。

## 预览

直接在浏览器打开 `index.html` 即可预览，无需安装 Node.js 或其他依赖。

## 当前交互

- 月份、家庭和侧边导航状态切换
- 收支趋势按日/周/月切换反馈
- 快速记账弹窗及新增账单行
- 账单导入入口提示

## API 对接建议

页面应优先对接 `wx_mini-program/server/main.py` 中的 `/statistics/home`、`/statistics/trend`、`/statistics/category`、`/transactions` 与 `/budgets` 接口。请求需携带 `Authorization: Bearer <token>` 和 `X-Family-Id`，以保持与小程序端一致的家庭上下文。
