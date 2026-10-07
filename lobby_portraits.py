"""Select mod portraits only in the lobby hero gallery.
The instruction transform was confirmed on Android game 1.64.1.8 by the user.
Shared picture/head table keys remain untouched. No loader checks are changed.
"""
import struct,zipfile,io,copy,hashlib
from pathlib import Path
import pyzstd
from resource_encoding import decode,encode,HEADERS
class Reader:
 def __init__(self,b):self.b=b;self.o=b.index(b'\x1bLua')+33
 def r(self,n):v=self.b[self.o:self.o+n];self.o+=n;return v
 def num(self,f):return struct.unpack('<'+f,self.r(struct.calcsize(f)))[0]
 def s(self):
  n=self.num('B')
  if n==0:return None
  if n==255:n=self.num('Q')
  return self.r(n-1).decode('utf8','replace')
 def fn(self,parent=''):
  src=self.s() or parent;start=self.num('i');end=self.num('i');params=self.num('B');vararg=self.num('B');stack=self.num('B')
  nc=self.num('i');off=self.o;code=[self.num('I') for _ in range(nc)]
  const=[]
  for _ in range(self.num('i')):
   t=self.num('B')
   if t==0:v=None
   elif t==1:v=self.num('B')!=0
   elif t==3:v=self.num('d')
   elif t==19:v=self.num('q')
   elif t in (4,20):v=self.s()
   else:raise ValueError((t,self.o))
   const.append(v)
  ups=[list(self.r(2)) for _ in range(self.num('i'))]
  kids=[self.fn(src) for _ in range(self.num('i'))]
  lines=[self.num('i') for _ in range(self.num('i'))]
  loc=[(self.s(),self.num('i'),self.num('i')) for _ in range(self.num('i'))]
  upnames=[self.s() for _ in range(self.num('i'))]
  return dict(src=src,start=start,end=end,params=params,stack=stack,offset=off,code=code,constants=const,upvalues=ups,children=kids,lines=lines,locals=loc,upnames=upnames)
def walk(f):
 yield f
 for k in f['children']:yield from walk(k)
class ExactReader(Reader):
 def fn(self,parent=''):
  begin=self.o;raw_src=self.s();src=raw_src or parent;start=self.num('i');end=self.num('i');params=self.num('B');vararg=self.num('B');stack=self.num('B')
  nc=self.num('i');off=self.o;code=[self.num('I') for _ in range(nc)]
  const=[];types=[]
  for _ in range(self.num('i')):
   t=self.num('B');types.append(t)
   if t==0:v=None
   elif t==1:v=self.num('B')!=0
   elif t==3:v=self.num('d')
   elif t==19:v=self.num('q')
   elif t in (4,20):v=self.s()
   else:raise ValueError((t,self.o))
   const.append(v)
  ups=[list(self.r(2)) for _ in range(self.num('i'))]
  kids=[self.fn(src) for _ in range(self.num('i'))]
  lines=[self.num('i') for _ in range(self.num('i'))]
  loc=[(self.s(),self.num('i'),self.num('i')) for _ in range(self.num('i'))]
  upnames=[self.s() for _ in range(self.num('i'))]
  return dict(src=src,raw_src=raw_src,start=start,end=end,params=params,vararg=vararg,stack=stack,offset=off,code=code,constants=const,types=types,upvalues=ups,children=kids,lines=lines,locals=loc,upnames=upnames,begin=begin,finish=self.o)
def i(v):return struct.pack('<i',v)
def string(s):
 if s is None:return b'\0'
 b=s.encode();n=len(b)+1
 return (bytes([n]) if n<255 else b'\xff'+struct.pack('<Q',n))+b
def serialize(f):
 b=string(f['raw_src'])+i(f['start'])+i(f['end'])+bytes([f['params'],f['vararg'],f['stack']])+i(len(f['code']))+b''.join(struct.pack('<I',v) for v in f['code'])+i(len(f['constants']))
 for t,v in zip(f['types'],f['constants']):
  b+=bytes([t])
  if t==1:b+=bytes([int(v)])
  elif t==3:b+=struct.pack('<d',v)
  elif t==19:b+=struct.pack('<q',v)
  elif t in (4,20):b+=string(v)
 b+=i(len(f['upvalues']))+b''.join(bytes(v) for v in f['upvalues'])+i(len(f['children']))+b''.join(serialize(k) for k in f['children'])
 b+=i(len(f['lines']))+b''.join(i(v) for v in f['lines'])
 b+=i(len(f['locals']))+b''.join(string(n)+i(a)+i(e) for n,a,e in f['locals'])
 b+=i(len(f['upnames']))+b''.join(string(n) for n in f['upnames'])
 return b
def abc(op,a,b,c):return op+(a<<6)+(c<<14)+(b<<23)
def load(a,k):return 14+(a<<6)+(k<<14)
def jump(a,n):return 20+(a<<6)+((n+131071)<<14)

def gallery_package(package,selections,dictionary):
    selections={int(h):int(s) for h,s in selections.items()}
    if not 1<=len(selections)<=50:raise ValueError('Số tướng không hợp lệ')
    if any(not 100<=h<=999 or not 0<=s<=99 for h,s in selections.items()):raise ValueError('Mã skin không hợp lệ')
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        name='Lua_Signed/AOV/HeroInfo/HeroOverviewSys_lua.bytes'
        raw=z.read(name);mode=HEADERS.get(raw[:4]);native=decode(raw,mode,name,dictionary) if mode else raw
        rd=ExactReader(native);start=rd.o;tree=rd.fn();assert rd.o==len(native);assert native[:start]+serialize(tree)==native,'Native serialization not byte-exact'
        original_tree=copy.deepcopy(tree)
        target=next(f for f in walk(tree) if 'GetHeroSkinPicFeature' in f['constants']);orig=copy.deepcopy(target)
        assert (target['start'],target['end'],target['params'],target['stack'])==(519,855,5,42)
        # Exact native sequence: role:GetHeroWearSkinId(data.cfgID), result R25.
        at=621;cfg=target['constants'].index('cfgID')
        expected=[abc(44,25,16,256+target['constants'].index('GetHeroWearSkinId')),abc(19,27,2,256+cfg),abc(4,25,3,2)]
        assert target['code'][at-3:at]==expected,'Unexpected gallery argument layout'
        assert abc(18,28,25,0) in target['code'][at:at+12]
        # R26/R27 are dead here and overwritten by the native next image-helper call.
        inserted=[abc(19,26,2,256+cfg)]
        for hero,skin in sorted(selections.items()):
         def const(v):
          k=len(target['constants']);target['constants'].append(v);target['types'].append(19);return k
         inserted.extend([load(27,const(hero)),abc(15,0,26,27),jump(0,1),load(25,const(skin))])
        shift=len(inserted)
        # Rebase only native JMP destinations crossing the insertion point.
        # This native function contains no loop opcodes; no child prototype is changed.
        for pc,c in enumerate(orig['code']):
         if c&63!=20:continue
         destination=pc+1+(c>>14)-131071
         assert 0<=destination<=len(orig['code'])
         new_pc=pc+(shift if pc>=at else 0);new_destination=destination+(shift if destination>=at else 0)
         target['code'][pc]=jump(c>>6&255,new_destination-new_pc-1)
        target['code'][at:at]=inserted
        target['lines'][at:at]=[735]*shift
        target['locals']=[(n,a+(shift if a>=at else 0),e+(shift if e>=at else 0)) for n,a,e in orig['locals']]
        # All existing instructions are identical except rebased jumps. Those jumps
        # still point to the exact same original instructions after the insertion.
        for pc,c in enumerate(orig['code']):
         np=pc+(shift if pc>=at else 0);new=target['code'][np]
         if c&63==20:
          d=pc+1+(c>>14)-131071;nd=np+1+(new>>14)-131071;assert nd==d+(shift if d>=at else 0)
         else:assert new==c
        # Execute the inserted arithmetic/control fragment, including unknown heroes.
        def evaluate(hero,wear):
         regs={2:{'cfgID':hero},25:wear};pc=0
         while pc<len(inserted):
          c=inserted[pc];op=c&63;a=c>>6&255;b=c>>23&511;cc=c>>14&511;pc+=1
          if op==19:regs[a]=regs[b][target['constants'][cc-256]]
          elif op==14:regs[a]=target['constants'][c>>14]
          elif op==15:
           if (regs[b]==regs[cc])!=bool(a):pc+=1
          elif op==20:pc+=(c>>14)-131071
          else:raise AssertionError(op)
         return regs[25]
        for hero in range(100,610):
         for wear in [0,1,18]:assert evaluate(hero,wear)==selections.get(hero,wear)
        changed=native[:start]+serialize(tree);assert changed[:128]==native[:128]
        reread=ExactReader(changed);reparsed=reread.fn();assert reread.o==len(changed)
        # Verify every other prototype is unchanged, including its debug metadata.
        originals=list(walk(original_tree));modified=list(walk(reparsed));assert len(originals)==len(modified)
        for a,b in zip(originals,modified):
         if a['start']==519 and a['end']==855:continue
         aa=copy.deepcopy(a);bb=copy.deepcopy(b);aa['children']=[];bb['children']=[];assert serialize(aa)==serialize(bb)
        wrapped=encode(changed,mode,name,dictionary) if mode else changed
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as dst:
            for item in z.infolist():dst.writestr(copy.copy(item),wrapped if item.filename==name else z.read(item))
        updated=output.getvalue()
        with zipfile.ZipFile(io.BytesIO(updated)) as check:
            if check.testzip() is not None:raise RuntimeError('Gói ảnh sảnh bị lỗi')
            for n in z.namelist():
                if n!=name and check.read(n)!=z.read(n):raise RuntimeError('Mã ngoài màn sảnh bị thay đổi')
        return updated

def apply_lobby_portraits(resource_root,version,skin_ids):
    if version!='1.64.1':raise RuntimeError('Phiên bản ảnh sảnh chưa được hỗ trợ')
    selections={}
    for sid in skin_ids:
        sid=str(sid)
        if len(sid)!=5 or not sid.isdecimal():raise ValueError('Mã skin không hợp lệ')
        hero=int(sid[:3]);skin=int(sid[3:])
        if hero in selections and selections[hero]!=skin:raise ValueError('Một tướng chỉ chọn một skin')
        selections[hero]=skin
    module=Path(__file__).resolve().parent
    package=(module/'Resources_1'/version/'HeroInfoLua.pkg.bytes').read_bytes()
    if hashlib.sha256(package).hexdigest()!='29125cf31901c40a871e2b7a46998b01dc450427ce25e52d6c9a028d71488308':raise RuntimeError('Gói ảnh sảnh nguồn khác bản đã kiểm tra')
    dictionary=pyzstd.ZstdDict((module/'Data/Code/ZSTD_DICT.xml').read_bytes())
    result=gallery_package(package,selections,dictionary)
    (Path(resource_root)/'HeroInfoLua.pkg.bytes').write_bytes(result)
