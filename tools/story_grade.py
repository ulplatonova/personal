import sys; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from photo_grade import grade, luma
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageOps
import numpy as np
src=Image.open('/root/.claude/uploads/36e0079a-a4d6-5290-8a9c-2475c659e3da/729db122-image.jpg').convert('RGB')
V={
 '1_естественный':dict(temp=-0.02,tint=0.01,exp=0.06,curve=[(0,0.0),(0.15,0.13),(0.45,0.46),(0.75,0.79),(1,0.98)],sat=1.0,hsl=[]),
 '2_теплый_мягкий':dict(temp=0.08,tint=-0.01,exp=0.10,curve=[(0,0.025),(0.15,0.15),(0.45,0.47),(0.75,0.78),(1,0.96)],sat=0.92,hsl=[],hl_tone=[0.015,0.006,-0.01]),
 '3_холодный_хром':dict(temp=-0.10,tint=0.0,exp=0.0,curve=[(0,0.0),(0.12,0.08),(0.4,0.39),(0.72,0.77),(1,0.98)],sat=0.82,hsl=[(0.08,0.08,1.0)],sh_tone=[-0.006,0,0.008]),
 '4_чб':dict(temp=0,exp=0.04,curve=[(0,0.0),(0.12,0.08),(0.42,0.42),(0.75,0.8),(1,0.98)],sat=0.0,hsl=[]),
}
def finish(im):
    im=im.filter(ImageFilter.UnsharpMask(radius=40,percent=18,threshold=0))   # clarity
    im=im.filter(ImageFilter.UnsharpMask(radius=1.2,percent=70,threshold=3))  # sharpness
    return im
outs=[]
for k,p in V.items():
    o=finish(grade(src,p)); o.save(f'IMG_3428_{k}.jpg',quality=96,subsampling=0); outs.append((k,o))
W=480; H=int(W*16/9)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',26)
items=[('оригинал',src)]+[(k.replace('_',' '),o) for k,o in outs]
sheet=Image.new('RGB',(len(items)*(W+12),H+50),(245,243,240)); d=ImageDraw.Draw(sheet)
for i,(n,im) in enumerate(items):
    sheet.paste(im.resize((W,H),Image.LANCZOS),(i*(W+12),50)); d.text((i*(W+12)+8,10),n,fill=(40,40,40),font=font)
sheet.save('story_compare.jpg',quality=92)
# zoom crop face for sharpness check
z=Image.new('RGB',(2*600+12,700),(245,243,240))
z.paste(src.crop((300,500,900,1200)),(0,0)); z.paste(outs[0][1].crop((300,500,900,1200)),(612,0)); z.save('zoom.jpg',quality=92)
