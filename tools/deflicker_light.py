#!/usr/bin/env python3
"""Убирает мерцание тёплой лампы на заднем плане, сохраняя сам оранжевый свет.
python deflicker_light.py in.mp4 out.mp4 [--masks masks.npy] [--win 1.0]
Двухпроходно: 1) яркость тёплой зоны по кадрам; 2) каждый кадр подтягивается к плавному среднему
(скользящее окно ~1 с), но только в «оранжевых» пикселях фона (человек по маске не трогается)."""
import argparse, subprocess, numpy as np, cv2

ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out')
ap.add_argument('--masks'); ap.add_argument('--mfps', type=float, default=15); ap.add_argument('--win', type=float, default=1.0)
ap.add_argument('--crf', default='16')
ap.add_argument('--zone', default='0,0.33,0.35,0.78')   # x0,x1,y0,y1 в долях кадра
a = ap.parse_args()
pr = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height,r_frame_rate',
                     '-of', 'csv=p=0', a.src], capture_output=True, text=True).stdout.strip().split(',')
W, H = int(pr[0]), int(pr[1]); num, den = map(int, pr[2].split('/')); FPS = num / den
SW, SH = 270, 480
M = np.load(a.masks) if a.masks else None


ZONE = np.zeros((SH, SW), np.float32)
x0, x1, y0, y1 = [float(v) for v in a.zone.split(',')]               # зона лампы, доли кадра
ZONE[int(y0 * SH):int(y1 * SH), int(x0 * SW):int(x1 * SW)] = 1
ZONE = cv2.GaussianBlur(ZONE, (0, 0), 12)


def warm_weight(small):
    f = small.astype(np.float32)
    w = np.clip((f[..., 0] - f[..., 2] - 30) / 50, 0, 1)          # оранжевость
    return cv2.GaussianBlur(w, (0, 0), 4) * ZONE


def person(t):
    if M is None: return 0
    m = M[min(int(t * a.mfps), len(M) - 1)].astype(np.float32) / 255
    return cv2.GaussianBlur(np.clip((m - .3) / .4, 0, 1), (0, 0), 3)


# проход 1
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', a.src, '-vf', f'scale={SW}:{SH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
L = []; i = 0
while True:
    r = p.stdout.read(SW * SH * 3)
    if len(r) < SW * SH * 3: break
    f = np.frombuffer(r, np.uint8).reshape(SH, SW, 3)
    w = warm_weight(f) * (1 - person(i / FPS))
    L.append((f.astype(np.float32).mean(2) * w).sum() / max(w.sum(), 1)); i += 1
L = np.array(L); k = max(3, int(a.win * FPS) | 1)
pad = np.pad(L, (k // 2, k // 2), mode='edge'); smooth = np.convolve(pad, np.ones(k) / k, 'valid')
gain = np.clip(smooth / np.maximum(L, 1), 0.85, 1.15)
print(f'кадров {len(L)}, мерцание до: {np.abs(np.diff(L)).mean():.2f}, после (оценка): {np.abs(np.diff(L * gain)).mean():.2f}', flush=True)

# проход 2
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', a.src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f'{num}/{den}', '-i', '-',
                        '-i', a.src, '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-crf', a.crf, '-preset', 'fast', '-pix_fmt', 'yuv420p',
                        '-c:a', 'copy', a.out], stdin=subprocess.PIPE)
fb = W * H * 3
for i in range(len(L)):
    r = dec.stdout.read(fb)
    if len(r) < fb: break
    f = np.frombuffer(r, np.uint8).reshape(H, W, 3)
    small = cv2.resize(f, (SW, SH), interpolation=cv2.INTER_AREA)
    w = warm_weight(small) * (1 - person(i / FPS))
    w = cv2.resize(w, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    g = 1 + (gain[i] - 1) * w
    enc.stdin.write(np.clip(f.astype(np.float32) * g, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print('->', a.out)
