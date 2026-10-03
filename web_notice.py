"""Editable welcome notice, isolated from bot and mod generation."""
import json
import re
import io
from notice_content import clean_html, plain_html
import os
import secrets
import time
from pathlib import Path
from aiohttp import web

LEGACY_DEFAULT = {'enabled': True, 'title': 'Lưu ý trước khi sử dụng', 'content': 'Để hiện đầy đủ nút bấm và thông báo hạ, hãy tải hoàn tất gói Bối cảnh ngoại vi trong game: Danh sách tải → Trải nghiệm đa dạng → Bối cảnh ngoại vi.\n\nThoát hẳn game trước khi chép file mod. Nên thử trong đấu luyện trước khi chơi trận thường.'}
LEGACY_DEFAULT['html'] = '<p><strong style="color:#70d8f2">Chọn kiểu mod bạn muốn</strong></p><p>Bấm <strong>TẠO MOD</strong>, rồi chọn <strong>Có nút + hạ địch</strong> hoặc <strong>Không nút • không hạ</strong> trước khi tạo file.</p><p><strong style="color:#67c7af">Để hiện đầy đủ hiệu ứng:</strong><br>Tải hoàn tất <strong>Bối cảnh ngoại vi</strong> trong game: Danh sách tải → Trải nghiệm đa dạng → Bối cảnh ngoại vi.</p><p>Thoát hẳn game trước khi chép file. Nên thử đấu luyện trước khi chơi trận thường. Skin không có bộ hiệu ứng riêng sẽ giữ giao diện thông thường.</p>'
DEFAULT = {'enabled': True, 'title': 'Lưu ý trước khi sử dụng', 'html': '<p><strong style="color:#70d8f2">Cách tạo file mod</strong></p><ol><li>Vào <strong>CHỌN SKIN</strong>, chọn tướng và các skin muốn mod.</li><li>Mở <strong>ĐÃ CHỌN</strong>, kiểm tra skin và chọn đúng nền tảng <strong>Android / iOS</strong>.</li><li>Bấm <strong>TẠO MOD</strong>, chọn <strong>Có nút bấm + hạ địch</strong> hoặc <strong>Không có nút bấm + hạ địch</strong>. Bấm nút <strong>TẠO MOD</strong> bên dưới để bắt đầu.</li><li>Đợi tạo file hoàn tất, làm nhiệm vụ để mở tải rồi tải file ZIP. Có thể xem lại trong <strong>LỊCH SỬ</strong>.</li></ol><p><strong style="color:#67c7af">Tải tài nguyên trước khi sử dụng:</strong><br>Trong game, mở <strong>Danh sách tải</strong> và tải đủ <strong>Cần thiết trong trận (100%)</strong> cùng <strong>Trải nghiệm đa dạng → Bối cảnh ngoại vi (100%)</strong> để hiện đầy đủ hiệu ứng.</p><p>Thoát hẳn game trước khi chép file. Giải nén đúng thư mục và chọn ghi đè. Skin không hỗ trợ hiệu ứng riêng sẽ dùng giao diện thông thường.</p>'}
COOKIE = 'tdmod_notice_admin' 

def setup_notice(app, storage):
    target = Path(storage) / 'web_notice.json'
    sessions = {}
    attempts = {}

    def read():
        if not target.exists():
            return {**DEFAULT, 'html': clean_html(DEFAULT['html'])}
        value = json.loads(target.read_text(encoding='utf-8'))
        # Upgrade only the previous built-in notice; retain admin-written content.
        previous = value.get('html')
        legacy = (isinstance(previous, str) and clean_html(previous) == clean_html(LEGACY_DEFAULT['html'])) or (previous is None and value.get('content') == LEGACY_DEFAULT['content'])
        if value.get('title') == LEGACY_DEFAULT['title'] and legacy:
            value = {**value, 'html': DEFAULT['html']}
            value.pop('content', None)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            temporary.replace(target)
        value['html'] = clean_html(value['html']) if isinstance(value.get('html'), str) else plain_html(value.get('content',''))
        return value

    def authorized(request):
        now = time.time()
        for key in list(sessions):
            if sessions[key] <= now:
                del sessions[key]
        return sessions.get(request.cookies.get(COOKIE, ''), 0) > now

    async def public(request):
        return web.json_response(read(), headers={'Cache-Control': 'no-store'})

    async def admin_page(request):
        return web.FileResponse(Path(__file__).with_name('web_notice_admin.html'))

    async def login(request):
        expected = os.getenv('WEB_ADMIN_PASSWORD', '177207')
        if not expected:
            return web.json_response({'error': 'Chưa cấu hình WEB_ADMIN_PASSWORD .'}, status=503)
        now = time.time()
        for key in list(attempts):
            if attempts[key][1] <= now:
                del attempts[key]
        ip = request.remote or 'unknown'
        count, until = attempts.get(ip, (0, now + 300))
        if count >= 5 or len(attempts) >= 1000:
            return web.json_response({'error': 'Thử lại sau 5 phút.'}, status=429)
        try:
            data = await request.json()
        except (ValueError, UnicodeDecodeError):
            data = None
        password = data.get('password') if isinstance(data, dict) else None
        if not isinstance(password, str) or not secrets.compare_digest(password.encode(), expected.encode()):
            attempts[ip] = (count + 1, until)
            return web.json_response({'error': 'Mật khẩu không đúng.'}, status=401)
        attempts.pop(ip, None)
        if len(sessions) >= 1000:
            sessions.clear()
        token = secrets.token_hex(32)
        sessions[token] = now + 8 * 3600
        response = web.json_response({'ok': True})
        response.set_cookie(COOKIE, token, httponly=True, samesite='Strict', secure=request.secure or request.headers.get('X-Forwarded-Proto') == 'https', max_age=8 * 3600, path='/api/admin/notice')
        return response

    async def logout(request):
        sessions.pop(request.cookies.get(COOKIE, ''), None)
        response = web.json_response({'ok': True})
        response.del_cookie(COOKIE, path='/api/admin/notice')
        return response

    async def settings(request):
        if not authorized(request):
            return web.json_response({'error': 'Vui lòng đăng nhập admin.'}, status=401)
        if request.method == 'GET':
            return web.json_response(read())
        try:
            data = await request.json()
        except (ValueError, UnicodeDecodeError):
            data = None
        if not isinstance(data, dict) or type(data.get('enabled')) is not bool or not isinstance(data.get('title'), str) or not isinstance(data.get('html', data.get('content')), str):
            return web.json_response({'error': 'Dữ liệu không hợp lệ.'}, status=400)
        title = data['title'].strip()
        content = data.get('html', data.get('content')).strip()
        if not 1 <= len(title) <= 120 or not 1 <= len(content) <= 20000:
            return web.json_response({'error': 'Tiêu đề 1–120 ký tự; nội dung 1–20000 ký tự.'}, status=400)
        rich = clean_html(content) if 'html' in data else plain_html(content)
        result = {'enabled': data['enabled'], 'title': title, 'html': rich}
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
        return web.json_response(result)

    media_folder = Path(storage) / 'notice_media'
    media_folder.mkdir(exist_ok=True)

    async def upload(request):
        if not authorized(request):
            return web.json_response({'error': 'Vui lòng đăng nhập admin.'}, status=401)
        reader = await request.multipart()
        part = await reader.next()
        if part is None or part.name != 'file':
            return web.json_response({'error': 'Chọn ảnh hoặc video.'}, status=400)
        suffix = Path(part.filename or '').suffix.lower()
        if suffix not in ('.jpg','.jpeg','.png','.webp','.gif','.mp4','.webm'):
            return web.json_response({'error': 'Hỗ trợ JPG, PNG, WEBP, GIF, MP4 và WEBM.'}, status=400)
        if suffix == '.jpeg':suffix = '.jpg'
        data = bytearray()
        while True:
            chunk = await part.read_chunk()
            if not chunk:break
            data.extend(chunk)
            if len(data) > 25 * 1024 * 1024:
                return web.json_response({'error': 'Tệp tối đa 25 MB.'}, status=413)
        if not data:
            return web.json_response({'error': 'Tệp rỗng.'}, status=400)
        if suffix in ('.jpg','.png','.webp','.gif'):
            from PIL import Image
            try:
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in ('JPEG','PNG','WEBP','GIF'):raise ValueError()
                    image.verify()
            except Exception:
                return web.json_response({'error': 'Ảnh không hợp lệ.'}, status=400)
        elif suffix == '.mp4' and not (len(data)>12 and data[4:8]==b'ftyp'):
            return web.json_response({'error': 'Video MP4 không hợp lệ.'}, status=400)
        elif suffix == '.webm' and data[:4] != b'\x1a\x45\xdf\xa3':
            return web.json_response({'error': 'Video WEBM không hợp lệ.'}, status=400)
        name = secrets.token_hex(16) + suffix
        (media_folder / name).write_bytes(data)
        return web.json_response({'url': '/api/notice-media/' + name, 'kind': 'video' if suffix in ('.mp4','.webm') else 'image'})

    async def media(request):
        name = request.match_info['filename']
        if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|webp|gif|mp4|webm)', name):
            raise web.HTTPNotFound()
        path = media_folder / name
        if not path.is_file():raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def preview(request):
        if not authorized(request):
            return web.json_response({'error': 'Vui lòng đăng nhập admin.'}, status=401)
        data = await request.json()
        value = data.get('html') if isinstance(data, dict) else None
        if not isinstance(value, str) or len(value) > 20000:
            return web.json_response({'error': 'Nội dung không hợp lệ.'}, status=400)
        return web.json_response({'html': clean_html(value)})

    app.router.add_post('/api/admin/notice/upload', upload)
    app.router.add_post('/api/admin/notice/preview', preview)
    app.router.add_get('/api/notice-media/{filename}', media)
    app.router.add_get('/api/notice', public)
    app.router.add_get('/admin/notice', admin_page)
    app.router.add_get('/admin/notice/', admin_page)
    app.router.add_get('/admin', admin_page)
    app.router.add_get('/admin/stats', admin_page)
    app.router.add_get('/admin/music', admin_page)
    app.router.add_post('/api/admin/notice/login', login)
    app.router.add_post('/api/admin/notice/logout', logout)
    app.router.add_get('/api/admin/notice', settings)
    app.router.add_post('/api/admin/notice', settings)

    return authorized
