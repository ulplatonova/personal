#!/usr/bin/env python3
"""Шаг 1. Расшифровка всей записи: она режется по паузам, каждый кусок распознаётся отдельно.
python transcribe.py видео.mp4 --out папка/words_all.json   (первый запуск скачивает модель, около 1,6 ГБ)
"""
import argparse, json, os
import numpy as np
from asr import read_audio, recognizer, SR

ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--out', required=True)
ap.add_argument('--lang', default='ru'); ap.add_argument('--engine', default='auto', choices=['auto', 'mlx', 'faster']); ap.add_argument('--model', default='')
a = ap.parse_args()
x = read_audio(a.video); hop = int(0.01 * SR); n = len(x) // hop
db = 20 * np.log10(np.sqrt(np.add.reduce(x[:n * hop].reshape(n, hop) ** 2, 1) / hop + 1e-12) + 1e-9)
on = db > max(np.percentile(db, 10) + 12, -48)
chunks, s, last = [], None, None
for i, v in enumerate(on):
    if v:
        if s is None: s = i
        last = i
    elif s is not None and i - last > 30:            # пауза от 0,3 с делит куски
        chunks.append((s, last + 1)); s = None
if s is not None: chunks.append((s, last + 1))
chunks = [(max(0, p - 6) / 100, min(n, q + 6) / 100) for p, q in chunks if q - p >= 20]
print(f'участков со звуком: {len(chunks)}, без слов будут пропущены, поэтому номера могут идти подряд с меньшим числом', flush=True)
rec = recognizer(a.lang, a.engine, a.model)
NOISE = ('продолжение следует', 'субтитры сделал', 'субтитры создавал', 'субтитры подогнал', 'спасибо за просмотр', 'dimatorzok')   # галлюцинации на шуме
out, PAD = [], 0.3
for c0, c1 in chunks:
    seg = np.concatenate([np.zeros(int(SR * PAD), np.float32), x[int(c0 * SR):int(c1 * SR)], np.zeros(int(SR * PAD), np.float32)])
    txt = ' '.join(w for w, _, _ in rec(seg))
    if not txt or any(z in txt.lower() for z in NOISE): continue
    out.append({'id': len(out), 'start': c0, 'end': c1, 'text': txt})
    print(f'[{len(out) - 1}] {c0:7.2f}-{c1:7.2f}  {txt}', flush=True)
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
json.dump({'video': os.path.abspath(a.video), 'chunks': out}, open(a.out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('->', a.out)
