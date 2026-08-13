(function () {
  document.querySelectorAll('.site-nav a').forEach(function (a) {
    if (a.pathname === location.pathname) a.classList.add('active');
  });
  var name = getUsername();
  if (!name) return;
  document.getElementById('avatar-btn').textContent = name.charAt(0).toUpperCase();
  document.getElementById('avatar-dname').textContent = name;
  document.getElementById('nav-avatar').style.display = 'flex';
  var badges = document.getElementById('avatar-badges');
  if (isAdmin()) {
    var a = document.createElement('span');
    a.className = 'badge badge-admin';
    a.textContent = 'admin';
    badges.appendChild(a);
  }
  if (isPremium()) {
    var p = document.createElement('span');
    p.className = 'badge badge-premium';
    p.textContent = 'premium';
    badges.appendChild(p);
  }
  document.getElementById('avatar-btn').addEventListener('click', function (e) {
    e.stopPropagation();
    document.getElementById('avatar-dropdown').classList.toggle('open');
  });
  document.addEventListener('click', function () {
    document.getElementById('avatar-dropdown').classList.remove('open');
  });
})();
