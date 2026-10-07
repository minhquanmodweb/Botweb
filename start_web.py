"""Verify, assemble and extract the uploaded parts, then start the web service."""
import hashlib,json,os,shutil,stat,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent


def apply_root_updates(target):
    """Use current root-level application updates with the verified data bundle."""
    required = (
        'web_server.py', 'web_index.html', 'web_engine.py', 'web_worker.py',
        'web_admin_features.py','web_site.py','web_atomic.py','web_notice.py', 'web_notice_admin.html', 'web_cosmetics.py',
        'cosmetic_lua.py', 'ifix_codec.py', 'notice_content.py',
    )
    if not (ROOT / 'web_notice.py').is_file():
        raise RuntimeError('Thiếu source cập nhật ở thư mục gốc: tải đủ các tệp của bản full/patch V2 cùng vị trí start_web.py.')
    missing = [name for name in required if not (ROOT / name).is_file()]
    template_names = ('native.json', 'HeroSkin_1.bytes', 'HeroSkin_2.bytes', 'Customization.pkg.bytes')
    missing += ['CosmeticTemplates/' + name for name in template_names if not (ROOT / 'CosmeticTemplates' / name).is_file()]
    if missing:
        raise RuntimeError('Source cập nhật chưa đầy đủ: ' + ', '.join(missing))
    optional = (
        'web_errors.py', 'lobby_portraits.py', 'resource_encoding.py',
        'resource_fixes.py', 'reset_overlay.py', 'action_validation.py',
        'skin_extras.py', 'skin_features.json', 'web_catalog.json',
        'resource_formats.json', 'resource_original_hashes.json', 'web_avatar.jpg',
    )
    for name in required + optional:
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, target / name)
    dst = target / 'CosmeticTemplates'
    dst.mkdir(exist_ok=True)
    for name in template_names:
        shutil.copy2(ROOT / 'CosmeticTemplates' / name, dst / name)
    # No resource-data bundle, jobs, notice JSON or uploaded media is overwritten.
    print('TD MOD: đã áp dụng source mới bên ngoài bundle vào thư mục chạy web.', flush=True)
    return target

def prepare():
    meta=json.loads((ROOT/'bundle.json').read_text())
    digest=meta['sha256'];target=ROOT/'app'
    marker=target/'.bundle.sha256'
    if marker.is_file() and marker.read_text().strip()==digest and (target/'web_server.py').is_file():return apply_root_updates(target)
    stage=Path(tempfile.mkdtemp(prefix='tdmod-unpack-',dir=ROOT))
    try:
        archive=stage/'payload.zip';combined=hashlib.sha256()
        with archive.open('wb') as out:
            for part in meta['parts']:
                name=part['name']
                if Path(name).name!=name:raise RuntimeError('Invalid part filename')
                p=ROOT/name
                if not p.is_file():raise RuntimeError(f'Thiếu file {name}. Tải đủ các file lên GitHub.')
                local=hashlib.sha256();size=0
                with p.open('rb') as inp:
                    while block:=inp.read(1024*1024):
                        local.update(block);combined.update(block);out.write(block);size+=len(block)
                if size!=part['size'] or local.hexdigest()!=part['sha256']:raise RuntimeError(f'File {name} tải lên chưa đầy đủ hoặc đã thay đổi.')
        if combined.hexdigest()!=digest:raise RuntimeError('Source checksum mismatch')
        unpack=stage/'app';unpack.mkdir()
        with zipfile.ZipFile(archive) as z:
            entries=z.infolist()
            if len(entries)>20000 or sum(i.file_size for i in entries)>512*1024*1024:raise RuntimeError('Source exceeds unpack limit')
            for item in entries:
                rel=PurePosixPath(item.filename)
                if rel.is_absolute() or '..' in rel.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise RuntimeError('Unsafe archive path')
                dest=unpack.joinpath(*rel.parts)
                if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
                dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as inp,dest.open('wb') as out:shutil.copyfileobj(inp,out)
        if not (unpack/'web_server.py').is_file():raise RuntimeError('Missing web entrypoint')
        (unpack/'.bundle.sha256').write_text(digest)
        if target.exists():shutil.rmtree(target)
        unpack.rename(target)
        return apply_root_updates(target)
    finally:shutil.rmtree(stage,ignore_errors=True)

if __name__=='__main__':
    app=prepare()
    if os.environ.get('TD_MOD_UNPACK_ONLY')=='1':print('Verified and unpacked web source:',app)
    else:
        os.chdir(app)
        os.execv(sys.executable,[sys.executable,str(app/'web_server.py')])
