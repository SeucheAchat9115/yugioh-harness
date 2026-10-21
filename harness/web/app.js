const token = new URLSearchParams(location.hash.slice(1)).get('token');
history.replaceState(null, '', location.pathname);
const $ = id => document.getElementById(id);
let current, sending = false, pending;
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
function card(c, label) {
  if (!c) return el('div', label || 'Empty', 'card empty');
  const node = el('button', undefined, 'card ' + (c.hidden && !c.name ? 'hidden' : ''));
  node.type = 'button';
  node.append(el('strong', c.name || 'Face-down card'));
  if (c.position) node.append(el('small', c.position));
  if (c.atk !== undefined) node.append(el('small', `ATK ${c.atk} / DEF ${c.def ?? '—'}`));
  node.onclick = () => { $('detail').replaceChildren(el('strong', c.name || 'Face-down card')); for (const [key, value] of Object.entries({...current?.cards?.[String(c.card_id)], ...c})) if (key !== 'name') $('detail').append(el('p', `${key.replaceAll('_', ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)); };
  return node;
}
function row(title, cards) { const section = el('section', undefined, 'zone'); section.append(el('h3', title)); const items = el('div', undefined, 'cards'); (cards || []).forEach((c, i) => items.append(card(c, String(i + 1)))); if (!cards?.length) items.append(el('span', 'Empty', 'muted')); section.append(items); return section; }
function player(id, p) {
  const area = el('section', undefined, 'player ' + id);
  const head = el('div', undefined, 'player-head'); head.append(el('h2', id === 'human' ? 'You' : 'Opponent'), el('strong', `${p.lp.toLocaleString()} LP`, 'lp')); area.append(head);
  area.append(el('p', `Hand ${p.hand_count} · Deck ${p.deck_count} · Extra ${p.extra_count} · Side ${p.side_count}`, 'counts'));
  if (id === 'agent') area.append(row('Hand', Array.from({length: p.hand_count}, () => ({hidden: true}))));
  area.append(row('Monster zones', p.monster_zones), row('Spell & trap zones', p.spell_trap_zones));
  const piles = el('div', undefined, 'piles'); piles.append(row('Field zone', [p.field_spell]), row('Graveyard', p.graveyard), row('Banished', p.banished)); area.append(piles);
  if (id === 'human' && p.extra_deck) { const details = el('details'); details.append(el('summary', 'Your Extra & Side Decks'), row('Extra Deck', p.extra_deck), row('Side Deck', p.side_deck)); area.append(details); }
  return area;
}
function render(data) {
  current = data; const s = data.state;
  $('message').textContent = data.message;
  $('submit').disabled = !data.can_reply || sending;
  $('action').disabled = !data.can_reply || sending;
  $('choices').replaceChildren();
  if (!s) return;
  $('meta').textContent = `${s.game_id} · ${s.mode} · revision ${s.revision}`;
  $('turn').textContent = `Turn ${s.turn} / ${s.phase} · ${s.active_player === 'human' ? 'Your turn' : 'Opponent turn'} · ${s.status}`;
  $('board').replaceChildren(player('agent', s.players.agent));
  for (const [name, cards] of Object.entries(s.shared_zones || {})) $('board').append(row(name.replaceAll('_', ' '), cards));
  $('board').append(player('human', s.players.human));
  $('hand').replaceChildren(...(s.players.human.hand || []).map(c => card(c)));
  if (!s.players.human.hand) $('hand').append(el('p', 'You manage your hidden cards privately.'));
  $('question').textContent = data.decision?.question || '';
  (data.decision?.recommendations || []).forEach((choice, i) => { const b = el('button', `${i + 1}. ${choice.label}`, 'choice'); b.append(el('small', typeof choice.reason === 'string' ? choice.reason : '')); b.disabled = !data.can_reply || sending; b.onclick = () => submit(String(i + 1)); $('choices').append(b); });
  $('events').replaceChildren(...(data.events || []).map(e => el('li', e)));
  $('chain').replaceChildren(el('p', s.chain.length ? JSON.stringify(s.chain) : 'No active chain.'));
  for (const id of ['human', 'agent']) { const p = s.players[id]; $('chain').append(el('p', `${id === 'human' ? 'You' : 'Opponent'}: Normal Summon ${p.normal_summon_used ? 'used' : 'available'}`)); if (p.restrictions.length || Object.keys(p.effect_usage).length) $('chain').append(el('p', JSON.stringify({usage: p.effect_usage, restrictions: p.restrictions}))); }
  if (s.pending_effects.length) $('chain').append(el('p', JSON.stringify(s.pending_effects)));
}
function disconnect(message) {
  current = undefined;
  $('connection').textContent = '● Disconnected';
  $('message').textContent = message;
  $('submit').disabled = true;
  $('action').disabled = true;
  for (const button of $('choices').querySelectorAll('button')) button.disabled = true;
}
async function refresh() { try { const r = await fetch('/api/state', {headers: {'X-Duel-Token': token}}); if (!r.ok) throw Error('Connection unavailable. Reopen the player UI link from your host.'); render(await r.json()); $('connection').textContent = '● Connected'; } catch (e) { disconnect(e.message); } }
async function submit(response) {
  if (sending || !current?.can_reply) return;
  const decision_id = current.decision.decision_id;
  if (!pending || pending.decision_id !== decision_id || pending.response !== response) pending = {decision_id, request_id: crypto.randomUUID(), response};
  sending = true; render(current);
  try { const r = await fetch('/api/reply', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Duel-Token': token}, body: JSON.stringify(pending)}); if (!r.ok) throw Error('Reply rejected. Refreshing the current decision.'); $('action').value = ''; pending = null; } catch (e) { $('message').textContent = e.message; } finally { sending = false; await refresh(); }
}
$('reply').onsubmit = event => { event.preventDefault(); if ($('action').value.trim()) submit($('action').value.trim()); };
refresh(); setInterval(refresh, 1500);
