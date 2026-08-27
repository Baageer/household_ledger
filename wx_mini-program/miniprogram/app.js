const store = require('./store/app-store')

App({
  globalData: {
    apiBaseUrl: 'https://api.example.com',
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
})
