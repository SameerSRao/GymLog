(function () {
  function getToken() {
    return localStorage.getItem('access_token');
  }

  function checkAuth() {
    if (!getToken()) {
      window.location.replace('/login');
    }
  }

  async function authFetch(url, options) {
    const opts = options || {};
    const headers = Object.assign({}, opts.headers, {
      'Authorization': 'Bearer ' + getToken(),
    });
    const res = await fetch(url, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
      localStorage.removeItem('access_token');
      window.location.replace('/login');
      return res;
    }
    return res;
  }

  function logout() {
    localStorage.removeItem('access_token');
    window.location.replace('/login');
  }

  function getTokenPayload() {
    var token = getToken();
    if (!token) return null;
    try { return JSON.parse(atob(token.split('.')[1])); } catch (e) { return null; }
  }

  function getUsername() { var p = getTokenPayload(); return p ? p.username : ''; }
  function isAdmin() { var p = getTokenPayload(); return p ? Boolean(p.is_admin) : false; }
  function isPremium() { var p = getTokenPayload(); return p ? Boolean(p.is_premium) : false; }
  function getCurrentUserId() { var p = getTokenPayload(); return p ? parseInt(p.sub, 10) : null; }

  window.checkAuth = checkAuth;
  window.authFetch = authFetch;
  window.logout = logout;
  window.getTokenPayload = getTokenPayload;
  window.getUsername = getUsername;
  window.isAdmin = isAdmin;
  window.isPremium = isPremium;
  window.getCurrentUserId = getCurrentUserId;
})();
