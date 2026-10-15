import sqlite3,json,glob,sys
sys.path.insert(0,'app'); import app as A
c=sqlite3.connect(A.DB)
for tag,name in [('gbn','Gautam Buddha Nagar'),('gzb','Ghaziabad')]:
    cid=c.execute('select id from constituency where name=?',(name,)).fetchone()[0]
    c.execute('delete from voter where cid=?',(cid,))
    recs=[json.loads(l) for f in sorted(glob.glob(f'out/{tag}-*.jsonl')) for l in open(f)]
    A.insert(cid,recs,c); print(name,len(recs))
