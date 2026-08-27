const { request } = require('./api')
module.exports = {
  home: (data) => request({ url: '/statistics/home', data }),
  monthly: (data) => request({ url: '/statistics/monthly', data }),
  trend: (data) => request({ url: '/statistics/trend', data }),
  category: (data) => request({ url: '/statistics/category', data }),
  members: (data) => request({ url: '/statistics/members', data }),
  budgets: (data) => request({ url: '/budgets', data }),
}
