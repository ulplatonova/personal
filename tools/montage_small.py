import sys; sys.path.insert(0, '/home/user/personal/.claude/skills/ugc-girl-edit/scripts')
#!/usr/bin/env python3
"""Сборка ролика 1080x1920 по плану plan.json. Три вида монтажа: subs (субтитры с акцентами), sketch (окно сверху и текст
от руки на чистом фоне), board (окно в центре и живая доска из картинок). Формат плана — references/plan.md.
python montage.py папка/plan.json --out ролик.mp4
python montage.py папка/plan.json --check            только проверить план
python montage.py папка/plan.json --preview 1,5,12   кадры в папку preview рядом с планом
"""
import argparse, json, math, os, re, subprocess, sys, tempfile
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from letters import LET
from ff import FF

W, H, FPS = 1080, 1920, 30
SAFE = (85, 170, 995, 1750)                 # текст и графика не подходят к краям: около 8–9 % со всех сторон
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = '/home/user/personal/.claude/skills/ugc-girl-edit/assets/fonts'
ap = argparse.ArgumentParser()
ap.add_argument('plan'); ap.add_argument('--out', default=''); ap.add_argument('--preview', default=''); ap.add_argument('--check', action='store_true')
A = ap.parse_args()
PLAN_DIR = os.path.dirname(os.path.abspath(A.plan))
P = json.load(open(A.plan, encoding='utf8'))


def rel(p):
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.join(PLAN_DIR, p)


def fail(msg):
    print('ОШИБКА:', msg); sys.exit(1)


def hexcol(s, d):
    s = (s or d).lstrip('#'); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


SRC = rel(P['video'])
if not os.path.exists(SRC): fail(f'не найдено видео {SRC}')
ACCENT = hexcol(P.get('accent'), '#FAE4B6')
WHITE, DARK = (255, 255, 255), (28, 20, 15)
KEEP = [(float(a), float(b)) for a, b in P['keep']]


ROWS = []; _f = 0
for a, b in KEEP:
    n = int(round((b - a) * FPS)); ROWS.append((_f, _f + n, a, n)); _f += n
TOTAL = _f; END = TOTAL / FPS
SEG_T = [(r[0] / FPS, r[2]) for r in ROWS]


def to_out(s):
    for (a, b), r in zip(KEEP, ROWS):
        if a - 1e-3 <= s <= b + 1e-3: return r[0] / FPS + (s - a)
    return None


# ------------------------------ слова ------------------------------
WD = json.load(open(rel(P['words']), encoding='utf8'))
WORDS = []
for c in WD['chunks']:
    for w in c['words']:
        for (ka, kb), r in zip(KEEP, ROWS):
            ov = min(w['e'], kb) - max(w['s'], ka)                # первое слово куска распознаётся растянутым: хватает части слова
            if ov >= min(0.06, (w['e'] - w['s']) * .5) and ov > 0:
                WORDS.append({'w': w['w'], 's': r[0] / FPS + max(w['s'], ka) - ka}); break
WORDS.sort(key=lambda w: w['s'])

# ------------------------------ шрифты и стили ------------------------------
_fc = {}


def fnt(name, size, var=None):
    k = (name, size)
    if k not in _fc:
        f = ImageFont.truetype(f'{FD}/{name}', max(8, int(size)))
        if var:
            try: f.set_variation_by_axes([var])
            except Exception: pass
        _fc[k] = f
    return _fc[k]


#  стиль: шрифт, насыщенность, трекинг, сжатие, цвет, шаг строк, тень
ST = {'b': ('InterTight.ttf', 500, -0.085, 1.0, WHITE, 0.78, 1),       # основной: плотный гротеск
      'h': ('InterTight.ttf', 500, -0.085, 1.0, ACCENT, 0.78, 1),      # кремовый с подчёркиванием (#слово#)
      'i': ('PlayfairDisplay-Italic.ttf', 640, -0.07, 0.84, WHITE, 0.62, 1),  # акцент (*слово*)
      's': ('GreatVibes-Regular.ttf', None, 0.0, 1.0, ACCENT, 0.56, 1),        # росчерк (%слово%)
      'p': ('Arimo.ttf', 700, 0.0, 1.0, WHITE, 1.08, 2)}               # нарочно обычные субтитры, сильная тень
ANIM = ('i', 'h', 's')
AD = 0.34


def word_mask(txt, st, size):
    name, var, tr, sq = ST[st][:4]
    f = fnt(name, size, var)
    asc, desc = f.getmetrics()
    xs, x = [], 0.0
    for ch in txt:
        xs.append(x); x += f.getlength(ch) + tr * size
    x -= tr * size
    m = Image.new('L', (int(x) + 16, asc + desc + 16)); d = ImageDraw.Draw(m)
    for ch, xx in zip(txt, xs): d.text((8 + xx, 8), ch, font=f, fill=255)
    if sq != 1: m = m.resize((max(1, int(m.width * sq)), m.height), Image.LANCZOS)
    return np.asarray(m).astype(np.float32), 8 + asc


# ------------------------------ лицо: где голова на каждом куске ------------------------------
def probe():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'f.png')
        subprocess.run([FF, '-v', 'error', '-y', '-ss', f'{KEEP[0][0]:.3f}', '-i', SRC, '-frames:v', '1', p], check=True)
        im = cv2.imread(p)
    return im.shape[1], im.shape[0]


VW, VH = probe()
K0 = max(W / VW, H / VH)
SW, SH = int(math.ceil(VW * K0 / 2) * 2), int(math.ceil(VH * K0 / 2) * 2)   # до расчёта масштаба: лица ищем в этом кадре


def grab(t):
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{t:.3f}', '-i', SRC, '-frames:v', '1', '-vf', f'scale={SW}:{SH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return np.frombuffer(r, np.uint8).reshape(SH, SW, 3)


CASC = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
cache_f = os.path.join(PLAN_DIR, '.faces.json')
_key = json.dumps(KEEP)
FACES = None; CHEST = []
if os.path.exists(cache_f):
    c = json.load(open(cache_f))
    if c.get('key') == _key: FACES = c['faces']; CHEST = c.get('chest', [])
if FACES is None:
    FACES = []
    for a, b in KEEP:
        got = []
        for u in (0.1, 0.3, 0.5, 0.7, 0.9):
            g = cv2.cvtColor(grab(a + (b - a) * u), cv2.COLOR_RGB2GRAY); k = 540 / g.shape[1]
            CHEST.append(float(np.median(g[int(g.shape[0] * .55):int(g.shape[0] * .75), g.shape[1] // 3:g.shape[1] * 2 // 3])))
            fs = CASC.detectMultiScale(cv2.resize(g, None, fx=k, fy=k), 1.1, 6, minSize=(50, 50))
            if len(fs):
                x, y, w, h = max(fs, key=lambda q: q[2] * q[3]); got.append(((x + w / 2) / k, y / k, h / k))
        c_ = np.median(got, 0).tolist() if got else [SW / 2, SH * 0.2, SH * 0.17]
        FACES.append([c_[0] / SW, c_[1] / SH, c_[2] / SH])
    json.dump({'key': _key, 'faces': FACES, 'chest': CHEST}, open(cache_f, 'w'))
# Один масштаб на весь ролик: зумов и перекадрирования нет, человек просто занимает кадр от груди и выше.
_fh = float(np.median([x[2] for x in FACES]))
ZOOM = float(P.get('zoom') or np.clip(0.155 / max(_fh, 1e-3), 1.0, 1.35))
SW, SH = int(math.ceil(VW * K0 * ZOOM / 2) * 2), int(math.ceil(VH * K0 * ZOOM / 2) * 2)


def row_of(f):
    for k, r in enumerate(ROWS):
        if r[0] <= f < r[1]: return k
    return len(ROWS) - 1


def crop_x(k):
    x_, y_, _h = FACES[k]
    return int(np.clip(x_ * SW - W / 2, 0, SW - W)), int(np.clip(y_ * SH - H * 0.285, 0, SH - H))


def face(k):
    """лицо в координатах кадра 1080x1920: центр x, верх лица, высота"""
    x_, y_, h_ = FACES[k]; ox, oy = crop_x(k)
    return x_ * SW - ox, y_ * SH - oy, h_ * SH


# ------------------------------ окна ------------------------------
RECT = {'full': (0, 0, W, H), 'mid': (115, 450, 850, 750), 'top': (115, 180, 850, 750), 'board': (95, 550, 890, 680)}
FRAMING = {'mid': (.29, .17), 'top': (.29, .17), 'board': (.25, .15)}   # доля лица в окне, отступ лица сверху (над лицом ещё лоб и волосы)


def matrix(name, f):
    if name == 'full': return np.array([1.0, 0.0, 0.0])
    cx, top, fh = face(row_of(f)); x, y, w, h = RECT[name]; ratio, off = FRAMING[name]
    z = float(np.clip(ratio * h / max(fh, 1), max(w / W, h / H), 1.7))
    tx = x + w / 2 - cx * z; ty = y + off * h - top * z
    tx = min(x, max(x + w - W * z, tx)); ty = min(y, max(y + h - H * z, ty))
    return np.array([z, tx, ty])


def ease(q):
    q = float(np.clip(q, 0, 1)); return 4 * q ** 3 if q < .5 else 1 - (-2 * q + 2) ** 3 / 2


# ------------------------------ план: блоки подписей ------------------------------
TOK = re.compile(r'^(.*?)(?:~(\d+))?$')
errors = []


class Block:
    pass


def parse_text(text):
    """'девчонки с / *UGC и lifestyle*' -> строки из (слово, стиль, сколько слов речи)"""
    lines, st = [], 'b'
    for raw in text.split('/'):
        line = []
        for tok in raw.split():
            nst = st
            for ch, name in (('*', 'i'), ('#', 'h'), ('%', 's')):
                if tok.startswith(ch):
                    st = name; nst = name; tok = tok[1:]
                if tok.rstrip('.,!?:;').endswith(ch) or tok.split('~')[0].endswith(ch):
                    tail = tok.replace(ch, '', 1) if ch in tok else tok
                    tok = tail; st = 'b'
            m = TOK.match(tok); word, cnt = m.group(1), m.group(2)
            line.append((word.replace('_', ' '), nst, 1 if cnt is None else int(cnt)))
        if line: lines.append(line)
    return lines


cursor = 0
BLOCKS = []
mode = 'full'
SIZE = {'full': (102, 170, 75), 'sketch': (88, 148, 70), 'board': (72, 122, 60)}
for bi, spec in enumerate(P['blocks']):
    b = Block(); b.i = bi; b.spec = spec; b.lines = parse_text(spec['text']); b.mode = spec.get('mode', mode); mode = b.mode
    b.place = spec.get('place', 'chest'); b.plain = bool(spec.get('plain'))
    b.times, b.heard = [], []
    for line in b.lines:
        for word, st, cnt in line:
            if cnt == 0:
                b.times.append(None); continue
            if cursor >= len(WORDS):
                errors.append(f'блок {bi} «{spec["text"]}»: слова закончились, в тексте плана больше слов, чем в речи'); b.times.append(None); continue
            b.times.append(WORDS[cursor]['s']); b.heard += [w['w'] for w in WORDS[cursor:cursor + cnt]]; cursor += cnt
    tt = [x for x in b.times if x is not None]
    b.t0 = tt[0] if tt else (BLOCKS[-1].t0 if BLOCKS else 0)
    b.times = [b.t0 if x is None else x for x in b.times]
    BLOCKS.append(b)
if cursor != len(WORDS):
    errors.append(f'в речи осталось {len(WORDS) - cursor} слов без подписи: {" ".join(w["w"] for w in WORDS[cursor:cursor + 8])}…')
if BLOCKS: BLOCKS[0].t0 = 0.0
# склейка: блок, начавшийся со склейкой, не раньше неё
for b in BLOCKS:
    for s0, _ in SEG_T:
        if abs(b.t0 - s0) < 0.2 and b.t0 < s0: b.t0 = s0

# ------------------------------ состояния кадра ------------------------------
STATES = [(0.0, 'full', 0.0)]
SCENES = []                      # (t0, t1, mode, блок)
prev = 'full'
for k, b in enumerate(BLOCKS):
    if b.mode != prev:
        SCENES.append([b.t0, END, b.mode, b])
        if SCENES[:-1]: SCENES[-2][1] = b.t0
        if b.t0 < .05:                                   # ролик сразу начинается с этого вида: без перехода
            STATES[0] = (0.0, 'top' if b.mode == 'sketch' else b.mode, 0.0); prev = b.mode; continue
        if b.mode == 'sketch':
            nxt = BLOCKS[k + 1] if k + 1 < len(BLOCKS) and BLOCKS[k + 1].mode == 'sketch' else None
            if nxt and nxt.t0 - b.t0 >= 0.3:
                STATES.append((b.t0, 'mid', 0.47)); STATES.append((nxt.t0, 'top', 0.63))
            else:
                STATES.append((b.t0, 'top', 0.75))
        elif b.mode == 'board': STATES.append((b.t0, 'board', 0.53))
        else: STATES.append((b.t0, 'full', 0.53))
        prev = b.mode


def state_at(t):
    i = 0
    for k, s in enumerate(STATES):
        if s[0] <= t + 1e-3: i = k
    c = STATES[i]; p = STATES[max(0, i - 1)]
    return p[1], c[1], (ease((t - c[0]) / c[2]) if c[2] else 1.0)


def lerp_rect(a, b, k):
    return tuple(RECT[a][j] + (RECT[b][j] - RECT[a][j]) * k for j in range(4))


def settled_state(t):
    i = 0
    for k, s in enumerate(STATES):
        if s[0] <= t + 1e-3: i = k
    return STATES[i][1]


# ------------------------------ маска: текст за головой (если есть) ------------------------------
SEG = None
if not A.check:
    try:
        import mediapipe as mp
        SEG = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
    except Exception:
        SEG = None
_ema = [None]


def person_mask(frame):
    r = SEG.process(cv2.resize(frame, (256, 456)))
    m = r.segmentation_mask.astype(np.float32)
    _ema[0] = m if _ema[0] is None else 0.6 * m + 0.4 * _ema[0]
    a = cv2.resize(_ema[0], (W, H), interpolation=cv2.INTER_CUBIC)
    return np.clip((a - .45) / .3, 0, 1)


# ------------------------------ раскладка подписей ------------------------------
def layout(b):
    """считает позиции слов; подпись стоит ниже подбородка и внутри безопасной зоны"""
    t = b.t0; stn = settled_state(t + 0.01); f = int(t * FPS); k = row_of(f)
    cx, ftop, fh = face(k)
    m = b.mode if b.mode in SIZE else 'full'
    _k = float(b.spec.get('size', P.get('text_scale', 1.0)))
    base_s, acc_s, plain_s = [v * _k for v in SIZE[m]]
    acc_s = base_s * float(P.get('accent_ratio', acc_s / base_s))
    align, x = 'c', W / 2
    top_lane = b.place in ('top', 'top-left', 'top-right')
    if m != 'full': top_lane = False
    if top_lane and b.place == 'top-left': align, x = 'l', SAFE[0] + 20
    if top_lane and b.place == 'top-right': align, x = 'r', SAFE[2] - 20
    if b.place == 'left' and m == 'full': align, x = 'l', SAFE[0] + 25
    maxw = (SAFE[2] - SAFE[0]) - (40 if align == 'c' else 60)
    z, tx, ty = matrix(stn, f)
    rect = RECT[stn]
    if m != 'full': maxw = rect[2] - 70; x = rect[0] + rect[2] / 2
    chin = ty + (ftop + fh * 1.18) * z
    for attempt in range(6):
        shrink = 0.88 ** attempt
        rows = []
        for line in b.lines:
            sc = 1.0
            for _ in range(5):
                parts = []
                for word, st, cnt in line:
                    s_ = 'p' if b.plain else st
                    sz = (plain_s if s_ == 'p' else acc_s * (1.05 if s_ == 's' else 1) if s_ in ('i', 's') else base_s) * shrink * sc
                    parts.append((word_mask(word, s_, sz), s_, sz))
                sz0 = max(p[2] for p in parts); gap = sz0 * (0.15 if parts[0][1] in ('b', 'h') else 0.21)
                tw = sum(p[0][0].shape[1] - 16 * ST[p[1]][3] for p in parts) + gap * (len(parts) - 1)
                if tw <= maxw: break
                sc *= maxw / tw * 0.98
            rows.append((parts, sz0, gap, tw))
        heights = 0
        for li, (parts, sz0, gap, tw) in enumerate(rows):
            if li: heights += ST[parts[0][1]][5] * sz0
        first = rows[0][1]
        if m == 'full':
            if top_lane:
                y0 = SAFE[1] + first * 0.9
                head_top = ftop - fh * 0.45
                bottom = y0 + heights + rows[-1][1] * .25
                can_hide = SEG is not None or A.check
                if bottom > head_top + (fh * 0.45 if can_hide else 0):
                    if attempt < 5: continue
                    top_lane = False                                            # нет места над головой — вниз
                    align, x = 'c', W / 2
                    continue
                break
            y0 = max(chin + first * .78, H * 0.60)
            lim = H * 0.83 - heights - rows[-1][1] * .28
            if b.place == 'left': y0 = max(y0, H * .66)
            if y0 > lim and attempt < 5: continue
            break
        else:
            y0 = chin + first * 0.82
            bottom_lim = rect[1] + rect[3] - 24 - heights - rows[-1][1] * .28
            if y0 > bottom_lim and attempt < 5: continue
            break
    b.top_lane = top_lane and m == 'full'
    b.words = []
    base = y0; idx = 0
    for li, (parts, sz0, gap, tw) in enumerate(rows):
        if li: base += ST[parts[0][1]][5] * sz0
        xx = x - tw / 2 if align == 'c' else (x if align == 'l' else x - tw)
        for (a, b0), s_, sz in parts:
            b.words.append((a, xx - 8 * ST[s_][3], base - b0, s_, b.times[idx], li)); idx += 1
            xx += a.shape[1] - 16 * ST[s_][3] + gap
    b.rect_y = rect[1]; b.cache = {}
    # проверка зоны и лица по пикселям
    for a, xx, yy, s_, tw_, li in b.words:
        ys, xs = np.nonzero(a > 128)
        if not len(xs): continue
        x0, x1, y0_, y1 = xx + xs.min(), xx + xs.max(), yy + ys.min(), yy + ys.max()
        if b.spec.get('hide'): break
        if x0 < SAFE[0] or x1 > SAFE[2] or y0_ < SAFE[1] or y1 > SAFE[3]:
            errors.append(f'блок {b.i} «{b.spec["text"]}»: текст у края экрана')
        if not b.top_lane and y0_ < chin - 8:
            errors.append(f'блок {b.i} «{b.spec["text"]}»: текст заходит на лицо, сделайте короче или разбейте')
        break


def b_layer(b, idx):
    if idx in b.cache: return b.cache[idx]
    ws = [b.words[k] for k in idx]
    x0 = int(min(w[1] for w in ws)) - 60; y0 = int(min(w[2] for w in ws)) - 60
    x1 = int(max(w[1] + w[0].shape[1] for w in ws)) + 60; y1 = int(max(w[2] + w[0].shape[0] for w in ws)) + 60
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.float32); s1 = np.zeros((y1 - y0, x1 - x0), np.float32); s2 = s1.copy()
    for a, xx, yy, st, t_, li in ws:
        cx, cy = int(round(xx - x0)), int(round(yy - y0)); h, w_ = a.shape
        col = np.array(ST[st][4], np.float32); al = a / 255
        reg = rgba[cy:cy + h, cx:cx + w_]
        reg[..., :3] = reg[..., :3] * (1 - al[..., None]) + col * al[..., None]; reg[..., 3] = np.maximum(reg[..., 3], a)
        (s2 if ST[st][6] == 2 else s1)[cy:cy + h, cx:cx + w_] = np.maximum((s2 if ST[st][6] == 2 else s1)[cy:cy + h, cx:cx + w_], a)
        if st == 'h':
            yb = cy + int(h * .9); lw = max(2, h // 36)
            rgba[yb:yb + lw, cx:cx + w_, :3] = col; rgba[yb:yb + lw, cx:cx + w_, 3] = 255
    sa = np.zeros_like(s1)
    if s1.max() > 0: sa = np.maximum(cv2.GaussianBlur(s1, (0, 0), 11) * .40, cv2.GaussianBlur(s1, (0, 0), 2.5) * .34)
    if s2.max() > 0:
        m2 = np.roll(s2, 5, axis=0)
        sa = np.maximum(sa, np.clip(np.maximum(cv2.GaussianBlur(m2, (0, 0), 8) * 1.5, cv2.GaussianBlur(m2, (0, 0), 2.5) * 1.6), 0, 245))
    if sa.max() > 0:
        o = np.zeros_like(rgba); ra = rgba[..., 3] / 255
        o[..., 3] = 255 * (ra + sa / 255 * (1 - ra)); ok = o[..., 3] > 0
        o[..., :3][ok] = rgba[..., :3][ok] * ra[ok, None] * 255 / o[..., 3][ok, None]
        rgba = o
    b.cache[idx] = (rgba, x0, y0)
    return b.cache[idx]


def blend(frame, rgba, x, y, alpha=1.0):
    h, w = rgba.shape[:2]; x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0: return
    p = rgba[y0 - y:y1 - y, x0 - x:x1 - x]; a = p[..., 3:4] * (alpha / 255)
    reg = frame[y0:y1, x0:x1]; reg *= (1 - a); reg += p[..., :3] * a


def draw_block(b, img, t, dy=0):
    still, moving = [], []
    for k, w in enumerate(b.words):
        dt = t - w[4]
        if dt < -1e-3: continue
        (moving if (not b.top_lane and w[3] in ANIM and dt < AD) else still).append(k)
    if still:
        r, x0, y0 = b_layer(b, tuple(still)); blend(img, r, x0, y0 + dy)
    for k in moving:
        r, x0, y0 = b_layer(b, (k,))
        dt = t - b.words[k][4]; q = min(1, dt / AD); e = 1 - (1 - q) ** 3; sc = .9 + .1 * e; h, w_ = r.shape[:2]
        rr = cv2.resize(r, (max(2, int(w_ * sc)), max(2, int(h * sc))), interpolation=cv2.INTER_LINEAR)
        blend(img, rr, x0 + (w_ - rr.shape[1]) / 2, y0 + (h - rr.shape[0]) / 2 + (1 - e) * 45 + dy, min(1, dt / (AD * .6)))


for b in BLOCKS: layout(b)
# дорожки: нижняя и верхняя живут независимо; подпись держится до следующей в своей дорожке, смены сцены или 3 с тишины
for lane in (False, True):
    ls = [b for b in BLOCKS if b.top_lane == lane]
    for k, b in enumerate(ls):
        nxt = ls[k + 1].t0 if k + 1 < len(ls) else END
        last = max(w[4] for w in b.words)
        b.t1 = min(nxt, last + 3.0, END)
        sc_end = [s[0] for s in SCENES if s[0] > b.t0 + 1e-3]
        if sc_end: b.t1 = min(b.t1, sc_end[0])
        if 'until' in b.spec: b.t1 = min(b.t1, float(b.spec['until']))
for k, b in enumerate(BLOCKS):                 # в начале смены фона белому тексту мешает переход
    b.min_t = b.t0 + 0.22 if b.t0 > .05 and any(abs(s[0] - b.t0) < 1e-3 and s[2] in ('board', 'sketch') for s in SCENES) else b.t0


# ------------------------------ рисунок от руки ------------------------------
def jitter(pts, rng, amp):
    p = np.asarray(pts, np.float32); out = []
    for a, c in zip(p[:-1], p[1:]):
        n = max(2, int(np.linalg.norm(c - a) / 7))
        out += [a + (c - a) * q for q in np.linspace(0, 1, n, endpoint=False)]
    out.append(p[-1]); q = np.array(out)
    lo = np.cumsum(rng.normal(0, 1, (len(q), 2)), 0); lo -= np.linspace(0, 1, len(q))[:, None] * lo[-1]
    lo = lo / max(1e-6, np.abs(lo).max()) * amp
    return q + lo + rng.normal(0, amp * .1, q.shape)


def build_drawing(spec, seed):
    """текст крупными буквами и рамка под окном"""
    rng = np.random.RandomState(seed)
    ry0, ry1 = RECT['top'][1] + RECT['top'][3] + 45, SAFE[3] - 30
    lines = [re.sub(r'[.,;:]', '', str(x)).upper() for x in spec.get('lines', [])]
    strokes = []
    frame = spec.get('frame', True) and bool(lines)
    pad = 70 if frame else 0
    y0, y1 = ry0 + pad, ry1 - pad
    x0, x1 = SAFE[0] + 40 + pad, SAFE[2] - 40 - pad
    if lines:
        d_h = 0
        n = len(lines); lh = min(175, (y1 - y0 - d_h - (n - 1) * 34) / n)
        lw = max(len(l) for l in lines)
        step = min(lh * .82, (x1 - x0) / max(lw, 1)); gw = step * .82
        lh = min(lh, gw * 1.62)
        tot = n * lh + (n - 1) * 34 + d_h
        yy = y0 + (y1 - y0 - tot) / 2
        top_text = yy
        for li, l in enumerate(lines):
            xx = (x0 + x1) / 2 - step * len(l) / 2 + (step - gw) / 2
            for ch in l:
                if ch != ' ' and ch in LET:
                    dy = rng.normal(0, 3); h_ = lh * rng.uniform(.93, 1.04); w_ = gw * rng.uniform(.92, 1.05)
                    for s in LET[ch]:
                        strokes.append(jitter([(xx + a * w_, yy + dy + c * h_) for a, c in s], rng, 4.5))
                elif ch != ' ':
                    errors.append(f'рисунок: нет буквы «{ch}»')
                xx += step
            yy += lh + 34
    n_text = len(strokes)
    if frame:
        L, R, T, B, r = x0 - pad + 8, x1 + pad - 8, ry0 + 8, ry1 - 8, 100
        def carc(cx, cy, a0, a1):
            return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in np.linspace(a0, a1, 12)]
        fr = [(R - 20, T + 3), ((L + R) / 2, T - 3), (L + r, T)] + carc(L + r, T + r, -90, -180) + [(L - 2, (T + B) / 2), (L, B - r)] + carc(L + r, B - r, 180, 90) + [((L + R) / 2, B + 4), (R - r, B)] + carc(R - r, B - r, 90, 0) + [(R + 3, (T + B) * .52)]
        strokes.append(jitter(fr, rng, 7))
    return strokes, n_text


DRAWS = []; warn_soft = []
for k, b in enumerate(BLOCKS):
    if b.spec.get('draw'):
        if b.mode != 'sketch': errors.append(f'блок {b.i}: рисунок возможен только в режиме sketch')
        end = next((s[0] for s in SCENES if s[0] > b.t0 + 1e-3), END)
        nd = next((x.t0 for x in BLOCKS[k + 1:] if x.spec.get('draw')), None)
        t1 = min(end, nd) if nd else end
        st, nt = build_drawing(b.spec['draw'], b.i + 3)
        DRAWS.append({'t0': b.t0, 't1': t1 - .05, 'strokes': st, 'n_text': nt, 'mid': b.t0 + (t1 - b.t0) * (.78 if len(st) > nt else .95)})
        if t1 - b.t0 < 2.2: warn_soft.append(f'блок {b.i}: рисунку всего {t1 - b.t0:.1f} с, он не успеет дорисоваться: начни его раньше или упрости')
_draw_c = {}


def sketch_mask(t):
    d = None
    for x in DRAWS:
        if x['t0'] <= t: d = x
    if d is None: return None
    kt = min(1, (t - d['t0']) / max(.1, d['mid'] - d['t0'])); kf = min(1, max(0, (t - d['mid']) / max(.1, d['t1'] - d['mid'])))
    key = (id(d), round(kt, 3), round(kf, 3))
    if key in _draw_c: return _draw_c[key]
    m = Image.new('L', (W, H)); dr = ImageDraw.Draw(m)
    tot = sum(len(s) for s in d['strokes'][:d['n_text']]); budget = kt * tot
    def put(s, n, r):
        for i in range(1, n): dr.line([tuple(s[i - 1]), tuple(s[i])], fill=255, width=int(r))
        for p in s[:n]: dr.ellipse([p[0] - r / 2, p[1] - r / 2, p[0] + r / 2, p[1] + r / 2], fill=255)
    for s in d['strokes'][:d['n_text']]:
        n = min(len(s), int(budget))
        if n <= 0: break
        put(s, n, 12); budget -= n
    if kf > 0 and len(d['strokes']) > d['n_text']:
        s = d['strokes'][d['n_text']]; put(s, int(kf * len(s)), 13)
    a = cv2.GaussianBlur(np.asarray(m).astype(np.float32), (0, 0), .8)
    _draw_c.clear(); _draw_c[key] = a
    return a


# ------------------------------ доска ------------------------------
SLOTS = [(95, 175, 280, 355), (705, 1270, 280, 380), (395, 175, 260, 295), (675, 250, 310, 280), (95, 1250, 280, 380), (395, 1250, 290, 330)]
BOARD = []
BG_BOARD = None
bcfg = P.get('board') or {}
has_board = any(b.mode == 'board' for b in BLOCKS)


def cover(path, w, h):
    im = Image.open(path).convert('RGB'); k = max(w / im.width, h / im.height)
    im = im.resize((int(math.ceil(im.width * k)), int(math.ceil(im.height * k))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return np.asarray(im.crop((x, y, x + w, y + h))).astype(np.float32)


IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp')
if has_board:
    folder = rel(bcfg.get('folder', 'картинки'))
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(IMG_EXT)) if os.path.isdir(folder) else []
    own = [f for f in files if os.path.splitext(os.path.basename(f))[0].lower() in ('фон', 'background')]
    files = [f for f in files if f not in own]
    if not files: errors.append(f'для доски нужны картинки: положите их в папку {folder}')
    bgf = bcfg.get('background') or (own[0] if own else '#EFE6D8')      # фон подбирается под ролик; без него ровный тёплый цвет
    if str(bgf).startswith('#'): BG_BOARD = np.full((H, W, 3), hexcol(bgf, '#EFE6D8'), np.float32)
    elif os.path.exists(rel(bgf)): BG_BOARD = cover(rel(bgf), W, H)
    else: errors.append(f'не найден фон {bgf}')
    for s in SCENES:
        if s[2] != 'board' or not files: continue
        t0, t1 = s[0], s[1]; ws = [w['s'] for w in WORDS if t0 <= w['s'] < t1]
        def snap(t): return min(ws, key=lambda x: abs(x - t)) if ws and min(abs(x - t) for x in ws) < .16 else t
        k, t, order, q = 0, t0 + .55, list(files), 0
        while t < t1 - .15:
            slot = k % 6
            f_ = order[q % len(order)]; q += 1
            x, y, w_, h_ = SLOTS[slot]
            BOARD.append((snap(t), slot, cover(f_, w_, h_)))
            k += 1; t += .42 if k < 6 else (.62 if t1 - t0 < 12 else 1.15)
    BOARD.sort(key=lambda g: g[0])


def bg_of(name, t):
    if name in ('mid', 'top'):
        img = np.full((H, W, 3), 255, np.float32)
        a = sketch_mask(t)
        if a is not None:
            q = a[..., None] / 255; img = img * (1 - q) + np.array((14, 12, 12), np.float32) * q
        return img
    img = BG_BOARD.copy() if BG_BOARD is not None else np.full((H, W, 3), 230, np.float32)
    last = {}
    for tg, slot, im in BOARD:
        if tg <= t: last[slot] = im
    for slot, im in last.items():
        x, y, w_, h_ = SLOTS[slot]; img[y:y + h_, x:x + w_] = im
    return img


# ------------------------------ стикеры ------------------------------
STICK = []
for b in BLOCKS:
    st = b.spec.get('sticker')
    if st:
        if not os.path.exists(rel(st)): errors.append(f'блок {b.i}: не найден стикер {st}'); continue
        STICK.append((b.t0, b.t1, np.dstack([cover(rel(st), 300, 340), np.full((340, 300), 255, np.float32)]), SAFE[0] + 15, int(H * .535)))

# ------------------------------ кадр ------------------------------
SHADE = np.ones((H, 1, 1), np.float32)
# затемнение низа кадра: чем светлее одежда, тем сильнее, иначе подпись на ней не читается
SHADE_AMT = float(P['shade']) if P.get('shade') is not None else float(np.clip((np.median(CHEST or [120]) - 70) / 130 * .4, .12, .35))
_r = np.clip((np.arange(H) - 850) / 280, 0, 1); SHADE[:, 0, 0] = 1 - SHADE_AMT * _r * _r * (3 - 2 * _r)
TOPS = [b for b in BLOCKS if b.top_lane]; LOWS = [b for b in BLOCKS if not b.top_lane]


def compose(frame_cover, f):
    t = f / FPS; ox, oy = crop_x(row_of(f))
    fr = frame_cover[oy:oy + H, ox:ox + W].astype(np.float32)
    a, c, k = state_at(t)
    if c == 'full' and (a == 'full' or k >= 1):
        img = fr * SHADE
        back = [b for b in TOPS if b.t0 <= t < b.t1]
        if back:
            orig = img.copy()
            for b in back: draw_block(b, img, t)
            if SEG is not None:
                q = person_mask(frame_cover[oy:oy + H, ox:ox + W])[..., None]
                img = img * (1 - q) + orig * q
        for s0, s1, r, x, y in STICK:
            if s0 <= t < s1: blend(img, r, x, y)
    else:
        bga = bg_of(a if a != 'full' else c, t); bgb = bg_of(c if c != 'full' else a, t)
        fam = (a in ('mid', 'top') and c in ('mid', 'top')) or a == 'full' or c == 'full'
        img = bgb if fam else bga * (1 - k) + bgb * k
        ma, mb = matrix(a, f), matrix(c, f); m = ma + (mb - ma) * k
        M = np.float32([[m[0], 0, m[1]], [0, m[0], m[2]]])
        fx = cv2.warpAffine(fr * (SHADE if c == 'full' else 1), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        x, y, w, h = lerp_rect(a, c, k); x0, y0, x1, y1 = int(round(x)), int(round(y)), int(round(x + w)), int(round(y + h))
        reg = fx[y0:y1, x0:x1]
        pa, pc, pk = state_at(t - 1 / FPS)
        if (pa, pc) == (a, c):
            dv = abs(lerp_rect(a, c, k)[1] - lerp_rect(a, c, pk)[1]); ker = int(min(dv * .3, 13)) | 1
            if ker > 3: reg = cv2.blur(reg, (1, ker))
        q_ = np.clip((np.arange(y1 - y0) / max(1, y1 - y0) - .42) / .3, 0, 1)
        win = 1 - min(.6, SHADE_AMT * 1.4) * (1 - k if c == 'full' else 1) * (q_ * q_ * (3 - 2 * q_))
        img[y0:y1, x0:x1] = reg * win[:, None, None].astype(np.float32)
        if c == 'full':                                  # верхние подписи не пропадают на время перехода
            for b in TOPS:
                if b.t0 <= t < b.t1: draw_block(b, img, t)
    dy_top = lerp_rect(a, c, k)[1] - RECT[c][1] if c in ('top', 'mid') and a != 'full' else 0
    for b in LOWS:
        if max(b.t0, b.min_t) <= t < b.t1: draw_block(b, img, t, dy_top if b.mode == 'sketch' else 0)
    return np.clip(img, 0, 255).astype(np.uint8)


# ------------------------------ отчёт ------------------------------
print(f'длина ролика {END:.1f} с, кусков {len(KEEP)}, блоков {len(BLOCKS)}' + ('' if A.check else f', текст за головой: {"да" if SEG is not None else "нет"}') + f', затемнение низа {SHADE_AMT:.2f}')
report = []
for b in BLOCKS:
    shown = ' '.join(w for line in b.lines for w, _, cnt in line)
    report.append(f'{b.t0:6.2f}  {b.mode:6s} {b.place:9s} {shown}   |  в речи: {" ".join(b.heard)}')
open(os.path.join(PLAN_DIR, 'check.txt'), 'w', encoding='utf8').write('\n'.join(report) + '\n')
import difflib
_n = lambda s_: re.sub(r'[^\wё]', '', s_.lower())
for b in BLOCKS:
    a_, c_ = _n(' '.join(w for line in b.lines for w, _, cnt in line if cnt)), _n(' '.join(b.heard))
    if a_ and not re.search(r'[a-z]', a_ + c_) and difflib.SequenceMatcher(None, a_, c_).ratio() < .6:
        print(f'ПРОВЕРИТЬ: блок {b.i} «{b.spec["text"]}» не похож на речь: «{" ".join(b.heard)}». Если слова сдвинулись, смотрите с этого блока: одно слово в распознавании могло склеиться или разбиться (знак ~)')
        break
for w_ in warn_soft: print('ПРОВЕРИТЬ:', w_)
if errors:
    for e in dict.fromkeys(errors): print('ОШИБКА:', e)
    print('Сверка блоков с речью: check.txt')
    if A.check or A.out: sys.exit(1)
if A.check:
    print('план в порядке, сверка блоков с речью: check.txt'); sys.exit(0)

if A.preview:
    d = os.path.join(PLAN_DIR, 'preview'); os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):
        if old.endswith('.jpg'): os.remove(os.path.join(d, old))      # только свои прошлые кадры, чтобы не смотреть устаревшее
    for t in [float(x) for x in A.preview.split(',')]:
        f = min(int(round(t * FPS)), TOTAL - 1); r = ROWS[row_of(f)]
        Image.fromarray(compose(grab(r[2] + (f - r[0]) / FPS), f)).save(f'{d}/{t:06.2f}.jpg', quality=88)
    fs_ = sorted(f for f in os.listdir(d) if f.endswith('.jpg') and not f.startswith('_'))
    cols = min(8, len(fs_)); tw, th = 270, 480; rows_ = (len(fs_) + cols - 1) // cols
    sh_ = Image.new('RGB', (cols * tw, rows_ * th)); dd = ImageDraw.Draw(sh_)
    for i, f_ in enumerate(fs_):
        sh_.paste(Image.open(os.path.join(d, f_)).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        dd.text(((i % cols) * tw + 5, (i // cols) * th + 5), f_[:-4] + ' с', fill=(255, 40, 40))
    sh_.save(os.path.join(d, '_лист.jpg'), quality=85)
    print('кадры ->', d, ' обзор: _лист.jpg'); sys.exit(0)

# ------------------------------ сборка ------------------------------
if not A.out: fail('укажите --out файл.mp4')
OUT = os.path.expanduser(A.out)
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    parts = ''.join(f'[0:a]atrim={a:.3f}:{a + r[3] / FPS:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={r[3] / FPS - .008:.3f}:d=0.008[a{i}];' for i, (r, (a, b)) in enumerate(zip(ROWS, KEEP)))
    conc = ''.join(f'[a{i}]' for i in range(len(KEEP)))
    voice = f'{td}/v.wav'
    subprocess.run([FF, '-v', 'error', '-y', '-i', SRC, '-filter_complex', f'{parts}{conc}concat=n={len(KEEP)}:v=0:a=1,highpass=f=75,loudnorm=I=-14.5:TP=-1.5:LRA=11[o]', '-map', '[o]', '-ar', '48000', '-ac', '2', voice], check=True)
    audio = voice
    mcfg = P.get('music')
    if mcfg:
        mp_ = rel(mcfg['file'] if isinstance(mcfg, dict) else mcfg); lv = (mcfg.get('level', -24) if isinstance(mcfg, dict) else -24)
        if not os.path.exists(mp_): fail(f'не найдена музыка {mp_}')
        audio = f'{td}/mix.wav'
        subprocess.run([FF, '-v', 'error', '-y', '-i', voice, '-stream_loop', '-1', '-i', mp_, '-filter_complex',
                        f'[1:a]atrim=0:{END:.3f},aresample=48000,aformat=channel_layouts=stereo,loudnorm=I={lv}:TP=-3:LRA=11,afade=t=out:st={max(0, END - .8):.3f}:d=0.8[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.87:level=false[o]',
                        '-map', '[o]', '-ar', '48000', audio], check=True)
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', audio,
                            '-c:v', 'libx264', '-crf', '20', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    done = 0
    for r in ROWS:
        cmd = [FF, '-v', 'error', '-ss', f'{r[2]:.3f}', '-i', SRC, '-frames:v', str(r[3]), '-vf', f'fps={FPS},scale={SW}:{SH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE); last = None; got = 0
        size = SW * SH * 3
        while got < r[3]:
            buf = p.stdout.read(size)
            if len(buf) < size:
                if last is None: fail('не удалось прочитать видео')
                fr = last
            else:
                fr = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3); last = fr
            enc.stdin.write(compose(fr, r[0] + got).tobytes()); got += 1; done += 1
            if done % 150 == 0: print(f'  {done}/{TOTAL} кадров', flush=True)
        p.stdout.close(); p.wait()
    enc.stdin.close(); enc.wait()
print('готово ->', OUT, f'{os.path.getsize(OUT) / 1e6:.1f} МБ')
