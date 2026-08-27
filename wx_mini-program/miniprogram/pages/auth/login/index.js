const app = getApp()
const auth = require('../../../services/auth')
Page({ data: { loading: false }, login() { if (this.data.loading) return; this.setData({ loading: true }); auth.login().then((session) => { app.setSession(session); wx.reLaunch({ url: (session.families || []).length ? '/pages/home/index' : '/pages/family/select/index' }) }).catch(() => wx.showToast({ title: '登录失败，请重试', icon: 'none' })).finally(() => this.setData({ loading: false })) } })
