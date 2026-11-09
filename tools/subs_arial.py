#!/usr/bin/env python3
"""Субтитры в стиле референса: Arial Narrow, белый текст, мятные акценты и бренды, мягкая тень.
python subs_arial.py plan.json words.json out.ass
В тексте блока: *слова* — мятный акцент, ~N — сколько слов речи забирает слово.
Поле блока "hook": [мелкая строка, крупная строка] — заголовок наверху до "until"."""
import json, re, sys

plan, words_f, out = sys.argv[1:4]
P = json.load(open(plan, encoding='utf8'))
WORDS = [w for ch in json.load(open(words_f, encoding='utf8'))['chunks'] for w in ch['words']]
MINT = '&HD8F2BF&'          # #BFF2D8 в BGR
BRANDS = ['Vichy', 'Clarins', 'SPF', 'Dior', 'MAC', 'Kiko']


def ts(x):
    return f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'


def fmt(txt):
    txt = re.sub(r'\*(.+?)\*', lambda m: '{\\c' + MINT + '}' + m.group(1) + '{\\c&HFFFFFF&}', txt)
    for b in BRANDS:
        rep = '{\\c' + MINT + '}' + b + '{\\c&HFFFFFF&}'
        txt = re.sub(rf'\b{b}\b', lambda m, r=rep: r, txt)
    return txt


blocks, wi = [], 0
for b in P['blocks']:
    toks, n, clean = b['text'].replace(' / ', ' ').split(), 0, []
    for tk in toks:
        k = 1
        m = re.match(r'(.*?)~(\d+)(.*)$', tk)
        if m: tk, k = m.group(1) + m.group(3), int(m.group(2))
        clean.append(tk); n += k
    st, en = WORDS[wi]['s'], WORDS[wi + n - 1]['e']; wi += n
    blocks.append({'st': st, 'en': en, 'txt': ' '.join(clean), 'spec': b})
for i in range(len(blocks) - 1):
    blocks[i]['en'] = min(max(blocks[i]['en'], blocks[i]['en'] + 0.5), blocks[i + 1]['st'])
blocks[-1]['en'] = float(P.get('end', blocks[-1]['en'] + 1.5))

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial Narrow,60,&H00FFFFFF,&H00FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,2,110,110,{mv},1
Style: HookS,Arial Narrow,58,&H00FFFFFF,&H00FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,8,90,90,230,1
Style: HookB,Arial Narrow,112,&H00D8F2BF,&H00FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,8,90,90,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".replace('{mv}', str(P.get('sub_margin_v', 640)))
ev = []
for b in blocks:
    sp = b['spec']
    if sp.get('hook'):
        small, big = sp['hook']; until = float(sp.get('until', b['en']))
        ev.append(f"Dialogue: 0,{ts(max(0, b['st'] - 0.05))},{ts(until)},HookS,,0,0,0,,{{\\blur4}}{small}")
        ev.append(f"Dialogue: 0,{ts(max(0, b['st'] - 0.05))},{ts(until)},HookB,,0,0,0,,{{\\blur4}}{big}")
        continue
    ev.append(f"Dialogue: 0,{ts(b['st'])},{ts(b['en'])},Sub,,0,0,0,,{{\\blur4}}{fmt(b['txt'])}")
open(out, 'w', encoding='utf8').write(head + '\n'.join(ev) + '\n')
print('блоков:', len(ev), '->', out)
