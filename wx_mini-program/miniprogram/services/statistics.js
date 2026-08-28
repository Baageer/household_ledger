const { request } = require('./api')
module.exports = {
  home: (data) => request({ url: '/statistics/home', data }),
  monthly: (data) => request({ url: '/statistics/monthly', data }),
  trend: (data) => request({ url: '/statistics/trend', data }),
  category: (data) => request({ url: '/statistics/category', data }),
  members: (data) => request({ url: '/statistics/members', data }),
  budgets: (data) => request({ url: '/budgets', data }),
  create: (data) => request({ url: '/budgets', method: 'POST', data }),
  update: (id, data) => request({ url: `/budgets/${id}`, method: 'PUT', data }),
  remove: (id) => request({ url: `/budgets/${id}`, method: 'DELETE' }),
}
