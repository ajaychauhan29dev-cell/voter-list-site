# Load OCR output (out/*.jsonl) into DATABASE_URL (Postgres) or local SQLite.
import json,glob,sys
sys.path.insert(0,'app'); import app as A
c=A.connect()
for tag,name in [('gbn','Gautam Buddha Nagar'),('gzb','Ghaziabad')]:
    cid=c.execute('select id from constituency where name=?',(name,)).fetchone()['id']
    c.execute('delete from voter where cid=?',(cid,))
    recs=[json.loads(l) for f in sorted(glob.glob(f'out/{tag}-*.jsonl')) for l in open(f)]
    A.insert(cid,recs,c); print(name,len(recs))
c.close()
