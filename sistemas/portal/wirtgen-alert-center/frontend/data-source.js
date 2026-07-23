(function () {
  'use strict';

  // Vazio = same-origin. As requisições vão para /api/... no host atual e
  // são proxiadas pelo frontend/server.js para o wac-backend:4016.
  const API_BASE_URL = window.WIRTGEN_API_URL || '';

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: { 'Accept': 'application/json', ...(options.headers || {}) },
        signal: controller.signal,
        cache: 'no-store'
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(`API ${response.status}: ${detail || response.statusText}`);
      }
      return await response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  window.WirtgenDataSource = {
    loadAlerts() {
      return request('/api/alertas');
    },
    health() {
      return request('/api/health');
    }
  };
})();
