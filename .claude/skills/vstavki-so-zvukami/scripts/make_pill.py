#!/usr/bin/env python3
"""Плашка-отметка как в рилсах: тёмная полупрозрачная капсула, круглая аватарка, ник и имя.
python make_pill.py avatar.jpg "@nick" "Имя Фамилия" out.png [--font путь.ttf] [--scale 1]"""
import argparse
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser(); ap.add_argument('avatar'); ap.add_argument('nick'); ap.add_argument('name'); ap.add_argument('out')
ap.add_argument('--font', default='/home/user/personal/.claude/skills/belo-rozovye-subtitry/fonts/InterTightUGC.ttf'); ap.add_argument('--scale', type=float, default=1.0)
a = ap.parse_args(); k = a.scale
H = int(96 * k); pad = int(14 * k); av = H - 2 * pad
f1 = ImageFont.truetype(a.font, int(30 * k)); f2 = ImageFont.truetype(a.font, int(24 * k))
tw = max(f1.getlength(a.nick), f2.getlength(a.name))
W = int(pad + av + 18 * k + tw + 34 * k)
im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle((0, 0, W - 1, H - 1), radius=H // 2, fill=(30, 30, 30, 200))
ava = Image.open(a.avatar).convert('RGB'); s = min(ava.size)
ava = ava.crop(((ava.width - s) // 2, (ava.height - s) // 2, (ava.width + s) // 2, (ava.height + s) // 2)).resize((av, av), Image.LANCZOS)
m = Image.new('L', (av, av), 0); ImageDraw.Draw(m).ellipse((0, 0, av - 1, av - 1), fill=255)
im.paste(ava, (pad, pad), m)
x = pad + av + int(18 * k)
d.text((x, int(16 * k)), a.nick, font=f1, fill=(255, 255, 255, 255))
d.text((x, int(52 * k)), a.name, font=f2, fill=(205, 205, 205, 255))
im.save(a.out); print('->', a.out, im.size)
