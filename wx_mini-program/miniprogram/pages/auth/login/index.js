const app = getApp()
const auth = require('../../../services/auth')
Page({
  data: { loading: false, error: '' },
  onShow() {
    if (app.globalData.token) {
      if (app.globalData.currentFamilyId) wx.switchTab({ url: '/pages/home/index' })
      else wx.redirectTo({ url: '/pages/family/select/index' })
    }
  },
  login() {
    if (this.data.loading) return
    this.setData({ loading: true, error: '' })
    auth.login().then((session) => {
      app.setSession(session)
      if ((session.families || []).length) wx.switchTab({ url: '/pages/home/index' })
      else wx.redirectTo({ url: '/pages/family/select/index' })
    }).catch((error) => {
      const message = error && error.errMsg && error.errMsg.indexOf('request') >= 0 ? '无法连接服务，请检查 API 地址' : '登录失败，请重试'
      this.setData({ error: message })
      wx.showToast({ title: message, icon: 'none' })
    }).finally(() => this.setData({ loading: false }))
  },
})