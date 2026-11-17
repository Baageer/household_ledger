const modal = document.querySelector('#transaction-modal');
const form = document.querySelector('#transaction-form');
const categoryEditModal = document.querySelector('#category-edit-modal');
const categoryEditForm = document.querySelector('#category-edit-form');
const budgetActionModal = document.querySelector('#budget-action-modal');
const budgetActionAmount = document.querySelector('#budget-action-amount');
const budgetCreateModal = document.querySelector('#budget-create-modal');
const budgetCreateForm = document.querySelector('#budget-create-form');
const budgetCreateCategory = document.querySelector('#budget-create-category');
const budgetCreateAmount = document.querySelector('#budget-create-amount');
let activeBudgetId = null;
const toast = document.querySelector('#toast');
const transactionList = document.querySelector('#transaction-list');
const pageTitle = document.querySelector('#page-title');
const sidebar = document.querySelector('.sidebar');
const mainContent = document.querySelector('.main-content');
const baseSections = ['.welcome-row', '.summary-grid', '.content-grid', '.lower-grid'];
const monthSelect = document.querySelector('#month-select');
const demoTransactions = [
  { id: 'demo-1', merchant: '盒马鲜生', category: '餐饮', account: '微信支付', time: '今天 10:24', amount: -168, month: '2026-08', icon: '♨', iconClass: 'food' },
  { id: 'demo-2', merchant: '滴滴出行', category: '交通', account: '支付宝', time: '昨天 20:46', amount: -36.5, month: '2026-08', icon: '◉', iconClass: 'transport' },
  { id: 'demo-3', merchant: '工资入账', category: '工资', account: '招商银行', time: '8月21日 09:00', amount: 14300, month: '2026-08', icon: '¥', iconClass: 'salary' },
  { id: 'demo-4', merchant: '山姆会员商店', category: '购物', account: '招商银行', time: '8月20日 16:18', amount: -428, month: '2026-08', icon: '◈', iconClass: 'shopping' },
];
const state = { transactions: [...demoTransactions], remote: false, page: 'overview', transactionCategoryFilter: '', editingTransactionId: null, families: [], formOptions: { accounts: [], categories: [] }, budgets: [], importTask: null };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 2400);
}

function formatCurrency(value) {
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0);
}

function relatedName(value, id, options, fallback) {
  if (typeof value === 'string' && value) return value;
  if (value?.name) return value.name;
  return options.find((option) => option.id === id)?.name || fallback;
}

function transactionCategory(item) {
  return item.category_name || relatedName(item.category, item.category_id, state.formOptions.categories, '未分类');
}

function transactionAccount(item) {
  const accountName = item.account_name || relatedName(item.account, item.account_id, state.formOptions.accounts, '未指定账户');
  if (item.type !== 'transfer') return accountName;
  const targetName = item.transfer_to_account_name || relatedName(null, item.transfer_to_account_id, state.formOptions.accounts, '');
  return targetName ? `${accountName} → ${targetName}` : accountName;
}

const transactionTypePresentation = {
  income: { label: '收入', prefix: '+', amountClass: 'income-amount', icon: '¥', iconClass: 'salary' },
  expense: { label: '支出', prefix: '-', amountClass: 'expense-amount', icon: '♨', iconClass: 'food' },
  refund: { label: '退款', prefix: '+', amountClass: 'refund-amount', icon: '↩', iconClass: 'salary' },
  transfer: { label: '转账', prefix: '↔', amountClass: 'transfer-amount', icon: '↔', iconClass: 'transport' },
};

function transactionPresentation(item) {
  const amount = Number(item.amount || 0);
  const type = item.type || (amount < 0 ? 'expense' : 'income');
  return transactionTypePresentation[type] || { label: '其他', prefix: '', amountClass: '', icon: '¥', iconClass: 'food' };
}

function updateAccountOptions(payload) {
  const accounts = payload?.items || payload || [];
  state.formOptions.accounts = accounts;
  const accountSelect = form.querySelector('[name="account"]');
  accountSelect.innerHTML = accounts.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join('');
  return accounts;
}

function updateCategoryOptions(payload) {
  const categories = payload?.items || payload || [];
  state.formOptions.categories = categories;
  const categorySelect = form.querySelector('[name="category"]');
  categorySelect.innerHTML = categories.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join('');
  return categories;
}

async function refreshAccounts() {
  return updateAccountOptions(await ledgerApi.accounts());
}

async function refreshFormOptions() {
  const [accounts, categories] = await Promise.all([ledgerApi.accounts(), ledgerApi.categories()]);
  updateAccountOptions(accounts);
  updateCategoryOptions(categories);
}

function monthValue() {
  const match = monthSelect.value.match(/(\d{4})年(\d{1,2})月/);
  return match ? `${match[1]}-${String(match[2]).padStart(2, '0')}` : new Date().toISOString().slice(0, 7);
}

function setConnectionState(remote) {
  state.remote = remote;
  let badge = document.querySelector('.connection-badge');
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'connection-badge';
    document.querySelector('.topbar-actions').prepend(badge);
  }
  badge.textContent = remote ? '● 已连接' : '演示数据';
  badge.classList.toggle('online', remote);
}

function setModalVisible(visible) {
  modal.classList.toggle('open', visible);
  modal.setAttribute('aria-hidden', String(!visible));
  if (visible) document.querySelector('#amount-input').focus();
}

function setCategoryEditVisible(visible) {
  categoryEditModal.classList.toggle('open', visible);
  categoryEditModal.setAttribute('aria-hidden', String(!visible));
  if (!visible) state.editingTransactionId = null;
}

function setBudgetActionVisible(visible) {
  budgetActionModal.classList.toggle('open', visible);
  budgetActionModal.setAttribute('aria-hidden', String(!visible));
  if (!visible) activeBudgetId = null;
}

function setBudgetCreateVisible(visible) {
  budgetCreateModal.classList.toggle('open', visible);
  budgetCreateModal.setAttribute('aria-hidden', String(!visible));
  if (!visible) budgetCreateForm.reset();
}

function openBudgetCreate() {
  const categories = state.formOptions.categories || [];
  if (!state.remote) return showToast('请先连接 API');
  if (!categories.length) return showToast('暂无可用预算类型');
  budgetCreateCategory.innerHTML = categories.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join('');
  setBudgetCreateVisible(true);
  budgetCreateCategory.focus();
}

function openBudgetAction(budgetId) {
  const budget = state.budgets.find((item) => item.id === budgetId);
  if (!budget) return showToast('未找到该预算');
  activeBudgetId = budget.id;
  const category = relatedName(null, budget.category_id, state.formOptions.categories, budget.category || '未分类');
  document.querySelector('#budget-action-summary').textContent = category;
  budgetActionAmount.value = String(budget.budget ?? budget.amount ?? '');
  setBudgetActionVisible(true);
  budgetActionAmount.focus();
}

function openCategoryEditor(transactionId) {
  const transaction = state.transactions.find((item) => item.id === transactionId);
  if (!transaction) return showToast('未找到需要编辑的账单');
  const categories = state.remote
    ? state.formOptions.categories
    : [...new Set(state.transactions.map((item) => transactionCategory(item)))].map((name) => ({ id: name, name }));
  if (!categories.length) return showToast('暂无可用分类');
  const select = categoryEditForm.querySelector('[name="category_id"]');
  select.innerHTML = categories.map((category) => `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)}</option>`).join('');
  const currentCategory = transaction.category_id || categories.find((category) => category.name === transactionCategory(transaction))?.id || categories[0].id;
  select.value = currentCategory;
  document.querySelector('#category-edit-summary').textContent = `${transaction.merchant || transaction.description || '未命名交易'} · ${transactionAccount(transaction)}`;
  state.editingTransactionId = transactionId;
  setCategoryEditVisible(true);
  select.focus();
}

function renderTransactionRows(items, target = transactionList) {
  target.innerHTML = items.map((item) => {
    const amount = Number(item.amount || 0);
    const presentation = transactionPresentation(item);
    return `<div class="transaction"><span class="transaction-icon ${escapeHtml(item.iconClass || presentation.iconClass)}">${escapeHtml(item.icon || presentation.icon)}</span><div class="transaction-name"><strong>${escapeHtml(item.merchant || item.description || '未命名交易')}</strong><span>${escapeHtml(transactionCategory(item))} · ${escapeHtml(transactionAccount(item))}</span></div><time>${escapeHtml(item.time || item.transaction_time || '刚刚')}</time><b class="amount ${presentation.amountClass}" title="${presentation.label}">${presentation.prefix} ¥${formatCurrency(Math.abs(amount))}</b><button class="more-button" aria-label="更多操作">•••</button></div>`;
  }).join('');
}

function updateDashboard(data) {
  if (!data) return;
  const summary = data.summary || data;
  const cards = document.querySelectorAll('.summary-card strong');
  if (cards[0] && summary.balance != null) cards[0].textContent = `¥${formatCurrency(summary.balance)}`;
  if (cards[1] && summary.income != null) cards[1].textContent = `¥${formatCurrency(summary.income)}`;
  if (cards[2] && summary.expense != null) cards[2].textContent = `¥${formatCurrency(summary.expense)}`;
  const ranking = data.category_ranking || [];
  if (ranking.length) {
    const categoryKey = document.querySelector('.category-key');
    categoryKey.innerHTML = ranking.slice(0, 4).map((item, index) => `<p><i class="key-dot key-${(index % 4) + 1}"></i><span>${escapeHtml(item.category || item.name)}</span><b>¥${formatCurrency(item.amount)}</b><em>${item.ratio ? `${Number(item.ratio).toFixed(1)}%` : ''}</em></p>`).join('');
  }
  if (data.transactions) {
    state.transactions = data.transactions.items || data.transactions;
    renderTransactionRows(state.transactions.slice(0, 4));
  }
}

function dashboardVisible(visible) {
  baseSections.forEach((selector) => { const element = document.querySelector(selector); if (element) element.style.display = visible ? '' : 'none'; });
  document.querySelectorAll('.page-view').forEach((pageView) => pageView.remove());
}

function pageShell(title, description, body) {
  document.querySelectorAll('.page-view').forEach((pageView) => pageView.remove());
  const section = document.createElement('section');
  section.className = 'page-view';
  section.innerHTML = `<div class="page-view-heading"><div><p class="eyebrow">家庭空间 · ${escapeHtml(monthSelect.value)}</p><h2>${escapeHtml(title)}</h2><p class="subtle">${escapeHtml(description)}</p></div><div class="page-view-actions"></div></div><div class="page-view-body">${body}</div>`;
  mainContent.appendChild(section);
  return section;
}

async function renderTransactionsPage() {
  const selectedMonth = monthValue();
  if (state.remote) {
    try {
      const result = await ledgerApi.transactions(selectedMonth, 1, 200);
      state.transactions = result.items || result;
    } catch (error) { showToast(error.message); }
  }
  const periodRows = state.remote ? state.transactions : state.transactions.filter((item) => (item.month || '2026-08') === selectedMonth);
  const categoryNames = [...new Set(periodRows.map((item) => transactionCategory(item)))].sort((left, right) => left.localeCompare(right, 'zh-CN'));
  if (state.transactionCategoryFilter && !categoryNames.includes(state.transactionCategoryFilter)) state.transactionCategoryFilter = '';
  const rows = state.transactionCategoryFilter ? periodRows.filter((item) => transactionCategory(item) === state.transactionCategoryFilter) : periodRows;
  const monthOptions = Array.from(monthSelect.options).map((option) => `<option value="${escapeHtml(option.value)}" ${option.value === monthSelect.value ? 'selected' : ''}>${escapeHtml(option.textContent)}</option>`).join('');
  const categoryOptions = `<option value="">全部分类</option>${categoryNames.map((name) => `<option value="${escapeHtml(name)}" ${name === state.transactionCategoryFilter ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('')}`;
  const tableRows = rows.length ? rows.map((item) => {
    const amount = Number(item.amount || 0);
    const presentation = transactionPresentation(item);
    return `<tr><td><span class="table-merchant"><i class="transaction-icon ${escapeHtml(item.iconClass || presentation.iconClass)}">${escapeHtml(item.icon || presentation.icon)}</i><strong>${escapeHtml(item.merchant || item.description || '未命名交易')}</strong></span></td><td>${escapeHtml(transactionCategory(item))}</td><td>${escapeHtml(transactionAccount(item))}</td><td>${escapeHtml(item.time || item.transaction_time || '刚刚')}</td><td class="align-right ${presentation.amountClass}" title="${presentation.label}">${presentation.prefix} ¥${formatCurrency(Math.abs(amount))}</td><td><button class="more-button transaction-edit-button" type="button" data-action="edit-transaction-category" data-transaction-id="${escapeHtml(item.id)}" aria-label="编辑${escapeHtml(item.merchant || item.description || '账单')}的分类">•••</button></td></tr>`;
  }).join('') : '<tr><td colspan="6" class="subtle">该账期暂无账单</td></tr>';
  const section = pageShell('全部账单', '按月份查看家庭的每一笔收入与支出。', `<div class="toolbar transaction-toolbar"><label class="field-inline">账期<select id="transaction-month">${monthOptions}</select></label><label class="field-inline">分类<select id="transaction-category">${categoryOptions}</select></label><span class="subtle">显示 ${rows.length} / ${periodRows.length} 笔</span><button class="button button-primary" data-action="add">＋ 记一笔</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>交易</th><th>分类</th><th>账户</th><th>时间</th><th class="align-right">金额</th><th></th></tr></thead><tbody>${tableRows}</tbody></table></div>`);
  return section;
}

async function renderAnalyticsPage() {
  const section = pageShell('收支统计', '从趋势、分类和家庭成员三个维度理解支出。', `<div class="analytics-cards"><article class="stat-highlight"><span>本月收入</span><strong>¥28,600.00</strong><small class="income-amount">较上月 ↑ 8.2%</small></article><article class="stat-highlight"><span>本月支出</span><strong>¥12,860.00</strong><small class="income-amount">较上月 ↓ 4.5%</small></article><article class="stat-highlight"><span>储蓄率</span><strong>55.0%</strong><small>目标 50%</small></article></div><div class="analytics-columns"><article class="sub-panel"><h3>分类排行</h3><p class="subtle">本月各分类支出占比</p><div class="bar-list"><div><span>餐饮</span><b>¥3,620</b><i><em style="width:81%"></em></i></div><div><span>住房</span><b>¥3,100</b><i><em style="width:69%"></em></i></div><div><span>购物</span><b>¥2,180</b><i><em style="width:48%"></em></i></div><div><span>交通</span><b>¥620</b><i><em style="width:18%"></em></i></div></div></article><article class="sub-panel"><h3>成员支出</h3><p class="subtle">家庭成员本月支出汇总</p><div class="member-stat"><span class="avatar avatar-small">林</span><div><strong>林先生</strong><i><em style="width:72%"></em></i></div><b>¥8,460</b></div><div class="member-stat"><span class="avatar avatar-small avatar-pink">李</span><div><strong>李女士</strong><i><em style="width:38%"></em></i></div><b>¥4,400</b></div></article></div>`);
  if (state.remote) {
    try {
      const [summaryPayload, categories, members, trend] = await Promise.all([ledgerApi.home(monthValue()), ledgerApi.category(monthValue()), ledgerApi.membersStats(monthValue()), ledgerApi.trend(monthValue())]);
      const summary = summaryPayload.summary || summaryPayload;
      const summaryCards = section.querySelectorAll('.stat-highlight strong');
      if (summaryCards[0] && summary.income != null) summaryCards[0].textContent = `¥${formatCurrency(summary.income)}`;
      if (summaryCards[1] && summary.expense != null) summaryCards[1].textContent = `¥${formatCurrency(summary.expense)}`;
      if (summaryCards[2] && summary.income != null) {
        const income = Number(summary.income) || 0;
        const expense = Number(summary.expense) || 0;
        summaryCards[2].textContent = `${income ? ((income - expense) / income * 100).toFixed(1) : '0.0'}%`;
      }
      const categoryRows = categories.items || categories;
      if (Array.isArray(categoryRows) && categoryRows.length) {
        section.querySelector('.bar-list').innerHTML = categoryRows.slice(0, 6).map((item) => {
          const ratio = Number(item.ratio || 0);
          const percent = ratio <= 1 ? ratio * 100 : ratio;
          return `<div><span>${escapeHtml(item.category || item.name)}</span><b>¥${formatCurrency(item.amount)}</b><i><em style="width:${Math.min(100, percent)}%"></em></i></div>`;
        }).join('');
      } else {
        section.querySelector('.bar-list').innerHTML = '<p class="subtle">暂无分类数据</p>';
      }
      const memberRows = members.items || members;
      if (Array.isArray(memberRows) && memberRows.length) {
        const maxMemberAmount = Math.max(...memberRows.map((item) => Number(item.amount) || 0), 1);
        section.querySelector('.member-stat').parentElement.innerHTML = `<h3>成员支出</h3><p class="subtle">家庭成员本月支出汇总</p>${memberRows.slice(0, 5).map((item) => `<div class="member-stat"><span class="avatar avatar-small">${escapeHtml((item.member || item.name || '家').slice(0, 1))}</span><div><strong>${escapeHtml(item.member || item.name || '家庭成员')}</strong><i><em style="width:${Math.min(100, (Number(item.amount) || 0) / maxMemberAmount * 100)}%"></em></i></div><b>¥${formatCurrency(item.amount)}</b></div>`).join('')}`;
      } else {
        section.querySelector('.member-stat').parentElement.innerHTML = '<h3>成员支出</h3><p class="subtle">暂无成员支出数据</p>';
      }
      const trendRows = trend.items || trend;
      if (Array.isArray(trendRows) && trendRows.length) {
        const trendPanel = document.createElement('article');
        trendPanel.className = 'sub-panel trend-data-panel';
        trendPanel.innerHTML = `<h3>收支趋势</h3><p class="subtle">本月实际收入与支出</p><div class="trend-data-list">${trendRows.slice(0, 10).map((item) => `<div class="trend-data-row"><span>${escapeHtml(item.period)}</span><span class="income-amount">+¥${formatCurrency(item.income)}</span><span class="expense-amount">-¥${formatCurrency(item.expense)}</span></div>`).join('')}</div>`;
        section.querySelector('.analytics-columns').prepend(trendPanel);
        const note = document.createElement('p');
        note.className = 'data-note';
        note.textContent = `已加载 ${trendRows.length} 个${trend.granularity === 'week' ? '周' : '日'}趋势数据点`;
        section.querySelector('.page-view-heading').appendChild(note);
      }
    } catch (error) { showToast(error.message); }
  }
  return section;
}

async function renderBudgetsPage() {
  const section = pageShell('预算管理', '为每个分类设定边界，及时发现超支风险。', `<div class="toolbar"><span class="subtle">${escapeHtml(monthSelect.value)} · 预算总额 ¥18,750</span><button class="button button-primary" data-action="budget">＋ 新建预算</button></div><div class="budget-grid"><article class="budget-detail"><div><span class="category-symbol food-symbol">♨</span><h3>餐饮</h3><b>86%</b></div><strong>¥2,580 <small>/ ¥3,000</small></strong><div class="budget-progress"><i style="width:86%"></i></div><p>剩余 ¥420 <span>本月支出 ¥2,580</span></p></article><article class="budget-detail warning"><div><span class="category-symbol shopping-symbol">◈</span><h3>购物</h3><b>87%</b></div><strong>¥2,180 <small>/ ¥2,500</small></strong><div class="budget-progress warning"><i style="width:87%"></i></div><p>剩余 ¥320 <span>本月支出 ¥2,180</span></p></article><article class="budget-detail"><div><span class="category-symbol home-symbol">⌂</span><h3>住房</h3><b>69%</b></div><strong>¥3,100 <small>/ ¥4,500</small></strong><div class="budget-progress"><i style="width:69%"></i></div><p>剩余 ¥1,400 <span>本月支出 ¥3,100</span></p></article></div>`);
  if (state.remote) {
    try {
      const budgets = await ledgerApi.budgets(monthValue());
      const rows = budgets.items || budgets;
      state.budgets = Array.isArray(rows) ? rows : [];
      if (Array.isArray(rows) && rows.length) {
        const totalBudget = rows.reduce((total, item) => total + (Number(item.amount ?? item.budget) || 0), 0);
        section.querySelector('.toolbar .subtle').textContent = `${monthSelect.value} · 预算总额 ¥${formatCurrency(totalBudget)}`;
        section.querySelector('.budget-grid').innerHTML = rows.map((item) => {
          const budget = Number(item.amount ?? item.budget) || 0;
          const used = Number(item.used_amount ?? item.spent ?? item.used) || 0;
          const remaining = Number(item.remaining ?? (budget - used));
          const rawRatio = Number(item.usage_ratio ?? item.ratio ?? (budget ? used / budget : 0)) || 0;
          const ratio = Math.round(rawRatio <= 1 ? rawRatio * 100 : rawRatio);
          const category = relatedName(null, item.category_id, state.formOptions.categories, item.category || item.name || '未分类');
          return `<article class="budget-detail ${ratio >= 90 ? 'warning' : ''}"><div><span class="category-symbol food-symbol">◒</span><h3>${escapeHtml(category)}</h3><b>${ratio}%</b></div><strong>¥${formatCurrency(used)} <small>/ ¥${formatCurrency(budget)}</small></strong><div class="budget-progress ${ratio >= 90 ? 'warning' : ''}"><i style="width:${Math.min(100, ratio)}%"></i></div><p>剩余 ¥${formatCurrency(remaining)}</p></article>`;
        }).join('');
      } else {
        section.querySelector('.toolbar .subtle').textContent = `${monthSelect.value} · 暂无预算`;
        section.querySelector('.budget-grid').innerHTML = '<p class="subtle">暂无预算数据</p>';
      }
    } catch (error) { showToast(error.message); }
  }
  section.querySelectorAll('.budget-detail').forEach((card, index) => {
    const budget = state.budgets[index];
    if (budget) card.insertAdjacentHTML('beforeend', `<button class="more-button budget-more-button" type="button" data-action="budget-menu" data-budget-id="${escapeHtml(budget.id)}" aria-label="预算更多操作">•••</button>`);
  });
  return section;
}

async function renderImportsPage() {
  if (state.remote) {
    try { await refreshAccounts(); } catch (error) { showToast(`账户列表刷新失败：${error.message}`); }
  }
  const accounts = state.formOptions.accounts || [];
  const accountOptions = accounts.length ? accounts.map((account) => `<option value="${escapeHtml(account.id)}">${escapeHtml(account.name)}</option>`).join('') : '<option value="">连接后选择账户</option>';
  const section = pageShell('账单导入', '上传支付宝或微信账单，审核后再正式入账。', `<div class="import-toolbar"><label class="field-inline">账单来源<select id="import-source"><option value="alipay">支付宝</option><option value="wechat">微信支付</option></select></label><label class="field-inline">入账账户<select id="import-account">${accountOptions}</select></label><span class="subtle">来源必须与文件格式一致</span></div><div class="import-layout"><label class="upload-box" for="import-file"><span class="upload-icon">⇪</span><strong>拖拽文件到这里，或点击选择</strong><small>支持 CSV、XLSX，单个文件不超过 10MB</small><input id="import-file" type="file" accept=".csv,.xlsx,.xls" /></label><div class="import-steps"><div class="import-step active"><b>01</b><span><strong>上传账单</strong><small>选择来源和文件</small></span></div><div class="import-step"><b>02</b><span><strong>审核明细</strong><small>修正分类与重复项</small></span></div><div class="import-step"><b>03</b><span><strong>确认入账</strong><small>只将确认行写入账本</small></span></div></div></div><div class="import-notice">提示：支付宝和微信账单的解析规则不同，请先选择正确来源。所有识别结果都需要确认后才会入账。</div><div id="import-preview" class="import-preview"></div>`);
  if (state.importTask) renderImportPreview(section, state.importTask);
  return section;
}

function normalizeImportPreview(payload) {
  if (!payload?.task) return payload;
  return { ...payload.task, rows: payload.rows || [], preview: payload };
}

function renderImportPreview(section, task) {
  const rows = task.rows || task.items || [];
  const preview = section.querySelector('#import-preview');
  const steps = section.querySelectorAll('.import-step');
  steps.forEach((step, index) => step.classList.toggle('active', index > 0));
  preview.innerHTML = `<div class="preview-header"><div><h3>审核导入明细</h3><p class="subtle">共 ${rows.length} 行，确认后才会创建正式交易</p></div><div><button class="button button-secondary" data-action="retry-import">重新解析</button><button class="button button-primary" data-action="confirm-import">确认入账</button></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>商户</th><th>金额</th><th>类型</th><th>状态</th><th>日期</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${escapeHtml(row.merchant || row.description || '未识别')}</td><td>¥${formatCurrency(row.amount)}</td><td>${escapeHtml(transactionTypePresentation[row.direction]?.label || '待判断')}</td><td><span class="status-pill ${row.status === 'error' ? 'error' : 'pending'}">${escapeHtml(row.error_reason || row.status || '待确认')}</span></td><td>${escapeHtml(row.transaction_time || row.date || '')}</td></tr>`).join('')}</tbody></table></div>`;
}

function createLocalImportTask(file, text = '') {
  const rows = text.split(/\r?\n/).filter(Boolean).slice(1, 6).map((line, index) => {
    const columns = line.split(',');
    return { id: `local-row-${index}`, merchant: columns[1] || '待识别商户', amount: Number(String(columns[2] || '0').replace(/[^\d.-]/g, '')) || 0, status: 'pending', date: columns[0] || new Date().toISOString().slice(0, 10) };
  });
  return { id: `local-${Date.now()}`, file_name: file.name, rows: rows.length ? rows : [{ id: 'local-row-1', merchant: `${file.name} · 待审核`, amount: 0, status: 'pending', date: new Date().toISOString().slice(0, 10) }] };
}

function showLocalImportPreview(file, text = '') {
  state.importTask = createLocalImportTask(file, text);
  renderImportPreview(document.querySelector('.page-view'), state.importTask);
  showToast('文件已读取，请审核导入明细');
}

async function renderFamilyPage() {
  const section = pageShell('家庭成员', '邀请家人一起维护同一个家庭账本。', '<div class="loading-card">正在读取成员信息…</div>');
  let members = [{ name: '林先生', role: 'owner', status: '正常' }, { name: '李女士', role: 'member', status: '正常' }];
  const session = ledgerApi.getSession();
  let families = state.families;
  if (state.remote) { try { families = state.families = await ledgerApi.families(); } catch (error) { showToast(error.message); } }
  if (state.remote && session.familyId) { try { members = await ledgerApi.members(session.familyId); } catch (error) { showToast(error.message); } }
  section.querySelector('.page-view-body').innerHTML = `<div class="toolbar"><label class="field-inline">当前家庭<select id="family-page-select">${families.map((family) => `<option value="${escapeHtml(family.id)}" ${family.id === session.familyId ? 'selected' : ''}>${escapeHtml(family.name)}</option>`).join('')}</select></label><div><button class="button button-secondary" data-action="new-family">＋ 新建家庭</button><button class="button button-primary" data-action="invite">＋ 邀请成员</button></div></div><div class="member-grid">${members.map((member) => { const memberId = member.user_id || member.user?.id || ''; const isOwner = member.role === 'owner'; return `<article class="member-card"><span class="avatar avatar-small">${escapeHtml((member.user?.nickname || member.name || '家').slice(0, 1))}</span><div><strong>${escapeHtml(member.user?.nickname || member.name || '家庭成员')}</strong><small>${escapeHtml(member.role || 'member')} · ${escapeHtml(member.status || '正常')}</small></div>${!isOwner && memberId ? `<div class="member-actions"><button data-action="member-role" data-member-id="${escapeHtml(memberId)}">改角色</button><button data-action="member-disable" data-member-id="${escapeHtml(memberId)}">停用</button></div>` : ''}</article>`; }).join('')}</div>`;
  return section;
}

function renderFamilySetupPage() {
  return pageShell('创建你的第一个家庭', '家庭账本需要先绑定一个家庭空间，之后才能记录账单和邀请成员。', '<form class="sub-panel family-setup-form" id="family-setup-form"><span class="setup-icon">家</span><h3>创建家庭空间</h3><p class="subtle">例如“我们的小家”“2026 旅行基金”，创建后你会自动成为管理员。</p><label class="form-field">家庭名称<input name="name" maxlength="80" placeholder="请输入家庭名称" required /></label><button class="button button-primary" type="submit">创建并进入家庭</button></form>');
}

async function renderAccountsPage() {
  const section = pageShell('账户管理', '管理微信、支付宝、银行卡和现金账户。', '<div class="loading-card">正在读取账户信息…</div>');
  let accounts = [{ name: '微信支付', type: '移动支付', balance: '¥2,860.00' }, { name: '招商银行', type: '银行卡', balance: '¥18,420.00' }, { name: '现金', type: '现金账户', balance: '¥560.00' }];
  if (state.remote) { try { accounts = await refreshAccounts(); } catch (error) { showToast(error.message); } }
  section.querySelector('.page-view-body').innerHTML = `<div class="toolbar"><span class="subtle">${accounts.length} 个启用账户</span><button class="button button-primary" data-action="account">＋ 添加账户</button></div><div class="account-grid">${accounts.map((account) => `<article class="account-detail"><span class="account-badge">▣</span><div><strong>${escapeHtml(account.name)}</strong><small>${escapeHtml(account.type || '家庭账户')}</small></div><b>${escapeHtml(account.balance || '余额待同步')}</b></article>`).join('')}</div>`;
  return section;
}

function renderSettingsPage() {
  const session = ledgerApi.getSession();
  return pageShell('偏好设置', '配置 Web API 和开发环境登录，会话信息仅保存在当前浏览器。', `<div class="settings-grid"><form class="sub-panel settings-form" id="settings-form"><h3>连接设置</h3><label class="form-field">API 地址<input name="baseUrl" value="${escapeHtml(ledgerApi.getBaseUrl())}" placeholder="http://127.0.0.1:8000" /></label><button class="button button-secondary" type="submit">保存地址</button></form><form class="sub-panel settings-form" id="login-form"><h3>开发登录</h3><p class="subtle">后端当前提供 wechat-login 开发接口，可使用任意非空 code 联调。</p><label class="form-field">Code<input name="code" value="dev-web" required /></label><label class="form-field">昵称<input name="nickname" value="林先生" /></label><button class="button button-primary" type="submit">登录并加载家庭</button>${session.token ? '<button class="button button-secondary" type="button" data-action="logout">退出当前会话</button>' : ''}</form></div>`);
}

async function openPage(page) {
  state.page = page;
  document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.getAttribute('href') === `#${page}`));
  pageTitle.textContent = document.querySelector(`.nav-item[href="#${page}"]`)?.dataset.page || (page === 'family-setup' ? '创建家庭' : '财务概览');
  sidebar.classList.remove('mobile-open');
  if (page === 'overview') { dashboardVisible(true); return; }
  dashboardVisible(false);
  if (page === 'transactions') await renderTransactionsPage();
  if (page === 'analytics') await renderAnalyticsPage();
  if (page === 'budgets') await renderBudgetsPage();
  if (page === 'imports') await renderImportsPage();
  if (page === 'family') await renderFamilyPage();
  if (page === 'family-setup') renderFamilySetupPage();
  if (page === 'accounts') await renderAccountsPage();
  if (page === 'settings') renderSettingsPage();
}

async function loadRemoteData() {
  const session = ledgerApi.getSession();
  if (!session.token) { setConnectionState(false); return; }
  try {
    state.families = await ledgerApi.families();
    if (!state.families.length) {
      setConnectionState(false);
      if (state.page !== 'family-setup') await openPage('family-setup');
      return;
    }
    if (!session.familyId || !state.families.some((family) => family.id === session.familyId)) {
      localStorage.setItem(ledgerApi.storageKeys.family, state.families[0].id);
    }
    const familySelect = document.querySelector('#family-select');
    familySelect.innerHTML = state.families.map((family) => `<option value="${escapeHtml(family.id)}">${escapeHtml(family.name)}</option>`).join('');
    familySelect.value = ledgerApi.getSession().familyId;
    const data = await ledgerApi.home(monthValue());
    updateDashboard(data);
    try {
      await refreshFormOptions();
    } catch (_) { state.formOptions = { accounts: [], categories: [] }; }
    setConnectionState(true);
    if (state.page === 'analytics') await openPage('analytics');
    if (state.page === 'budgets') await openPage('budgets');
  } catch (error) {
    setConnectionState(false);
    showToast(error.status === 403 ? '当前账号没有访问该家庭的权限' : error.status === 422 ? `请求参数有误：${error.message}` : error.message);
  }
}

async function saveTransaction(event) {
  event.preventDefault();
  const data = new FormData(form);
  const amount = Number(data.get('amount'));
  if (!amount || amount <= 0) return showToast('请输入大于 0 的金额');
  const isIncome = data.get('type') === 'income';
  if (state.remote && state.formOptions.accounts.length) {
    try {
      await ledgerApi.createTransaction({ type: isIncome ? 'income' : 'expense', amount: amount.toFixed(2), account_id: data.get('account'), category_id: data.get('category') || null, merchant: data.get('merchant') || '', transaction_time: new Date().toISOString() });
      await loadRemoteData();
    } catch (error) { return showToast(error.message); }
  } else {
    state.transactions.unshift({ merchant: data.get('merchant') || data.get('category'), category: data.get('category'), account: data.get('account'), type: isIncome ? 'income' : 'expense', time: '刚刚', amount, month: monthValue(), icon: isIncome ? '¥' : '♨', iconClass: isIncome ? 'salary' : 'food' });
    renderTransactionRows(state.transactions.slice(0, 4));
  }
  form.reset();
  form.querySelector('[value="expense"]').checked = true;
  setModalVisible(false);
  showToast('已添加到本月账单');
}

async function saveTransactionCategory(event) {
  event.preventDefault();
  const transaction = state.transactions.find((item) => item.id === state.editingTransactionId);
  if (!transaction) return showToast('未找到需要编辑的账单');
  const categoryId = new FormData(categoryEditForm).get('category_id');
  const submitButton = categoryEditForm.querySelector('[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = '正在保存…';
  try {
    if (state.remote) {
      const updated = await ledgerApi.updateTransaction(transaction.id, { category_id: categoryId });
      Object.assign(transaction, updated);
    } else {
      transaction.category = categoryId;
      transaction.category_name = categoryId;
    }
    setCategoryEditVisible(false);
    await openPage('transactions');
    showToast('账单分类已更新');
  } catch (error) {
    showToast(`保存失败：${error.message}`);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = '保存分类';
  }
}

document.querySelector('#add-transaction').addEventListener('click', () => setModalVisible(true));
document.querySelector('.close-modal').addEventListener('click', () => setModalVisible(false));
document.querySelector('.close-category-modal').addEventListener('click', () => setCategoryEditVisible(false));
document.querySelector('.close-budget-modal').addEventListener('click', () => setBudgetActionVisible(false));
document.querySelector('.close-budget-create-modal').addEventListener('click', () => setBudgetCreateVisible(false));
modal.addEventListener('click', (event) => { if (event.target === modal) setModalVisible(false); });
categoryEditModal.addEventListener('click', (event) => { if (event.target === categoryEditModal) setCategoryEditVisible(false); });
budgetActionModal.addEventListener('click', async (event) => {
  if (event.target === budgetActionModal) return setBudgetActionVisible(false);
  const action = event.target.closest('[data-budget-action]')?.dataset.budgetAction;
  if (!action || !activeBudgetId) return;
  const budget = state.budgets.find((item) => item.id === activeBudgetId);
  if (!budget) return setBudgetActionVisible(false);
  if (action === 'delete') {
    if (!window.confirm('确定删除该预算吗？')) return;
    try { await ledgerApi.deleteBudget(budget.id); setBudgetActionVisible(false); showToast('预算已删除'); await openPage('budgets'); } catch (error) { showToast(error.message); }
  }
  if (action === 'save') {
    const amount = budgetActionAmount.value;
    if (!amount || Number(amount) <= 0) return showToast('请输入大于 0 的预算金额');
    try { await ledgerApi.updateBudget(budget.id, { category_id: budget.category_id, amount }); setBudgetActionVisible(false); showToast('预算已更新'); await openPage('budgets'); } catch (error) { showToast(error.message); }
  }
});
document.querySelector('.mobile-menu').addEventListener('click', () => sidebar.classList.toggle('mobile-open'));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') { setModalVisible(false); setCategoryEditVisible(false); setBudgetActionVisible(false); setBudgetCreateVisible(false); } });
form.addEventListener('submit', saveTransaction);
categoryEditForm.addEventListener('submit', saveTransactionCategory);
budgetCreateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const categoryId = budgetCreateCategory.value;
  const amount = budgetCreateAmount.value;
  if (!categoryId || !amount || Number(amount) <= 0) return showToast('请选择预算类型并输入大于 0 的金额');
  try { await ledgerApi.createBudget({ category_id: categoryId, amount }); setBudgetCreateVisible(false); showToast('预算已创建'); await openPage('budgets'); } catch (error) { showToast(error.message); }
});

document.querySelector('#month-select').addEventListener('change', async () => { state.transactionCategoryFilter = ''; showToast(`已切换至${monthSelect.value}`); await loadRemoteData(); if (state.page !== 'overview') await openPage(state.page); });
document.querySelector('#family-select').addEventListener('change', async (event) => { localStorage.setItem(ledgerApi.storageKeys.family, event.target.value); showToast('正在切换家庭'); await loadRemoteData(); if (state.page !== 'overview') await openPage(state.page); });
document.querySelector('#import-button').addEventListener('click', () => { window.location.hash = '#imports'; });
document.querySelectorAll('.segmented button').forEach((button) => button.addEventListener('click', () => { button.parentElement.querySelector('.active').classList.remove('active'); button.classList.add('active'); showToast(`已切换至按${button.textContent}查看趋势`); }));

mainContent.addEventListener('click', async (event) => {
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'add') setModalVisible(true);
  if (action === 'edit-transaction-category') openCategoryEditor(event.target.closest('[data-transaction-id]')?.dataset.transactionId);
  if (action === 'logout') { ledgerApi.clearSession(); setConnectionState(false); showToast('已退出当前会话'); await openPage('settings'); }
  if (action === 'new-family') {
    const name = window.prompt('请输入新家庭名称');
    if (name && state.remote) { try { const family = await ledgerApi.createFamily(name); localStorage.setItem(ledgerApi.storageKeys.family, family.id); showToast('家庭已创建'); await loadRemoteData(); await openPage('overview'); } catch (error) { showToast(error.message); } }
  }
  if (action === 'invite') {
    const openid = window.prompt('请输入成员的 OpenID');
    if (openid && state.remote) { try { await ledgerApi.inviteMember(ledgerApi.getSession().familyId, { invitee_openid: openid, role: 'member' }); showToast('邀请已创建'); await openPage('family'); } catch (error) { showToast(error.message); } }
  }
  if (action === 'member-role' && state.remote) {
    const role = window.prompt('请输入角色：admin 或 member', 'member');
    const memberId = event.target.closest('[data-member-id]')?.dataset.memberId;
    if (memberId && role) { try { await ledgerApi.updateMemberRole(ledgerApi.getSession().familyId, memberId, role); showToast('成员角色已更新'); await openPage('family'); } catch (error) { showToast(error.message); } }
  }
  if (action === 'member-disable' && state.remote) {
    const memberId = event.target.closest('[data-member-id]')?.dataset.memberId;
    if (memberId && window.confirm('确定停用该家庭成员？')) { try { await ledgerApi.disableMember(ledgerApi.getSession().familyId, memberId); showToast('成员已停用'); await openPage('family'); } catch (error) { showToast(error.message); } }
  }
  if (action === 'account') {
    const name = window.prompt('账户名称，例如：微信支付');
    if (name && state.remote) { try { const account = await ledgerApi.createAccount({ name, type: 'cash', initial_balance: '0.00' }); updateAccountOptions([...state.formOptions.accounts.filter((item) => item.id !== account.id), account]); showToast('账户已创建'); await openPage('accounts'); } catch (error) { showToast(error.message); } }
  }
  if (action === 'budget') {
    openBudgetCreate();
  }
  if (action === 'budget-menu') {
    if (!state.remote) return showToast('请先连接 API');
    openBudgetAction(event.target.closest('[data-budget-id]')?.dataset.budgetId);
  }
  if (action === 'confirm-import' && state.importTask?.id) {
    if (state.importTask.id.startsWith('local-')) { showToast('演示模式已确认；连接 API 后将正式入账'); return; }
    const confirmButton = event.target.closest('[data-action="confirm-import"]');
    if (confirmButton) { confirmButton.disabled = true; confirmButton.textContent = '正在确认…'; }
    const taskId = state.importTask.id;
    try {
      const result = await ledgerApi.confirmImport(taskId);
      if (result.status === 'completed') {
        showToast('导入明细已确认入账');
        state.importTask = null;
        await openPage('imports');
      } else {
        state.importTask = normalizeImportPreview(await ledgerApi.importPreview(taskId));
        renderImportPreview(document.querySelector('.page-view'), state.importTask);
        showToast(`仍有 ${result.error_count || 0} 行需要处理，请查看错误原因`);
      }
    } catch (error) {
      showToast(`确认失败：${error.message}`);
      if (confirmButton?.isConnected) { confirmButton.disabled = false; confirmButton.textContent = '确认入账'; }
    }
  }
  if (action === 'retry-import' && state.importTask?.id) {
    if (state.importTask.id.startsWith('local-')) { renderImportPreview(document.querySelector('.page-view'), state.importTask); showToast('已重新生成本地审核预览'); return; }
    try { state.importTask = await ledgerApi.retryImport(state.importTask.id); renderImportPreview(document.querySelector('.page-view'), state.importTask); showToast('已重新解析导入文件'); } catch (error) { showToast(error.message); }
  }
});

mainContent.addEventListener('submit', async (event) => {
  if (event.target.id === 'settings-form') {
    event.preventDefault();
    localStorage.setItem(ledgerApi.storageKeys.baseUrl, new FormData(event.target).get('baseUrl').replace(/\/$/, ''));
    showToast('API 地址已保存');
  }
  if (event.target.id === 'login-form') {
    event.preventDefault();
    const data = new FormData(event.target);
    try {
      const result = await ledgerApi.login(data.get('code'), data.get('nickname'));
      state.families = result.families || [];
      if (!result.currentFamilyId && result.families?.[0]) { localStorage.setItem(ledgerApi.storageKeys.family, result.families[0].id); }
      showToast('登录成功，正在加载家庭数据');
      if (!result.currentFamilyId && !result.families?.length) { setConnectionState(false); await openPage('family-setup'); return; }
      await loadRemoteData();
      await openPage('overview');
    } catch (error) { showToast(error.message); }
  }
  if (event.target.id === 'family-setup-form') {
    event.preventDefault();
    const name = new FormData(event.target).get('name').trim();
    if (!name) return showToast('请输入家庭名称');
    try { const family = await ledgerApi.createFamily(name); localStorage.setItem(ledgerApi.storageKeys.family, family.id); state.families = [family]; showToast('家庭创建成功'); await loadRemoteData(); await openPage('overview'); } catch (error) { showToast(error.message); }
  }
});

document.addEventListener('change', async (event) => {
  if (event.target.id === 'transaction-category') {
    state.transactionCategoryFilter = event.target.value;
    await openPage('transactions');
    return;
  }
  if (event.target.id === 'transaction-month') {
    monthSelect.value = event.target.value;
    state.transactionCategoryFilter = '';
    showToast(`已切换至${monthSelect.value}`);
    await loadRemoteData();
    await openPage('transactions');
    return;
  }
  if (event.target.id === 'family-page-select') {
    localStorage.setItem(ledgerApi.storageKeys.family, event.target.value);
    showToast('正在切换家庭');
    await loadRemoteData();
    await openPage('family');
    return;
  }
  if (event.target.id !== 'import-file') return;
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { showToast('文件不能超过 10MB'); event.target.value = ''; return; }
  const isCsv = /\.csv$/i.test(file.name);
  const sourceSelect = document.querySelector('#import-source');
  const accountSelect = document.querySelector('#import-account');
  if (state.remote && !accountSelect?.value) { showToast('请先选择入账账户'); event.target.value = ''; return; }
  if (sourceSelect) {
    const lowerName = file.name.toLowerCase();
    if (lowerName.includes('微信') || lowerName.includes('wechat')) sourceSelect.value = 'wechat';
    if (lowerName.includes('支付宝') || lowerName.includes('alipay')) sourceSelect.value = 'alipay';
  }
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      if (!state.remote) { showLocalImportPreview(file, isCsv ? String(reader.result) : ''); return; }
      const base64 = String(reader.result).split(',')[1];
      const task = await ledgerApi.imports({ filename: file.name, source: sourceSelect?.value || 'alipay', account_id: accountSelect?.value || null, content: base64 });
      state.importTask = normalizeImportPreview(await ledgerApi.importPreview(task.id));
      renderImportPreview(document.querySelector('.page-view'), state.importTask);
      showToast('上传成功，请审核导入明细');
    } catch (error) { showToast(error.message); }
  };
  if (!state.remote && isCsv) reader.readAsText(file, 'utf-8');
  else reader.readAsDataURL(file);
});

window.addEventListener('hashchange', () => openPage(window.location.hash.slice(1) || 'overview'));
setConnectionState(Boolean(ledgerApi.getSession().token));
renderTransactionRows(state.transactions);
loadRemoteData();
openPage(window.location.hash.slice(1) || 'overview');
