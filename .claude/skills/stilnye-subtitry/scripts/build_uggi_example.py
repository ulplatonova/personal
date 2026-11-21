import json, os, subprocess, sys
from PIL import Image, ImageFilter, ImageDraw
K=float(os.environ.get('K','1'))      # 1 = 1080x1920, 2 = 4K
W=[x for c in json.load(open('words_cut.json'))['chunks'] for x in c['words']]
t=lambda i: W[i]['s']
# группы: (фото, индекс слова появления, центр (x,y), ширина), конец группы
# каскад: (файл, слово-индекс или время, (cx,cy), ширина); группа уходит целиком в end
def at(x): return t(x) if isinstance(x,int) else x
G=[
 ([('g1_1_polka.jpg',17,(175,330),265),('g1_4_noga.jpg',19,(365,318),225),('g1_2_v_ruke.jpg',22,(545,335),220),('g1_5_mnogo.jpg',23,(730,320),250),('g1_3_kofe.jpg',24,(905,340),235)], t(25)-0.15),
 ([('g0_1_kreml.jpg',31,(245,330),320),('g0_2_hollywood.jpg',32,(520,322),290),('g0_3_ikra.jpg',33,(790,338),300)], t(34)-0.15),
 ([('g2_1_zerkalo.jpg',35,(240,330),320),('g2_2_meh.jpg',36,(510,318),275),('g2_3_mem.jpg',37,(790,338),310)], t(41)),
 ([('g4_1_motorola.jpg',90,(192,520),250),('g4_2_skameyka.jpg',91,(352,640),250),('g4_3_sumka.jpg',27.41,(187,860),245),('g4_4_kamera.jpg',27.76,(300,985),250)], 31.04-0.05),
]
SFX=['tick']
os.makedirs('cards',exist_ok=True)
items=[]
for photos,end in G:
    for k,(f,wi,(cx,cy),w) in enumerate(photos):
        wi=at(wi)
        im=Image.open('photos/'+f).convert('RGB'); w=int(w*K)
        h=int(im.height*w/im.width)
        cap=282 if f.startswith('g4') else (270 if f.startswith('g3') else 305)
        if h>int(cap*K): h=int(cap*K); w=int(im.width*h/im.height)
        im=im.resize((w,h),Image.LANCZOS)
        pad=int(30*K); cv=Image.new('RGBA',(w+2*pad,h+2*pad),(0,0,0,0))
        sh=Image.new('RGBA',cv.size,(0,0,0,0)); ImageDraw.Draw(sh).rectangle([pad,pad+int(6*K),pad+w,pad+h+int(6*K)],fill=(0,0,0,110))
        cv=Image.alpha_composite(cv,sh.filter(ImageFilter.GaussianBlur(10*K))); cv.paste(im,(pad,pad))
        p=f'cards/{f[:-4]}_{int(K)}.png'; cv.save(p)
        t0=wi; t1=end
        items.append((p,int(cx*K)-cv.width//2,int(cy*K)-cv.height//2,t0,t1))
STARS=[('stars/star0.png',173,479,122),('stars/star2.png',549,552,59),('stars/star1.png',840,320,54)]
static=[]
for f,cx,cy,hh in STARS:
    im=Image.open(f).convert('RGBA'); hh=int(hh*K); ww=int(im.width*hh/im.height); im=im.resize((ww,hh),Image.LANCZOS)
    pad=int(20*K); cv=Image.new('RGBA',(ww+2*pad,hh+2*pad),(0,0,0,0))
    sh=Image.new('RGBA',cv.size,(0,0,0,0)); a=im.split()[3]
    shadow=Image.new('RGBA',im.size,(20,10,10,0)); shadow.putalpha(a.point(lambda v:int(v*0.45)))
    sh.paste(shadow,(pad,pad+int(4*K)),shadow); cv=Image.alpha_composite(cv,sh.filter(ImageFilter.GaussianBlur(8*K)))
    cv.alpha_composite(im,(pad,pad))
    p=f[:-4]+f'_{int(K)}.png'; cv.save(p)
    static.append((p,int(cx*K)-cv.width//2,int(cy*K)-cv.height//2))
src=sys.argv[1]; ass=sys.argv[2]; out=sys.argv[3]; vargs=sys.argv[4].split('|'); scale=sys.argv[5] if len(sys.argv)>5 else ''
PART=os.environ.get('PART','')
if PART=='A': cmd=['ffmpeg','-nostdin','-v','error','-y','-t','22.75','-i',src]
elif PART=='B': cmd=['ffmpeg','-nostdin','-v','error','-y','-ss','29.14','-t','8.34','-i',src]
else: cmd=['ffmpeg','-nostdin','-v','error','-y','-i',src]
for p,x,y,t0,t1 in items: cmd+=['-loop','1','-framerate',os.environ.get('FPS','30'),'-t',f'{t1+0.4:.2f}','-i',p]
import zoom
FPS=int(os.environ.get('FPS','30')); OW,OH=int(1080*K),int(1920*K)
fc=[f"[0:v]trim=0:22.70,setpts=PTS-STARTPTS[va];[0:v]trim=29.14:37.48,setpts=PTS-STARTPTS[vb];[va][vb]concat=n=2:v=1:a=0,scale={OW}:{OH},fps={FPS},split[zr][zb];[zr]{zoom.zp(OW,OH,FPS)}[za];[zb]scale=trunc(iw*0.84/2)*2:trunc(ih*0.84/2)*2,pad={OW}:{OH}:(ow-iw)/2:(oh-ih)/2:black[zs];[za][zs]overlay=0:0:enable='between(t,21.06,22.68)',format=yuv420p[b0]",
    "[0:a]atrim=0:22.70,asetpts=PTS-STARTPTS[aa];[0:a]atrim=29.14:37.48,asetpts=PTS-STARTPTS[ab];[aa][ab]concat=n=2:v=0:a=1[aout]"]
if PART=='A':
    fc[0]=fc[0].replace('[0:v]trim=0:22.70,setpts=PTS-STARTPTS[va];[0:v]trim=29.14:37.48,setpts=PTS-STARTPTS[vb];[va][vb]concat=n=2:v=1:a=0,','[0:v]trim=0:22.70,setpts=PTS-STARTPTS,')
    fc[1]='[0:a]atrim=0:22.70,asetpts=PTS-STARTPTS[aout]'
elif PART=='B':
    fc[0]=fc[0].replace('[0:v]trim=0:22.70,setpts=PTS-STARTPTS[va];[0:v]trim=29.14:37.48,setpts=PTS-STARTPTS[vb];[va][vb]concat=n=2:v=1:a=0,',f'color=black:s={OW}x{OH}:r={FPS}:d=22.70,format=yuv420p,setsar=1[vbl];[0:v]setpts=PTS-STARTPTS,scale={OW}:{OH},setsar=1[vb];[vbl][vb]concat=n=2:v=1:a=0,')
    fc[1]='anullsrc=r=48000:cl=stereo,atrim=0:22.70[abl];[0:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[ab];[abl][ab]concat=n=2:v=0:a=1[aout]'

for n,(p,x,y,t0,t1) in enumerate(items,1):
    fc.append(f"[{n}:v]format=rgba,fade=t=in:st={t0:.2f}:d=0.03:alpha=1,fade=t=out:st={t1:.2f}:d=0.05:alpha=1,trim=0:{t1+0.3:.2f}[p{n}]")
    fc.append(f"[b{n-1}][p{n}]overlay={x}:{y}:enable='between(t,{t0:.2f},{t1+0.15:.2f})':eof_action=pass[b{n}]")
base=len(items)
for j,(p,x,y) in enumerate(static):
    n=len(items)+1+j
    cmd+=['-loop','1','-framerate',os.environ.get('FPS','30'),'-t','4.9','-i',p]
    fc.append(f"[{n}:v]format=rgba[s{j}]")
    fc.append(f"[b{base+j}][s{j}]overlay={x}:{y}:enable='lt(t,4.85)':eof_action=pass[b{base+j+1}]")
fc.append(f"[b{base+len(static)}]ass={ass}:fontsdir=fonts[v]")
cmd+=['-filter_complex',';'.join(fc),'-map','[v]','-map','[aout]']+(['-ss','22.70'] if PART=='B' else [])+['-t',os.environ.get('END','22.70' if PART=='A' else ('8.34' if PART=='B' else '31.04')),*vargs,out]
subprocess.run(cmd,check=True)
cues=[{'t':round(i[3],2),'sfx':SFX[n%len(SFX)],'db':-18.6} for n,i in enumerate(items)]
cues+=[{'t':27.51,'sfx':os.path.abspath('song/song_cut.wav'),'db':-1},{'t':0,'sfx':os.path.abspath('song/bg.wav'),'db':-28.48}]
json.dump(cues,open('cues.json','w'))
print('ok',len(items))
