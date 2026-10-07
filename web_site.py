"""Managed public content and signed, owner-bound 50-skin previews."""
import base64,hashlib,hmac,json,secrets,time,re
from pathlib import Path
from aiohttp import web
from notice_content import clean_html

MANUAL_LIMIT=30
QUICK_LIMIT=50
DEFAULTS={'name':'TD MOD SKIN AOV','tagline':'YOUR SKIN. YOUR STYLE.',
 'nav_heroes':'CHỌN SKIN','nav_cart':'ĐÃ CHỌN','nav_history':'LỊCH SỬ','nav_settings':'CÀI ĐẶT',
 'picker_title':'CHỌN TƯỚNG','picker_subtitle':'Chạm chọn nhanh • tìm tướng hoặc skin tức thì',
 'quick_title':'Chọn nhanh','random_label':'50 Skin Random','hot_label':'50 Skin Hot Pick',
 'quick_note':'50 tướng khác nhau · thay danh sách đang chọn. Xem lại trước khi tạo; Hot Pick do admin chọn.',
 'cart_title':'ĐÃ CHỌN','cart_subtitle':'Kiểm tra skin và chọn đúng nền tảng trước khi tạo file',
 'settings_title':'TÙY CHỌN','settings_subtitle':'Chọn nền tảng bạn đang sử dụng',
 'platform_title':'Gói thiết bị','platform_note':'Chọn đúng máy để file nhẹ hơn',
 'bright_title':'Hiệu ứng sáng đậm','bright_note':'Tăng độ sáng cho hiệu ứng kỹ năng',
 'choice_title':'Chọn kiểu mod','choice_note':'Trong game, tải đầy đủ Cần thiết trong trận (100%) và Trải nghiệm đa dạng → Bối cảnh ngoại vi (100%) để hiện đầy đủ hiệu ứng.',
 'music_label':'Phát nhạc nền',
 'usage_title':'Cách sử dụng','usage_html':'<ol><li>Vào <strong>CHỌN SKIN</strong>, chọn tối đa 30 skin hoặc dùng gói chọn nhanh 50 skin.</li><li>Mở <strong>ĐÃ CHỌN</strong>, kiểm tra danh sách và chọn <strong>Android / iOS / Cả 2</strong>.</li><li>Bấm <strong>TẠO MOD</strong>, chọn có hoặc không có nút bấm + hạ địch, rồi bấm <strong>TẠO MOD</strong> bên dưới.</li><li>Đợi tạo xong, làm nhiệm vụ để mở tải ZIP. Xem lại trong <strong>LỊCH SỬ</strong>.</li></ol><p>Trong game, tải đủ <strong>Cần thiết trong trận (100%)</strong> và <strong>Trải nghiệm đa dạng → Bối cảnh ngoại vi (100%)</strong>. Thoát hẳn game trước khi chép file; thử đấu luyện trước khi chơi trận thường.</p>'}

class SiteSettings:
 def __init__(self,storage,catalog):
  self.root=Path(storage);self.catalog=catalog;self.path=self.root/'web_site.json'
  self.media=self.root/'site_media';self.media.mkdir(exist_ok=True)
  key=self.root/'quick_preview.key'
  if not key.exists():key.write_bytes(secrets.token_bytes(32))
  self.key=key.read_bytes()
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
 def validate(self,rows):
  if not isinstance(rows,list) or len(rows)!=QUICK_LIMIT:raise ValueError('Gói chọn nhanh cần đúng 50 skin của 50 tướng khác nhau.')
  clean=[];seen=set()
  for row in rows:
   if not isinstance(row,dict):raise ValueError('Skin không hợp lệ.')
   hero,name,sid=row.get('tuong'),row.get('skin'),row.get('id')
   if not all(isinstance(v,str) for v in (hero,name,sid)) or hero in seen or self.catalog.get(hero,{}).get(name)!=sid:raise ValueError('Chọn skin có trong danh mục; mỗi tướng một skin.')
   seen.add(hero);clean.append({'tuong':hero,'skin':name,'id':sid})
  return clean
 def read(self):
  try:value=json.loads(self.path.read_text())
  except (OSError,ValueError):value={}
  result={**DEFAULTS,**{k:v for k,v in value.items() if k in DEFAULTS and isinstance(v,str)}}
  avatar=value.get('avatar','')
  result['avatar']=avatar if re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp|gif)',avatar) and (self.media/avatar).is_file() else ''
  try:result['hot_picks']=self.validate(value.get('hot_picks'))
  except ValueError:result['hot_picks']=self.default_hot()
  return result
 def save(self,value):
  tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');tmp.replace(self.path)
 def public(self):
  v=self.read();v.pop('hot_picks');v['avatar_url']='/api/site-media/'+v.pop('avatar') if v['avatar'] else None
  return {**v,'manual_limit':MANUAL_LIMIT,'quick_limit':QUICK_LIMIT}
 def preview(self,mode,owner):
  if mode=='hot':rows=self.read()['hot_picks']
  elif mode=='random':
   heroes=secrets.SystemRandom().sample([h for h,s in self.catalog.items() if s],QUICK_LIMIT)
   rows=[{'tuong':h,'skin':n,'id':s} for h in heroes for n,s in [secrets.choice(list(self.catalog[h].items()))]]
  else:raise ValueError('Gói chọn nhanh không hợp lệ.')
  payload={'mode':mode,'owner':hashlib.sha256(owner.encode()).hexdigest(),'expires':int(time.time())+86400,'selections':rows}
  raw=base64.urlsafe_b64encode(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')
  return {'mode':mode,'selections':rows,'token':raw+'.'+hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest(),'expires':payload['expires']}
 def resolve(self,token,mode,owner):
  try:
   if not isinstance(token,str) or len(token)>30000:raise ValueError()
   raw,sig=token.split('.')
   if not hmac.compare_digest(sig,hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()):raise ValueError()
   p=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
   if p['mode']!=mode or p['owner']!=hashlib.sha256(owner.encode()).hexdigest() or p['expires']<time.time():raise ValueError()
   return self.validate(p['selections'])
  except (ValueError,KeyError,TypeError):raise ValueError('Gói chọn nhanh đã hết hạn hoặc không hợp lệ. Hãy chọn lại gói.')

def setup_site(app,settings,authorized):
 def guard(request):
  if not authorized(request):raise web.HTTPUnauthorized(reason='Vui lòng đăng nhập admin.')
 async def public(request):return web.json_response(settings.public())
 async def preview(request):
  data=await request.json()
  try:return web.json_response(settings.preview(data.get('mode'),request['session']))
  except (ValueError,AttributeError) as e:return web.json_response({'error':str(e)},status=400)
 async def admin(request):
  guard(request);value=settings.read()
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
    if data.get('reset_avatar') is True:value['avatar']=''
   except ValueError as e:return web.json_response({'error':str(e)},status=400)
   settings.save(value)
  return web.json_response({**value,'avatar_url':settings.public()['avatar_url']})
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
  (settings.media/name).write_bytes(data);value=settings.read();old=value['avatar'];value['avatar']=name;settings.save(value)
  if old:(settings.media/old).unlink(missing_ok=True)
  return web.json_response({'avatar_url':settings.public()['avatar_url']})
 async def media(request):
  name=request.match_info['filename']
  if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|webp|gif)',name) or not (settings.media/name).is_file():raise web.HTTPNotFound()
  return web.FileResponse(settings.media/name)
 app.router.add_get('/api/site',public);app.router.add_post('/api/quick-picks',preview)
 app.router.add_get('/api/site-media/{filename}',media)
 app.router.add_get('/api/admin/notice/site',admin);app.router.add_post('/api/admin/notice/site',admin)
 app.router.add_post('/api/admin/notice/site/avatar',upload)
