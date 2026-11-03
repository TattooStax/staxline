// Tab switching, side card, and a live server dot. No build step,
// no dependencies — this file is served as-is (docs/ARCHITECTURE.md).
document.querySelectorAll('.tab').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
  });
});

var drawer = document.getElementById('drawer');
document.getElementById('drawerBtn').addEventListener('click', () => drawer.classList.add('open'));
document.getElementById('drawerClose').addEventListener('click', () => drawer.classList.remove('open'));

fetch('/api/health')
  .then(r => r.json())
  .then(() => document.getElementById('health').classList.add('ok'))
  .catch(() => document.getElementById('health').classList.add('down'));
