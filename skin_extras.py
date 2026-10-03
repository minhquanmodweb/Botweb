"""Inspect native cosmetic associations without moving their resource IDs."""
import hashlib,struct
from pathlib import Path

def read_table(path):
    raw=Path(path).read_bytes()
    if raw[:8]!=b'MSES\x07\x00\x00\x00' or len(raw)<140:
        raise RuntimeError('Bảng phụ kiện không đúng định dạng: '+Path(path).name)
    count=struct.unpack_from('<I',raw,12)[0];offset=140;rows=[]
    for _ in range(count):
        size=struct.unpack_from('<I',raw,offset)[0];offset+=4
        if size<=0 or offset+size>len(raw):raise RuntimeError('Bảng phụ kiện bị cắt ngắn')
        rows.append(bytearray(raw[offset:offset+size]));offset+=size
    if offset!=len(raw):raise RuntimeError('Bảng phụ kiện có dữ liệu thừa')
    return bytearray(raw[:140]),rows

def write_table(path,header,rows):
    payload=b''.join(struct.pack('<I',len(row))+row for row in rows)
    struct.pack_into('<I',header,8,len(rows[-1])+4 if rows else 0)
    struct.pack_into('<I',header,12,len(rows))
    header[96:128]=hashlib.md5(payload).hexdigest().encode()
    Path(path).write_bytes(header+payload)

def map_extras(folder,ids):
    selected={int(s) for s in ids};result={'buttons':[],'billboards':[]}
    for name,offset,key in [('ResPersonalButtonCfg.bytes',4,'buttons'),('ResBillboardSkinCfg.bytes',8,'billboards')]:
        p=Path(folder)/name
        if not p.is_file():continue
        header,rows=read_table(p)
        for row in rows:
            if len(row)<offset+4:raise RuntimeError('Bảng phụ kiện sai cấu trúc: '+name)
            sid=struct.unpack_from('<I',row,offset)[0]
            if sid in selected:
                result[key].append(str(sid))
                # Icon_Bac moves SkinID to slot 0 but retains ID. Native themes
                # reference that ID. Do not move it or duplicate global theme IDs.
    return result
