"""Persistent catalog additions; native resource IDs remain authoritative."""
import re
import struct
from pathlib import Path
from aiohttp import web
from web_storage import read_json, update_json


class CatalogAdmin:
    def __init__(self, root, storage, catalog):
        self.root = Path(root)
        self.path = Path(storage) / 'web_catalog_custom.json'
        self.catalog = catalog
        self.base = {hero: dict(skins) for hero, skins in catalog.items()}
        self.refresh()

    def refresh(self):
        merged = {hero: dict(skins) for hero, skins in self.base.items()}
        for hero, skins in read_json(self.path).items():
            merged.setdefault(hero, {}).update(skins)
        self.catalog.clear()
        self.catalog.update(merged)

    def entries(self):
        return {'entries': [{'tuong': h, 'skin': n, 'id': sid}
                            for h, skins in read_json(self.path).items()
                            for n, sid in skins.items()], 'hero_limit': len(self.catalog)}

    def resource_check(self, sid):
        versions = sorted(p for p in (self.root / 'Resources_1').iterdir() if p.is_dir())
        if not versions:
            raise ValueError('Chưa có Resources_1. Cần bổ sung tài nguyên game trước.')
        # The generation engine processes every installed resource version.
        for version in versions:
            infos = version / 'Prefab_Characters/Prefab_Hero'
            ages = version / 'Ages/Prefab_Characters/Prefab_Hero'
            heroes = list(infos.glob(sid[:3] + '_*'))
            if len(heroes) != 1 or not heroes[0].is_dir() or not ages.is_dir() or not any(
                p.is_dir() and p.name.casefold() == heroes[0].name.casefold() for p in ages.iterdir()
            ) or not (version / 'AssetRefs/Hero' / (sid[:3] + '_AssetRef.bytes')).is_file():
                raise ValueError('Thiếu tài nguyên tướng ' + sid[:3] + ' trong ' + version.name + '. Bổ sung dữ liệu game rồi thử lại.')
            table = version / 'Databin/Client/Actor/heroSkin.bytes'
            if not table.is_file():
                raise ValueError('Thiếu bảng heroSkin.bytes trong ' + version.name)
            raw = table.read_bytes()
            offset = 140
            found = False
            while offset + 4 <= len(raw):
                size = struct.unpack_from('<I', raw, offset)[0]
                start = offset + 4
                if size < 16 or start + size > len(raw):
                    raise ValueError('Bảng heroSkin.bytes không hợp lệ trong ' + version.name)
                ident, hero_id = struct.unpack_from('<II', raw, start)
                if ident == int(sid) and hero_id == int(sid[:3]):
                    found = True
                    break
                offset = start + size
            if not found:
                raise ValueError('ID ' + sid + ' chưa có trong dữ liệu game ' + version.name + '. Thêm tên vào web không tự tạo tài nguyên skin; cần cập nhật Resources_1 trước.')

    def add(self, data):
        if not isinstance(data, dict):
            raise ValueError('Thông tin skin không hợp lệ.')
        values = [data.get(k) for k in ('tuong', 'skin', 'id')]
        if not all(isinstance(v, str) for v in values):
            raise ValueError('Nhập tên tướng, tên skin và ID.')
        hero, name, sid = (v.strip() for v in values)
        if not 1 <= len(hero) <= 80 or not 1 <= len(name) <= 120 or any(c in hero + name for c in '\n\r\x00'):
            raise ValueError('Tên tướng tối đa 80 ký tự, tên skin tối đa 120 ký tự; không xuống dòng.')
        if not re.fullmatch(r'[1-9][0-9]{4}', sid) or sid.endswith('00'):
            raise ValueError('ID skin gồm 5 chữ số, ví dụ 15015; không dùng ID skin mặc định 00.')
        self.resource_check(sid)
        def change(value):
            merged = {h: dict(s) for h, s in self.base.items()}
            for h, skins in value.items():
                merged.setdefault(h, {}).update(skins)
            if any(h.casefold() == hero.casefold() and h != hero for h in merged):
                raise ValueError('Tướng đã có trong danh mục. Chọn đúng tên tướng hiện có.')
            if name in merged.get(hero, {}):
                raise ValueError('Tên skin đã có trên tướng này.')
            if any(sid == s for skins in merged.values() for s in skins.values()):
                raise ValueError('ID skin này đã có trên web.')
            ids = list(merged.get(hero, {}).values())
            if ids and any(s[:3] != sid[:3] for s in ids):
                raise ValueError('Ba chữ số đầu của ID không khớp tướng đã chọn.')
            if any(h != hero and any(s[:3] == sid[:3] for s in skins.values()) for h, skins in merged.items()):
                raise ValueError('ID thuộc tướng đã có trên web. Chọn tên tướng đó thay vì tạo tên khác.')
            value.setdefault(hero, {})[name] = sid
        update_json(self.path, change)
        self.refresh()
        return self.entries()


def setup_catalog_admin(app, manager, authorized):
    async def catalog(request):
        if not authorized(request):
            raise web.HTTPUnauthorized(reason='Vui lòng đăng nhập admin.')
        if request.method == 'GET':
            return web.json_response(manager.entries())
        try:
            return web.json_response(manager.add(await request.json()))
        except (ValueError, OSError) as error:
            return web.json_response({'error': str(error)}, status=400)
    app.router.add_get('/api/admin/notice/catalog', catalog)
    app.router.add_post('/api/admin/notice/catalog', catalog)
