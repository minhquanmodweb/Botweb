"""Small, public error details; internal worker logs stay private."""
import json,re,traceback
from pathlib import Path

def save_failure(folder,error):
    chain=[];current=error
    for _ in range(6):
        if current is None:break
        chain.append(str(current));current=current.__cause__ or current.__context__
    text='\n'.join(chain)
    match=re.search(r'Không xử lý được skin (\d{5,6})',text)
    if 'Thiếu model sảnh' in text:code='LOBBY_MODEL_MISSING'
    elif 'Thiếu dữ liệu tướng' in text or 'Không có dữ liệu ảnh' in text:code='RESOURCE_MISSING'
    elif 'đã bị mod trước đó' in text:code='RESOURCE_NOT_CLEAN'
    elif any(isinstance(e,json.JSONDecodeError) for e in [error,error.__cause__]):code='RESOURCE_PARSE_ERROR'
    elif isinstance(error,MemoryError):code='MEMORY_LIMIT'
    else:code='WORKER_ERROR'
    origin=error.__cause__ or error
    frames=traceback.extract_tb(origin.__traceback__)
    module=Path(frames[-1].filename).name if frames else None
    Path(folder,'failure.json').write_text(json.dumps({'skin_id':match[1] if match else None,'code':code,'module':module,'exception':type(origin).__name__}))

def public_failure(folder,selections,returncode=None):
    try:details=json.loads(Path(folder,'failure.json').read_text())
    except (OSError,ValueError):details={}
    selected=next((s for s in selections if str(s.get('id'))==details.get('skin_id')),None)
    code=details.get('code')
    explanations={'LOBBY_MODEL_MISSING':'thiếu dữ liệu model sảnh tương ứng','RESOURCE_MISSING':'thiếu dữ liệu tài nguyên','RESOURCE_NOT_CLEAN':'dữ liệu nguồn đã bị chỉnh sửa','MEMORY_LIMIT':'không đủ bộ nhớ xử lý','RESOURCE_PARSE_ERROR':'dữ liệu chuyển đổi không đọc được','WORKER_ERROR':'không xử lý được dữ liệu skin'}
    if selected:
        return 'Không tạo được '+str(selected['tuong'])+' · '+str(selected['skin'])+': '+explanations.get(code,'lỗi xử lý dữ liệu')+'. Mã skin '+str(selected['id'])+'.'
    if returncode in (-9,137):return 'Tiến trình tạo file bị máy chủ dừng (mã 137). Có thể máy chủ thiếu bộ nhớ; kiểm tra log Railway.'
    if code=='MEMORY_LIMIT':return 'Máy chủ không đủ bộ nhớ để tạo file này.'
    return 'Tạo file thất bại. Mở log Railway để kiểm tra nguyên nhân (mã WORKER_ERROR).'
