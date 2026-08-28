const environments = {
  development: {
    apiBaseUrl: 'http://127.0.0.1:8000',
    requestTimeout: 10000,
  },
  test: {
    apiBaseUrl: 'https://test-api.example.com',
    requestTimeout: 10000,
  },
  production: {
    apiBaseUrl: 'https://api.example.com',
    requestTimeout: 10000,
  },
}

// 微信开发者工具可通过编译模式传入 env；未传入时默认本地开发环境。
const env = (typeof wx !== 'undefined' && wx.getStorageSync('ledger_env')) || 'development'
module.exports = environments[env] || environments.development
