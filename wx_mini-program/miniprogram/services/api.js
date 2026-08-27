const app = getApp()

function request({ url, method = 'GET', data = {} }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBaseUrl}${url}`,
      method,
      data,
      header: {
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : '',
        'X-Family-Id': app.globalData.currentFamilyId || '',
      },
      success(response) {
        const status = response.statusCode
        if (status >= 200 && status < 300) return resolve(response.data)
        if (status === 401) {
          app.clearSession()
          wx.reLaunch({ url: '/pages/auth/login/index' })
        }
        reject({ status, data: response.data })
      },
      fail: reject,
    })
  })
}

module.exports = { request }
