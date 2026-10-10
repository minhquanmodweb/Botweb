"""Mutable web data lives outside extracted source; transactional JSON merges."""
import os,json,tempfile,shutil,fcntl
from pathlib import Path
from contextlib import contextmanager

def storage_path(root):
 root=Path(root).resolve()
 mount=os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
 return Path(os.getenv('WEB_STORAGE_DIR') or (str(Path(mount)/'jobs') if mount else str(root.parent/'WebData'))).resolve()

def persistent_storage(path):
 path=Path(path).resolve();mount=os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
 if mount and path.is_relative_to(Path(mount).resolve()):return True
 return any(p!=Path('/') and p.is_mount() for p in [path,*path.parents])

def migrate_legacy(root,target):
 root=Path(root).resolve();target=Path(target).resolve()
 old=root/'WebJobs'
 if target==old or not old.is_dir():return
 # Only seed a new store. Never combine two independent installations.
 marker=target/'.storage-migrated'
 if marker.exists() or any((target/n).exists() for n in ['web_site.json','web_notice.json','web_usage.sqlite3','web_music.json','web_admin_auth.json']):return
 target.mkdir(parents=True,exist_ok=True)
 for entry in old.iterdir():
  if entry.is_symlink():continue
  dest=target/entry.name
  if dest.exists():continue
  if entry.is_dir():shutil.copytree(entry,dest,symlinks=True)
  elif entry.is_file():shutil.copy2(entry,dest)
 marker.write_text('Copied legacy web data without overwriting existing data.\n')

@contextmanager
def json_lock(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.with_suffix(path.suffix+'.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)

def read_json(path,default=None):
 path=Path(path)
 if not path.exists():return {} if default is None else default
 try:value=json.loads(path.read_text(encoding='utf-8'))
 except (OSError,ValueError) as e:raise RuntimeError('Không đọc được dữ liệu đã lưu; giữ nguyên tệp để khôi phục, không tự reset.') from e
 if not isinstance(value,dict):raise RuntimeError('Dữ liệu đã lưu không hợp lệ; không tự reset.')
 return value

def write_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as f:
   json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
  if path.exists():shutil.copy2(path,path.with_suffix(path.suffix+'.bak'))
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def update_json(path,change):
 with json_lock(path):
  value=read_json(path);result=change(value)
  write_json(path,value)
  return result
