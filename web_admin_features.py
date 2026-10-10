from web_storage import read_json,update_json
"""Persistent usage counters and opt-in music for the standalone web app."""
import hashlib,json,logging,re,secrets,sqlite3,time,wave,io
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from aiohttp import web

VN=timezone(timedelta(hours=7))
def day(ts=None):return datetime.fromtimestamp(time.time() if ts is None else ts,VN).date().isoformat()
class UsageStats:
    def __init__(self,path):
        self.path=Path(path)
        self.started=time.time()
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS info(key TEXT PRIMARY KEY,value REAL);
            CREATE TABLE IF NOT EXISTS visitors(id TEXT PRIMARY KEY,first_seen REAL,last_seen REAL);
            CREATE TABLE IF NOT EXISTS visits(day TEXT,id TEXT,PRIMARY KEY(day,id));
            CREATE TABLE IF NOT EXISTS events(kind TEXT,id TEXT,day TEXT,PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS job_details(id TEXT PRIMARY KEY,created REAL,day TEXT,state TEXT,platform TEXT,mode TEXT,visitor TEXT,detail TEXT);
            CREATE INDEX IF NOT EXISTS job_details_created ON job_details(created DESC);''')
            c.execute('INSERT OR IGNORE INTO info VALUES(?,?)',('started',self.started))
    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.path,timeout=0.5)
        try:
            with connection:yield connection
        finally:connection.close()
    def visit(self,session):
        now=time.time();sid=hashlib.sha256(session.encode()).hexdigest()
        try:
            with self.connect() as c:
                c.execute('INSERT INTO visitors VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen',(sid,now,now))
                c.execute('INSERT OR IGNORE INTO visits VALUES(?,?)',(day(now),sid))
        except sqlite3.Error:logging.exception('Cannot record web visit')
    def event(self,kind,identifier,ts=None):
        try:
            with self.connect() as c:c.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(kind,identifier,day(ts)))
        except sqlite3.Error:logging.exception('Cannot record web event')
    def job(self,jid,job):
        self.event('created',jid,job.get('created'))
        outcome=job.get('generation_state') or job.get('state')
        if outcome in ('done','error'):self.event(outcome,jid,job.get('finished') or job.get('created'))
        if job.get('task_complete'):self.event('unlocked',jid,job.get('finished') or job.get('created'))
        folder=Path(job.get('folder') or '.')
        size=job.get('size',0)
        if (folder/'result.zip').is_file():size=(folder/'result.zip').stat().st_size
        try:failure=json.loads((folder/'failure.json').read_text())
        except (OSError,ValueError):failure={}
        detail={k:job.get(k) for k in ('created','finished','started','state','generation_state','platform','mode','bright','cosmetics','selections','message','expires','task_complete','error_code','downloaded')}
        detail.update(id=jid,size=size,skin_count=len(job.get('selections',[])),error_code=job.get('error_code') or failure.get('code'),error_skin=failure.get('skin_id'),error_module=failure.get('module'),error_exception=failure.get('exception'))
        if outcome=='error' and not detail.get('error_code'):detail['error_code']='UNKNOWN'
        if not detail.get('mode'):detail['mode']='manual'
        detail['visitor']=hashlib.sha256(str(job.get('owner','')).encode()).hexdigest()
        detail['duration']=max(0,job['finished']-job['started']) if job.get('started') and job.get('finished') else None
        try:
            with self.connect() as c:c.execute('INSERT INTO job_details VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,detail=excluded.detail',(jid,detail['created'],day(detail['created']),outcome,detail['platform'],detail['mode'],detail['visitor'],json.dumps(detail,ensure_ascii=False)))
        except sqlite3.Error:logging.exception('Cannot record job details')
    def details(self,query):
        clauses=[];values=[]
        for key in ('state','platform','mode','day','visitor'):
            value=query.get(key,'')
            if value:clauses.append(key+'=?');values.append(value)
        q=query.get('q','')[:100]
        if q:clauses.append('(id LIKE ? OR detail LIKE ?)');values.extend(['%'+q+'%']*2)
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        try:page=max(1,min(100000,int(query.get('page',1))))
        except (ValueError,TypeError):page=1
        with self.connect() as c:
            count=c.execute('SELECT COUNT(*) FROM job_details'+where,values).fetchone()[0]
            rows=c.execute('SELECT detail FROM job_details'+where+' ORDER BY created DESC LIMIT 20 OFFSET ?',values+[(page-1)*20]).fetchall()
        return {'items':[json.loads(r[0]) for r in rows],'total':count,'page':page,'pages':max(1,(count+19)//20)}
    def detail(self,jid):
        with self.connect() as c:row=c.execute('SELECT detail FROM job_details WHERE id=?',(jid,)).fetchone()
        return json.loads(row[0]) if row else None
    def users(self,query):
        try:page=max(1,min(100000,int(query.get('page',1))))
        except (ValueError,TypeError):page=1
        online=query.get('online')=='1'
        cutoff=time.time()-90
        where=' WHERE v.last_seen>?' if online else ''
        parameters=[cutoff] if online else []
        with self.connect() as c:
            total=c.execute('SELECT COUNT(*) FROM visitors v'+where,parameters).fetchone()[0]
            rows=c.execute('SELECT v.id,v.first_seen,v.last_seen,COUNT(DISTINCT j.id),COUNT(DISTINCT t.day) FROM visitors v LEFT JOIN job_details j ON j.visitor=v.id LEFT JOIN visits t ON t.id=v.id'+where+' GROUP BY v.id ORDER BY v.last_seen DESC LIMIT 20 OFFSET ?',parameters+[(page-1)*20]).fetchall()
        return {'items':[dict(zip(('id','first_seen','last_seen','jobs','days'),r)) for r in rows],'total':total,'page':page,'pages':max(1,(total+19)//20)}
    def snapshot(self,jobs):
        with self.connect() as c:
            visitors=c.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
            today_visitors=c.execute('SELECT COUNT(*) FROM visits WHERE day=?',(day(),)).fetchone()[0]
            started=c.execute('SELECT value FROM info WHERE key=?',('started',)).fetchone()[0]
            totals=dict(c.execute('SELECT kind,COUNT(*) FROM events GROUP BY kind'))
            today=dict(c.execute('SELECT kind,COUNT(*) FROM events WHERE day=? GROUP BY kind',(day(),)))
            dates=[day(time.time()-i*86400) for i in range(6,-1,-1)]
            daily=[]
            for d in dates:
                row=dict(c.execute('SELECT kind,COUNT(*) FROM events WHERE day=? GROUP BY kind',(d,)))
                daily.append({'date':d,'visitors':c.execute('SELECT COUNT(*) FROM visits WHERE day=?',(d,)).fetchone()[0],**{k:row.get(k,0) for k in ('created','done','error','download','unlocked')}})
        with self.connect() as c:
            records=[json.loads(row[0]) for row in c.execute('SELECT detail FROM job_details')]
            online=c.execute('SELECT COUNT(*) FROM visitors WHERE last_seen>?',(time.time()-90,)).fetchone()[0]
        complete=[r for r in records if (r.get('generation_state') or r['state'])=='done']
        durations=[r['duration'] for r in complete if r.get('duration') is not None]
        from collections import Counter
        skins=Counter(s['tuong']+' · '+s['skin'] for r in records for s in (r.get('selections') or []))
        extra={'online':online,'details_count':len(records),'success_rate':round(100*totals.get('done',0)/max(1,totals.get('done',0)+totals.get('error',0)),1),'average_seconds':round(sum(durations)/len(durations),1) if durations else None,'output_bytes':sum(r.get('size',0) for r in complete),'skin_total':sum(r['skin_count'] for r in records),'platforms':dict(Counter(r['platform'] for r in records)),'modes':dict(Counter(r.get('mode') or 'manual' for r in records)),'error_codes':dict(Counter(r.get('error_code') or 'UNKNOWN' for r in records if (r.get('generation_state') or r['state'])=='error')),'top_skins':[{'name':name,'count':count} for name,count in skins.most_common(8)]}
        return {**extra,'started':started,'today':day(),'total':{'visitors':visitors,**{k:totals.get(k,0) for k in ('created','done','error','download','unlocked')}},'today_counts':{'visitors':today_visitors,**{k:today.get(k,0) for k in ('created','done','error','download','unlocked')}},'queued':sum(j['state']=='queued' for j in jobs.values()),'running':sum(j['state']=='running' for j in jobs.values()),'daily':daily}

def valid_audio(data,suffix):
    if suffix=='.wav':
        try:
            with wave.open(io.BytesIO(data)) as f:return f.getnframes()>0 and f.getnchannels() in (1,2)
        except (wave.Error,EOFError):return False
    if suffix=='.ogg':return data.startswith(b'OggS') and (b'vorbis' in data[:512] or b'OpusHead' in data[:512])
    if suffix=='.mp3':
        offset=0
        if data.startswith(b'ID3'):
            if len(data)<10 or any(v&128 for v in data[6:10]):return False
            offset=10+sum(v<<(7*(3-i)) for i,v in enumerate(data[6:10]))
        for i in range(offset,min(len(data)-3,offset+4096)):
            a,b,c=data[i:i+3]
            if a==255 and b&224==224 and b&24!=8 and b&6 and c>>4 not in (0,15) and c&12!=12:return True
    return False

def setup_admin_features(app,storage,authorized,stats,jobs):
    folder=Path(storage)/'music_media';folder.mkdir(exist_ok=True)
    config=Path(storage)/'web_music.json'
    def read():
        if not config.exists():return {'enabled':False,'title':'Nhạc nền','file':None}
        value=read_json(config)
        if not re.fullmatch(r'[a-f0-9]{32}\.(mp3|wav|ogg)',value.get('file') or '') or not (folder/value['file']).is_file():value.update(enabled=False,file=None)
        return value
    def save(value):
        update_json(config,lambda current:current.update(value))
    def public_value(value):return {'enabled':value['enabled'],'title':value['title'],'url':'/api/music-media/'+value['file'] if value.get('file') else None}
    async def public(request):return web.json_response(public_value(read()),headers={'Cache-Control':'no-store'})
    async def media(request):
        name=request.match_info['filename']
        if not re.fullmatch(r'[a-f0-9]{32}\.(mp3|wav|ogg)',name) or not (folder/name).is_file():raise web.HTTPNotFound()
        response=web.FileResponse(folder/name);response.headers['Content-Type']={'.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg'}[Path(name).suffix];return response
    async def dashboard(request):
        if not authorized(request):return web.json_response({'error':'Vui lòng đăng nhập admin.'},status=401)
        return web.json_response(stats.snapshot(jobs()),headers={'Cache-Control':'no-store'})
    async def settings(request):
        if not authorized(request):return web.json_response({'error':'Vui lòng đăng nhập admin.'},status=401)
        value=read()
        if request.method=='POST':
            data=await request.json()
            if not isinstance(data,dict) or type(data.get('enabled')) is not bool or not isinstance(data.get('title'),str) or not 1<=len(data['title'].strip())<=120:return web.json_response({'error':'Tiêu đề 1–120 ký tự và trạng thái hợp lệ.'},status=400)
            if data['enabled'] and not value.get('file'):return web.json_response({'error':'Tải nhạc lên trước khi bật.'},status=400)
            save({'enabled':data['enabled'],'title':data['title'].strip()});value=read()
        return web.json_response(public_value(value))
    async def upload(request):
        if not authorized(request):return web.json_response({'error':'Vui lòng đăng nhập admin.'},status=401)
        reader=await request.multipart();part=await reader.next()
        if part is None or part.name!='file':return web.json_response({'error':'Chọn file nhạc.'},status=400)
        suffix=Path(part.filename or '').suffix.lower()
        if suffix not in ('.mp3','.wav','.ogg'):return web.json_response({'error':'Hỗ trợ MP3, WAV hoặc OGG.'},status=400)
        data=bytearray()
        while chunk:=await part.read_chunk():
            data.extend(chunk)
            if len(data)>25*1024*1024:return web.json_response({'error':'Nhạc tối đa 25 MB.'},status=413)
        if not valid_audio(bytes(data),suffix):return web.json_response({'error':'File nhạc không hợp lệ.'},status=400)
        value=read();old=value.get('file');name=secrets.token_hex(16)+suffix
        (folder/name).write_bytes(data)
        save({'file':name,'title':Path(part.filename).stem[:120] or 'Nhạc nền','enabled':True});value=read()
        if old and old!=name:(folder/old).unlink(missing_ok=True)
        return web.json_response(public_value(value))
    async def job_list(request):
        if not authorized(request):raise web.HTTPUnauthorized()
        return web.json_response(stats.details(request.query))
    async def job_detail(request):
        if not authorized(request):raise web.HTTPUnauthorized()
        result=stats.detail(request.match_info['id'])
        if not result:raise web.HTTPNotFound(reason='Không có hồ sơ chi tiết cho lượt tạo này.')
        result['file_available']=bool(result['id'] in jobs() and (jobs()[result['id']]['folder']/'result.zip').is_file() and (not result.get('expires') or result['expires']>time.time()))
        return web.json_response(result)
    async def user_list(request):
        if not authorized(request):raise web.HTTPUnauthorized()
        return web.json_response(stats.users(request.query))
    app.router.add_get('/api/admin/notice/jobs',job_list)
    app.router.add_get('/api/admin/notice/jobs/{id}',job_detail)
    app.router.add_get('/api/admin/notice/users',user_list)
    app.router.add_get('/api/music',public)
    app.router.add_get('/api/music-media/{filename}',media)
    app.router.add_get('/api/admin/notice/stats',dashboard)
    app.router.add_get('/api/admin/notice/music',settings)
    app.router.add_post('/api/admin/notice/music',settings)
    app.router.add_post('/api/admin/notice/music/upload',upload)
