const keys = {
  token: 'ledger_token',
  user: 'ledger_user',
  families: 'ledger_families',
  currentFamilyId: 'ledger_current_family_id',
}

function read(key, fallback) {
  const value = wx.getStorageSync(key)
  return value === '' || value === undefined ? fallback : value
}

module.exports = {
  getToken: () => read(keys.token, null),
  getUser: () => read(keys.user, null),
  getFamilies: () => read(keys.families, []),
  getCurrentFamilyId: () => read(keys.currentFamilyId, null),
  saveSession(session) {
    if ('token' in session) wx.setStorageSync(keys.token, session.token)
    if ('user' in session) wx.setStorageSync(keys.user, session.user)
    if ('families' in session) wx.setStorageSync(keys.families, session.families)
    if ('currentFamilyId' in session) wx.setStorageSync(keys.currentFamilyId, session.currentFamilyId)
  },
  clearSession() {
    Object.values(keys).forEach((key) => wx.removeStorageSync(key))
  },
}
