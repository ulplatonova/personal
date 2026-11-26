// Бот и сервер «Контент-план Ульяны».
// Маршруты:
//   POST /telegram        вебхук бота (сообщение в чат -> идея; /start, /export)
//   GET  /setup           один раз после деплоя: подключает вебхук, кнопку «План» и команды
//   GET  /api/state       все темы и идеи (нужна подпись Telegram)
//   POST /api/sync        сохранить изменения (нужна подпись Telegram)
//   GET  /api/private/*   закрытые файлы вкладки «Бренд» (нужна подпись Telegram)
//   остальное             статические файлы приложения из public/
// Доступ только у владельца: env.ALLOWED_USER_ID.

const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
const text = (s, status = 200) => new Response(s, { status, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });

async function hmac(keyBytes, msg) {
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, enc.encode(msg)));
}
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

// Проверка подписи данных Mini App (initData) по документации Telegram.
export async function verifyInitData(raw, botToken, maxAgeSec = 172800, now = Date.now()) {
  if (!raw || !botToken) return null;
  const p = new URLSearchParams(raw);
  const hash = p.get('hash');
  if (!hash) return null;
  p.delete('hash');
  const check = [...p.entries()].map(([k, v]) => `${k}=${v}`).sort().join('\n');
  const secret = await hmac(enc.encode('WebAppData'), botToken);
  const sig = hex(await hmac(secret, check));
  if (!safeEqual(sig, hash)) return null;
  const age = now / 1000 - Number(p.get('auth_date'));
  if (!(age >= -60 && age < maxAgeSec)) return null;
  try { return JSON.parse(p.get('user')); } catch { return null; }
}

const isOwner = (env, id) => !!env.ALLOWED_USER_ID && String(id) === String(env.ALLOWED_USER_ID).trim();

async function tg(env, method, body) {
  const res = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: 'POST',
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  return res.json().catch(() => ({ ok: false }));
}
const say = (env, chat_id, t) => tg(env, 'sendMessage', { chat_id, text: t }).catch(() => null);

const newId = () => 'b' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

async function readState(env) {
  const [items, ideas] = await Promise.all([
    env.DB.prepare('SELECT data FROM items ORDER BY created_at').all(),
    env.DB.prepare('SELECT data FROM ideas ORDER BY created_at DESC, id').all(),
  ]);
  const parse = (r) => r.results.map((x) => { try { return JSON.parse(x.data); } catch { return null; } }).filter(Boolean);
  return { items: parse(items), ideas: parse(ideas) };
}

async function handleTelegram(req, env) {
  const secret = hex(await crypto.subtle.digest('SHA-256', enc.encode('wh:' + env.BOT_TOKEN))).slice(0, 48);
  if (!safeEqual(req.headers.get('X-Telegram-Bot-Api-Secret-Token') || '', secret)) return text('forbidden', 403);
  const update = await req.json().catch(() => null);
  const m = update && update.message;
  if (!m || !m.chat || m.chat.type !== 'private') return text('ok');
  const chat = m.chat.id;
  const body = (m.text || '').trim();

  if (!isOwner(env, m.from.id)) {
    if (!env.ALLOWED_USER_ID && body.startsWith('/start')) {
      await say(env, chat, `Ваш Telegram ID: ${m.from.id}\nЕго нужно записать в настройки бота, это делается один раз.`);
    } else {
      await say(env, chat, 'Это личный бот.');
    }
    return text('ok');
  }

  if (body.startsWith('/start')) {
    await say(env, chat, 'Привет! Кнопка «План» слева от поля ввода открывает контент-план.\nЛюбое сообщение сюда я запишу в «Идеи». Команда /export пришлёт резервную копию файлом.');
  } else if (body.startsWith('/export')) {
    const data = await readState(env);
    const day = new Date().toISOString().slice(0, 10);
    const form = new FormData();
    form.append('chat_id', String(chat));
    form.append('document', new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }), `plan-${day}.json`);
    form.append('caption', `Резервная копия: тем ${data.items.length}, идей ${data.ideas.length}`);
    await tg(env, 'sendDocument', form).catch(() => null);
  } else if (body) {
    const lines = body.split('\n');
    const title = lines[0].trim().slice(0, 200);
    const note = lines.slice(1).join('\n').trim().slice(0, 2000);
    const idea = { id: newId(), title, note, added: new Date().toISOString().slice(0, 10) };
    const now = Date.now();
    await env.DB.prepare('INSERT INTO ideas (id, data, created_at, updated_at) VALUES (?1, ?2, ?3, ?3)').bind(idea.id, JSON.stringify(idea), now).run();
    await say(env, chat, `Записала в идеи: «${title}»`);
  } else {
    await say(env, chat, 'Пока понимаю только текст. Напишите идею словами.');
  }
  return text('ok');
}

async function auth(req, env) {
  const h = req.headers.get('Authorization') || '';
  if (!h.startsWith('tma ')) return null;
  const user = await verifyInitData(h.slice(4), env.BOT_TOKEN);
  return user && isOwner(env, user.id) ? user : null;
}

const MAX_OPS = 300;
const validRec = (r) => r && typeof r.id === 'string' && r.id.length > 0 && r.id.length <= 64 && JSON.stringify(r).length <= 20000;

async function handleSync(req, env) {
  const body = await req.json().catch(() => null);
  if (!body) return json({ error: 'bad json' }, 400);
  const stmts = [];
  const now = Date.now();
  for (const table of ['items', 'ideas']) {
    const ops = body[table] || {};
    const up = Array.isArray(ops.upsert) ? ops.upsert : [];
    const del = Array.isArray(ops.delete) ? ops.delete : [];
    if (up.length + del.length > MAX_OPS) return json({ error: 'too many' }, 413);
    for (const r of up) {
      if (!validRec(r)) return json({ error: 'bad record' }, 400);
      stmts.push(env.DB.prepare(
        `INSERT INTO ${table} (id, data, created_at, updated_at) VALUES (?1, ?2, ?3, ?3)
         ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at`
      ).bind(r.id, JSON.stringify(r), now));
    }
    for (const id of del) {
      if (typeof id !== 'string' || id.length > 64) return json({ error: 'bad id' }, 400);
      stmts.push(env.DB.prepare(`DELETE FROM ${table} WHERE id = ?1`).bind(id));
    }
  }
  if (stmts.length) await env.DB.batch(stmts);
  return json({ ok: true });
}

async function handleApi(req, env, url) {
  const user = await auth(req, env);
  if (!user) return json({ error: 'forbidden' }, 403);
  const path = url.pathname;
  if (path === '/api/state' && req.method === 'GET') return json(await readState(env));
  if (path === '/api/sync' && req.method === 'POST') return handleSync(req, env);
  if (path === '/api/private/brand.js' || /^\/api\/private\/img\/[a-z0-9-]+\.jpg$/.test(path)) {
    const inner = new URL(path.replace('/api/private/', '/private/'), url);
    const res = await env.ASSETS.fetch(new Request(inner, { method: 'GET' }));
    const out = new Response(res.body, res);
    out.headers.set('Cache-Control', 'private, max-age=86400');
    return out;
  }
  return json({ error: 'not found' }, 404);
}

// Одноразовая настройка после деплоя. Безопасно открывать повторно, токен не показывается.
async function handleSetup(url, env) {
  if (!env.BOT_TOKEN) return text('Сначала запишите BOT_TOKEN: npx wrangler secret put BOT_TOKEN', 500);
  const origin = url.origin;
  const secret = hex(await crypto.subtle.digest('SHA-256', enc.encode('wh:' + env.BOT_TOKEN))).slice(0, 48);
  const a = await tg(env, 'setWebhook', { url: `${origin}/telegram`, secret_token: secret, allowed_updates: ['message'] });
  const b = await tg(env, 'setChatMenuButton', { menu_button: { type: 'web_app', text: 'План', web_app: { url: origin + '/' } } });
  const c = await tg(env, 'setMyCommands', { commands: [{ command: 'start', description: 'Начать' }, { command: 'export', description: 'Резервная копия файлом' }] });
  const ok = a.ok && b.ok && c.ok;
  return text(
    `${ok ? 'Готово.' : 'Что-то не получилось.'}\n` +
    `Вебхук: ${a.ok ? 'ок' : a.description || 'ошибка'}\n` +
    `Кнопка «План»: ${b.ok ? 'ок' : b.description || 'ошибка'}\n` +
    `Команды: ${c.ok ? 'ок' : c.description || 'ошибка'}\n` +
    `Доступ ограничен: ${env.ALLOWED_USER_ID ? 'да' : 'нет, запишите ALLOWED_USER_ID'}`,
    ok ? 200 : 500
  );
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname;
    try {
      if (path === '/health') return text('ok');
      if (path === '/setup') return await handleSetup(url, env);
      if (path === '/telegram' && req.method === 'POST') return await handleTelegram(req, env);
      if (path.startsWith('/api/')) return await handleApi(req, env, url);
      if (path.startsWith('/private/')) return text('not found', 404);
      return await env.ASSETS.fetch(req);
    } catch (e) {
      console.error(e && e.stack ? e.stack : String(e));
      return text('error', 500);
    }
  },
};
