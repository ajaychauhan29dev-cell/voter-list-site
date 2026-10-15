import os, sqlite3, secrets, threading, json, sys, tempfile, time, hmac
from flask import Flask, request, jsonify, g, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.environ.get('DB', os.path.join(os.path.dirname(__file__), 'voters.db'))
USER = 'kuldeep-malik@mlc.com'
PW_HASH = generate_password_hash('kuldeep123')
FIELDS = ['serial','name','relative_name','relation','address','gender','dob','institution','c9','c10','state','pincode','page']
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 400*1024*1024
SESSIONS = {}  # token -> expiry
JOBS = {}

PG = os.environ.get('DATABASE_URL')
class Conn:
    def __init__(self):
        if PG:
            import psycopg
            from psycopg.rows import dict_row
            self.c = psycopg.connect(PG, row_factory=dict_row)
        else:
            self.c = sqlite3.connect(DB); self.c.row_factory = lambda cur, row: {d[0]: row[i] for i, d in enumerate(cur.description)}
    def q(self, sql):
        if PG: sql = sql.replace('?', '%s').replace(' like ', ' ilike ').replace('insert or ignore', 'insert')
        return sql
    def execute(self, sql, args=()):
        cur = self.c.cursor(); cur.execute(self.q(sql), args); return cur
    def executemany(self, sql, rows):
        cur = self.c.cursor(); cur.executemany(self.q(sql), rows); return cur
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()
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
    for n in ['Gautam Buddha Nagar', 'Ghaziabad']:
        c.execute('insert or ignore into constituency(name) values(?)' + (' on conflict do nothing' if PG else ''), (n,))
    c.commit(); c.close()

def authed():
    t = request.cookies.get('sid'); exp = SESSIONS.get(t)
    return bool(t and exp and exp > time.time())
@app.before_request
def guard():
    if request.path.startswith('/api/') and request.path != '/api/login' and not authed():
        return jsonify(error='unauthorized'), 401

@app.post('/api/login')
def login():
    d = request.get_json(force=True, silent=True) or {}
    ok = hmac.compare_digest((d.get('id') or '').strip().lower(), USER) and check_password_hash(PW_HASH, d.get('password') or '')
    if not ok:
        time.sleep(1); return jsonify(error='Invalid ID or password'), 401
    t = secrets.token_urlsafe(32); SESSIONS[t] = time.time() + 12*3600
    r = make_response(jsonify(ok=True))
    r.set_cookie('sid', t, httponly=True, samesite='Lax', secure=request.headers.get('X-Forwarded-Proto','http')=='https' or request.is_secure, max_age=12*3600)
    return r
@app.post('/api/logout')
def logout():
    SESSIONS.pop(request.cookies.get('sid'), None)
    r = make_response(jsonify(ok=True)); r.delete_cookie('sid'); return r
@app.get('/api/me')
def me(): return jsonify(user=USER)

@app.get('/api/constituencies')
def consts():
    rows = db().execute('select c.id, c.name, count(v.id) n from constituency c left join voter v on v.cid=c.id group by c.id, c.name order by c.id').fetchall()
    return jsonify(rows)
@app.post('/api/constituencies')
def add_const():
    name = ((request.get_json(force=True, silent=True) or {}).get('name') or '').strip()
    if not name: return jsonify(error='Name required'), 400
    if db().execute('select 1 from constituency where lower(name)=lower(?)', (name,)).fetchone():
        return jsonify(error='Already exists'), 400
    db().execute('insert into constituency(name) values(?)', (name,)); db().commit()
    return jsonify(ok=True)

@app.get('/api/constituencies/<int:cid>/institutions')
def insts(cid):
    rows = db().execute("select institution, count(*) n from voter where cid=? and institution<>'' group by institution order by institution", (cid,)).fetchall()
    return jsonify(rows)

@app.get('/api/constituencies/<int:cid>/voters')
def voters(cid):
    q = (request.args.get('q') or '').strip(); inst = request.args.get('institution')
    page = max(1, int(request.args.get('page', 1))); size = min(500, int(request.args.get('size', 50)))
    where = ['cid=?']; args = [cid]
    if inst: where.append('institution=?'); args.append(inst)
    for term in q.split():
        cols = ['name','relative_name','relation','address','gender','dob','institution','serial','pincode','state']
        where.append('(' + ' or '.join(f'{c} like ?' for c in cols) + ')'); args += [f'%{term}%']*len(cols)
    w = ' and '.join(where)
    total = db().execute(f'select count(*) n from voter where {w}', args).fetchone()['n']
    rows = db().execute(f'select * from voter where {w} order by institution, cast(serial as integer) limit ? offset ?', args+[size,(page-1)*size]).fetchall()
    return jsonify(total=total, page=page, size=size, rows=rows)

def insert(cid, recs, conn=None):
    c = conn or connect()
    c.executemany(f'insert into voter(cid,{",".join(FIELDS)}) values(?,{",".join("?"*len(FIELDS))})',
                  [[cid]+[r.get(f,'') for f in FIELDS] for r in recs])
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
            JOBS[jid]['done'] = p; JOBS[jid]['added'] += len(recs)
        JOBS[jid]['status'] = 'finished'
    except Exception as e:
        JOBS[jid].update(status='error', error=str(e))
    finally:
        os.remove(path)

@app.post('/api/constituencies/<int:cid>/upload')
def upload(cid):
    f = request.files.get('file')
    if not f or not f.filename.lower().endswith('.pdf'): return jsonify(error='Please upload a PDF'), 400
    fd, path = tempfile.mkstemp(suffix='.pdf'); os.close(fd); f.save(path)
    if request.form.get('replace') == '1':
        db().execute('delete from voter where cid=?', (cid,)); db().commit()
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
