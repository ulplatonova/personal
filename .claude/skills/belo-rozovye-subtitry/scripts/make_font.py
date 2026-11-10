#!/usr/bin/env python3
"""Статичный экземпляр Inter Tight Regular для libass (вариативный шрифт libass не подхватывает).
python make_font.py <InterTight.ttf (вариативный)> <out.ttf>"""
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
src, out = sys.argv[1], sys.argv[2]
inst = instantiateVariableFont(TTFont(src), {"wght": 400}, updateFontNames=False)
for rec in inst["name"].names:
    if rec.nameID in (1, 16): rec.string = "InterTightUGC"
    if rec.nameID in (2, 17): rec.string = "Regular"
    if rec.nameID == 4: rec.string = "InterTightUGC Regular"
    if rec.nameID == 6: rec.string = "InterTightUGC-Regular"
inst["OS/2"].usWeightClass = 400
inst.save(out)
print("->", out)
