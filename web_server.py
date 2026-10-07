"""Standalone HTTP service; never imports or starts bot.py."""
import hashlib
import asyncio, json, os, secrets, shutil, sys, time, unicodedata, logging
from contextlib import suppress
from pathlib import Path
from aiohttp import web, ClientSession, ClientTimeout
from urllib.parse import urlsplit
from web_errors import public_failure
from web_notice import setup_notice
from web_admin_features import UsageStats, setup_admin_features
from web_site import SiteSettings,setup_site,MANUAL_LIMIT,QUICK_LIMIT

ROOT=Path(__file__).resolve().parent
STORE=Path(os.getenv('WEB_STORAGE_DIR',str(Path(os.environ['RAILWAY_VOLUME_MOUNT_PATH'])/'jobs') if os.getenv('RAILWAY_VOLUME_MOUNT_PATH') else str(ROOT/'WebJobs'))).resolve()
STORE.mkdir(parents=True,exist_ok=True)
CAT=json.loads((ROOT/'web_catalog.json').read_text())
FEATURES=json.loads((ROOT/'skin_features.json').read_text())
STATS=UsageStats(STORE/'web_usage.sqlite3')
SITE=SiteSettings(STORE,CAT)
JOBS={}
QUEUE=asyncio.Queue(maxsize=10)
TTL=max(3600,min(int(os.getenv("WEB_FILE_TTL", "86400")),604800))
MAX_TIME=int(os.getenv('WEB_JOB_TIMEOUT','900'))
SESSION_COOKIE='tdmod_web_session'
RETURN_TICKETS={}

def save_job(jid):
    job=JOBS[jid]
    data={k:v for k,v in job.items() if k not in ('folder','task_lock')}
    target=job['folder']/'meta.json'
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False))
    temporary.replace(target)
    STATS.job(jid,job)

def job_view(jid,job):
    expired=bool(job.get('expires') and time.time()>job['expires'])
    return {'id':jid,'state':'expired' if expired else job['state'],
        'percent':job['percent'],'message':job['message'],
        'platform':job['platform'],'cosmetics':job.get('cosmetics',False),'mode':job.get('mode','manual'),'created':job.get('created',0),
        'expires':job.get('expires'),'selections':job.get('selections',[]),
        'task_complete':job.get('task_complete',False),
        'size':(job['folder']/'result.zip').stat().st_size if (job['folder']/'result.zip').is_file() else 0}

def can_access(job,session):
    return job['owner']==session or session in job.get('access_sessions',[])

async def history(request):
    rows=[job_view(jid,j) for jid,j in JOBS.items() if can_access(j,request['session'])]
    return web.json_response({'jobs':sorted(rows,key=lambda j:j['created'],reverse=True)[:50]})

async def visit(request):
    STATS.visit(request['session']);return web.json_response({'ok':True})

async def avatar(request):
    return web.FileResponse(ROOT/'web_avatar.jpg')

def public_origin():
    value=os.getenv('WEB_PUBLIC_URL','').strip().rstrip('/')
    if not value and os.getenv('RAILWAY_PUBLIC_DOMAIN'):
        value='https://'+os.environ['RAILWAY_PUBLIC_DOMAIN']
    u=urlsplit(value)
    if u.scheme!='https' or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise RuntimeError('Cần đặt WEB_PUBLIC_URL là tên miền HTTPS của web.')
    return u.scheme+'://'+u.netloc

async def create_short_link(target):
    token=os.getenv('VUOTLINK_API','').strip()
    if not token:raise RuntimeError('Admin chưa cấu hình VUOTLINK_API cho nhiệm vụ.')
    async with ClientSession(timeout=ClientTimeout(total=30)) as client:
        async with client.get('https://vuotlink.xyz/api',params={'api':token,'url':target}) as response:
            if response.status!=200:raise RuntimeError('Dịch vụ nhiệm vụ đang lỗi. Vui lòng thử lại.')
            data=await response.json(content_type=None)
    link=data.get('shortenedUrl') if isinstance(data,dict) and data.get('status')=='success' else None
    u=urlsplit(link or '')
    if u.scheme!='https' or not u.netloc:raise RuntimeError('Dịch vụ nhiệm vụ chưa trả về link hợp lệ.')
    return link

def normal(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s.casefold().replace('đ','d')) if not unicodedata.combining(c))

def icon(sid):
    code=sid[:3]+sid[4] if len(sid)==5 and sid[3]=='0' else sid
    return f'https://dl.ops.kgvn.garenanow.com/hok/VN/HeroHeadPath/30{code}head.jpg'

def summary(name):
    skins=CAT[name]
    return {'name':name,'icon':icon(str(next(iter(skins.values())))[:3]+'00'),'skinCount':len(skins)}

def fail(text, status=400):
    return web.json_response({'error':text},status=status)

@web.middleware
async def headers(request,handler):
    # A same-site cookie owns each job; no public listing of download tokens.
    session=request.cookies.get(SESSION_COOKIE)
    if not session or len(session)!=48:
        session=secrets.token_hex(24)
    request['session']=session
    if request.method=='POST':
        origin=request.headers.get('Origin')
        if origin and origin not in ('https://'+request.host,'http://'+request.host):
            return fail('Yêu cầu khác nguồn không được phép.',403)
    try:
        response=await handler(request)
    except web.HTTPException as e:
        response=fail(e.reason,e.status)
    except Exception:
        logging.exception('HTTP request failed')
        response=fail('Có lỗi xử lý yêu cầu. Vui lòng thử lại.',500)
    if request.path.startswith('/assets/') and response.status in (200,304):
        response.headers['Cache-Control']='private, max-age=31536000' if request.query.get('v') else 'private, max-age=86400'
    elif request.path in ('/api/heroes','/api/hero-skins','/api/skins') and response.status==200:
        response.headers['Cache-Control']='private, max-age=60'
    else:
        response.headers['Cache-Control']='no-store'
    if isinstance(response,web.Response) and response.body and len(response.body)>1024:
        response.enable_compression()
    if request.path.startswith('/assets/') and response.status == 200:
        mime={'.woff2':'font/woff2','.webp':'image/webp','.png':'image/png'}
        content_type=mime.get(Path(request.path).suffix)
        if content_type:response.headers['Content-Type']=content_type
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    if request.cookies.get(SESSION_COOKIE)!=session:
        # Secure on Railway TLS termination or local HTTPS.
        secure=request.secure or request.headers.get('X-Forwarded-Proto')=='https'
        response.set_cookie(SESSION_COOKIE,session,httponly=True,samesite='Lax',secure=secure,max_age=30*86400)
    return response

async def index(request):
    if request.method=='GET':STATS.visit(request['session'])
    return web.Response(text=(ROOT/'web_index.html').read_text(),content_type='text/html',headers={'Cache-Control':'no-store'})

async def health(request):
    return web.json_response({'ok':True,'service':'TD MOD SKIN AOV','build':'2026-10-06-30-quick50-admin-v8','features':{'cosmetics':True,'notice_admin':True,'create_choice_dialog':True,'admin_stats':True,'background_music':True,'manual_limit':MANUAL_LIMIT,'quick_limit':QUICK_LIMIT,'site_settings':True,'job_details':True}})

async def heroes(request):
    items=[summary(n) for n in sorted(CAT,key=normal) if CAT[n]]
    return web.json_response({'heroes':items,'totalHeroes':len(items),'totalSkins':sum(len(x) for x in CAT.values())})

async def hero_skins(request):
    name=request.query.get('hero','')
    if name not in CAT:return fail('Không tìm thấy tướng.',404)
    return web.json_response({'name':name,'skins':[{'name':n,'id':sid,'icon':icon(sid),'icon_fallback':icon(sid).replace('head.jpg','.jpg'),'extras':FEATURES.get(sid,[])} for n,sid in CAT[name].items()]})

async def all_skins(request):
    items=[]
    for name in sorted(CAT,key=normal):
        h=summary(name)
        h['skins']=[{'name':n,'id':sid,'icon':icon(sid),'icon_fallback':icon(sid).replace('head.jpg','.jpg'),'extras':FEATURES.get(sid,[])} for n,sid in CAT[name].items()]
        items.append(h)
    return web.json_response({'heroes':items,'totalHeroes':len(items),'totalSkins':sum(len(x) for x in CAT.values())})

async def search(request):
    q=normal(request.query.get('q','')[:100])
    return web.json_response({'heroes':[summary(n) for n in sorted(CAT,key=normal) if q and (q in normal(n) or any(q in normal(s) for s in CAT[n]))][:30]})

async def create_job(request):
    session=request['session']
    if any(j['owner']==session and j['state'] in ('queued','running') for j in JOBS.values()):
        return fail('Bạn đang có file chờ xử lý. Hãy đợi hoàn tất.',429)
    active_jobs=sum(j['state'] in ('queued','running') for j in JOBS.values())
    if active_jobs>=200 or QUEUE.full():return fail('Hàng chờ đã đầy. Thử lại sau ít phút.',429)
    try:data=await request.json()
    except Exception:return fail('Dữ liệu không hợp lệ.')
    if not isinstance(data,dict):return fail('Dữ liệu không hợp lệ.')
    if type(data.get('cosmetics',False)) is not bool:return fail('Lựa chọn nút và thông báo hạ không hợp lệ.')
    selected=data.get('selections')
    platform=data.get('platform')
    if platform not in ('android','ios','both'):return fail('Thiết bị không hợp lệ.')
    mode=data.get('mode','manual')
    if mode not in ('manual','random','hot'):return fail('Kiểu chọn skin không hợp lệ.')
    if mode!='manual':
        try:preview=SITE.resolve(data.get('quick_token'),mode,session)
        except ValueError as e:return fail(str(e))
        if selected!=preview:return fail('Danh sách gói đã thay đổi. Hãy chọn lại gói nhanh.')
    limit=MANUAL_LIMIT if mode=='manual' else QUICK_LIMIT
    if not isinstance(selected,list) or not 1<=len(selected)<=limit:return fail('Chọn từ 1 đến 30 skin, hoặc dùng gói chọn nhanh 50 skin.')
    seen=set();clean=[]
    for x in selected:
        if not isinstance(x,dict):return fail('Skin không hợp lệ.')
        hero=x.get('tuong');skin=x.get('skin');sid=x.get('id')
        if not isinstance(hero,str) or not isinstance(skin,str) or not isinstance(sid,str):return fail('Skin không hợp lệ.')
        if hero in seen or CAT.get(hero,{}).get(skin)!=sid:return fail('Chọn đúng skin trong danh sách, mỗi tướng 1 skin.')
        seen.add(hero);clean.append({'tuong':hero,'skin':skin,'id':sid})
    jid=secrets.token_hex(24)
    folder=STORE/jid;folder.mkdir()
    (folder/'request.json').write_text(json.dumps({'selections':clean,'mode':mode,'platform':platform,'bright':data.get('bright') is True,'cosmetics':data.get('cosmetics',False)},ensure_ascii=False))
    JOBS[jid]={'owner':session,'state':'queued','percent':0,'message':'Đang chờ xử lý…','folder':folder,'platform':platform,'cosmetics':data.get('cosmetics',False),'expires':None,'task_complete':False,'task_link':None,'task_lock':asyncio.Lock(),'created':time.time(),'mode':mode,'bright':data.get('bright') is True,'selections':clean}
    save_job(jid)
    QUEUE.put_nowait(jid)
    return web.json_response({'id':jid},status=202)

def owned(request):
    job=JOBS.get(request.match_info['id'])
    if not job or not can_access(job,request['session']):raise web.HTTPNotFound()
    return job

async def status(request):
    job=owned(request)
    p=job['folder']/'progress.json'
    if job['state']=='running' and p.exists():
        with suppress(ValueError,OSError):
            d=json.loads(p.read_text());job['percent']=d['percent'];job['message']=d['message']
    return web.json_response(job_view(request.match_info['id'],job))

async def download(request):
    job=owned(request)
    if job['state']!='done':return fail('File chưa sẵn sàng.',409)
    if time.time()>job['expires']:return fail('Link tải đã hết hạn.',410)
    if not job.get('task_complete'):return fail('Bạn cần hoàn thành nhiệm vụ trước khi tải file.',403)
    if not (job['folder']/'result.zip').is_file():return fail('File không còn trên máy chủ.',410)
    if request.method=='GET':STATS.event('download',hashlib.sha256((request.match_info['id']+':'+request['session']).encode()).hexdigest())
    job['downloaded']=True;save_job(request.match_info['id'])
    response=web.FileResponse(job['folder']/'result.zip')
    response.headers['Content-Type']='application/zip'
    response.headers['Content-Disposition']=f'attachment; filename="TD-MOD-{job["platform"]}.zip"'
    return response

async def task_link(request):
    job=owned(request)
    if job['state']!='done':return fail('File chưa sẵn sàng.',409)
    if time.time()>job['expires']:return fail('Lượt tạo đã hết hạn. Hãy tạo lại file.',410)
    if job.get('task_complete'):return web.json_response({'complete':True})
    async with job['task_lock']:
        if not job.get('task_link'):
            ticket=secrets.token_urlsafe(32)
            try:
                target=public_origin()+'/task/complete/'+ticket
                link=await create_short_link(target)
            except RuntimeError as e:return fail(str(e),503)
            except Exception:return fail('Không kết nối được dịch vụ nhiệm vụ. Thử lại sau.',503)
            RETURN_TICKETS[ticket]=request.match_info['id']
            job['task_link']=link
            job['ticket']=ticket
            save_job(request.match_info['id'])
        return web.json_response({'url':job['task_link']})

def task_error(message,status):
    # Fixed messages only; no tokens or request text are reflected into HTML.
    page='<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nhiệm vụ · TD MOD SKIN AOV</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#080e1b;color:#eef6ff;font:15px system-ui}main{max-width:420px;margin:20px;padding:28px;background:linear-gradient(135deg,#142d40,#1d2038);border:1px solid #59e4ff44;border-radius:24px}small{color:#6ee5ff;letter-spacing:.1em}h1{font-size:24px}p{color:#a9bad1;line-height:1.7}a{display:block;text-align:center;padding:15px;border-radius:14px;background:#81d9fa;color:#0c1628;text-decoration:none;font-weight:750}</style><main><small>TD MOD SKIN AOV</small><h1>Chưa mở được file</h1><p>MESSAGE</p><a href="/">Về web · Xem lịch sử</a><p>Mở Lịch sử để kiểm tra lượt tạo. Nếu file không còn, hãy tạo lại. Link cũ từ trước khi cập nhật có thể không khôi phục được.</p></main></html>'
    return web.Response(text=page.replace('MESSAGE',message),content_type='text/html',status=status)

async def task_complete(request):
    ticket=request.match_info['ticket']
    jid=RETURN_TICKETS.get(ticket)
    job=JOBS.get(jid) if jid else None
    if not job:return task_error('Link nhiệm vụ không còn hiệu lực. File có thể đã hết hạn hoặc dữ liệu bị mất khi máy chủ deploy lại.',404)
    if job['state']!='done' or not job.get('expires') or time.time()>job['expires']:
        return task_error('File đã hết hạn hoặc chưa tạo xong. Vui lòng quay lại web để tạo file mới.',410)
    if not (job['folder']/'result.zip').is_file():
        return task_error('File không còn trên máy chủ. Vui lòng tạo lại file.',410)
    # The unpredictable ticket delivered only through the shortener is a bearer
    # receipt. It grants this browser access while keeping the original owner.
    # No user account is being authenticated or moved between browsers.
    session=request['session']
    if not can_access(job,session):
        grants=job.setdefault('access_sessions',[])
        grants.append(session);job['access_sessions']=grants[-5:]
    job['task_complete']=True
    save_job(jid)
    return web.Response(status=303,headers={'Location':'/?job='+jid+'&from_task=1'})

async def queue_worker(app):
    while True:
        jid=await QUEUE.get();job=JOBS[jid];process=None
        try:
            folder=job['folder']
            # Private job working directory; bundled input resources are read only.
            for name in ('Data','Resources_1'):
                (folder/name).symlink_to(ROOT/name,target_is_directory=True)
            job.update(state='running',started=time.time(),message='Đang chuẩn bị tạo file…')
            save_job(jid)
            env=os.environ.copy()
            for name in ('BOT_TOKEN','VUOTLINK_API','WEBAPP_URL','WEB_ADMIN_PASSWORD'):env.pop(name,None)
            with (folder/'worker.log').open('wb') as log:
                process=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'web_worker.py'),str(folder),cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
                try:await asyncio.wait_for(process.wait(),MAX_TIME)
                except asyncio.TimeoutError:
                    process.kill();await process.wait();job['error_code']='TIMEOUT';raise RuntimeError('Quá thời gian xử lý.')
            if process.returncode or not (folder/'result.zip').is_file():raise RuntimeError('Worker failed')
            job.update(state='done',generation_state='done',size=(folder/'result.zip').stat().st_size,finished=time.time(),percent=100,message='Đã tạo file · Hoàn thành nhiệm vụ để tải',expires=time.time()+TTL)
        except asyncio.CancelledError:
            if process and process.returncode is None:
                process.kill();await process.wait()
            raise
        except Exception:
            logging.exception('Job %s failed; inspect WebJobs/%s/worker.log',jid,jid)
            job.update(state='error',generation_state='error',finished=time.time(),message=('Quá thời gian xử lý. Thử gói ít skin hơn.' if job.get('error_code')=='TIMEOUT' else public_failure(folder,job.get('selections',[]),process.returncode if process else None)),expires=time.time()+TTL)
        finally:
            save_job(jid)
            QUEUE.task_done()

async def cleaner():
    while True:
        await asyncio.sleep(30)
        for jid,j in list(JOBS.items()):
            if j['expires'] and j['expires']<time.time():
                shutil.rmtree(j['folder'],ignore_errors=True);JOBS.pop(jid,None)
                for ticket,target in list(RETURN_TICKETS.items()):
                    if target==jid:RETURN_TICKETS.pop(ticket,None)

async def lifecycle(app):
    for folder in STORE.iterdir():
        if not folder.is_dir() or len(folder.name)!=48 or any(c not in '0123456789abcdef' for c in folder.name):continue
        try:
            j=json.loads((folder/'meta.json').read_text())
            if j.get('state') in ('done','error'):j.setdefault('generation_state',j['state'])
            STATS.job(folder.name,{**j,'folder':folder})
            if j.get('expires') and j['expires']<time.time():
                shutil.rmtree(folder,ignore_errors=True);continue
            j.update(folder=folder,task_lock=asyncio.Lock())
            if j['state'] in ('queued','running'):
                j.update(state='error',generation_state='error',error_code='SERVER_RESTART',finished=time.time(),message='Máy chủ đã khởi động lại khi đang tạo file. Vui lòng tạo lại.',expires=time.time()+TTL)
            if j['state']=='done' and not (folder/'result.zip').is_file():
                j.update(state='error',message='File không còn trên máy chủ.',expires=time.time()+TTL)
            JOBS[folder.name]=j
            if j.get('ticket'):RETURN_TICKETS[j['ticket']]=folder.name
            save_job(folder.name)
        except (OSError,ValueError,KeyError):
            logging.warning('Cannot restore job %s',folder.name)
    tasks=[asyncio.create_task(queue_worker(app)),asyncio.create_task(cleaner())]
    yield
    for t in tasks:t.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)

def make_app():
    app=web.Application(middlewares=[headers],client_max_size=26*1024*1024)
    authorized=setup_notice(app, STORE)
    setup_admin_features(app,STORE,authorized,STATS,lambda:JOBS)
    setup_site(app,SITE,authorized)
    app.router.add_post('/api/visit',visit)
    app.router.add_get('/',index)
    app.router.add_get('/health',health)
    app.router.add_get('/web-avatar.jpg',avatar)
    app.router.add_static('/assets/',ROOT/'assets',show_index=False)
    app.router.add_get('/api/jobs',history)
    for path,fn in [('heroes',heroes),('hero-skins',hero_skins),('search',search),('skins',all_skins)]:app.router.add_get('/api/'+path,fn)
    app.router.add_post('/api/jobs',create_job)
    app.router.add_get('/api/jobs/{id}',status)
    app.router.add_get('/api/jobs/{id}/download',download)
    app.router.add_post('/api/jobs/{id}/task',task_link)
    app.router.add_get('/task/complete/{ticket}',task_complete)
    app.cleanup_ctx.append(lifecycle)
    return app

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(make_app(),host='0.0.0.0',port=int(os.getenv('PORT','8080')))
