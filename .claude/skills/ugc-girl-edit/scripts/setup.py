#!/usr/bin/env python3
"""Подготовка один раз: своя папка с программами, на компьютере ничего не меняет и не требует ffmpeg.
python3 setup.py  -> последняя строка PYTHON=<путь>, этим Python запускать остальные скрипты."""
import os, platform, subprocess, sys, venv

HOME = os.path.join(os.path.expanduser('~'), '.ugc-girl-edit')
VENV = os.path.join(HOME, 'venv')
PY = os.path.join(VENV, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(VENV, 'bin', 'python')
V = sys.version_info


def pip(*pkgs):
    return subprocess.run([PY, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', *pkgs]).returncode == 0


if V < (3, 9):
    sys.exit('НУЖЕН_НОВЫЙ_PYTHON: этот Python старый, нужен 3.9 или новее.')
if not os.path.exists(PY):
    print('Создаю папку с программами…', flush=True)
    venv.create(VENV, with_pip=True)
print('Ставлю программы для монтажа, это один раз и несколько минут…', flush=True)
numpy = 'numpy<2' if V < (3, 13) else 'numpy'
if not pip(numpy, 'opencv-python-headless<4.12' if V < (3, 13) else 'opencv-python-headless', 'pillow', 'imageio-ffmpeg'):
    sys.exit('НЕТ_ИНТЕРНЕТА: не удалось поставить программы. Проверьте интернет и запустите ещё раз.')
apple = platform.system() == 'Darwin' and platform.machine() == 'arm64'
if not (pip('mlx-whisper') if apple else False) and not pip('faster-whisper'):
    sys.exit('НЕТ_ИНТЕРНЕТА: не удалось поставить распознавание речи. Проверьте интернет и запустите ещё раз.')
# Необязательная часть: текст за головой. Без неё всё работает, текст просто стоит над головой.
ok = V < (3, 13) and pip('mediapipe==0.10.21')
print('Текст за головой:', 'доступен' if ok else 'недоступен на этом компьютере, текст будет над головой')
print(f'PYTHON={PY}')
