"""Preserve verification entries for original assets; exclude changed mod files only."""
import hashlib,io,json,zipfile
from pathlib import Path
import pyzstd
import Data.UnityPy_AOV as Unity
from resource_encoding import HEADERS,decode

def fingerprint(raw,name,dictionary):
    if raw[:4] in HEADERS:raw=decode(raw,HEADERS[raw[:4]],name,dictionary)
    if name.endswith('.pkg.bytes') and zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            values={n:fingerprint(z.read(n),n,dictionary) for n in z.namelist() if not n.endswith('/')}
        raw=json.dumps(values,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()

def patch_verification(resource_root):
    resource_root=Path(resource_root);module=Path(__file__).resolve().parent
    original=json.loads((module/'resource_original_hashes.json').read_text())
    dictionary=pyzstd.ZstdDict((module/'Data/Code/ZSTD_DICT.xml').read_bytes())
    changed=set()
    for file in resource_root.rglob('*'):
        if not file.is_file():continue
        rel=file.relative_to(resource_root).as_posix()
        if rel in original and fingerprint(file.read_bytes(),rel,dictionary)!=original[rel]:changed.add(rel)
    bundle=resource_root/'assetbundle/resourceverificationinfosetall.assetbundle'
    env=Unity.load(str(bundle));removed=[]
    for obj in env.objects:
        if obj.type.name!='MonoBehaviour' or not obj.serialized_type.nodes:continue
        tree=obj.read_typetree()
        if tree.get('m_Name')!='ResourceVerificationInfoSetXML':continue
        for key in ('AllZipVerificationInfo','AllDatabinVerificationInfo'):
            entries=tree.get(key,[])
            removed.extend(x['PathInIFS'] for x in entries if x.get('PathInIFS') in changed)
            tree[key]=[x for x in entries if x.get('PathInIFS') not in changed]
        obj.save_typetree(tree)
    if removed:bundle.write_bytes(env.file.save(packer='lz4'))
    print('Verification excludes changed mod files:',sorted(set(removed)))
    return sorted(set(removed))
