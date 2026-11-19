import json,sys
W=[w for ch in json.load(open('words.json'))['chunks'] for w in ch['words']]
SS,BS=int(sys.argv[1]),int(sys.argv[2]); Y=400; GS=int(sys.argv[3]); GB=int(sys.argv[4])
until=3.7; t0=0.0
ul=json.loads(sys.argv[5]) if len(sys.argv)>5 else None
lines=[['самые','неожиданные','открытия'],['за','4','месяца'],['жизни','с','собакой']]
def ts(x): return f'{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}'
PEACH='&HA6C9F5&'
ev=[];wi=0;y=Y
for li,ws in enumerate(lines):
    fsp=-3 if li==0 else -6
    parts=[]
    for k,w in enumerate(ws):
        ms=int((W[wi]['s']-t0)*1000); wi+=1
        tag=f"{{\\alpha&HFF&\\t({ms},{ms+120},\\alpha&H00&)}}"
        parts.append(tag+w)
    txt=f"{{\\fsp3}} {{\\fsp{fsp}}}".join(parts)
    style='HookS' if li==0 else 'HookB'
    col='' if li==0 else '{\\c'+PEACH+'}'
    ev.append(f"Dialogue: 0,{ts(t0)},{ts(until)},{style},,0,0,0,,{{\\an8\\pos(540,{y})\\fsp{fsp}}}{col}{txt}")
    if ul and li==ul['line']:
        x0,w,uy=ul['x'],ul['w'],y+ul['dy']; ta=int((ul['t']-t0)*1000); tb=ta+int(ul['dur']*1000)
        ev.append(f"Dialogue: 1,{ts(t0)},{ts(until)},HookB,,0,0,0,,{{\\an7\\pos({x0},{uy})\\bord0\\shad0\\1c{PEACH}\\clip({x0},{uy-5},{x0},{uy+12})\\t({ta},{tb},\\clip({x0},{uy-5},{x0+w},{uy+12}))\\p1}}m 0 0 l {w} -1 l {w} 2 l 0 3{{\\p0}}")
    y+= GS if li==0 else GB
hdr=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookS,InterTightUGC,{SS},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,60,60,0,1
Style: HookB,InterTightUGC,{BS},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,60,60,0,1
"""
open('hook3.ass','w').write(hdr+'\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'+'\n'.join(ev)+'\n')
