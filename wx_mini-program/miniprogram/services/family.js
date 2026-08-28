const { request } = require('./api')

const listFamilies = () => request({ url: '/families' })
const listMembers = (familyId) => request({ url: `/families/${familyId}/members` })
const invite = (familyId, data) => request({ url: `/families/${familyId}/invitations`, method: 'POST', data })
const updateMember = (familyId, userId, role) => request({ url: `/families/${familyId}/members/${userId}`, method: 'PUT', data: { role } })
const disableMember = (familyId, userId) => request({ url: `/families/${familyId}/members/${userId}`, method: 'DELETE' })
const listAccounts = () => request({ url: '/accounts' })
const createAccount = (data) => request({ url: '/accounts', method: 'POST', data })
const updateAccount = (id, data) => request({ url: `/accounts/${id}`, method: 'PUT', data })
const disableAccount = (id) => request({ url: `/accounts/${id}`, method: 'DELETE' })

module.exports = { listFamilies, listMembers, invite, updateMember, disableMember, listAccounts, createAccount, updateAccount, disableAccount }
