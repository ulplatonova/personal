#!/usr/bin/env python3
"""Накладывает звуки вставок на видео. Видео копируется без перекодирования.
python add_sfx.py in.mp4 cues.json out.mp4
cues.json: [{"t": 2.6, "sfx": "pop", "db": -10}, ...]  sfx: pop | click | whoosh | sparkle | путь к своему wav
Громкость голоса выравнивается под Instagram (loudnorm −14 LUFS) ДО смешивания, звуки идут поверх на db (по умолч. −10).
Шумоподавления нет — музыку в исходнике не трогаем."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SFX = os.path.join(HERE, '..', 'sfx')
src, cues_f, out = sys.argv[1:4]
cues = json.load(open(cues_f, encoding='utf8'))
cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src]
for c in cues:
    p = c['sfx'] if os.path.isfile(c['sfx']) else os.path.join(SFX, c['sfx'] + '.wav')
    cmd += ['-i', p]
parts = ['[0:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[v]']
for i, c in enumerate(cues, 1):
    ms = int(c['t'] * 1000)
    parts.append(f"[{i}:a]aresample=48000,volume={c.get('db', -10)}dB,adelay={ms}|{ms}[s{i}]")
parts.append('[v]' + ''.join(f'[s{i}]' for i in range(1, len(cues) + 1)) +
             f'amix=inputs={len(cues) + 1}:normalize=0:duration=first,alimiter=limit=0.89[a]')
cmd += ['-filter_complex', ';'.join(parts), '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', out]
subprocess.run(cmd, check=True)
print('->', out, f'({len(cues)} звуков)')
