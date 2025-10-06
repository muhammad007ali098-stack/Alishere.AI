async function uploadFile(e){
  e.preventDefault();
  const f = document.getElementById('fileInput').files[0];
  if(!f){ document.getElementById('uploadStatus').textContent = 'Select a file first'; return; }
  const fd = new FormData(); fd.append('file', f);
  document.getElementById('uploadStatus').textContent = 'Uploading...';
  const res = await fetch('/api/upload', {method:'POST', body: fd});
  const j = await res.json();
  document.getElementById('uploadStatus').textContent = JSON.stringify(j);
}

function appendMsg(cls, text){
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  document.getElementById('chat').appendChild(div);
  document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
}

async function send(e){
  e.preventDefault();
  const m = document.getElementById('msg').value.trim();
  if(!m) return;
  appendMsg('user', 'You: ' + m);
  appendMsg('ai', 'AI: …thinking…');
  document.getElementById('msg').value='';
  const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: m})});
  const j = await res.json();
  // replace last thinking
  const ais = document.querySelectorAll('#chat .ai');
  if(ais.length) ais[ais.length-1].textContent = 'AI: ' + (j.reply || JSON.stringify(j));
}

async function loadHistory(){
  const res = await fetch('/api/history');
  const j = await res.json();
  document.getElementById('chat').innerHTML = '';
  j.forEach(m => {
    appendMsg(m.role === 'user' ? 'user' : 'ai', (m.role === 'user' ? 'You: ' : 'AI: ') + m.content);
  });
}

async function resetConv(){
  await fetch('/api/reset', {method:'POST'});
  document.getElementById('chat').innerHTML = '';
  document.getElementById('uploadStatus').textContent = 'Conversation reset.';
}
