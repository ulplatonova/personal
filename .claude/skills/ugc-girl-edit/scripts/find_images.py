#!/usr/bin/env python3
"""Подбор картинок с Pinterest под тему ролика. Без входа в аккаунт: поисковики находят публичные картинки Pinterest.
python find_images.py "coffee flatlay aesthetic" "beige moodboard" --out папка/кандидаты [--each 14] [--bg]
--bg: подбор фона, нужны крупные вертикальные картинки.
Складывает файлы в папку и делает обзорный лист _лист.jpg с именами: посмотрите его и выберите подходящие."""
import argparse, concurrent.futures as cf, hashlib, html, io, json, os, re, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
ap = argparse.ArgumentParser(); ap.add_argument('queries', nargs='+'); ap.add_argument('--out', required=True)
ap.add_argument('--each', type=int, default=14); ap.add_argument('--bg', action='store_true')
a = ap.parse_args()


def get(url, ref=None, t=25):
    h = {'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9', 'Accept': 'text/html,application/json,image/*,*/*'}
    if ref: h['Referer'] = ref
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t).read()


def from_bing(q):
    u = 'https://www.bing.com/images/search?first=1&count=60&q=' + urllib.parse.quote(q + ' pinterest')
    t = html.unescape(get(u).decode('utf8', 'ignore'))
    return re.findall(r'"murl":"(https://i\.pinimg\.com/[^"]+)"', t)


def from_ddg(q):
    q2 = 'site:pinterest.com ' + q
    t = get('https://duckduckgo.com/?iax=images&ia=images&q=' + urllib.parse.quote(q2)).decode('utf8', 'ignore')
    m = re.search(r'vqd=["\']?([\d-]+)', t)
    if not m: return []
    u = 'https://duckduckgo.com/i.js?l=wt-wt&o=json&f=,,,&p=-1&q=' + urllib.parse.quote(q2) + '&vqd=' + m.group(1)
    d = json.loads(get(u, ref='https://duckduckgo.com/').decode('utf8', 'ignore'))
    return [r['image'] for r in d.get('results', []) if 'pinimg.com' in r.get('image', '')]


def search(q):
    found = []
    for attempt in range(3):
        for fn in (from_bing, from_ddg):
            try:
                found += fn(q)
            except Exception:
                pass
        found = list(dict.fromkeys(x.split('?')[0] for x in found))
        if len(found) >= a.each: break
        time.sleep(1.5 * (attempt + 1))
    return found


def best(url):
    """сначала оригинал, потом 736x"""
    for v in (re.sub(r'/(\d+x|\d+x\d+)/', '/originals/', url), re.sub(r'/(originals|\d+x\d+|\d+x)/', '/736x/', url)):
        try:
            b = get(v)
            if len(b) > 12000: return b
        except Exception:
            pass
    return None


os.makedirs(a.out, exist_ok=True)
got = 0; seen = set()
for qi, q in enumerate(a.queries):
    urls = search(q)
    print(f'«{q}»: найдено {len(urls)}', flush=True)
    print(f'   файлы q{qi + 1}_*', flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        data = list(ex.map(best, urls[:a.each * (5 if a.bg else 2)]))
    n = 0
    for b in data:
        if not b or n >= a.each: continue
        h_ = hashlib.md5(b).hexdigest()
        if h_ in seen: continue
        try:
            im = Image.open(io.BytesIO(b)); im.load(); W_, H_ = im.size
        except Exception:
            continue
        r = H_ / W_
        if a.bg:
            if H_ < 900 or r < 1.1: continue
        elif min(W_, H_) < 400 or r > 2.4 or r < .45: continue       # мелкие и длинные коллажи не годятся
        seen.add(h_); n += 1; got += 1
        im.convert('RGB').save(os.path.join(a.out, f'q{qi + 1}_{n:02d}.jpg'), quality=92)
if not got:
    print('НЕ_НАЙДЕНО: поиск не ответил. Подождите минуту и повторите, откройте Pinterest в браузере или попросите человека сохранить картинки в папку.')
    sys.exit(2)
fs = sorted(f for f in os.listdir(a.out) if f.endswith('.jpg') and not f.startswith('_'))
T, H_, cols = 300, 430, 7                                   # крупно: на мелких не видно водяных знаков
c = Image.new('RGB', (cols * T, ((len(fs) + cols - 1) // cols) * H_), 'white'); d = ImageDraw.Draw(c)
for i, f in enumerate(fs):
    im = Image.open(os.path.join(a.out, f)).convert('RGB'); sz = im.size; im.thumbnail((T - 4, H_ - 18))
    c.paste(im, ((i % cols) * T + 2, (i // cols) * H_ + 16))
    d.text(((i % cols) * T + 2, (i // cols) * H_ + 2), os.path.splitext(f)[0], fill='black')
c.save(os.path.join(a.out, '_лист.jpg'), quality=85)
print('картинок:', got, '->', a.out, ' обзор: _лист.jpg')
