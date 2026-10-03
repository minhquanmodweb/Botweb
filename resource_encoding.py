"""Restore the on-device resource envelopes before packaging.
Profiles come from the user's actual Resources.zip (1.64.1.8).
This preserves encoding; it does not disable the game's update checks.
"""
import io,json,struct,zipfile
from pathlib import Path
import pyzstd
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad,unpad
from Data.Module.Zstd import _key

HEADERS={b'\x22\x4a\x00\xef':'zstd',b'\x22\x4a\x67\x00':'aes',b'\x22\x4a\x67\xef':'aes_zstd'}

def decode(raw,mode,name,dictionary):
    if len(raw)<8:raise ValueError('Resource header too short')
    length=struct.unpack_from('<I',raw,4)[0]
    payload=raw[8:]
    if mode in ('aes','aes_zstd'):
        payload=unpad(AES.new(_key(Path(name).stem),AES.MODE_CBC,bytes(16)).decrypt(payload),16)
    if mode in ('zstd','aes_zstd'):
        payload=pyzstd.decompress(payload,zstd_dict=dictionary)
    if len(payload)!=length:raise ValueError(f'Invalid resource length: {name}')
    return payload

def encode(raw,mode,name,dictionary):
    if raw[:4] in HEADERS:
        raw=decode(raw,HEADERS[raw[:4]],name,dictionary)
    payload=raw
    if mode in ('zstd','aes_zstd'):
        payload=pyzstd.compress(payload,3,zstd_dict=dictionary)
    if mode in ('aes','aes_zstd'):
        payload=AES.new(_key(Path(name).stem),AES.MODE_CBC,bytes(16)).encrypt(pad(payload,16))
    magic={'zstd':b'\x22\x4a\x00\xef','aes':b'\x22\x4a\x67\x00','aes_zstd':b'\x22\x4a\x67\xef'}[mode]
    wrapped=magic+struct.pack('<I',len(raw))+payload
    if decode(wrapped,mode,name,dictionary)!=raw:raise ValueError('Resource round-trip mismatch')
    return wrapped

def restore_resource_encoding(resource_root,profile_path=None):
    module_root=Path(__file__).resolve().parent
    meta=json.loads(Path(profile_path or module_root/'resource_formats.json').read_text())
    resource_root=Path(resource_root)
    version=(resource_root/'version.txt').read_text().strip()
    if version!=meta['version']:raise RuntimeError('Resource encoding profile differs from game version')
    formats=meta['formats']
    dictionary=pyzstd.ZstdDict((module_root/'Data/Code/ZSTD_DICT.xml').read_bytes())
    changed=0
    for p in sorted(resource_root.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(resource_root).as_posix()
        if rel in formats:
            p.write_bytes(encode(p.read_bytes(),formats[rel],p.name,dictionary));changed+=1
        elif p.name.endswith('.pkg.bytes'):
            data=p.read_bytes()
            if not zipfile.is_zipfile(io.BytesIO(data)):continue
            count=0;out=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out,'w') as dst:
                for item in src.infolist():
                    raw=src.read(item)
                    if item.filename.endswith(".xml"):
                        from action_validation import normalize_action_xml
                        if raw[:4] in HEADERS:raw=decode(raw,HEADERS[raw[:4]],item.filename,dictionary)
                        raw=normalize_action_xml(raw,item.filename)
                        count+=1
                    mode=formats.get(rel+'::'+item.filename)
                    if mode and not item.is_dir():
                        raw=encode(raw,mode,item.filename,dictionary);count+=1
                    dst.writestr(item,raw)
            if count:p.write_bytes(out.getvalue());changed+=count
    return changed
