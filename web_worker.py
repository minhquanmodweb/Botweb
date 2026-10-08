"""One isolated job per process. No Telegram token or network calls to Telegram."""
import asyncio, json, os, sys, zipfile, shutil, importlib
from pathlib import Path
from types import SimpleNamespace
import web_engine as engine

# This old actor-info converter asks a terminal-only question for skin 52102.
# Only its module gets an answer; builtins.input and other processors stay intact.
_infos_code = importlib.import_module('Data.Module.Infos.Code')

def _web_info_answer(prompt=''):
    if str(prompt).strip() == 'Mod Ngoại Hình Lính (y/n):':
        return 'n'  # Keep the requested hero skin; do not replace soldier models.
    raise RuntimeError('Bộ xử lý Infos yêu cầu lựa chọn chưa được hỗ trợ trên web.')

_infos_code.input = _web_info_answer


job = Path(sys.argv[1]).resolve()
data = json.loads((job / 'request.json').read_text())
os.chdir(job)
from web_atomic import install_output_writes
install_output_writes(job)

def progress(percent, message):
    p = job / 'progress.tmp'
    p.write_text(json.dumps({'percent':percent,'message':message},ensure_ascii=False))
    p.replace(job / 'progress.json')

async def update_progress(message, heroes, skins, ids, percent, context):
    progress(min(percent,99),f'Đang tạo file · {min(percent,99)}%')

async def finish_message(*args):
    pass

engine.update_progress = update_progress
engine.finish_message = finish_message

async def main():
    selected=data['selections']
    context=SimpleNamespace(user_data={'SDages':'yes' if data['bright'] else 'no', 'cosmetics':data.get('cosmetics') is True})
    update=SimpleNamespace(effective_user=SimpleNamespace(username='web_'+job.name[:8]))
    await engine.MainCodeMod(update, context, ' '.join(x['id'] for x in selected), ', '.join(x['skin'] for x in selected), ', '.join(x['tuong'] for x in selected), None)
    output=context.user_data.get('output_zip')
    if not output or not Path(output).is_file():
        raise RuntimeError('Không tạo được file từ dữ liệu hiện tại.')
    dest=job/'result.zip'
    platform=data['platform']
    if platform=='both':
        shutil.copyfile(output,dest)
    else:
        with zipfile.ZipFile(output) as src:
            if platform=='ios':
                with src.open('iOS.zip') as inp, dest.open('wb') as out:
                    shutil.copyfileobj(inp,out)
            else:
                with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as out:
                    for info in src.infolist():
                        if info.filename.startswith('com.garena.game.kgvn/') or info.filename=='DanhSáchSkin.txt':
                            with src.open(info) as inp, out.open(info.filename,'w') as dst:
                                shutil.copyfileobj(inp,dst)
    with zipfile.ZipFile(dest) as z:
        if not z.namelist() or z.testzip():
            raise RuntimeError('File đầu ra không hợp lệ.')
    shutil.rmtree(job/'Output',ignore_errors=True)
    progress(100,'Hoàn tất · Làm nhiệm vụ để mở tải')

if __name__=='__main__':
    from web_errors import save_failure
    try:asyncio.run(main())
    except Exception as error:
        save_failure(job,error)
        raise
