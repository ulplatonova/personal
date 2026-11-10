#!/usr/bin/env python3
"""Субтитры в стиле референса: Arial Narrow, белый текст, мятные акценты и бренды, мягкая тень.
python subs_arial.py plan.json words.json out.ass
В тексте блока: *слова* — мятный акцент, ~N — сколько слов речи забирает слово.
Поле блока "hook": [мелкая строка, крупная строка] — заголовок наверху до "until"."""
import json, re, sys

plan, words_f, out = sys.argv[1:4]
P = json.load(open(plan, encoding='utf8'))
WORDS = [w for ch in json.load(open(words_f, encoding='utf8'))['chunks'] for w in ch['words']]
import os
ACC_HEX = os.environ.get('ACCENT', '#F5C9A6')
MINT = '&H' + ACC_HEX[5:7] + ACC_HEX[3:5] + ACC_HEX[1:3] + '&'   # акцент, BGR
BRANDS = ['Vichy', 'Clarins', 'SPF', 'Dior', 'MAC', 'Kiko']


def ts(x):
    return f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'


SUB_ACC = os.environ.get('SUB_ACCENT', 'none')   # 'bold' — белый жирный, 'color' — цвет акцента


def fmt(txt):
    if SUB_ACC == 'none': on, off = '', ''
    elif SUB_ACC == 'bold': on, off = '{\\b1}', '{\\b0}'
    else: on, off = '{\\c' + MINT + '}', '{\\c&HFFFFFF&}'
    txt = re.sub(r'\*(.+?)\*', lambda m: on + m.group(1) + off, txt)
    for b in BRANDS:
        rep = on + b + off
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
Style: Sub,{font},{ss},&H00FFFFFF,&H00FFFFFF,&H88000000,&H00000000,0,0,0,0,100,100,{sp},0,1,{ob},0,2,110,110,{mv},1
Style: HookS,{font},{hs},&H00FFFFFF,&H00FFFFFF,&HB4000000,&H00000000,0,0,0,0,100,100,{sphs},0,1,{obh},0,8,90,90,230,1
Style: HookB,{font},{hb},&H00FFFFFF,&H00FFFFFF,&HB4000000,&H00000000,0,0,0,0,100,100,{sph},0,1,{obh},0,8,90,90,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".replace('{mv}', str(P.get('sub_margin_v', 400))).replace('{font}', os.environ.get('FONT', 'Arial Narrow')).replace('{ss}', os.environ.get('SUB_SIZE', '60')).replace('{hs}', os.environ.get('HOOKS_SIZE', '58')).replace('{hb}', os.environ.get('HOOKB_SIZE', '112')).replace('{sp}', os.environ.get('SPACING_SUB', '0')).replace('{sphs}', os.environ.get('SPACING_HOOKS', os.environ.get('SPACING_HOOK', '0'))).replace('{sph}', os.environ.get('SPACING_HOOK', '0')).replace('{obh}', os.environ.get('OUTLINE_HOOK', '3')).replace('{ob}', os.environ.get('OUTLINE_SUB', '2.5'))
WT = os.environ.get('WEIGHT', '')
WTAG = ('\\b' + WT) if WT else ''
FSP = lambda k: ('\\fsp' + os.environ[k]) if os.environ.get(k) else ''
WORD_GAP = os.environ.get('WORD_GAP', '')   # доп. ширина пробела при плотном трекинге, px


def gaps(txt, k):
    # плотный трекинг сжимает и пробелы; возвращаем словам воздух
    if not (WORD_GAP and os.environ.get(k)): return txt
    return txt.replace(' ', '{\\fsp' + WORD_GAP + '} {\\fsp' + os.environ[k] + '}')
HBL = '0' if os.environ.get('OUTLINE_HOOK', '3') == '0' else '3'
SOFT = os.environ.get('SOFT_SHADOW', '')   # альфа мягкой тени у субтитров (отдельный слой), напр. '90'
ev = []
for b in blocks:
    sp = b['spec']
    if sp.get('hook'):
        # хук: строки вручную, с плотным межстрочным интервалом; подчёркивание слова анимацией
        until = float(sp.get('until', b['en'])); t0 = max(0, b['st'] - 0.05)
        y = int(sp.get('hook_y', 220)); col = '{\\c' + MINT + '}'
        ev.append(f"Dialogue: 0,{ts(t0)},{ts(until)},HookS,,0,0,0,,{{\\an8\\pos(540,{y})\\blur{HBL}{WTAG}{FSP('FSP_HOOKS')}}}{gaps(sp['hook'][0], 'FSP_HOOKS')}")
        y += int(sp.get('gap_small', 66))
        for li, line in enumerate(sp['hook'][1:]):
            ev.append(f"Dialogue: 0,{ts(t0)},{ts(until)},HookB,,0,0,0,,{{\\an8\\pos(540,{y})\\blur{HBL}{WTAG}{FSP('FSP_HOOK')}}}{col}{gaps(line, 'FSP_HOOK')}")
            ul = sp.get('underline')
            if ul and ul['line'] == li:
                x0, w, uy = ul['x'], ul['w'], y + ul['dy']
                ta = int((ul['t'] - t0) * 1000); tb = ta + 350
                ev.append(f"Dialogue: 1,{ts(t0)},{ts(until)},HookB,,0,0,0,,{{\\an7\\pos({x0},{uy})\\bord0\\shad0\\1c{MINT}\\clip({x0},{uy-5},{x0},{uy+12})\\t({ta},{tb},\\clip({x0},{uy-5},{x0+w},{uy+12}))\\p1}}m 0 0 l {w} -1 l {w} 2 l 0 3{{\\p0}}")
            y += int(sp.get('gap_big', 96))
        continue
    if SOFT:
        mv = int(P.get('sub_margin_v', 400)) - 3
        ev.append(f"Dialogue: 0,{ts(b['st'])},{ts(b['en'])},Sub,,112,108,{mv},,{{\\1c&H000000&\\1a&H{SOFT}&\\bord0\\shad0\\blur7{WTAG}{FSP('FSP_SUB')}}}{gaps(b['txt'], 'FSP_SUB')}")
    ev.append(f"Dialogue: 1,{ts(b['st'])},{ts(b['en'])},Sub,,0,0,0,,{{\\blur{'0' if SOFT else '3'}{WTAG}{FSP('FSP_SUB')}}}{gaps(fmt(b['txt']), 'FSP_SUB')}")
open(out, 'w', encoding='utf8').write(head + '\n'.join(ev) + '\n')
print('блоков:', len(ev), '->', out)
