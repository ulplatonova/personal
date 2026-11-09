"""Путь к ffmpeg: свой из папки скилла, ставить отдельно ничего не нужно."""
import shutil


def ffmpeg():
    p = shutil.which('ffmpeg')
    if p: return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FF = ffmpeg()
