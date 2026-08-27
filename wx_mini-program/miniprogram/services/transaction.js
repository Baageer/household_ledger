const { request } = require('./api')
module.exports = {
  list: (data) => request({ url: '/transactions', data }),
  create: (data) => request({ url: '/transactions', method: 'POST', data }),
  update: (id, data) => request({ url: `/transactions/${id}`, method: 'PUT', data }),
  remove: (id) => request({ url: `/transactions/${id}`, method: 'DELETE' }),
}
