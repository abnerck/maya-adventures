"""Run with python -m unittest test_cms (isolated temporary database)."""
import io
import os
import re
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image

_sandbox = tempfile.TemporaryDirectory()
os.environ['MAYA_DATA_DIR'] = str(Path(_sandbox.name) / 'data')
os.environ['MAYA_UPLOAD_DIR'] = str(Path(_sandbox.name) / 'uploads')
os.environ['ADMIN_PASSWORD'] = 'Test-password-2026'
import app as cms


class CmsTests(unittest.TestCase):
    def test_translation_is_authenticated_and_does_not_publish(self):
        anonymous = cms.app.test_client()
        self.assertEqual(anonymous.post('/admin/translate').status_code, 302)
        self.assertEqual(self.client.post('/admin/translate').status_code, 400)
        before = self.client.get('/').data
        with patch.object(cms, 'translate_texts', return_value=['Hello']) as service:
            result = self.client.post('/admin/translate', data={'_csrf': self.token, 'texts': '["Hola"]'})
            self.assertEqual(result.json, {'translations': ['Hello']})
            service.assert_called_once_with(['Hola'])
        self.assertEqual(self.client.get('/').data, before)
        for invalid in ['null', '{}', '[1]', '[]', 'bad json']:
            self.assertEqual(self.client.post('/admin/translate', data={'_csrf': self.token, 'texts': invalid}).status_code, 400)
        with patch.object(cms, 'translate_texts', side_effect=ValueError('Service unavailable')):
            self.assertEqual(self.client.post('/admin/translate', data={'_csrf': self.token, 'texts': '["Hola"]'}).status_code, 503)

    def test_translation_adapter(self):
        import translation
        from unittest.mock import MagicMock
        import json
        response = MagicMock()
        response.__enter__.return_value.read.return_value = '{"translations":[{"text":"Hello"}]}'
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test:fx'}), patch.object(translation, 'urlopen', return_value=response) as send:
            self.assertEqual(translation.translate_texts(['Hola']), ['Hello'])
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api-free.deepl.com/v2/translate')
            self.assertEqual(json.loads(request.data)['source_lang'], 'ES')
        with patch.dict(os.environ, {'DEEPL_API_KEY': ''}):
            with self.assertRaises(ValueError):
                translation.translate_texts(['Hola'])

    def test_original_landing_migration_preserves_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(cms, 'DATA_DIR', root), patch.object(cms, 'DB_PATH', root / 'site.db'), patch.object(cms, 'UPLOAD_DIR', root / 'uploads'):
                cms.init_db()
                with cms.db() as connection:
                    user = tuple(connection.execute('SELECT username,password_hash FROM users').fetchone())
                    connection.execute("DELETE FROM settings WHERE key='original_landing_v1'")
                    connection.execute("UPDATE settings SET value_es='/static/img/Muelle.jpg',value_en='/static/uploads/custom.jpg' WHERE key='hero_image'")
                    connection.execute("UPDATE items SET description_en='Customer text' WHERE title_es='Terminal segura'")
                    connection.execute("UPDATE items SET description_en='The main pier may be closed for scheduled maintenance on certain dates.' WHERE title_es='Mantenimiento programado'")
                    connection.execute("UPDATE items SET price_en='' WHERE title_es='Tour + Ferry'")
                cms.init_db()
                self.assertTrue((root / 'before-original-landing-v1.sqlite3').exists())
                with cms.db() as connection:
                    hero = connection.execute("SELECT value_es,value_en FROM settings WHERE key='hero_image'").fetchone()
                    self.assertIn('photo-1544551763', hero[0])
                    self.assertEqual(hero[1], '/static/uploads/custom.jpg')
                    self.assertEqual(tuple(connection.execute('SELECT username,password_hash FROM users').fetchone()), user)
                    self.assertEqual(connection.execute("SELECT description_en FROM items WHERE title_es='Terminal segura'").fetchone()[0], 'Customer text')
                    self.assertIn('Thank you for your understanding.', connection.execute("SELECT description_en FROM items WHERE title_es='Mantenimiento programado'").fetchone()[0])
                    self.assertEqual(connection.execute("SELECT price_en FROM items WHERE title_es='Tour + Ferry'").fetchone()[0], 'Special offer')
                    connection.execute("UPDATE settings SET value_es='/static/img/Muelle.jpg' WHERE key='hero_image'")
                cms.init_db()
                with cms.db() as connection:
                    self.assertEqual(connection.execute("SELECT value_es FROM settings WHERE key='hero_image'").fetchone()[0], '/static/img/Muelle.jpg')

    def test_promotion_english_price_persists(self):
        self.client.post('/admin/items/save', data={'_csrf': self.token, 'kind': 'promotions', 'title_es': 'Precio bilingue', 'price': 'Desde $500', 'price_en': 'From $500', 'active': 'on'})
        with cms.db() as connection:
            item = connection.execute("SELECT * FROM items WHERE title_es='Precio bilingue'").fetchone()
            self.assertEqual(item['price_en'], 'From $500')
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('data-en="From $500"', page)

    def setUp(self):
        self.client = cms.app.test_client()
        page = self.client.get('/admin/login')
        self.token = re.search(rb'name="_csrf" value="([^"]+)"', page.data)[1].decode()
        response = self.client.post('/admin/login', data={'_csrf': self.token, 'username': 'admin', 'password': 'Test-password-2026'})
        self.assertEqual(response.status_code, 302)
        page = self.client.get('/admin')
        self.token = re.search(rb'name="_csrf" value="([^"]+)"', page.data)[1].decode()

    def test_access_and_csrf(self):
        anonymous = cms.app.test_client()
        self.assertEqual(anonymous.get('/admin').status_code, 302)
        self.assertEqual(anonymous.post('/admin/login', data={}).status_code, 400)
        self.assertEqual(self.client.post('/admin/settings', data={}).status_code, 400)

    def test_settings_persist(self):
        self.client.post('/admin/settings', data={'_csrf': self.token, 'hero_title_es': 'Mi nueva portada', 'hero_title_en': 'My new cover'})
        page = cms.app.test_client().get('/').get_data(as_text=True)
        self.assertIn('Mi nueva portada', page)
        self.assertIn('My new cover', page)
        cms.init_db()
        self.assertIn('Mi nueva portada', self.client.get('/').get_data(as_text=True))

    def test_full_item_lifecycle(self):
        image = io.BytesIO()
        Image.new('RGB', (100, 60), 'blue').save(image, 'PNG')
        image.seek(0)
        data = {'_csrf': self.token, 'kind': 'promotions', 'title_es': 'Prueba oferta', 'title_en': 'Test offer', 'position': '1', 'active': 'on', 'price': '$800', 'old_price': '$1000', 'duration_es': 'Todo el mes', 'image_upload': (image, 'photo.png')}
        response = self.client.post('/admin/items/save', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 302)
        with cms.db() as connection:
            item = connection.execute("SELECT * FROM items WHERE title_es='Prueba oferta'").fetchone()
        self.assertIsNotNone(item)
        self.assertTrue((cms.UPLOAD_DIR / Path(item['image']).name).exists())
        self.assertEqual(item['old_price'], '$1000')
        self.assertIn('Prueba oferta', self.client.get('/').get_data(as_text=True))
        data = {'_csrf': self.token, 'id': item['id'], 'kind': 'promotions', 'title_es': 'Oculta prueba', 'image': item['image'], 'position': 2}
        self.client.post('/admin/items/save', data=data)
        self.assertNotIn('Oculta prueba', self.client.get('/').get_data(as_text=True))
        self.client.post(f"/admin/items/{item['id']}/delete", data={'_csrf': self.token, 'kind': 'promotions'})
        with cms.db() as connection:
            self.assertIsNone(connection.execute('SELECT id FROM items WHERE id=?', (item['id'],)).fetchone())

    def test_reject_invalid_upload_and_link(self):
        base = {'_csrf': self.token, 'kind': 'ferries', 'title_es': 'Invalid', 'active': 'on'}
        result = self.client.post('/admin/items/save', data={**base, 'image_upload': (io.BytesIO(b'not an image'), 'fake.jpg')}, follow_redirects=True)
        self.assertIn('No se pudo leer', result.get_data(as_text=True))
        result = self.client.post('/admin/items/save', data={**base, 'link': 'javascript:alert(1)'}, follow_redirects=True)
        self.assertIn('caracteres no permitidos', result.get_data(as_text=True))
        with cms.db() as connection:
            self.assertIsNone(connection.execute("SELECT id FROM items WHERE title_es='Invalid'").fetchone())

    def test_empty_content_stays_empty(self):
        with cms.db() as connection:
            rows = connection.execute('SELECT * FROM items').fetchall()
            connection.execute('DELETE FROM items')
        cms.init_db()
        with cms.db() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM items').fetchone()[0], 0)
            names = list(rows[0].keys())
            connection.executemany(f"INSERT INTO items ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", [tuple(row) for row in rows])

    def test_password_and_logout(self):
        updated = 'A-new-password-2026'
        response = self.client.post('/admin/password', data={'_csrf': self.token, 'current_password': 'wrong-password', 'new_password': updated}, follow_redirects=True)
        self.assertIn('no es correcta', response.get_data(as_text=True))
        self.client.post('/admin/password', data={'_csrf': self.token, 'current_password': 'Test-password-2026', 'new_password': updated})
        self.client.post('/admin/logout', data={'_csrf': self.token})
        self.assertEqual(self.client.get('/admin').status_code, 302)
        page = self.client.get('/admin/login')
        token = re.search(rb'name="_csrf" value="([^"]+)"', page.data)[1].decode()
        self.client.post('/admin/login', data={'_csrf': token, 'username': 'admin', 'password': updated})
        self.assertEqual(self.client.get('/admin').status_code, 200)
        with cms.db() as connection:
            connection.execute('UPDATE users SET password_hash=? WHERE username=?', (cms.generate_password_hash('Test-password-2026'), 'admin'))


if __name__ == '__main__':
    unittest.main()
