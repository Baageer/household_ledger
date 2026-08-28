const app = getApp()
const family = require('../../../services/family')

Page({
  data: { members: [], loading: true, canManage: false, roleOptions: [{ key: 'member', name: '普通成员' }, { key: 'admin', name: '管理员' }, { key: 'owner', name: '所有者' }] },
  onShow() { this.load() },
  load() {
    const familyId = app.globalData.currentFamilyId
    if (!familyId) return
    this.setData({ loading: true })
    family.listMembers(familyId).then((members) => {
      const current = members.find((item) => item.user_id === (app.globalData.user || {}).id)
      this.setData({ members: members.map((item) => ({ ...item, display_name: (item.user && item.user.nickname) || item.nickname || '未命名成员' })), canManage: !!current && ['owner', 'admin'].includes(current.role), loading: false })
    }).catch(() => this.setData({ loading: false }))
  },
  invite() {
    if (!this.data.canManage) return
    wx.showModal({ title: '邀请成员', editable: true, placeholderText: '输入对方 OpenID', success: (result) => {
      if (!result.confirm || !result.content.trim()) return
      family.invite(app.globalData.currentFamilyId, { invitee_openid: result.content.trim(), role: 'member' }).then(() => {
        wx.showToast({ title: '邀请已创建' }); this.load()
      })
    } })
  },
  changeRole(e) {
    if (!this.data.canManage) return
    const item = e.currentTarget.dataset.item
    const roles = this.data.roleOptions.map((role) => role.name)
    wx.showActionSheet({ itemList: roles, success: (result) => {
      const role = this.data.roleOptions[result.tapIndex].key
      family.updateMember(app.globalData.currentFamilyId, item.user_id, role).then(() => { wx.showToast({ title: '角色已更新' }); this.load() })
    } })
  },
  disable(e) {
    if (!this.data.canManage) return
    const item = e.currentTarget.dataset.item
    wx.showModal({ title: '停用成员', content: `确定停用${item.user && item.user.nickname ? item.user.nickname : '该成员'}？`, success: (result) => {
      if (result.confirm) family.disableMember(app.globalData.currentFamilyId, item.user_id).then(() => { wx.showToast({ title: '已停用' }); this.load() })
    } })
  },
})
