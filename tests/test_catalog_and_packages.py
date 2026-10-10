import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_catalog_admin import CatalogAdmin
from web_site import SiteSettings

ROOT = Path(__file__).resolve().parents[1]

class CatalogAndPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = json.loads((ROOT / 'web_catalog.json').read_text())
        self.manager = CatalogAdmin(ROOT, self.temp.name, self.catalog)
        self.site = SiteSettings(self.temp.name, self.catalog)

    def test_add_reload_package_and_preview(self):
        # 10509 exists in bundled resources but is absent from the web catalog.
        row = {'tuong': 'Toro', 'skin': 'Skin bổ sung kiểm thử', 'id': '10509'}
        self.manager.add(row)
        data = self.site.change_package({'name': 'Gói thử', 'count': 1, 'kind': 'fixed', 'selections': [row]})
        pack = data['quick_packages'][-1]
        preview = self.site.preview('package', 'owner', pack['id'])
        self.assertEqual(self.site.resolve(preview['token'], 'package', 'owner'), [row])
        fresh = json.loads((ROOT / 'web_catalog.json').read_text())
        CatalogAdmin(ROOT, self.temp.name, fresh)
        self.assertEqual(fresh['Toro'][row['skin']], '10509')
        reloaded = SiteSettings(self.temp.name, fresh)
        self.assertEqual(reloaded.read()['quick_packages'][-1]['selections'], [row])
        changed = reloaded.change_package({**pack, 'name': 'Đã đổi'})['quick_packages'][-1]
        self.assertEqual(changed['revision'], pack['revision'] + 1)
        with self.assertRaises(ValueError):
            reloaded.change_package({**pack, 'name': 'Dữ liệu cũ'})
        with self.assertRaises(ValueError):
            reloaded.resolve(preview['token'], 'package', 'owner')

    def test_new_hero_and_deployment_overlay(self):
        catalog = {h: dict(skins) for h, skins in self.manager.base.items() if h != 'Toro'}
        manager = CatalogAdmin(ROOT, self.temp.name, catalog)
        row = {'tuong': 'Toro', 'skin': 'Skin mới', 'id': '10509'}
        before = len(catalog)
        manager.add(row)
        self.assertEqual(len(catalog), before + 1)
        self.assertEqual(catalog['Toro'], {'Skin mới': '10509'})
        from start_web import apply_root_updates
        with tempfile.TemporaryDirectory() as target:
            apply_root_updates(Path(target))
            self.assertTrue((Path(target) / 'web_catalog_admin.py').is_file())
            self.assertIn('setup_catalog_admin', (Path(target) / 'web_server.py').read_text())

    def test_bad_and_duplicate_ids_do_not_write(self):
        for row in [
            {'tuong': 'Toro', 'skin': 'Sai tướng', 'id': '15015'},
            {'tuong': 'Toro', 'skin': 'Không tồn tại', 'id': '10599'},
            {'tuong': 'Tên tướng khác', 'skin': 'Trùng mã tướng', 'id': '10509'},
            {'tuong': 'Toro', 'skin': 'Mặc định', 'id': '10500'},
            {'tuong': 'Toro', 'skin': 'Đặc cảnh NYPD', 'id': '10509'},
        ]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.manager.add(row)
        self.assertEqual(self.manager.entries()['entries'], [])
        self.manager.add({'tuong': 'Toro', 'skin': 'Mới', 'id': '10509'})
        with self.assertRaises(ValueError):
            self.manager.add({'tuong': 'Toro', 'skin': 'Trùng ID', 'id': '10509'})
        self.assertEqual(len(self.manager.entries()['entries']), 1)

if __name__ == '__main__':
    unittest.main()
