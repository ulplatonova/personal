#!/usr/bin/env python3
"""Шаг 2. Заготовка плана: какие куски оставить.
python plan_draft.py папка/words_all.json --out папка/plan.json [--keep 2,4,5]
Куски нумеруются с нуля, как их печатает transcribe.py. Без --keep: все куски, но если следующий начинается теми же словами, прошлый считается неудачным дублем. Проверьте результат глазами."""
import argparse, json, os, re

ap = argparse.ArgumentParser(); ap.add_argument('words'); ap.add_argument('--out', required=True); ap.add_argument('--keep', default='')
a = ap.parse_args()
d = json.load(open(a.words, encoding='utf8')); ch = d['chunks']
norm = lambda s: re.sub(r'[^\wё]', '', s.lower())
if a.keep:
    ids = [int(x) for x in a.keep.split(',')]
else:
    ids = []
    for k, c in enumerate(ch):
        nxt = ch[k + 1] if k + 1 < len(ch) else None
        same = nxt and [norm(w) for w in c['text'].split()[:2]] == [norm(w) for w in nxt['text'].split()[:2]]
        if not same: ids.append(k)
plan = {'video': d['video'], 'keep': [[ch[i]['start'], ch[i]['end']] for i in ids],
        'board': {'folder': 'картинки'}, 'music': None, 'blocks': []}
json.dump(plan, open(a.out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('оставлены куски:', ids, '->', a.out)
