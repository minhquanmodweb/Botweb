"""Selective native Lua cosmetics; original bodies remain unchanged."""
import copy
from lobby_portraits import abc,load,jump

def const(f,v):
 k=len(f['constants']);f['constants'].append(v);f['types'].append(1 if isinstance(v,bool) else 4 if isinstance(v,str) else 19);return k

def patch_fn(f,mapping,action):
 original=copy.deepcopy(f);added=[]
 temp=f['params'];f['stack']=max(f['stack'],temp+1)
 for key,value in sorted(mapping.items()):
  added.extend([load(temp,const(f,key)),abc(15,0,0,temp),jump(0,2),load(0 if action=='alias' else temp,const(f,value)), jump(0,0) if action=='alias' else abc(11,temp,2,0)])
 if action=='alias':
  # Jump past the remaining comparisons into the unchanged native body.
  for pc in range(4,len(added),5):added[pc]=jump(0,len(added)-pc-1)
 shift=len(added);f['code']=added+f['code'];f['lines']=[f['start']]*shift+f['lines']
 f['locals']=[(n,a+(shift if a>0 else 0),e+shift) for n,a,e in f['locals']]
 assert f['code'][shift:]==original['code']
 # Execute every branch in this small prefix, including all unselected IDs.
 def evaluate(param):
  regs={0:param};pc=0
  while pc<len(added):
   c=added[pc];pc+=1;op=c&63;a=c>>6&255;b=c>>23&511;cc=c>>14&511
   if op==14:regs[a]=f['constants'][c>>14]
   elif op==15:
    if (regs[b]==regs[cc])!=bool(a):pc+=1
   elif op==20:pc+=(c>>14)-131071
   elif op==11:return ('return',regs[a])
   else:raise AssertionError(op)
  return ('native',regs[0])
 for param in sorted(set(mapping) | {0,1,10000,61000}):
  expected=('return',mapping[param]) if param in mapping and action=='return' else ('native',mapping.get(param,param) if action=='alias' else param)
  assert evaluate(param)==expected,(param,evaluate(param),expected)
 return original

def settings_prefix(f,key):
 original=copy.deepcopy(f)
 assert f['params']==0 and '_ENV' in f['upnames']
 env=f['upnames'].index('_ENV')
 keys={k:const(f,k) for k in ['N','GameSettings',key,'SetBool','Save']}
 assert max(keys.values())<256
 added=[abc(3,0,env,256+keys['N']),abc(19,0,0,256+keys['GameSettings']),abc(19,0,0,256+keys[key]),abc(44,0,0,256+keys['SetBool']),abc(1,2,1,0),abc(4,0,3,1),abc(3,0,env,256+keys['N']),abc(19,0,0,256+keys['GameSettings']),abc(19,0,0,256+keys[key]),abc(44,0,0,256+keys['Save']),abc(4,0,2,1)]
 shift=len(added);f['code']=added+f['code'];f['lines']=[f['start']]*shift+f['lines'];f['stack']=max(f['stack'],3)
 f['locals']=[(n,a+(shift if a>0 else 0),e+shift) for n,a,e in f['locals']]
 assert f['code'][shift:]==original['code']
