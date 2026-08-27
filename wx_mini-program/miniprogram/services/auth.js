const api = require('./api')

function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: ({ code }) => api.request({ url: '/auth/wechat-login', method: 'POST', data: { code } }).then(resolve).catch(reject),
      fail: reject,
    })
  })
}

module.exports = { login }
