(function attachLedgerApi(global) {
  const storageKeys = { baseUrl: 'ledger.apiBaseUrl', token: 'ledger.token', family: 'ledger.familyId', user: 'ledger.user' };
  const fallbackBaseUrl = 'http://127.0.0.1:8000';

  function getBaseUrl() {
    return (localStorage.getItem(storageKeys.baseUrl) || fallbackBaseUrl).replace(/\/$/, '');
  }

  function getSession() {
    return {
      token: localStorage.getItem(storageKeys.token) || '',
      familyId: localStorage.getItem(storageKeys.family) || '',
      user: JSON.parse(localStorage.getItem(storageKeys.user) || 'null'),
    };
  }

  function saveSession(payload) {
    if (payload.token) localStorage.setItem(storageKeys.token, payload.token);
    if (payload.currentFamilyId) localStorage.setItem(storageKeys.family, payload.currentFamilyId);
    if (payload.user) localStorage.setItem(storageKeys.user, JSON.stringify(payload.user));
  }

  function clearSession() {
    [storageKeys.token, storageKeys.family, storageKeys.user].forEach((key) => localStorage.removeItem(key));
  }

  async function request(path, options = {}) {
    const session = getSession();
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    if (session.token) headers.set('Authorization', `Bearer ${session.token}`);
    if (session.familyId) headers.set('X-Family-Id', session.familyId);
    const response = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });
    if (response.status === 401) {
      clearSession();
      const error = new Error('登录已过期，请重新登录');
      error.status = 401;
      throw error;
    }
    if (!response.ok) {
      let message = `请求失败（${response.status}）`;
      try { message = (await response.json()).detail || message; } catch (_) {}
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : response.json();
  }

  const api = {
    storageKeys,
    getBaseUrl,
    getSession,
    saveSession,
    clearSession,
    request,
    login: async (code, nickname = '') => {
      const data = await request('/auth/wechat-login', { method: 'POST', body: JSON.stringify({ code, nickname }) });
      saveSession(data);
      return data;
    },
    families: () => request('/families'),
    createFamily: (name) => request('/families', { method: 'POST', body: JSON.stringify({ name }) }),
    home: (month) => request(`/statistics/home?month=${encodeURIComponent(month)}`),
    trend: (month, granularity = 'day') => request(`/statistics/trend?month=${encodeURIComponent(month)}&granularity=${granularity}`),
    category: (month) => request(`/statistics/category?month=${encodeURIComponent(month)}`),
    membersStats: (month) => request(`/statistics/members?month=${encodeURIComponent(month)}`),
    transactions: (month, page = 1, pageSize = 20) => request(`/transactions?month=${encodeURIComponent(month)}&page=${page}&page_size=${pageSize}`),
    createTransaction: (payload) => request('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
    updateTransaction: (id, payload) => request(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    deleteTransaction: (id) => request(`/transactions/${id}`, { method: 'DELETE' }),
    budgets: (month) => request(`/budgets?month=${encodeURIComponent(month)}`),
    createBudget: (payload) => request('/budgets', { method: 'POST', body: JSON.stringify(payload) }),
    updateBudget: (id, payload) => request(`/budgets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    deleteBudget: (id) => request(`/budgets/${id}`, { method: 'DELETE' }),
    categories: () => request('/categories'),
    accounts: () => request('/accounts'),
    members: (familyId) => request(`/families/${familyId}/members`),
    inviteMember: (familyId, payload) => request(`/families/${familyId}/invitations`, { method: 'POST', body: JSON.stringify(payload) }),
    updateMemberRole: (familyId, memberId, role) => request(`/families/${familyId}/members/${memberId}`, { method: 'PUT', body: JSON.stringify({ role }) }),
    disableMember: (familyId, memberId) => request(`/families/${familyId}/members/${memberId}`, { method: 'DELETE' }),
    createAccount: (payload) => request('/accounts', { method: 'POST', body: JSON.stringify(payload) }),
    updateAccount: (id, payload) => request(`/accounts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    disableAccount: (id) => request(`/accounts/${id}`, { method: 'DELETE' }),
    imports: (payload) => request('/imports', { method: 'POST', body: JSON.stringify(payload) }),
    importPreview: (id) => request(`/imports/${id}`),
    updateImportRow: (taskId, rowId, payload) => request(`/imports/${taskId}/rows/${rowId}`, { method: 'PUT', body: JSON.stringify(payload) }),
    confirmImport: (id, rowIds) => request(`/imports/${id}/confirm`, { method: 'POST', body: JSON.stringify({ row_ids: rowIds }) }),
    retryImport: (id) => request(`/imports/${id}/retry`, { method: 'POST' }),
  };

  global.ledgerApi = api;
})(window);
