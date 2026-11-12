#!/usr/bin/env python3
"""v2: мелкие субтитры, крупный заголовок только на хуке, белый фон с уменьшенным кадром,
наклейки средств с белой обводкой, покачиванием и тенью."""
import json, math, subprocess, os
import numpy as np, cv2
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'work.mp4')
FONTS = os.path.join('/home/user/personal', '.claude', 'skills', 'ugc-girl-edit', 'assets', 'fonts')
OUT = os.environ.get('OUT', os.path.join(HERE, 'clean.mp4'))
W, H, FPS = 1080, 1920, 30
KEEP = [(0.0, float(os.environ.get('DUR', '36.0')))]
BG = (246, 242, 236)              # тёплый белый
ACCENT = '&H4E6EA8&'              # пыльный беж-абрикос #D9A27E (ASS: BGR)

# белый фон: (начало, конец) в секундах готового ролика
WHITE = []
SCALE = 0.78
# наклейки: файл, начало, конец, центр (x, y), размер по длинной стороне
STICK = [tuple(x[:3]) + (tuple(x[3]), x[4]) for x in json.load(open(os.environ['SLOTS']))['stick']]

PDIR = os.path.join(HERE, 'prices')
# карточки с ценой: файл, начало, конец, центр, ширина
PRICES = []

MASKS = np.load(os.environ['MASKS']) if os.environ.get('MASKS') else None
MFPS = 15

def ease(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)

def white_p(t):
    return 1.0 if any(a <= t < b for a, b in WHITE) else 0.0

def out_to_src(t):
    acc = 0
    for a, b in KEEP:
        if t < acc + (b - a): return a + (t - acc)
        acc += b - a
    return KEEP[-1][1]

TOTAL = sum(b - a for a, b in KEEP)

# --- наклейки
stickers = {}
for name, *_r, size in STICK:
    im = Image.open((name if name.endswith('.png') else name + '.png')).convert('RGBA')
    k = size / max(im.size); im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    stickers[name] = im

def back_out(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def paste_rgba(base, im, cx, cy):
    """base: np uint8 HxWx3, im: PIL RGBA"""
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb: return
    sub = a[ya - y0:yb - y0, xa - x0:xb - x0]
    al = sub[..., 3:4] / 255
    base[ya:yb, xa:xb] = (base[ya:yb, xa:xb] * (1 - al) + sub[..., :3] * al).astype(np.uint8)

def draw_sticker(frame, name, t, t0, t1, c):
    if not (t0 <= t <= t1): return
    im = stickers[name]
    k = 0.9 + 0.1 * ease((t - t0) / 0.3)
    fade = min(ease((t - t0) / 0.25), ease((t1 - t) / 0.2))
    if fade <= 0.02: return
    ang = 3 * math.sin(2 * math.pi * 0.35 * (t - t0))
    im2 = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS).rotate(ang, Image.BICUBIC, expand=True)
    # тень
    sh = np.zeros((im2.height + 60, im2.width + 60, 4), np.uint8)
    sh[30:30 + im2.height, 30:30 + im2.width, 3] = (np.asarray(im2)[..., 3] * 0.28).astype(np.uint8)
    sh[..., 3] = cv2.GaussianBlur(sh[..., 3], (0, 0), 12)
    if fade < 1:
        im2 = im2.copy(); a = np.asarray(im2).copy(); a[..., 3] = (a[..., 3] * fade).astype(np.uint8); im2 = Image.fromarray(a)
        sh[..., 3] = (sh[..., 3] * fade).astype(np.uint8)
    paste_rgba(frame, Image.fromarray(sh), c[0] + 8, c[1] + 14)
    paste_rgba(frame, im2, c[0], c[1])

cards = {}
for name, *_r, wdt in PRICES:
    im = Image.open(os.path.join(PDIR, name + '.png')).convert('RGBA')
    cards[name] = im.resize((wdt, int(im.height * wdt / im.width)), Image.LANCZOS)

def draw_price(frame, name, t, t0, t1, c):
    if not (t0 <= t <= t1): return
    fade = min(ease((t - t0) / 0.25), ease((t1 - t) / 0.2))
    if fade <= 0.02: return
    im = cards[name]; a = np.asarray(im).copy()
    sh = np.zeros((im.height + 60, im.width + 60, 4), np.uint8)
    sh[30:30 + im.height, 30:30 + im.width, 3] = (a[..., 3] * 0.22 * fade).astype(np.uint8)
    sh[..., 3] = cv2.GaussianBlur(sh[..., 3], (0, 0), 10)
    a[..., 3] = (a[..., 3] * fade).astype(np.uint8)
    dy = int(12 * (1 - ease((t - t0) / 0.3)))
    paste_rgba(frame, Image.fromarray(sh), c[0] + 6, c[1] + 10 + dy)
    paste_rgba(frame, Image.fromarray(a), c[0], c[1] + dy)

# скругление кадра
def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1); cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in [(r, r), (w - r, r), (r, h - r), (w - r, h - r)]: cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m

def compose(src, p):
    if p <= 0.001: return src
    s = 1 - (1 - SCALE) * p
    w, h = int(W * s), int(H * s)
    small = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA)
    out = np.empty_like(src); out[:] = BG
    bg_mix = (src.astype(np.float32) * (1 - p) + out.astype(np.float32) * p).astype(np.uint8) if p < 1 else out
    x0, y0 = (W - w) // 2, (H - h) // 2
    r = 1
    m = np.ones((h, w), np.float32)
    # тень под кадром
    shadow = np.zeros((H + 40, W), np.float32); shadow[y0 + 18:y0 + 18 + h, x0:x0 + w] = m; shadow = shadow[:H]
    shadow = cv2.GaussianBlur(shadow, (0, 0), 28) * 0.22 * p
    res = (bg_mix.astype(np.float32) * (1 - shadow[..., None])).astype(np.float32)
    reg = res[y0:y0 + h, x0:x0 + w]
    res[y0:y0 + h, x0:x0 + w] = reg * (1 - m[..., None]) + small.astype(np.float32) * m[..., None]
    return res.astype(np.uint8)

# --- субтитры (ASS)
def ts(x):
    return f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'

plan = json.load(open(os.path.join(HERE, 'plan.json'), encoding='utf8'))
words = []
for ch in json.load(open(os.path.join(HERE, 'words.json'), encoding='utf8'))['chunks']:
    words += ch['words']
def w_out(sx):
    acc = 0
    for a, b in KEEP:
        if a - 0.05 <= sx <= b + 0.05: return acc + (min(max(sx, a), b) - a)
        acc += b - a
    return acc
blocks = []
wi = 0
for b in plan['blocks']:
    toks = b['text'].replace(' / ', ' ').split()
    n = 0; clean = []
    for tk in toks:
        k = 1
        if '~' in tk:
            import re as _re
            m_ = _re.match(r'(.*?)~(\d+)(.*)$', tk); tk = m_.group(1) + m_.group(3); k = int(m_.group(2))
        clean.append(tk.replace('_', ' ')); n += k
    st = w_out(words[wi]['s']); en = w_out(words[wi + n - 1]['e']); wi += n
    blocks.append([st, en, ' '.join(clean)])
for i in range(len(blocks) - 1):
    blocks[i][1] = max(blocks[i][1], min(blocks[i + 1][0], blocks[i][1] + 0.6))
    blocks[i][1] = min(blocks[i][1], blocks[i + 1][0])
blocks[-1][1] = TOTAL

def to_ass(txt):
    import re
    txt = re.sub(r'\*(.+?)\*', lambda m: '{\\c' + ACCENT + '\\fnPlayfair Display\\i1}' + m.group(1) + '{\\r}', txt)
    txt = re.sub(r'#(.+?)#', r'\1', txt)
    return txt.lower()

HOOK_END = 1.95
ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Sub,Inter Tight,44,&H00242A3B,&H00242A3B,&H40FFFFFF,&H00000000,0,0,0,0,100,100,0.5,0,1,2.5,0,2,120,120,560,1",
       "Style: Hook,Inter Tight,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,2.2,8,80,80,250,1",
       "Style: HookA,Playfair Display,104,&H007EA2D9,&H00FFFFFF,&H00000000,&H64000000,0,1,0,0,100,100,0,0,1,0,2.2,8,80,80,345,1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
ass.append(f"Dialogue: 0,{ts(0.15)},{ts(HOOK_END)},Hook,,0,0,0,,{{\\fad(150,200)}}делаю")
ass.append(f"Dialogue: 0,{ts(0.55)},{ts(HOOK_END)},HookA,,0,0,0,,{{\\fad(250,200)}}макияж без макияжа")
for st, en, txt in blocks:
    if en <= HOOK_END + 0.05: continue
    st = max(st, HOOK_END)
    ass.append(f"Dialogue: 0,{ts(st)},{ts(en)},Sub,,0,0,0,,{{\\blur4}}{to_ass(txt)}")
ass_path = os.path.join(HERE, 'subs_v2.ass')
open(ass_path, 'w', encoding='utf8').write('\n'.join(ass) + '\n')

# --- звук с теми же склейками
parts = ''.join(f'[1:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}];' for i, (a, b) in enumerate(KEEP))
afilt = parts + ''.join(f'[a{i}]' for i in range(len(KEEP))) + f'concat=n={len(KEEP)}:v=0:a=1[aout]'

dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-vf', f'scale={W}:{H}:flags=lanczos,fps={FPS}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-i', SRC, '-filter_complex', f'[0:v]null[vout];{afilt}',
                        '-map', '[vout]', '-map', '[aout]', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', OUT], stdin=subprocess.PIPE)
fb = W * H * 3
si = 0
nout = int(TOTAL * FPS)
oi = 0
cur = None
while oi < nout:
    t = oi / FPS
    want = int(round(out_to_src(t) * FPS))
    while si <= want:
        raw = dec.stdout.read(fb)
        if len(raw) < fb: break
        cur = np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy(); si += 1
    if cur is None: break
    fr = compose(cur, white_p(t))
    for name, t0, t1, c, _ in STICK:
        draw_sticker(fr, name, t, t0, t1, c)
    for name, t0, t1, c, _ in PRICES:
        draw_price(fr, name, t, t0, t1, c)
    if MASKS is not None:
        mi = min(int(t * MFPS), len(MASKS) - 1)
        m = cv2.resize(MASKS[mi], (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
        m = np.clip((m - 0.35) / 0.4, 0, 1)
        m = cv2.GaussianBlur(m, (0, 0), 2 * W / 1080)[..., None]
        fr = (fr * (1 - m) + cur * m).astype(np.uint8)
    enc.stdin.write(fr.tobytes()); oi += 1
enc.stdin.close(); enc.wait(); dec.terminate()
print('->', OUT)
