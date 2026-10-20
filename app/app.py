import os, sqlite3, secrets, threading, json, sys, tempfile, time, hmac
from flask import Flask, request, jsonify, g, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.environ.get('DB', os.path.join(os.path.dirname(__file__), 'voters.db'))
USER = 'kuldeep-malik@mlc.com'
PW_HASH = generate_password_hash('kuldeep123')
SEARCH_COLS = ['name','relative_name','relation','address','gender','dob','institution','serial','pincode','state']
FIELDS = ['serial','name','relative_name','relation','address','gender','dob','institution','c9','c10','state','pincode','page']
app = Flask(__name__, static_folder=None)
try:
    from flask_compress import Compress; Compress(app)
except ImportError: pass
app.config['MAX_CONTENT_LENGTH'] = 400*1024*1024
SESSIONS = {}  # token -> expiry
JOBS = {}

PG = os.environ.get('DATABASE_URL')
POOL = None
if PG and not os.environ.get('NEON_HTTP'):
    # Reuse connections across requests (new TLS connections to Neon cost ~1 s each).
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    POOL = ConnectionPool(PG, min_size=1, max_size=8, kwargs={'row_factory': dict_row, 'autocommit': True}, max_idle=240, open=True)
    # autocommit + no per-checkout health check: one network round trip per query. Dead connections are retried below.
import re, difflib
def norm(t):
    # lowercase; dots/punctuation/extra spaces removed; Hindi "0" abbreviation marks (पी0जी0) treated as dots
    t = re.sub(r'(?<=[\u0900-\u097f])0', ' ', (t or '').lower())
    return ' '.join(re.sub(r'[^a-z0-9\u0900-\u097f]+', ' ', t).split())
def inst_score(nq, cq, v):
    ne = norm(v); ce = ne.replace(' ', '')
    if not ce: return 0
    if ce == cq: return 100
    if ce.startswith(cq) or ne.startswith(nq): return 90
    if any(w.startswith(cq) for w in ne.split()) and len(cq) >= 3: return 85
    if cq in ce: return 80
    if len(cq) < 4: return 0
    def merge(t): return re.sub(r'\b(\w)\b ?(?=\w\b)', r'\1', t)  # "i p college" -> "ip college"
    qw = merge(nq).split(); ws = merge(ne).split(); k = len(qw); best = 0
    def wsim(a, b):
        if a == b: return 1
        if len(a) <= 2: return 0          # short words / initials must match exactly
        if b.startswith(a): return 0.95
        if len(a) < 4: return 0
        r = difflib.SequenceMatcher(None, a, b).ratio(); return r if r >= 0.75 else 0
    for i in range(len(ws) - k + 1):
        sims = [wsim(a, b) for a, b in zip(qw, ws[i:i+k])]
        if all(sims): best = max(best, sum(sims) / k)
    return 50 + best * 20 if best else 0
CACHE = {}; CACHE_LOCK = threading.Lock(); CACHE_TTL = 60
def cached(key, fn, ttl=CACHE_TTL):
    now = time.time(); v = CACHE.get(key)
    if v and v[0] > now: return v[1]
    val = fn()
    with CACHE_LOCK: CACHE[key] = (now + ttl, val)
    return val
def invalidate():
    with CACHE_LOCK: CACHE.clear()
class NeonHTTP:
    # Neon's HTTPS SQL endpoint (for networks where port 5432 is blocked). Autocommit per statement.
    def __init__(self, url):
        import urllib.parse; self.url = url; self.host = urllib.parse.urlparse(url).hostname
    def cursor(self): return self
    def execute(self, sql, args=()):
        import urllib.request, re
        n = iter(range(1, 100000)); sql = re.sub(r'%s', lambda m: f'${next(n)}', sql).replace('%%', '%')
        req = urllib.request.Request(f'https://{self.host}/sql', data=json.dumps({'query': sql, 'params': [None if a is None else str(a) for a in args]}).encode(),
            headers={'Neon-Connection-String': self.url, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r: res = json.load(r)
        self.rows = [{k: (int(v) if v is not None and k in ('id','n','cid','page') else v) for k, v in row.items()} for row in res.get('rows', [])]
    def executemany(self, sql, rows):
        for r in rows: self.execute(sql, r)
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
class Conn:
    def __init__(self):
        if PG and os.environ.get('NEON_HTTP'):
            self.c = NeonHTTP(PG)
        elif PG:
            self.pooled = True; self.c = POOL.getconn()
        else:
            self.c = sqlite3.connect(DB); self.c.row_factory = lambda cur, row: {d[0]: row[i] for i, d in enumerate(cur.description)}
    def q(self, sql):
        if PG: sql = sql.replace('?', '%s').replace(' like ', ' ilike ').replace('insert or ignore', 'insert')
        return sql
    def execute(self, sql, args=()):
        try:
            cur = self.c.cursor(); cur.execute(self.q(sql), args); return cur
        except Exception as e:
            if not getattr(self, 'pooled', False) or not self.c.closed: raise
            POOL.putconn(self.c); self.c = POOL.getconn()  # stale pooled connection: retry once on a fresh one
            cur = self.c.cursor(); cur.execute(self.q(sql), args); return cur
    def executemany(self, sql, rows):
        cur = self.c.cursor(); cur.executemany(self.q(sql), rows); return cur
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self):
        if getattr(self, 'pooled', False): POOL.putconn(self.c)
        else: self.c.close()
def connect(): return Conn()
def db():
    if 'db' not in g: g.db = connect()
    return g.db
@app.teardown_appcontext
def close(e):
    d = g.pop('db', None)
    if d: d.close()
def init():
    c = connect()
    pk = 'serial primary key' if PG else 'integer primary key'
    for stmt in f'''create table if not exists constituency(id {pk}, name text unique);
    create table if not exists voter(id {pk}, cid integer, serial text, name text, relative_name text, relation text,
      address text, gender text, dob text, institution text, c9 text, c10 text, state text, pincode text, page integer);
    create index if not exists vc on voter(cid); create index if not exists vi on voter(cid, institution);
    create table if not exists institution_hi(name text primary key, hi text)'''.split(';'):
        c.execute(stmt)
    if PG:
        try:
            c.execute('create extension if not exists pg_trgm'); c.commit()
            for col in SEARCH_COLS:
                c.execute(f'create index if not exists vt_{col} on voter using gin ({col} gin_trgm_ops)')
            c.commit()
        except Exception as e:
            c.rollback(); print('trigram indexes skipped:', e, file=sys.stderr)
    for n in ['Gautam Buddha Nagar', 'Ghaziabad']:
        c.execute('insert or ignore into constituency(name) values(?)' + (' on conflict do nothing' if PG else ''), (n,))
    c.commit(); c.close()

def authed():
    t = request.cookies.get('sid'); v = SESSIONS.get(t)
    return bool(t and v and v[0] > time.time())
def role():
    v = SESSIONS.get(request.cookies.get('sid')); return v[1] if v else None
@app.before_request
def guard():
    if request.path.startswith('/api/') and request.path not in ('/api/login', '/api/guest') and not authed():
        return jsonify(error='unauthorized'), 401
    if request.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS') and request.path not in ('/api/login', '/api/guest', '/api/logout', '/api/geo') and role() != 'admin':
        return jsonify(error='forbidden: admin only'), 403
    if request.path.startswith('/api/jobs/') and role() != 'admin':
        return jsonify(error='forbidden: admin only'), 403

@app.post('/api/login')
def login():
    d = request.get_json(force=True, silent=True) or {}
    ok = hmac.compare_digest((d.get('id') or '').strip().lower(), USER) and check_password_hash(PW_HASH, d.get('password') or '')
    if not ok:
        time.sleep(1); return jsonify(error='Invalid ID or password'), 401
    return start_session('admin')
def start_session(rl):
    t = secrets.token_urlsafe(32); SESSIONS[t] = (time.time() + 12*3600, rl)
    r = make_response(jsonify(ok=True, role=rl))
    r.set_cookie('sid', t, httponly=True, samesite='Lax', secure=request.headers.get('X-Forwarded-Proto','http')=='https' or request.is_secure, max_age=12*3600)
    return r
@app.post('/api/guest')
def guest(): return start_session('guest')
@app.post('/api/logout')
def logout():
    SESSIONS.pop(request.cookies.get('sid'), None)
    r = make_response(jsonify(ok=True)); r.delete_cookie('sid'); return r
@app.get('/api/me')
def me(): return jsonify(user=USER if role() == 'admin' else 'guest', role=role())

@app.get('/api/constituencies')
def consts():
    rows = cached('consts', lambda: db().execute('select c.id, c.name, count(v.id) n from constituency c left join voter v on v.cid=c.id group by c.id, c.name order by c.id').fetchall())
    return jsonify(rows)
@app.post('/api/constituencies')
def add_const():
    name = ((request.get_json(force=True, silent=True) or {}).get('name') or '').strip()
    if not name: return jsonify(error='Name required'), 400
    if db().execute('select 1 from constituency where lower(name)=lower(?)', (name,)).fetchone():
        return jsonify(error='This district already exists'), 400
    db().execute('insert into constituency(name) values(?)', (name,)); db().commit(); invalidate()
    cid = db().execute('select id from constituency where name=?', (name,)).fetchone()['id']
    return jsonify(ok=True, id=cid)

@app.delete('/api/constituencies/<int:cid>')
def del_const(cid):
    if not db().execute('select 1 from constituency where id=?', (cid,)).fetchone():
        return jsonify(error='Not found'), 404
    db().execute('delete from voter where cid=?', (cid,))
    db().execute('delete from constituency where id=?', (cid,)); db().commit(); invalidate()
    return jsonify(ok=True)

@app.get('/api/constituencies/<int:cid>/institutions')
def insts(cid):
    return jsonify(inst_list(cid))
def inst_list(cid):
    return cached(('insts', cid), lambda: db().execute("select v.institution, count(*) n, max(h.hi) hi from voter v left join institution_hi h on h.name=v.institution where v.cid=? and v.institution<>'' group by v.institution order by v.institution", (cid,)).fetchall())
def fuzzy_insts(cid, q):
    # Forgiving institution match (English or Hindi name): returns [(institution, score)], best first.
    def f():
        nq = norm(q); cq = nq.replace(' ', '')
        if len(cq) < 2: return []
        out = []
        for i in inst_list(cid):
            sc = max(inst_score(nq, cq, i['institution']), inst_score(nq, cq, i.get('hi') or ''))
            if sc: out.append((i['institution'], sc))
        return sorted(out, key=lambda x: -x[1])[:400]
    return cached(('fz', cid, q), f)

@app.get('/api/constituencies/<int:cid>/voters')
def voters(cid):
    q = (request.args.get('q') or '').strip(); inst = request.args.get('institution')
    page = max(1, int(request.args.get('page', 1))); size = min(500, int(request.args.get('size', 50)))
    where = ['cid=?']; args = [cid]
    if inst: where.append('institution=?'); args.append(inst)
    for term in q.split():
        # PG: "col ilike ?" (same matches as lower()/lower()) so the pg_trgm indexes can be used.
        where.append('(' + ' or '.join(f'{c} like ?' if PG else f'lower({c}) like lower(?)' for c in SEARCH_COLS) + ')'); args += [f'%{term}%']*len(SEARCH_COLS)
    lit = ' and '.join(where[1 + bool(inst):]) or '1=1'
    base = ' and '.join(where[:1 + bool(inst)]); bargs = args[:1 + bool(inst)]; largs = args[1 + bool(inst):]
    fz = fuzzy_insts(cid, q) if q and not inst else []
    if fz:
        strong = [n for n, sc in fz if sc >= 80]; allm = [n for n, _ in fz]
        ph = lambda l: ','.join('?' * len(l))
        w = f"{base} and (({lit}) or institution in ({ph(allm)}))"; args = bargs + largs + allm
        # rank: exact/prefix/substring institution matches, then other literal matches, then typo-tolerant matches
        rank = "(case " + (f"when institution in ({ph(strong)}) then 0 " if strong else '') + f"when ({lit}) then 1 else 2 end), "; rargs = strong + largs
    else:
        w = ' and '.join(where); rank = ''; rargs = []
    rows = db().execute(f"select *, count(*) over() as _total from voter where {w} order by {rank}(case when coalesce(institution, '') = '' then 1 else 0 end), institution, cast(serial as integer), page, id limit ? offset ?", args+rargs+[size,(page-1)*size]).fetchall()
    if not rows and page == 1 and q and PG and not fz:
        # nothing matched literally: forgiving voter-name match (pg_trgm word similarity, uses the trigram index)
        terms = [t for t in q.split() if len(t) >= 3]
        if terms:
            fw = ' and '.join(where[:1 + bool(inst)] + ['(? <%% name or ? <%% relative_name)'] * len(terms))
            fa = bargs + [x for t in terms for x in (t, t)]
            rows = db().execute(f"select *, count(*) over() as _total from voter where {fw} order by greatest({' + '.join(['word_similarity(?, name)'] * len(terms))}) desc, id limit ? offset ?", fa + terms + [size, 0]).fetchall()
            for r in rows: r['_total'] = len(rows)
    if rows: total = int(rows[0]['_total'])
    else: total = db().execute(f'select count(*) n from voter where {w}', args).fetchone()['n'] if page > 1 else 0
    for r in rows: r.pop('_total', None)
    return jsonify(total=total, page=page, size=size, rows=rows)

def insert(cid, recs, conn=None):
    c = conn or connect()
    ph = '(' + ','.join('?' * (len(FIELDS) + 1)) + ')'
    for i in range(0, len(recs), 300):
        chunk = recs[i:i+300]
        c.execute(f'insert into voter(cid,{",".join(FIELDS)}) values ' + ','.join([ph] * len(chunk)),
                  [v for r in chunk for v in [cid] + [r.get(f, '') for f in FIELDS]])
    c.commit()
    if not conn: c.close()

def run_job(jid, cid, path):
    from parse import parse_pdf
    import subprocess, re
    try:
        n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', path], capture_output=True, text=True).stdout)[1])
        JOBS[jid].update(pages=n)
        for p in range(1, n+1):
            recs = parse_pdf(path, p, p)
            insert(cid, recs)
            JOBS[jid]['done'] = p; JOBS[jid]['added'] += len(recs); invalidate()
        add_hindi_names(cid)
        JOBS[jid]['status'] = 'finished'; invalidate()
    except Exception as e:
        JOBS[jid].update(status='error', error=str(e)); invalidate()
    finally:
        os.remove(path)

def add_hindi_names(cid):
    # Give newly uploaded institutions a Hindi name (falls back to the English name).
    try:
        from hindi import to_hindi
        c = connect()
        new = [x['institution'] for x in c.execute("select distinct institution from voter v where cid=? and institution<>'' and not exists (select 1 from institution_hi h where h.name=v.institution)", (cid,)).fetchall()]
        for n in new:
            c.execute('insert into institution_hi(name, hi) values(?, ?) on conflict do nothing' if PG else 'insert or ignore into institution_hi(name, hi) values(?, ?)', (n, to_hindi(n)))
        c.commit(); c.close()
    except Exception as e: print('hindi names failed:', e, file=sys.stderr)

@app.post('/api/constituencies/<int:cid>/upload')
def upload(cid):
    f = request.files.get('file')
    if not f or not f.filename.lower().endswith('.pdf'): return jsonify(error='Please upload a PDF'), 400
    fd, path = tempfile.mkstemp(suffix='.pdf'); os.close(fd); f.save(path)
    if request.form.get('replace') == '1':
        db().execute('delete from voter where cid=?', (cid,)); db().commit(); invalidate()
    jid = secrets.token_hex(6); JOBS[jid] = dict(status='running', done=0, pages=0, added=0)
    threading.Thread(target=run_job, args=(jid, cid, path), daemon=True).start()
    return jsonify(job=jid)
@app.get('/api/jobs/<jid>')
def job(jid): return jsonify(JOBS.get(jid) or {'status': 'unknown'})

_GEO = None
def _in_ring(x, y, ring):
    ins = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: ins = not ins
        j = i
    return ins
@app.post('/api/geo')
def geo():
    # Map a point to a UP district using the bundled offline boundaries (up_districts.json).
    # Coordinates are rounded and used only for this lookup: never stored, logged or forwarded.
    global _GEO
    d = request.get_json(force=True, silent=True) or {}
    try: x = round(float(d.get('lng')), 3); y = round(float(d.get('lat')), 3)
    except Exception: return jsonify(district='unknown', state='unknown')
    if _GEO is None:
        _GEO = json.load(open(os.path.join(os.path.dirname(__file__), 'up_districts.json')))
        for f in _GEO:
            polys = f['c'] if f['t'] == 'MultiPolygon' else [f['c']]
            xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
            f['polys'] = polys; f['bb'] = (min(xs), min(ys), max(xs), max(ys))
    for f in _GEO:
        b = f['bb']
        if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]): continue
        for poly in f['polys']:
            if _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, h) for h in poly[1:]):
                return jsonify(district=f['d'], state=f['s'])
    return jsonify(district='unknown', state='unknown')

GA_PROD_HOST = 'voter-list-site.onrender.com'; GA_DEFAULT_ID = 'G-H222BYZLFJ'
@app.get('/ga.js')
def ga_js():
    # GA4 config: env GA_MEASUREMENT_ID wins; otherwise the default ID only on the production host. Never on localhost/dev.
    host = (request.headers.get('X-Forwarded-Host') or request.host or '').split(':')[0].lower()
    gid = os.environ.get('GA_MEASUREMENT_ID') or (GA_DEFAULT_ID if host == GA_PROD_HOST else '')
    if host in ('localhost', '127.0.0.1', '0.0.0.0') or host.endswith('.local') or os.environ.get('GA_DISABLED'): gid = ''
    cfg = json.dumps({'id': gid, 'debug': os.environ.get('GA_DEBUG', '') in ('1', 'true', 'yes')})
    body = f'window.GA_CFG={cfg};\n' + open(os.path.join(os.path.dirname(__file__), 'static', 'analytics.js'), encoding='utf-8').read()
    r = make_response(body); r.headers['Content-Type'] = 'application/javascript; charset=utf-8'; r.headers['Cache-Control'] = 'no-cache'
    return r
@app.get('/')
def index(): return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'index.html')
@app.get('/static/<path:p>')
def st(p): return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), p)

init()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), threaded=True)
