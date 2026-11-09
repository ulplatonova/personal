#!/usr/bin/env python3
"""Шаг 3. Чистовая нарезка: подрезает вдохи на краях кусков, расшифровывает КАЖДЫЙ кусок отдельно (только так видны повторы
и обрубки: расшифровка всей записи их прячет), показывает паузы на стыках, делает черновик подписей.
python cut.py папка/plan.json [--draft]     --draft пересобрать подписи заново"""
import argparse, json, os, re, sys
import numpy as np
from asr import read_audio, recognizer, SR

ap = argparse.ArgumentParser(); ap.add_argument('plan'); ap.add_argument('--draft', action='store_true')
ap.add_argument('--lang', default='ru'); ap.add_argument('--engine', default='auto'); ap.add_argument('--model', default='')
ap.add_argument('--no-tighten', action='store_true'); ap.add_argument('--gaps', default='', help='напр. 20-30: паузы в этом участке исходника, чтобы точно поставить границу')
a = ap.parse_args()
P = json.load(open(a.plan, encoding='utf8')); d = os.path.dirname(os.path.abspath(a.plan))
video = P['video'] if os.path.isabs(os.path.expanduser(P['video'])) else os.path.join(d, P['video'])
x = read_audio(os.path.expanduser(video)); hop = int(.01 * SR)


def env(a0, b0):
    seg = x[int(a0 * SR):int(b0 * SR)]; n = len(seg) // hop
    return 20 * np.log10(np.sqrt(np.add.reduce(seg[:n * hop].reshape(n, hop) ** 2, 1) / hop + 1e-12) + 1e-9) if n else np.array([])


if a.gaps:
    g0, g1 = [float(q) for q in a.gaps.split('-')]; db = env(g0, g1); lvl = np.percentile(db, 90); run = 0; found = []
    for k, v in enumerate(list(db) + [0]):
        if v < lvl - 25: run += 1
        else:
            if run >= 6: found.append(f'{g0 + (k - run) / 100:.2f}-{g0 + k / 100:.2f}')
            run = 0
    print('паузы:', ', '.join(found) or 'нет'); sys.exit(0)
keep = []
done = [tuple(k) for k in P.get('cut_done', [])]        # уже подрезанные куски второй раз не трогаем
for a0, b0 in P['keep']:
    db = env(a0, b0)
    if a.no_tighten or len(db) < 10 or (a0, b0) in done: keep.append((a0, b0)); continue
    lvl = np.percentile(db, 90); on = np.nonzero(db > lvl - 10)[0]; off = np.nonzero(db > lvl - 22)[0]
    keep.append((round(a0 + max(0, on[0] - 4) / 100, 3), round(a0 + min(len(db), off[-1] + 8) / 100, 3)))
rec = recognizer(a.lang, a.engine, a.model)
chunks, PAD = [], .3
norm = lambda s: re.sub(r'[^\wё]', '', s.lower())
warn = []
for i, (a0, b0) in enumerate(keep):
    seg = np.concatenate([np.zeros(int(SR * PAD), np.float32), x[int(a0 * SR):int(b0 * SR)], np.zeros(int(SR * PAD), np.float32)])
    ws = [{'w': t, 's': round(max(a0, a0 + p - PAD), 3), 'e': round(min(b0, a0 + q - PAD), 3)} for t, p, q in rec(seg) if t]
    chunks.append({'id': i, 'start': a0, 'end': b0, 'text': ' '.join(w['w'] for w in ws), 'words': ws})
    print(f'[{i}] {a0:7.2f}-{b0:7.2f}  {chunks[-1]["text"]}', flush=True)
    # Вторая проверка: кусок дробится по коротким провалам громкости и распознаётся по частям.
    # Распознавание целого куска склеивает повторы («наверх, наверх экрана» -> «наверх экрана»), по частям они видны.
    db = env(a0, b0); lvl = np.percentile(db, 90) if len(db) else 0; cuts, run = [], 0
    for k, v in enumerate(db):
        run = run + 1 if v < lvl - 25 else 0
        if run == 10: cuts.append(k - 5)
    edges = [0] + cuts + [len(db)]; parts_t, part_toks = [], []
    if 1 < len(edges) - 1 <= 14:
        for p, q in zip(edges[:-1], edges[1:]):
            if q - p < 12: continue
            pa, pb = a0 + p / 100, a0 + q / 100
            t_ = ' '.join(w for w, _, _ in rec(np.concatenate([np.zeros(int(SR * PAD), np.float32), x[int(pa * SR):int(pb * SR)], np.zeros(int(SR * PAD), np.float32)])))
            if any(z in t_.lower() for z in ('продолжение следует', 'субтитры сделал', 'субтитры создавал', 'спасибо за просмотр')): t_ = ''      # галлюцинация на шуме
            parts_t.append(f'{pa:.2f}-{pb:.2f} {t_}'); part_toks += [norm(w) for w in t_.split()]
        print('     по частям:', ' | '.join(parts_t), flush=True)
        if part_toks and part_toks != [norm(w['w']) for w in ws]:
            whole = [norm(w['w']) for w in ws]
            if len(part_toks) > len(whole) + 1: warn.append(f'кусок {i}: по частям слов больше ({len(part_toks)} против {len(whole)}), вероятно скрытый дубль, смотрите «по частям»')
        for L in (1, 2, 3, 4):
            for k in range(len(part_toks) - 2 * L + 1):
                if part_toks[k:k + L] == part_toks[k + L:k + 2 * L] and all(part_toks[k:k + L]): warn.append(f'кусок {i}: по частям повтор «{" ".join(part_toks[k:k + L])}»')
    for w in ws:
        if w['e'] - w['s'] > .85 and w is not ws[0]: warn.append(f'кусок {i}: слово «{w["w"]}» длится {w["e"] - w["s"]:.2f} с ({w["s"]:.2f}-{w["e"]:.2f}), обычно это скрытый дубль или пауза')
    toks = [norm(w['w']) for w in ws]
    for k in range(len(toks) - 1):
        if toks[k] and toks[k] == toks[k + 1]: warn.append(f'кусок {i}: повтор «{toks[k]}»')
    for L in (2, 3, 4):
        for k in range(len(toks) - 2 * L + 1):
            if toks[k:k + L] == toks[k + L:k + 2 * L]: warn.append(f'кусок {i}: повтор фразы «{" ".join(toks[k:k + L])}»')
    if i and chunks[i - 1]['words'] and ws:
        pv = [norm(w['w']) for w in chunks[i - 1]['words']]
        for L in range(1, min(8, len(pv), len(toks)) + 1):       # конец прошлого куска совпадает с началом этого: хвост чужого дубля
            if pv[-L:] == toks[:L]: warn.append(f'стык {i - 1}-{i}: повтор «{" ".join(toks[:L])}»')
        for L in (3, 4, 5, 6):                                   # начало этого куска уже сказано в конце прошлого
            if len(toks) >= L and any(pv[k:k + L] == toks[:L] for k in range(max(0, len(pv) - 12), len(pv) - L + 1)):
                warn.append(f'стык {i - 1}-{i}: фраза «{" ".join(toks[:L])}» уже была в прошлом куске, скорее всего хвост прошлого дубля'); break
for i in range(1, len(keep)):
    # тишина на стыке: хвост прошлого куска + начало следующего
    tail = env(*keep[i - 1]); head = env(*keep[i])
    q = sum(1 for v in tail[::-1][:60] if v < -40); w_ = 0
    for v in tail[::-1]:
        if v >= -40: break
        w_ += 1
    h_ = 0
    for v in head:
        if v >= -40: break
        h_ += 1
    gap = (w_ + h_) / 100
    if gap > .3: warn.append(f'стык {i - 1}-{i}: пауза {gap:.2f} с, длинновато')
out_w = 'words.json'
json.dump({'video': P['video'], 'chunks': chunks}, open(os.path.join(d, out_w), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
P['keep'] = [list(k) for k in keep]; P['words'] = out_w; P['cut_done'] = [list(k) for k in keep]
SHORT = {'и', 'а', 'в', 'с', 'к', 'у', 'о', 'на', 'не', 'но', 'по', 'за', 'из', 'от', 'до', 'что', 'это', 'как', 'для', 'со', 'то', 'ты', 'вы', 'он', 'она', 'мы', 'я'}
if a.draft or not P.get('blocks'):
    blocks = []
    for c in chunks:
        cur = []
        for k, w in enumerate(c['words']):
            t = w['w'].strip(' .…')
            cur.append(t)
            end = bool(re.search(r'[.,!?…:;]$', w['w'])) or k == len(c['words']) - 1
            if end or ((len(cur) >= 3 or len(' '.join(cur)) > 20) and t.lower() not in SHORT):
                s = ' '.join(cur).rstrip(',')
                blocks.append({'text': s[0].lower() + s[1:] if not re.match(r'[A-ZА-ЯЁ]{2}', s) else s}); cur = []
    P['blocks'] = blocks; print(f'черновик подписей: {len(blocks)} блоков')
else:
    print('подписи не менялись: если менялись куски, пересоберите черновик (--draft) или поправьте блоки по check.txt')
json.dump(P, open(a.plan, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
for w_ in dict.fromkeys(warn): print('ПРОВЕРИТЬ:', w_)
print('план обновлён ->', a.plan, f'длина {sum(b - a_ for a_, b in keep):.1f} с')
