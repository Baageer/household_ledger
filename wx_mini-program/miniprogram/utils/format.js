function amount(value) {
  return `¥${Number(value || 0).toFixed(2)}`
}

function date(value) {
  if (!value) return ''
  const item = new Date(value)
  return `${item.getMonth() + 1}月${item.getDate()}日`
}

module.exports = { amount, date }
