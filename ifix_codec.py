import struct
from pathlib import Path
class Reader:
 def __init__(self,b): self.b=b; self.o=0
 def i(self): v=struct.unpack_from('<i',self.b,self.o)[0];self.o+=4;return v
 def boolean(self): v=self.b[self.o];self.o+=1;assert v in (0,1);return bool(v)
 def s(self):
  n=0;shift=0
  while True:
   v=self.b[self.o];self.o+=1;n|=(v&127)<<shift
   if not v&128:break
   shift+=7
  v=self.b[self.o:self.o+n].decode();self.o+=n;return v
 def method(self):
  g=self.boolean();t=self.i();n=self.s();args=[]
  if g: args=[self.i() for _ in range(self.i())]
  params=[]
  for _ in range(self.i()):
   if g:
    isg=self.boolean();params.append(('g',self.s()) if isg else self.i())
   else:params.append(self.i())
  return dict(generic=g,type=t,name=n,args=args,params=params)
def parse(b):
 r=Reader(b);p={'magic':b[:8].hex()};r.o=8;p['bridge']=r.s();p['types']=[r.s() for _ in range(r.i())];p['methods']=[]
 for _ in range(r.i()):
  start=r.o;code=[(r.i(),r.i()) for _ in range(r.i())];eh=[[r.i() for _ in range(6)] for _ in range(r.i())]
  p['methods'].append(dict(code=code,eh=eh,raw=b[start:r.o].hex()))
 p['extern']=[r.method() for _ in range(r.i())];p['strings']=[r.s() for _ in range(r.i())];p['fields']=[]
 for _ in range(r.i()):
  f=dict(new=r.boolean(),type=r.i(),name=r.s())
  if f['new']:f.update(field_type=r.i(),method=r.i())
  p['fields'].append(f)
 p['static']=[(r.i(),r.i()) for _ in range(r.i())];p['anonymous']=[]
 for _ in range(r.i()):
  f=[r.i() for _ in range(r.i())];ctor=r.i();argc=r.i();interfaces=r.i()
  assert interfaces==0,'interface count requires reflection'
  v=[r.i() for _ in range(r.i())];p['anonymous'].append(dict(fields=f,ctor=ctor,argc=argc,vtable=v))
 p['wrapper']=r.s();p['assembly']=r.s();p['fixes']=[]
 for _ in range(r.i()):
  m=r.method();m['method']=r.i();p['fixes'].append(m)
 p['newclasses']=[r.s() for _ in range(r.i())];assert r.o==len(b),(r.o,len(b));return p
def serialize(p):
 out=bytearray(bytes.fromhex(p['magic']))
 def i(v):out.extend(struct.pack('<i',v))
 def s(v):
  data=v.encode();n=len(data)
  while n>=128:out.append((n&127)|128);n>>=7
  out.append(n);out.extend(data)
 def m(v):
  out.append(v['generic']);i(v['type']);s(v['name'])
  if v['generic']:
   i(len(v['args']))
   for x in v['args']:i(x)
  i(len(v['params']))
  for x in v['params']:
   if v['generic']:
    out.append(isinstance(x,(tuple,list)))
    if isinstance(x,(tuple,list)):s(x[1]);continue
   i(x)
 s(p['bridge']);i(len(p['types']))
 for x in p['types']:s(x)
 i(len(p['methods']))
 for method in p['methods']:
  i(len(method['code']))
  for op,arg in method['code']:i(op);i(arg)
  i(len(method['eh']))
  for handler in method['eh']:
   for x in handler:i(x)
 i(len(p['extern']))
 for x in p['extern']:m(x)
 i(len(p['strings']))
 for x in p['strings']:s(x)
 i(len(p['fields']))
 for f in p['fields']:
  out.append(f['new']);i(f['type']);s(f['name'])
  if f['new']:i(f['field_type']);i(f['method'])
 i(len(p['static']))
 for t,c in p['static']:i(t);i(c)
 i(len(p['anonymous']))
 for a in p['anonymous']:
  i(len(a['fields']))
  for t in a['fields']:i(t)
  i(a['ctor']);i(a['argc']);i(0);i(len(a['vtable']))
  for x in a['vtable']:i(x)
 s(p['wrapper']);s(p['assembly']);i(len(p['fixes']))
 for f in p['fixes']:m(f);i(f['method'])
 i(len(p['newclasses']))
 for x in p['newclasses']:s(x)
 return bytes(out)
if __name__=='__main__':
 import json
 for name in ('HeroSkin_1','HeroSkin_2'):
  p=parse(Path('checks/reference50/'+name+'.bytes').read_bytes());Path('checks/reference50/'+name+'.json').write_text(json.dumps(p,indent=2));print(name,len(p['methods']),len(p['extern']),len(p['fields']),len(p['anonymous']));print(p['fixes'][-4:])
