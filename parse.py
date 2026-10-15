import cv2, numpy as np, subprocess, sys, json, os, tempfile, csv, io, re
COLS=['serial','name','relative_name','relation','address','gender','dob','institution','c9','c10','state']
def lines(mask, axis):
    s=mask.sum(axis=axis)/255
    thr=0.5*mask.shape[axis]
    idx=np.where(s>thr*0.6)[0] if axis==0 else np.where(s>thr)[0]
    out=[]
    for i in idx:
        if out and i-out[-1][-1]<=4: out[-1].append(i)
        else: out.append([i])
    return [int(np.mean(g)) for g in out]
import tesserocr
from PIL import Image
_api={}
def api(lang,psm):
    k=(lang,psm)
    if k not in _api: _api[k]=tesserocr.PyTessBaseAPI(path='/usr/share/tesseract-ocr/5/tessdata/',lang=lang,psm=psm)
    return _api[k]
def grp(idx,gap=5):
    out=[]
    for i in idx:
        if out and i-out[-1][-1]<=gap: out[-1].append(i)
        else: out.append([i])
    return [int(np.mean(g)) for g in out]
LANG={'serial':'eng','dob':'eng','institution':'eng','address':'hin+eng'}
def ocr(img,lang,psm):
    a=api(lang,psm); a.SetImage(Image.fromarray(img)); return a.GetUTF8Text().strip()
def parse_img(img):
    bw=cv2.threshold(img,235,255,cv2.THRESH_BINARY_INV)[1]
    h=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(img.shape[1]//8,1)))
    v=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,25)))
    xs=grp(np.where(v.sum(axis=0)/255>img.shape[0]*0.1)[0])
    ys=grp(np.where(h.sum(axis=1)/255>img.shape[1]*0.3)[0])
    if len(xs)>2 and xs[1]-xs[0]<40: xs=xs[1:]
    if len(xs)<12: return []
    T=[59,162,428,658,786,901,994,1143,1309,1432,1532,1658]
    sc=img.shape[1]/2338
    xs=[min(xs,key=lambda x:abs(x-t*sc)) if min(abs(x-t*sc) for x in xs)<15*sc else int(t*sc) for t in T]
    clean=img.copy(); clean[(h>0)|(v>0)]=255
    res=[]
    for yi in range(len(ys)-1):
        y0,y1=ys[yi]+3,ys[yi+1]-3
        if y1-y0<25: continue
        r={}
        for ci,c in enumerate(COLS):
            x0,x1=xs[ci]+3,xs[ci+1]-3
            crop=clean[y0:y1,x0:x1]
            if crop.min()>150: r[c]=''; continue
            crop=cv2.copyMakeBorder(crop,10,10,10,10,cv2.BORDER_CONSTANT,value=255)
            if c=='serial':
                r[c]=re.sub(r'\D','',ocr(crop,'eng',7))
                if not r[c]: break
            elif c in('gender','relation','state'): r[c]=ocr(crop,'hin',6).replace('\n',' ')
            elif c in('c9','c10'): r[c]=ocr(crop,'hin+eng',6).replace('\n',' ')
            else: r[c]=re.sub(r'\s+',' ',ocr(crop,LANG.get(c,'hin'),6))
        if r.get('serial') and len(r)==len(COLS) and not (r['name'].strip()=='2' or r['relation'].strip()=='4'): res.append(r)
    return res
def fix(r):
    g=r['gender']
    r['gender']='महिला' if 'हि' in g or 'ला' in g else ('पुरुष' if 'पु' in g or 'रु' in g or 'ष' in g else g)
    m=re.search(r'(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})',r['dob'])
    if m: r['dob']=f"{int(m[1]):02d}/{int(m[2]):02d}/{m[3]}"
    r['state']=r['state'].replace(' ','') and 'उत्तर प्रदेश' if 'उत्त' in r['state'] or 'प्रदे' in r['state'] else r['state']
    m=re.search(r'\b(\d{6})\b',r['address']); r['pincode']=m[1] if m else ''
    return r
def parse_pdf(pdf,first=1,last=None,dpi=200,out=None):
    d=tempfile.mkdtemp(); recs=[]
    import glob
    n=int(re.search(r'Pages:\s+(\d+)',subprocess.run(['pdfinfo',pdf],capture_output=True,text=True).stdout)[1])
    last=last or n
    for p in range(first,last+1):
        subprocess.run(['pdftoppm','-f',str(p),'-l',str(p),'-r',str(dpi),'-gray','-png',pdf,f'{d}/p'])
        f=glob.glob(f'{d}/p*.png')[0]
        try:
            rs=[fix(r) for r in parse_img(cv2.imread(f,0))]
        except Exception as e: rs=[]; print('ERR',p,e,file=sys.stderr)
        os.remove(f)
        for r in rs: r['page']=p
        recs+=rs
        if out: 
            with open(out,'a') as fh:
                for r in rs: fh.write(json.dumps(r,ensure_ascii=False)+'\n')
    return recs
if __name__=='__main__':
    pdf,a,b,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
    parse_pdf(pdf,a,b,out=out)
