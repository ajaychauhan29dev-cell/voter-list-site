# English -> Hindi rendering of institution names (word-level transliteration + dictionary + acronym spelling).
import re, json, os, urllib.request, urllib.parse
LET = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'ए बी सी डी ई एफ जी एच आई जे के एल एम एन ओ पी क्यू आर एस टी यू वी डब्ल्यू एक्स वाई ज़ेड'.split()))
DICT = {'college':'कॉलेज','collage':'कॉलेज','colleg':'कॉलेज','gollege':'कॉलेज','inter':'इंटर','school':'स्कूल','schoole':'स्कूल','scool':'स्कूल',
 'public':'पब्लिक','publis':'पब्लिक','pubic':'पब्लिक','international':'इंटरनेशनल','national':'नेशनल','nationla':'नेशनल','degree':'डिग्री','digree':'डिग्री',
 'govt':'गवर्नमेंट','government':'गवर्नमेंट','university':'यूनिवर्सिटी','uni':'यूनि','univ':'यूनि','academy':'एकेडमी','institute':'इंस्टीट्यूट',
 'technology':'टेक्नोलॉजी','engineering':'इंजीनियरिंग','management':'मैनेजमेंट','convent':'कॉन्वेंट','senior':'सीनियर','secondary':'सेकेंडरी',
 'primary':'प्राइमरी','junior':'जूनियर','high':'हाई','global':'ग्लोबल','modern':'मॉडर्न','girls':'गर्ल्स','girl':'गर्ल','boys':'बॉयज़','kanya':'कन्या',
 'vidyalaya':'विद्यालय','vidyalay':'विद्यालय','mahavidyalaya':'महाविद्यालय','mahavidyalay':'महाविद्यालय','of':'ऑफ','and':'एंड','the':'द',
 'memorial':'मेमोरियल','model':'मॉडल','central':'सेंट्रल','city':'सिटी','academic':'एकेडमिक','polytechnic':'पॉलिटेक्निक','iti':'आईटीआई',
 'nursing':'नर्सिंग','pharmacy':'फार्मेसी','medical':'मेडिकल','science':'साइंस','arts':'आर्ट्स','commerce':'कॉमर्स','education':'एजुकेशन',
 'world':'वर्ल्ड','star':'स्टार','new':'न्यू','st':'सेंट','saint':'सेंट','mission':'मिशन','english':'इंग्लिश','medium':'मीडियम','campus':'कैंपस',
 'noida':'नोएडा','ghaziabad':'गाज़ियाबाद','greater':'ग्रेटर','delhi':'दिल्ली','road':'रोड','sector':'सेक्टर','group':'ग्रुप','institutions':'इंस्टीट्यूशंस','ram':'राम','om':'ओम','shri':'श्री','sri':'श्री','shree':'श्री','jai':'जय','dev':'देव','sai':'साईं','eng':'इंजीनियरिंग','engg':'इंजीनियरिंग'}
_DIR = os.path.dirname(os.path.abspath(__file__)); _WF = os.path.join(_DIR, 'hi_words.json')
_NF = os.path.join(_DIR, 'hi_normal.json'); NORMAL = set(json.load(open(_NF))) if os.path.exists(_NF) else set()
WORDS = json.load(open(_WF, encoding='utf-8')) if os.path.exists(_WF) else {}
def is_acronym(tok):
    if len(tok) == 1: return True
    if len(tok) <= 4 and not re.search('[aeiouAEIOU]', tok): return True
    # ALL-CAPS token up to 5 letters: spell letters (DPS, IIMT, GNIOT, HRIT) unless it reads like a word (ARYA, AMITY, WAIR)
    if not (len(tok) <= 5 and tok.isupper()) or tok.lower() in DICT: return False
    w = tok.lower()
    if len(w) <= 3: return True
    return not pronounceable(w)
CL = set('bl br ch cl cr dr fl fr gl gr kh ph pl pr sh sk sl sm sn sp st sw th tr bh dh gh jh'.split())
def pronounceable(w):
    if w.startswith(('ii', 'uu')): return False
    m = re.match('[^aeiou]+', w)
    if m and len(m.group()) == 2 and m.group() not in CL: return False
    return bool(re.fullmatch(r'([^aeiou]{0,2}[aeiouy]{1,2})+[^aeiou]{0,2}', w))
def online(words, timeout=8):
    # Google Input Tools transliteration (free, no key). Returns {} on any failure.
    out = {}
    for w in words:
        try:
            u = 'https://inputtools.google.com/request?' + urllib.parse.urlencode(dict(text=w, itc='hi-t-i0-und', num=1, ie='utf-8', oe='utf-8'))
            with urllib.request.urlopen(u, timeout=timeout) as r: j = json.load(r)
            if j[0] == 'SUCCESS': out[w] = j[1][0][1][0]
        except Exception: pass
    return out
def word_hi(tok, fetch=True):
    l = tok.lower()
    if l in DICT: return DICT[l]
    if is_acronym(tok): return ''.join(LET[c] for c in tok.upper())
    if l in WORDS: return WORDS[l]
    if fetch:
        r = online([l]).get(l)
        if r: WORDS[l] = r; return r
    return None
def to_hindi(name, fetch=True):
    if not name or re.search('[\u0900-\u097f]', name) and not re.search('[A-Za-z]{2,}', name): return name
    miss = False
    def rep(m):
        nonlocal miss
        h = word_hi(m.group(0), fetch)
        if h is None: miss = True; return m.group(0)
        return h
    out = re.sub(r'[A-Za-z]+', rep, name)
    return name if miss else out
