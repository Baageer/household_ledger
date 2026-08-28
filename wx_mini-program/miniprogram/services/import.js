const { request } = require('./api')
module.exports = {
  create: (data) => request({ url: '/imports', method: 'POST', data }),
  preview: (id) => request({ url: `/imports/${id}` }),
  confirm: (id, row_ids) => request({ url: `/imports/${id}/confirm`, method: 'POST', data: { row_ids } }),
  retry: (id) => request({ url: `/imports/${id}/retry`, method: 'POST' }),
}
