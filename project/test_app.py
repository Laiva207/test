import unittest
from app import app
import sqlite3


class FlaskTestCase(unittest.TestCase):

    def setUp(self):
        # testēšanas režīms
        app.config['TESTING'] = True
        self.client = app.test_client()

    # =========================
    # ✅ POZITĪVIE TESTI
    # =========================

    def test_register_success(self):
        # pareiza reģistrācija
        response = self.client.post('/register', data={
            'username': 'testuser1',
            'password': 'Test123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        # vispirms izveido user
        self.client.post('/register', data={
            'username': 'testuser2',
            'password': 'Test123'
        })

        # tad login
        response = self.client.post('/', data={
            'username': 'testuser2',
            'password': 'Test123'
        }, follow_redirects=True)

        self.assertIn(b'Sveiks', response.data)

    def test_add_note_success(self):
        # izveido user
        self.client.post('/register', data={
            'username': 'testuser3',
            'password': 'Test123'
        })

        # login
        self.client.post('/', data={
            'username': 'testuser3',
            'password': 'Test123'
        })

        # pievieno ierakstu
        response = self.client.post('/add', data={
            'location': 'Venta',
            'date': '2024-01-01',
            'season': 'Ziema',
            'weather': 'auksts',
            'notes': 'labs loms',
            'fish': ['1']
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

    # =========================
    # ❌ NEGATĪVIE TESTI
    # =========================

    def test_register_short_password(self):
        # parole par īsu
        response = self.client.post('/register', data={
            'username': 'baduser',
            'password': '123'
        }, follow_redirects=True)

        self.assertIn(b'Parolei', response.data)

    def test_login_wrong_password(self):
        # izveido user
        self.client.post('/register', data={
            'username': 'testuser4',
            'password': 'Test123'
        })

        # login ar nepareizu paroli
        response = self.client.post('/', data={
            'username': 'testuser4',
            'password': 'Wrong123'
        }, follow_redirects=True)

        self.assertIn(b'Nepareizs', response.data)

    def test_add_note_missing_fields(self):
        # izveido user
        self.client.post('/register', data={
            'username': 'testuser5',
            'password': 'Test123'
        })

        # login
        self.client.post('/', data={
            'username': 'testuser5',
            'password': 'Test123'
        })

        # tukši lauki
        response = self.client.post('/add', data={
            'location': '',
            'date': '',
            'season': '',
            'weather': '',
        }, follow_redirects=True)

        self.assertIn(b'Aizpildi', response.data)


if __name__ == '__main__':
    unittest.main()