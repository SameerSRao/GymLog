checkAuth();

document.getElementById('import-btn').addEventListener('click', async function () {
  var raw = document.getElementById('json-input').value.trim();
  var resultEl = document.getElementById('result');
  var btn = document.getElementById('import-btn');

  var payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    resultEl.className = 'result error';
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<strong>Invalid JSON</strong> — ' + e.message;
    return;
  }

  if (!Array.isArray(payload)) {
    resultEl.className = 'result error';
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<strong>Invalid format</strong> — payload must be a JSON array.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Importing…';
  resultEl.style.display = 'none';

  try {
    var res = await authFetch('/api/workouts/import', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    var data = await res.json();

    if (!res.ok) {
      resultEl.className = 'result error';
      resultEl.innerHTML = '<strong>Error ' + res.status + '</strong> — ' + (data.detail || 'Import failed.');
    } else if (data.sessions_created > 0) {
      window.location.replace('/workouts');
    } else {
      var errHtml = '';
      if (data.errors && data.errors.length > 0) {
        errHtml = '<div class="error-list">' +
          data.errors.map(function(e) {
            return '<div class="error-item">Session ' + e.index + ': ' + e.reason + '</div>';
          }).join('') +
          '</div>';
      }
      resultEl.className = 'result error';
      resultEl.style.display = 'block';
      resultEl.innerHTML =
        '<div class="result-stat">0 sessions imported</div>' +
        '<div style="color:#888;font-size:0.82rem;">' + data.errors.length + ' session(s) skipped</div>' +
        errHtml;
    }
  } catch (e) {
    resultEl.className = 'result error';
    resultEl.innerHTML = '<strong>Network error</strong> — ' + e.message;
  }

  resultEl.style.display = 'block';
  btn.disabled = false;
  btn.textContent = 'Import';
});
