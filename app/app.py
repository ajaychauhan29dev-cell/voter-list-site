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
        n = iter(range(1, 100000)); sql = re.sub(r'%s', lambda m: f'${next(n)}', sql)
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
    create index if not exists vc on voter(cid); create index if not exists vi on voter(cid, institution)'''.split(';'):
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
    if request.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS') and request.path not in ('/api/login', '/api/guest', '/api/logout') and role() != 'admin':
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
    rows = cached(('insts', cid), lambda: db().execute("select institution, count(*) n from voter where cid=? and institution<>'' group by institution order by institution", (cid,)).fetchall())
    return jsonify(rows)

@app.get('/api/constituencies/<int:cid>/voters')
def voters(cid):
    q = (request.args.get('q') or '').strip(); inst = request.args.get('institution')
    page = max(1, int(request.args.get('page', 1))); size = min(500, int(request.args.get('size', 50)))
    where = ['cid=?']; args = [cid]
    if inst: where.append('institution=?'); args.append(inst)
    for term in q.split():
        # PG: "col ilike ?" (same matches as lower()/lower()) so the pg_trgm indexes can be used.
        where.append('(' + ' or '.join(f'{c} like ?' if PG else f'lower({c}) like lower(?)' for c in SEARCH_COLS) + ')'); args += [f'%{term}%']*len(SEARCH_COLS)
    w = ' and '.join(where)
    rows = db().execute(f"select *, count(*) over() as _total from voter where {w} order by (case when coalesce(institution, '') = '' then 1 else 0 end), institution, cast(serial as integer), page, id limit ? offset ?", args+[size,(page-1)*size]).fetchall()
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
        JOBS[jid]['status'] = 'finished'; invalidate()
    except Exception as e:
        JOBS[jid].update(status='error', error=str(e)); invalidate()
    finally:
        os.remove(path)

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

@app.get('/')
def index(): return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'index.html')
@app.get('/static/<path:p>')
def st(p): return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), p)

init()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), threaded=True)
