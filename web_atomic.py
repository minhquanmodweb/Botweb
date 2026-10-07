"""Publish large intermediate text tables only after the complete write succeeds.

Installed inside an isolated web worker. Source Data/Resources and ZIP/binary
writers are untouched. Existing converters use both open() and Path.write_text().
"""
import builtins,io,os,tempfile,locale
from pathlib import Path


def install_output_writes(job):
    root=(Path(job)/'Output').resolve()
    original=builtins.open;original_io=io.open
    class TableWriter(io.StringIO):
        def __init__(self,path,encoding,newline):
            super().__init__(newline=newline);self.name=str(path);self.target=path;self.codec=locale.getencoding() if encoding=='locale' else encoding or 'utf-8';self.mode='w'
        def __exit__(self,kind,value,tb):
            if kind is not None:super().close()
            else:self.close()
            return False
        def close(self):
            if self.closed:return
            data=self.getvalue().encode(self.codec)
            fd,name=tempfile.mkstemp(prefix='.table-',dir=self.target.parent)
            temporary=Path(name)
            try:
                offset=0
                while offset<len(data):
                    n=os.write(fd,memoryview(data)[offset:])
                    if n<=0:raise OSError('Không ghi đủ bảng tài nguyên.')
                    offset+=n
                os.fsync(fd);os.close(fd);fd=-1
                if temporary.stat().st_size!=len(data):raise OSError('Bảng tài nguyên bị ghi thiếu.')
                temporary.replace(self.target)
            finally:
                if fd>=0:os.close(fd)
                temporary.unlink(missing_ok=True);super().close()
    def wrapper(file,mode='r',buffering=-1,encoding=None,errors=None,newline=None,closefd=True,opener=None):
        if mode in ('w','wt') and isinstance(file,(str,bytes,os.PathLike)) and opener is None and errors in (None,'strict'):
            path=Path(os.fsdecode(file)).resolve()
            if path.is_relative_to(root) and path.suffix.lower() in ('.bytes','.xml','.json','.txt'):
                return TableWriter(path,encoding,newline)
        return original(file,mode,buffering,encoding,errors,newline,closefd,opener)
    builtins.open=wrapper;io.open=wrapper
    return lambda:(setattr(builtins,'open',original),setattr(io,'open',original_io))
