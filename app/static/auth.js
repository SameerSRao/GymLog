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

  window.checkAuth = checkAuth;
  window.authFetch = authFetch;
  window.logout = logout;
})();
