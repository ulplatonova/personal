import json,os,subprocess,sys,re
from PIL import Image,ImageDraw,ImageFilter
K=float(os.environ.get('K','1')); FPS=os.environ.get('FPS','30'); OW,OH=int(1080*K),int(1920*K)
W=[x for c in json.load(open('words.json'))['chunks'] for x in c['words']]
END1=4.47
# фото: файл, центр, высота
P=[('p4.jpg',(190,420),265),('p8.jpg',(885,430),250),('p3.jpg',(370,1295),300),('p6.jpg',(770,1240),310),('p2.jpg',(590,1390),310),('p1.jpg',(240,1500),295),('p7.jpg',(790,1505),330),('p5.jpg',(490,1600),245)]
os.makedirs('cards',exist_ok=True); items=[]
for f,(cx,cy),h in P:
    im=Image.open('photos/'+f).convert('RGB'); h=int(h*K); w=int(im.width*h/im.height); im=im.resize((w,h),Image.LANCZOS)
    pad=int(24*K); cv=Image.new('RGBA',(w+2*pad,h+2*pad),(0,0,0,0))
    sh=Image.new('RGBA',cv.size,(0,0,0,0)); ImageDraw.Draw(sh).rectangle([pad,pad+int(5*K),pad+w,pad+h+int(5*K)],fill=(0,0,0,110))
    cv=Image.alpha_composite(cv,sh.filter(ImageFilter.GaussianBlur(10*K))); cv.paste(im,(pad,pad))
    p=f'cards/{f[:-4]}_{int(K)}.png'; cv.save(p); items.append((p,int(cx*K)-cv.width//2,int(cy*K)-cv.height//2))
S=[('star_paper.png',(310,540),125),('mushroom.png',(928,1600),230)]
for f,(cx,cy),h in S:
    im=Image.open('stickers/'+f).convert('RGBA'); h=int(h*K); w=int(im.width*h/im.height); im=im.resize((w,h),Image.LANCZOS)
    pad=int(20*K); cv=Image.new('RGBA',(w+2*pad,h+2*pad),(0,0,0,0))
    shadow=Image.new('RGBA',im.size,(15,8,5,0)); shadow.putalpha(im.split()[3].point(lambda v:int(v*0.4)))
    sh=Image.new('RGBA',cv.size,(0,0,0,0)); sh.paste(shadow,(pad,pad+int(5*K)),shadow); cv=Image.alpha_composite(cv,sh.filter(ImageFilter.GaussianBlur(8*K)))
    cv.alpha_composite(im,(pad,pad)); p=f'cards/{f[:-4]}_{int(K)}.png'; cv.save(p); items.append((p,int(cx*K)-cv.width//2,int(cy*K)-cv.height//2))
# субтитры: по одному слову
fix={21:'дофаминовый',31:'ещё',52:'классической',53:'светло-жёлтой',54:None,57:'розовой',63:'Omi Home',60:'её'}
def ts(x): return f'{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}'
toks=[]
for i,w in enumerate(W):
    s=fix.get(i,w['w'])
    if s is None: toks[-1][2]=w['e']; continue
    s=re.sub(r'[.,?!]','',s)
    if s.startswith('-') and toks: toks[-1][0]+=s; toks[-1][2]=w['e']; continue
    if s not in ('Pinterest','Omi Home'): s=s.lower()
    toks.append([s,w['s'],w['e']])
ev=[]
PILL_T=21.09
for k,(s,a,e) in enumerate(toks):
    if a>=PILL_T-0.05: continue
    b=toks[k+1][1] if k+1<len(toks) else e+0.6
    if b-e>0.6: b=e+0.6
    parts=[(a,min(b,END1),(540,374)),(END1,b,(540,1555))] if a<END1<b else [(a,b,(540,374) if a<END1 else (540,1555))]
    for a2,b2,(X,Y) in parts:
        ev.append(f"Dialogue: 2,{ts(a2)},{ts(b2)},W,,0,0,0,,{{\\an2\\pos({X},{Y+2})\\1c&H000000&\\1a&HA8&\\blur4}}{s}")
        ev.append(f"Dialogue: 3,{ts(a2)},{ts(b2)},W,,0,0,0,,{{\\an2\\pos({X},{Y})}}{s}")
open('subs.ass','w').write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: W,Arial Narrow,46,&H33FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""+'\n'.join(ev)+'\n')
print(' '.join(t[0] for t in toks))
out=sys.argv[1]; vargs=sys.argv[2].split('|')
cmd=['ffmpeg','-nostdin','-v','error','-y','-i','source.mov']
for p,*_ in items: cmd+=['-loop','1','-framerate',FPS,'-t',str(END1+0.2),'-i',p]
Z=f"if(lt(it,{END1}),1.0+0.05*it/{END1},1.0)"
fc=[f"[0:v]scale={OW}:{OH},fps={FPS},zoompan=z='{Z}':x='iw/2-iw/zoom/2':y='ih*0.35-ih/zoom*0.35':d=1:s={OW}x{OH}:fps={FPS},format=yuv420p[b0]"]
for n,(p,x,y) in enumerate(items,1):
    fc.append(f"[b{n-1}][{n}:v]overlay={x}:{y}:enable='lt(t,{END1})':eof_action=pass[b{n}]")
pim=Image.open('stickers/pill.png'); pw,ph=int(pim.width*K),int(pim.height*K); pim.resize((pw,ph),Image.LANCZOS).save(f'cards/pill_{int(K)}.png')
cmd+=['-loop','1','-framerate',FPS,'-t','23.5','-i',f'cards/pill_{int(K)}.png']
n=len(items)+1; px=(OW-pw)//2; py=int(1505*K)-ph//2
fc.append(f"[{n}:v]format=rgba[pl]")
fc.append(f"[b{len(items)}][pl]overlay=x={px}:y={py}:enable='gte(t,{PILL_T})':eof_action=pass[bp]")
fc.append(f"[bp]ass=subs.ass:fontsdir=fonts[v]")
cmd+=['-filter_complex',';'.join(fc),'-map','[v]','-map','0:a',*vargs,out]
subprocess.run(cmd,check=True); print('ok')
