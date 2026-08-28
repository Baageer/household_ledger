const store = require('./store/app-store')
const config = require('./config')

App({
  globalData: {
    apiBaseUrl: config.apiBaseUrl,
    requestTimeout: config.requestTimeout,
    token: null,
    user: null,
    families: [],
    currentFamilyId: null,
  },

  onLaunch() {
    this.globalData.token = store.getToken()
    this.globalData.user = store.getUser()
    this.globalData.families = store.getFamilies()
    this.globalData.currentFamilyId = store.getCurrentFamilyId()
  },

  onShow() {
    // onLaunch 时页面栈尚未建立，路由守卫延后到 onShow 执行。
    this.routeGuard()
  },

  setSession(session) {
    Object.assign(this.globalData, session)
    store.saveSession(session)
  },

  clearSession() {
    this.globalData.token = null
    this.globalData.user = null
    this.globalData.families = []
    this.globalData.currentFamilyId = null
    store.clearSession()
  },

  routeGuard() {
    const pages = getCurrentPages()
    if (!pages.length) return true
    const page = pages[pages.length - 1]
    const route = page.route || page.__route__
    // 页面实例尚未完成初始化时不要重定向，避免登录页启动死循环。
    if (!route) return true
    const current = `/${route}`
    if (!this.globalData.token) {
      if (current !== '/pages/auth/login/index') wx.reLaunch({ url: '/pages/auth/login/index' })
      return false
    }
    if (!this.globalData.currentFamilyId && current !== '/pages/family/select/index') {
      wx.reLaunch({ url: '/pages/family/select/index' })
      return false
    }
    return true
  },
})
