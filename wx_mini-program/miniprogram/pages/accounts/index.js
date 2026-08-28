const app = getApp()
const family = require('../../services/family')
Page({
  data: { accounts: [], members: [], canManage: false, showForm: false, editingId: '', saving: false, ownerName: '家庭公共账户', ownerIndex: -1, types: [{ key: 'cash', name: '现金' }, { key: 'bank', name: '银行卡' }, { key: 'alipay', name: '支付宝' }, { key: 'wechat', name: '微信' }, { key: 'credit_card', name: '信用卡' }, { key: 'other', name: '其他' }], form: { name: '', type: 'cash', owner_id: null, currency: 'CNY', initial_balance: '0.00' } },
  onShow() { this.load() },
  load() { const familyId = app.globalData.currentFamilyId; if (!familyId) return; Promise.all([family.listAccounts(), family.listMembers(familyId)]).then(([accounts, members]) => { const current = members.find((item) => item.user_id === (app.globalData.user || {}).id); this.setData({ accounts, members, canManage: !!current && ['owner', 'admin'].includes(current.role) }) }).catch(() => {}) },
  openCreate() { this.setData({ showForm: true, editingId: '', ownerName: '家庭公共账户', ownerIndex: -1, form: { name: '', type: 'cash', owner_id: null, currency: 'CNY', initial_balance: '0.00' } }) },
  edit(e) { const account = e.currentTarget.dataset.item; const ownerIndex = account.owner_id ? this.data.members.findIndex((item) => item.user_id === account.owner_id) : -1; const owner = ownerIndex >= 0 ? this.data.members[ownerIndex] : null; this.setData({ showForm: true, editingId: account.id, ownerIndex, ownerName: owner ? (owner.user.nickname || owner.nickname || '成员') : '家庭公共账户', form: { name: account.name, type: account.type, owner_id: account.owner_id, currency: account.currency || 'CNY', initial_balance: account.initial_balance || '0.00' } }) },
  closeForm() { this.setData({ showForm: false }) },
  input(e) { this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value }) },
  pickType(e) { this.setData({ 'form.type': this.data.types[e.detail.value].key }) },
  pickOwner(e) { const index = Number(e.detail.value); const owner = this.data.members[index]; this.setData({ ownerIndex: index, ownerName: owner.user.nickname || owner.nickname || '成员', 'form.owner_id': owner.user_id }) },
  save() { const form = { ...this.data.form }; if (!form.name.trim()) return wx.showToast({ title: '请输入账户名称', icon: 'none' }); this.setData({ saving: true }); const action = this.data.editingId ? family.updateAccount(this.data.editingId, form) : family.createAccount(form); action.then(() => { wx.showToast({ title: this.data.editingId ? '已保存' : '账户已创建' }); this.setData({ showForm: false }); this.load() }).finally(() => this.setData({ saving: false })) },
  disable(e) { const account = e.currentTarget.dataset.item; wx.showModal({ title: '停用账户', content: `确定停用“${account.name}”？`, success: (result) => { if (result.confirm) family.disableAccount(account.id).then(() => { wx.showToast({ title: '已停用' }); this.load() }) } }) },
})
