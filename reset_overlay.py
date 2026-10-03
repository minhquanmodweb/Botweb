"""Install the user-supplied reset packages verbatim after resource encoding."""
import hashlib,json,shutil,zipfile
from pathlib import Path

EXPECTED_NAMES={'KernelLua.pkg.bytes','StableSystems_3.pkg.bytes'}
def reset_files(version):
    root=Path(__file__).resolve().parent/'ResetFiles'/version
    if not root.is_dir():raise RuntimeError('Chưa có bộ fix reset cho phiên bản '+version)
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest.get('resource_version')!=version or set(manifest.get('files',{}))!=EXPECTED_NAMES:
        raise RuntimeError('Bộ fix reset không đúng phiên bản hoặc thiếu file')
    result={}
    for name,expected in manifest['files'].items():
        p=root/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Bộ fix reset thiếu hoặc sai hash: '+name)
        with zipfile.ZipFile(p) as z:
            if not z.namelist() or z.testzip():raise RuntimeError('Bộ fix reset lỗi ZIP: '+name)
        result[name]=p
    return result

def apply_reset_overlay(resource_root,version):
    root=Path(resource_root)
    for name,p in reset_files(version).items():shutil.copyfile(p,root/name)
    print('Installed user reset packages verbatim for '+version)

def verify_reset_archive(archive,prefix,version):
    for name,p in reset_files(version).items():
        if archive.read(prefix+name)!=p.read_bytes():
            raise RuntimeError('File đầu ra không chứa đúng bộ fix reset: '+name)
