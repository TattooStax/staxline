// Tab switching, side card, live server dot, and the Messages
// surface over the local API. No build step, no dependencies —
// this file is served as-is (docs/ARCHITECTURE.md). All record
// text is rendered with textContent: message bodies are other
// people's words and never become markup.
document.querySelectorAll('.tab').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'contacts') loadContacts();
  });
});

var drawer = document.getElementById('drawer');
document.getElementById('drawerBtn').addEventListener('click', () => {
  drawer.classList.add('open');
  loadActivity();
});
document.getElementById('drawerClose').addEventListener('click', () => drawer.classList.remove('open'));

function api(path, opts) {
  return fetch(path, opts).then(function (r) {
    return r.json().then(function (j) {
      if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
      return j;
    });
  });
}

function el(tag, cls, text) {
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function when(ts) {
  return ts ? new Date(ts * 1000).toLocaleString() : '';
}

// -- Conversations ---------------------------------------------

var currentConv = null;

function loadConversations() {
  api('/api/conversations').then(function (list) {
    var box = document.getElementById('convList');
    box.replaceChildren();
    document.getElementById('convEmpty').hidden = list.length > 0;
    list.forEach(function (c) {
      var item = el('button', 'conv-item');
      var top = el('span', 'conv-top');
      top.append(el('span', 'conv-name', c.name || c.number));
      if (c.held_drafts) {
        top.append(el('span', 'badge', c.held_drafts + ' held'));
      }
      var last = el('span', 'conv-last',
        (c.last_direction === 'out' ? 'You: ' : '') + (c.last_body || ''));
      item.append(top, last);
      item.addEventListener('click', () => openThread(c.id));
      box.append(item);
    });
  }).catch(function (e) {
    document.getElementById('ingestNote').textContent = e.message;
  });
}

function openThread(id) {
  currentConv = id;
  api('/api/conversations/' + id).then(function (c) {
    document.getElementById('convView').hidden = true;
    document.getElementById('threadView').hidden = false;
    document.getElementById('threadTitle').textContent =
      c.name || c.number;
    var box = document.getElementById('threadMsgs');
    box.replaceChildren();
    c.messages.forEach(function (m) {
      var wrap = el('div', 'msg ' + (m.direction === 'in' ? 'in' : 'out'));
      wrap.append(el('p', 'msg-body', m.body || ''));
      wrap.append(el('p', 'msg-meta',
        when(m.at) + (m.direction === 'out' ? ' · ' + m.state : '')));
      box.append(wrap);
    });
    renderDrafts(c.drafts);
  });
}

function renderDrafts(drafts) {
  var box = document.getElementById('draftList');
  box.replaceChildren();
  drafts.filter(d => d.state === 'held').forEach(function (d) {
    var card = el('div', 'draft');
    card.append(el('p', 'draft-tag', 'Held draft — waiting for approval'));
    card.append(el('p', 'draft-body', d.body));
    var btn = el('button', 'btn', 'Approve & send');
    btn.addEventListener('click', function () {
      if (!window.confirm('Send this reply now?')) return;
      api('/api/drafts/' + d.id + '/approve', { method: 'POST' })
        .then(function () { openThread(currentConv); })
        .catch(function (e) {
          document.getElementById('composerNote').textContent = e.message;
        });
    });
    card.append(btn);
    box.append(card);
  });
}

document.getElementById('backBtn').addEventListener('click', function () {
  document.getElementById('threadView').hidden = true;
  document.getElementById('convView').hidden = false;
  currentConv = null;
  loadConversations();
});

document.getElementById('holdBtn').addEventListener('click', function () {
  var body = document.getElementById('draftBody').value.trim();
  var note = document.getElementById('composerNote');
  if (!body || !currentConv) return;
  api('/api/conversations/' + currentConv + '/drafts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body: body })
  }).then(function () {
    document.getElementById('draftBody').value = '';
    note.textContent = 'Held. Nothing sends until it is approved.';
    openThread(currentConv);
  }).catch(e => { note.textContent = e.message; });
});

document.getElementById('ingestBtn').addEventListener('click', function () {
  var note = document.getElementById('ingestNote');
  note.textContent = 'Checking the modem…';
  api('/api/ingest', { method: 'POST' }).then(function (r) {
    note.textContent = r.ingested
      ? r.ingested + ' new message(s).' : 'Nothing new.';
    loadConversations();
  }).catch(e => { note.textContent = e.message; });
});

// -- Contacts ---------------------------------------------------

function loadContacts() {
  api('/api/contacts').then(function (list) {
    var box = document.getElementById('contactList');
    box.replaceChildren();
    document.getElementById('contactEmpty').hidden = list.length > 0;
    list.forEach(function (c) {
      var row = el('div', 'contact-row');
      row.append(el('span', 'conv-name', c.name || c.number));
      row.append(el('span', 'conv-last',
        'Last contact ' + when(c.last_contact_at)));
      box.append(row);
    });
  }).catch(function () { /* the empty state stays honest */ });
}

// -- Activity ---------------------------------------------------

function loadActivity() {
  api('/api/activity').then(function (list) {
    var box = document.getElementById('activityList');
    box.replaceChildren();
    if (!list.length) {
      box.append(el('p', null, 'Nothing yet.'));
      return;
    }
    list.forEach(function (a) {
      var row = el('p', 'activity-row', a.text);
      row.title = when(a.at);
      box.append(row);
    });
  }).catch(function () { /* drawer keeps its placeholder text */ });
}

// -- Health -----------------------------------------------------

fetch('/api/health')
  .then(r => r.json())
  .then(function (h) {
    document.getElementById('health').classList.add('ok');
    if (!h.modem) {
      document.getElementById('ingestNote').textContent =
        'Modem worker not connected — showing records only.';
    }
  })
  .catch(() => document.getElementById('health').classList.add('down'));

loadConversations();
