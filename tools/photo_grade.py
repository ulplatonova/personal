import numpy as np, sys, json
from PIL import Image, ImageDraw, ImageFont

def srgb2lin(x): return np.where(x<=0.04045, x/12.92, ((x+0.055)/1.055)**2.4)
def lin2srgb(x):
    x=np.clip(x,0,1); return np.where(x<=0.0031308, x*12.92, 1.055*x**(1/2.4)-0.055)

def luma(x): return x[...,0]*0.2126+x[...,1]*0.7152+x[...,2]*0.0722

def curve(v, pts):
    xs,ys=zip(*pts)
    # smooth monotone via interpolation on fine grid
    return np.interp(v, xs, ys)

def rgb2hsv(c):
    r,g,b=c[...,0],c[...,1],c[...,2]
    mx=c.max(-1); mn=c.min(-1); d=mx-mn+1e-8
    h=np.where(mx==r, ((g-b)/d)%6, np.where(mx==g, (b-r)/d+2, (r-g)/d+4))/6
    return h, d/(mx+1e-8), mx

def grade(img, p, seed=0):
    x=np.asarray(img).astype(np.float32)/255
    lin=srgb2lin(x)
    # white balance (temperature/tint) in linear light, luminance-preserving
    t=p.get('temp',0); tn=p.get('tint',0)
    gains=np.array([1+t*0.5, 1-tn*0.5, 1-t*0.5],np.float32)
    gains/= (gains*[0.2126,0.7152,0.0722]).sum()
    lin=lin*gains*(2**p.get('exp',0))
    x=lin2srgb(lin)
    # tone curve on luminance, keep hue
    Y=luma(x); Y2=curve(Y, p['curve'])
    ratio=np.where(Y>1e-4, Y2/np.maximum(Y,1e-4), 1)[...,None]
    x=x*ratio
    # soft highlight rolloff to avoid clipping colour
    x=np.where(x>0.9, 0.9+(x-0.9)*0.6, x)
    # saturation global + hue-selective
    Y=luma(x)[...,None]
    h,s,v=rgb2hsv(np.clip(x,0,1))
    sat=np.full(h.shape,p.get('sat',1.0),np.float32)
    for (hc,width,mult) in p.get('hsl',[]):
        dh=np.abs(((h-hc+0.5)%1)-0.5)
        w=np.clip(1-dh/width,0,1)
        sat=sat*(1+(mult-1)*w)
    x=Y+(x-Y)*sat[...,None]
    # split toning
    Y=luma(np.clip(x,0,1))[...,None]
    hl=np.array(p.get('hl_tone',[0,0,0]),np.float32); sh=np.array(p.get('sh_tone',[0,0,0]),np.float32)
    x=x+hl*np.clip((Y-0.5)*2,0,1)+sh*np.clip((0.5-Y)*2,0,1)
    # vignette
    vg=p.get('vig',0)
    if vg:
        hh,ww=x.shape[:2]; yy,xx=np.mgrid[0:hh,0:ww].astype(np.float32)
        r=np.sqrt(((xx/ww-0.5)*1.0)**2+((yy/hh-0.5)*0.9)**2)/0.62
        x=x*(1-vg*np.clip(r-0.45,0,1)**1.6)[...,None]
    # grain
    g=p.get('grain',0)
    if g:
        rng=np.random.default_rng(seed)
        n=rng.normal(0,1,x.shape[:2]).astype(np.float32)
        # soften grain a bit
        n=(n+np.roll(n,1,0)+np.roll(n,1,1)+np.roll(np.roll(n,1,0),1,1))/2
        x=x+(g*n*(1-np.abs(Y[...,0]-0.5)*1.2))[...,None]
    return Image.fromarray((np.clip(x,0,1)*255+0.5).astype(np.uint8))

PRESETS={
 # A: тёплая плёнка — кремовые стены, мягкие поднятые чёрные, приглушённо
 'A':dict(temp=0.17,tint=-0.015,exp=0.08,
          curve=[(0,0.035),(0.12,0.10),(0.35,0.33),(0.6,0.62),(0.85,0.86),(1,0.95)],
          sat=0.88,hsl=[(0.33,0.12,0.6),(0.58,0.12,0.6)],
          hl_tone=[0.028,0.012,-0.02],sh_tone=[0.016,0.006,-0.008],grain=0.012),
 # B: глубокий вечер — плотные тени, тёплые света, кинематографично
 'B':dict(temp=0.11,tint=0.0,exp=-0.18,vig=0.35,
          curve=[(0,0.015),(0.10,0.045),(0.3,0.22),(0.55,0.53),(0.8,0.83),(1,0.96)],
          sat=0.85,hsl=[(0.33,0.12,0.5),(0.58,0.12,0.5),(0.06,0.06,1.05)],
          hl_tone=[0.022,0.010,-0.014],sh_tone=[0.0,0.004,0.008],grain=0.010),
 # C: чистый нейтральный — убираем синеву, светлее, почти без стилизации
 'C':dict(temp=0.05,tint=-0.01,exp=0.12,
          curve=[(0,0.01),(0.15,0.15),(0.4,0.42),(0.7,0.72),(1,0.97)],
          sat=0.95,hsl=[(0.58,0.12,0.7)],grain=0.0),
}
