const app = getApp()

function request({ url, method = 'GET', data = {} }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBaseUrl}${url}`,
      method,
      data,
      timeout: app.globalData.requestTimeout || 10000,
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
        if (status === 403) wx.showToast({ title: '暂无权限', icon: 'none' })
        if (status === 422) wx.showToast({ title: '请检查输入内容', icon: 'none' })
        if (status >= 500) wx.showToast({ title: '服务暂不可用，请重试', icon: 'none' })
        reject({ status, data: response.data })
      },
      fail(error) { wx.showToast({ title: '网络异常，请重试', icon: 'none' }); reject(error) },
    })
  })
}

module.exports = { request }
