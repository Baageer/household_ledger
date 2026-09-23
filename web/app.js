const modal = document.querySelector('#transaction-modal');
const addButton = document.querySelector('#add-transaction');
const importButton = document.querySelector('#import-button');
const closeButton = document.querySelector('.close-modal');
const form = document.querySelector('#transaction-form');
const toast = document.querySelector('#toast');
const transactionList = document.querySelector('#transaction-list');
const pageTitle = document.querySelector('#page-title');
const mobileMenu = document.querySelector('.mobile-menu');
const sidebar = document.querySelector('.sidebar');

function setModalVisible(visible) {
  modal.classList.toggle('open', visible);
  modal.setAttribute('aria-hidden', String(!visible));
  if (visible) document.querySelector('#amount-input').focus();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 2400);
}

function formatCurrency(value) {
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

addButton.addEventListener('click', () => setModalVisible(true));
closeButton.addEventListener('click', () => setModalVisible(false));
modal.addEventListener('click', (event) => { if (event.target === modal) setModalVisible(false); });
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setModalVisible(false); });

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    document.querySelector('.nav-item.active').classList.remove('active');
    item.classList.add('active');
    pageTitle.textContent = item.dataset.page;
  });
});

document.querySelectorAll('.segmented button').forEach((button) => {
  button.addEventListener('click', () => {
    button.parentElement.querySelector('.active').classList.remove('active');
    button.classList.add('active');
    showToast(`已切换至按${button.textContent}查看趋势`);
  });
});

document.querySelector('#month-select').addEventListener('change', (event) => showToast(`已切换至${event.target.value}`));
document.querySelector('#family-select').addEventListener('change', (event) => showToast(`已切换至${event.target.value}`));
importButton.addEventListener('click', () => showToast('账单导入功能将在此处接入文件上传服务'));
mobileMenu.addEventListener('click', () => sidebar.classList.toggle('mobile-open'));
document.querySelectorAll('.nav-item').forEach((item) => item.addEventListener('click', () => sidebar.classList.remove('mobile-open')));

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const amount = Number(data.get('amount'));
  const merchant = data.get('merchant').trim() || data.get('category');
  const type = data.get('type');
  const isIncome = type === 'income';
  const sign = isIncome ? '+' : '-';
  const iconClass = isIncome ? 'salary' : 'food';
  const icon = isIncome ? '¥' : '♨';
  const row = document.createElement('div');
  row.className = 'transaction';
  row.innerHTML = `<span class="transaction-icon ${iconClass}">${icon}</span><div class="transaction-name"><strong>${merchant}</strong><span>${data.get('category')} · ${data.get('account')}</span></div><time>刚刚</time><b class="amount ${isIncome ? 'income-amount' : 'expense-amount'}">${sign} ¥${formatCurrency(amount)}</b><button class="more-button" aria-label="${merchant}更多操作">•••</button>`;
  transactionList.prepend(row);
  form.reset();
  form.querySelector('[value="expense"]').checked = true;
  setModalVisible(false);
  showToast('已添加到本月账单');
});
