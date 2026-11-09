"""Распознавание речи: на Mac с Apple Silicon mlx-whisper, на остальных faster-whisper."""
import platform, subprocess
import numpy as np
from ff import FF

SR = 16000


def read_audio(video):
    raw = subprocess.run([FF, '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def recognizer(lang='ru', engine='auto', model=''):
    """-> функция: звук (float32, 16 кГц) -> [(слово, начало, конец), ...]"""
    if engine == 'auto':
        engine = 'mlx' if platform.system() == 'Darwin' and platform.machine() == 'arm64' else 'faster'
    if engine == 'mlx':
        try:
            import mlx_whisper
            M = model or 'mlx-community/whisper-large-v3-turbo'
            def rec(seg):
                r = mlx_whisper.transcribe(seg, path_or_hf_repo=M, language=lang, word_timestamps=True, condition_on_previous_text=False)
                return [(w['word'].strip(), w['start'], w['end']) for s in r['segments'] for w in s.get('words', [])]
            return rec
        except ImportError:
            pass
    from faster_whisper import WhisperModel
    m = WhisperModel(model or 'turbo', device='cpu', compute_type='int8')
    def rec(seg):
        ss, _ = m.transcribe(seg, language=lang, word_timestamps=True, condition_on_previous_text=False, vad_filter=False)
        return [(w.word.strip(), w.start, w.end) for s in ss for w in (s.words or [])]
    return rec
