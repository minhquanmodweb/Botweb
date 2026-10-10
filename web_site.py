"""Managed public content and signed, owner-bound 50-skin previews."""
import base64,hashlib,hmac,json,secrets,time,re
from pathlib import Path
from aiohttp import web
from notice_content import clean_html
from web_storage import read_json,update_json,persistent_storage

MANUAL_LIMIT=30
QUICK_LIMIT=50
DEFAULTS={'name':'TD MOD SKIN AOV','tagline':'YOUR SKIN. YOUR STYLE.',
 'nav_heroes':'CHỌN SKIN','nav_cart':'ĐÃ CHỌN','nav_history':'LỊCH SỬ','nav_settings':'CÀI ĐẶT',
 'picker_title':'CHỌN TƯỚNG','picker_subtitle':'Chạm chọn nhanh • tìm tướng hoặc skin tức thì',
 'quick_title':'Chọn nhanh','random_label':'50 Skin Random','hot_label':'50 Skin Hot Pick',
 'quick_note':'Mỗi tướng một skin · gói nhanh thay danh sách đang chọn. Xem lại trước khi tạo.',
 'cart_title':'ĐÃ CHỌN','cart_subtitle':'Kiểm tra skin và chọn đúng nền tảng trước khi tạo file',
 'settings_title':'TÙY CHỌN','settings_subtitle':'Chọn nền tảng bạn đang sử dụng',
 'platform_title':'Gói thiết bị','platform_note':'Chọn đúng máy để file nhẹ hơn',
 'bright_title':'Hiệu ứng sáng đậm','bright_note':'Tăng độ sáng cho hiệu ứng kỹ năng',
 'choice_title':'Chọn kiểu mod','choice_note':'Trong game, tải đầy đủ Cần thiết trong trận (100%) và Trải nghiệm đa dạng → Bối cảnh ngoại vi (100%) để hiện đầy đủ hiệu ứng.',
 'music_label':'Phát nhạc nền',
 'usage_title':'Cách sử dụng','usage_html':'<ol><li>Vào <strong>CHỌN SKIN</strong>, chọn skin trong giới hạn hiển thị hoặc dùng gói chọn nhanh.</li><li>Mở <strong>ĐÃ CHỌN</strong>, kiểm tra danh sách và chọn <strong>Android / iOS / Cả 2</strong>.</li><li>Bấm <strong>TẠO MOD</strong>, chọn có hoặc không có nút bấm + hạ địch, rồi bấm <strong>TẠO MOD</strong> bên dưới.</li><li>Đợi tạo xong, làm nhiệm vụ để mở tải ZIP. Xem lại trong <strong>LỊCH SỬ</strong>.</li></ol><p>Trong game, tải đủ <strong>Cần thiết trong trận (100%)</strong> và <strong>Trải nghiệm đa dạng → Bối cảnh ngoại vi (100%)</strong>. Thoát hẳn game trước khi chép file; thử đấu luyện trước khi chơi trận thường.</p>'}

class SiteSettings:
 def __init__(self,storage,catalog):
  self.root=Path(storage);self.catalog=catalog;self.path=self.root/'web_site.json'
  self.media=self.root/'site_media';self.media.mkdir(exist_ok=True)
  key=self.root/'quick_preview.key'
  if not key.exists():key.write_bytes(secrets.token_bytes(32))
  self.key=key.read_bytes()
  self.patch({})
 def default_hot(self):
  # Editorial starter pack, not a claim about live game popularity.
  priority=['Nakroth','Billow','Violet','Butterfly','Hayate','Airi','Murad','Lauriel','Tulen','Liliana','Yena','Florentino','Veres','Zata','Paine','Elsu','Raz','Capheny','Qi','Biron','Bolt Baron','Maloch','Gildur','Krixi','Điêu Thuyền','Yorn','Valhein','Allain','Ryoma','Wukong','Ngộ Không','Quillen','Zill','Dextra','Sinestrea','Keera','Aoi','Yan','Aya','Helen','Annette','Alice','Teeri','Erin','Tel’Annas','Tel\'Annas','Fennik','Slimz','Laville','Eland\'orr','Ishar','Natalya','Ilumia','Lữ Bố','Triệu Vân']
  heroes=list(dict.fromkeys(priority+list(self.catalog)))
  rows=[]
  for hero in heroes:
   if hero not in self.catalog or not self.catalog[hero]:continue
   entries=list(self.catalog[hero].items());name,sid=entries[-1]
   preferred={'Nakroth':'15015','Billow':'59906','Hayate':'13213'}
   name,sid=next(((n,s) for n,s in entries if s==preferred.get(hero)),(name,sid))
   rows.append({'tuong':hero,'skin':name,'id':sid})
   if len(rows)==QUICK_LIMIT:break
  return rows
 def validate(self,rows,count=None):
  if not isinstance(rows,list) or len(rows)!=(count if count is not None else min(QUICK_LIMIT,len(self.catalog))):raise ValueError('Số skin phải bằng số tướng của gói.')
  clean=[];seen=set()
  for row in rows:
   if not isinstance(row,dict):raise ValueError('Skin không hợp lệ.')
   hero,name,sid=row.get('tuong'),row.get('skin'),row.get('id')
   if not all(isinstance(v,str) for v in (hero,name,sid)) or hero in seen or self.catalog.get(hero,{}).get(name)!=sid:raise ValueError('Chọn skin có trong danh mục; mỗi tướng một skin.')
   seen.add(hero);clean.append({'tuong':hero,'skin':name,'id':sid})
  return clean
 def read(self):
  value=read_json(self.path);result={**DEFAULTS,**value}
  result.setdefault('manual_limit',MANUAL_LIMIT)
  result.setdefault('avatar','')
  result.setdefault('hot_picks',self.default_hot())
  result.setdefault('quick_packages',[{'id':'random','name':result['random_label'],'kind':'random','count':min(50,len(self.catalog)),'enabled':True,'selections':[],'revision':1},{'id':'hot','name':result['hot_label'],'kind':'fixed','count':len(result['hot_picks']),'enabled':True,'selections':result['hot_picks'],'revision':1}])
  return result
 def patch(self,data):
  def merge(value):
   for key,item in self.read().items():value.setdefault(key,item)
   value.update(data)
  update_json(self.path,merge)
  return self.read()
 def public(self):
  v=self.read();result={k:v[k] for k in DEFAULTS}
  avatar=v.get('avatar','')
  result.update(avatar_url='/api/site-media/'+avatar if avatar else None,manual_limit=v['manual_limit'],quick_limit=len(self.catalog),quick_packages=[{k:p[k] for k in ('id','name','kind','count')} for p in v['quick_packages'] if p['enabled']])
  return result
 def admin(self):
  return {**self.read(),'avatar_url':self.public()['avatar_url'],'hero_limit':len(self.catalog),'storage_persistent':persistent_storage(self.root)}
 def package(self,data):
  if not isinstance(data,dict):raise ValueError('Gói không hợp lệ.')
  name=data.get('name');count=data.get('count');kind=data.get('kind');enabled=data.get('enabled',True)
  if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('Tên gói cần từ 1 đến 120 ký tự.')
  if type(count)!=int or not 1<=count<=len(self.catalog):raise ValueError('Số tướng phải từ 1 đến '+str(len(self.catalog))+'.')
  if kind not in ('fixed','random') or type(enabled)!=bool:raise ValueError('Kiểu gói không hợp lệ.')
  return dict(name=name.strip(),count=count,kind=kind,enabled=enabled,selections=self.validate(data.get('selections'),count) if kind=='fixed' else [])
 def change_package(self,data,delete=False):
  ident=data.get('id');expected=data.get('revision')
  if ident is not None and (not isinstance(ident,str) or not re.fullmatch(r'[a-z0-9_-]{1,64}',ident)):raise ValueError('Mã gói không hợp lệ.')
  clean=None if delete else self.package(data)
  def change(value):
   packages=value.setdefault('quick_packages',self.read()['quick_packages'])
   old=next((p for p in packages if p['id']==ident),None)
   if ident and (not old or old['revision']!=expected):raise ValueError('Gói đã thay đổi. Tải lại danh sách trước khi sửa.')
   if delete:
    if not old:raise ValueError('Gói không tồn tại.')
    packages.remove(old)
   elif old:old.update(**clean,revision=old['revision']+1)
   else:packages.append(dict(id=secrets.token_hex(12),revision=1,**clean))
  update_json(self.path,change)
  return self.admin()
 def preview(self,mode,owner,package_id=None):
  ident=package_id if mode=='package' else mode
  package=next((p for p in self.read()['quick_packages'] if p['id']==ident and p['enabled']),None)
  if not package:raise ValueError('Gói không tồn tại hoặc đã tắt.')
  count=package['count']
  if package['kind']=='fixed':rows=self.validate(package['selections'],count)
  else:
   heroes=secrets.SystemRandom().sample([h for h,s in self.catalog.items() if s],count)
   rows=[{'tuong':h,'skin':n,'id':s} for h in heroes for n,s in [secrets.choice(list(self.catalog[h].items()))]]
  payload={'mode':mode,'package_id':ident,'revision':package['revision'],'owner':hashlib.sha256(owner.encode()).hexdigest(),'expires':int(time.time())+86400,'selections':rows}
  raw=base64.urlsafe_b64encode(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')
  return {k:payload[k] for k in ('mode','package_id','expires','selections')} | {'name':package['name'],'count':count,'token':raw+'.'+hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()}
 def resolve(self,token,mode,owner):
  try:
   if not isinstance(token,str) or len(token)>200000:raise ValueError()
   raw,sig=token.split('.')
   if not hmac.compare_digest(sig,hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()):raise ValueError()
   p=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
   if p['mode']!=mode or p['owner']!=hashlib.sha256(owner.encode()).hexdigest() or p['expires']<time.time():raise ValueError()
   package=next((x for x in self.read()['quick_packages'] if x['id']==p['package_id'] and x['enabled'] and x['revision']==p['revision']),None)
   if not package:raise ValueError()
   return self.validate(p['selections'],package['count'])
  except (ValueError,KeyError,TypeError):raise ValueError('Gói chọn nhanh đã thay đổi, hết hạn hoặc không hợp lệ. Hãy chọn lại gói.')

def setup_site(app,settings,authorized):
 def guard(request):
  if not authorized(request):raise web.HTTPUnauthorized(reason='Vui lòng đăng nhập admin.')
 async def public(request):return web.json_response(settings.public())
 async def preview(request):
  data=await request.json()
  try:return web.json_response(settings.preview(data.get('mode'),request['session'],data.get('package_id')))
  except (ValueError,AttributeError) as e:return web.json_response({'error':str(e)},status=400)
 async def admin(request):
  guard(request);value={}
  if request.method=='POST':
   data=await request.json()
   if not isinstance(data,dict):raise web.HTTPBadRequest()
   try:
    for key,default in DEFAULTS.items():
     if key not in data:continue
     v=data[key]
     limit=16000 if key=='usage_html' else 20 if key.startswith('nav_') else 250 if key.endswith(('note','subtitle')) else 120
     if not isinstance(v,str) or not v.strip() or len(v)>limit:raise ValueError('Nội dung '+key+' không hợp lệ hoặc quá dài.')
     value[key]=clean_html(v) if key=='usage_html' else v.strip()
    if 'hot_picks' in data:value['hot_picks']=settings.validate(data['hot_picks'])
    if 'manual_limit' in data:
     cap=data['manual_limit']
     if type(cap)!=int or not 1<=cap<=len(settings.catalog):raise ValueError('Giới hạn skin phải từ 1 đến '+str(len(settings.catalog))+'.')
     value['manual_limit']=cap
    if data.get('reset_avatar') is True:value['avatar']=''
   except ValueError as e:return web.json_response({'error':str(e)},status=400)
   settings.patch(value)
  return web.json_response(settings.admin())
 async def upload(request):
  guard(request);reader=await request.multipart();part=await reader.next()
  if part is None or part.name!='file':raise web.HTTPBadRequest(reason='Chọn ảnh avatar.')
  data=bytearray()
  while chunk:=await part.read_chunk():
   data.extend(chunk)
   if len(data)>3*1024*1024:raise web.HTTPRequestEntityTooLarge(max_size=3*1024*1024,actual_size=len(data))
  from PIL import Image
  import io
  try:
   im=Image.open(io.BytesIO(data));fmt=im.format
   if fmt not in ('JPEG','PNG','WEBP','GIF') or im.width*im.height>16000000:raise ValueError()
   im.verify()
  except Exception:raise web.HTTPBadRequest(reason='Ảnh không hợp lệ. Dùng JPG, PNG, WEBP hoặc GIF, tối đa 3 MB.')
  ext={'JPEG':'jpg','PNG':'png','WEBP':'webp','GIF':'gif'}[fmt];name=secrets.token_hex(16)+'.'+ext
  (settings.media/name).write_bytes(data);settings.patch({'avatar':name})
  return web.json_response({'avatar_url':settings.public()['avatar_url']})
 async def packages(request):
  guard(request)
  try:return web.json_response(settings.change_package(await request.json(),request.path.endswith('/delete')))
  except (ValueError,AttributeError) as e:return web.json_response({'error':str(e)},status=400)
 async def media(request):
  name=request.match_info['filename']
  if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|webp|gif)',name) or not (settings.media/name).is_file():raise web.HTTPNotFound()
  return web.FileResponse(settings.media/name)
 app.router.add_get('/api/site',public);app.router.add_post('/api/quick-picks',preview)
 app.router.add_get('/api/site-media/{filename}',media)
 app.router.add_get('/api/admin/notice/site',admin);app.router.add_post('/api/admin/notice/site',admin)
 app.router.add_post('/api/admin/notice/site/avatar',upload)

 app.router.add_post('/api/admin/notice/site/packages',packages)
 app.router.add_post('/api/admin/notice/site/packages/delete',packages)
