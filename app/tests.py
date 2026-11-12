import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from app.models import Badanie, Pacjent, UstawieniaSystemu, Uzytkownik
from app.views import _build_face_test_data


class FaceTestImageTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.image_root = Path(self.temp_dir.name)

        for set_number in range(1, 6):
            suffix = '' if set_number == 1 else f'.{set_number}'
            ages = ('18', '40', '70') if set_number == 1 else ('18', '40', '75')
            for gender in ('k', 'm'):
                for age in ages:
                    folder_name = f'{gender}{age}{suffix}'
                    if set_number == 4 and gender == 'm' and age == '40':
                        folder_name = 'm30.4'
                    folder = self.image_root / folder_name
                    folder.mkdir()
                    names = ['face1.png', 'face2.png', 'face3.png']
                    if folder_name == 'k40.3':
                        names = ['k40_3.1.png', 'k40_3.1wersja.2.png', 'k40_3.5.png', 'k40_3.8.png']
                    elif folder_name == 'm18.4':
                        names = ['m18.4.1 2.png', 'm18.4.1.png', 'm18.4.2.png', 'm18.4.3.png']
                    for name in names:
                        (folder / name).touch()

        wrong_set = self.image_root / 'k18.1'
        wrong_set.mkdir()
        for index in range(3):
            (wrong_set / f'wrong{index}.png').touch()

    def test_builds_five_six_trial_sets_and_omits_invalid_images(self):
        face_test_data = _build_face_test_data(self.image_root)
        trials = face_test_data['trials']

        self.assertEqual(len(trials), 30)
        self.assertEqual({trial['set_number'] for trial in trials}, {1, 2, 3, 4, 5})
        self.assertTrue(all(len(trial['images']) == 3 for trial in trials))
        self.assertEqual(len(face_test_data['warmup_trials']), 1)
        self.assertEqual(len(face_test_data['warmup_trials'][0]), 3)
        self.assertTrue(all(image.startswith('k18.1/') for image in face_test_data['warmup_trials'][0]))
        self.assertFalse(any(image.startswith('k18.1/') for trial in trials for image in trial['images']))
        self.assertFalse(any(image.endswith('k40_3.1.png') for trial in trials for image in trial['images']))
        self.assertFalse(any(image.endswith('m18.4.1.png') for trial in trials for image in trial['images']))

        aliased_folder_trial = next(
            trial for trial in trials
            if trial['set_number'] == 4 and trial['gender'] == 'M' and trial['age_group'] == '2'
        )
        self.assertTrue(all(image.startswith('m30.4/') for image in aliased_folder_trial['images']))

    def test_rejects_a_folder_without_three_usable_images(self):
        folder = self.image_root / 'm18.2'
        (folder / 'face3.png').unlink()

        with self.assertRaisesRegex(ValueError, 'm18.2 musi zawierać 3 zdjęcia'):
            _build_face_test_data(self.image_root)


class LegacySchemaSqlTests(SimpleTestCase):
    def test_schema_contains_every_unmanaged_model_column(self):
        schema_path = Path(__file__).resolve().parents[1] / 'baza_danych.sql'
        schema = schema_path.read_text(encoding='utf-8').lower()
        for model in (Uzytkownik, Pacjent, Badanie, UstawieniaSystemu):
            table_start = schema.index(f'create table if not exists {model._meta.db_table.lower()}')
            table_end = schema.index(') engine=', table_start)
            table_definition = schema[table_start:table_end]
            for field in model._meta.local_fields:
                self.assertIn(field.column.lower(), table_definition)

        self.assertIn('auth_user_id', schema)
        self.assertIn('wyniki_json', schema)
        self.assertIn('test_type', schema)
        self.assertIn('auth_user_id int null unique', schema)


class WhiteNoiseStaticAssetTests(SimpleTestCase):
    def test_application_static_files_are_served_without_debug_mode(self):
        for asset in ('css/home.css', 'js/mqtt-joystick.js', 'js/paho-mqtt.min.js'):
            with self.subTest(asset=asset):
                response = self.client.get(f'/static/{asset}')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(b''.join(response.streaming_content))
                response.close()


class SaveResultsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        connection.disable_constraint_checking()
        try:
            with connection.schema_editor() as editor:
                editor.create_model(Uzytkownik)
                editor.create_model(Pacjent)
                editor.create_model(Badanie)
        finally:
            connection.enable_constraint_checking()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        connection.disable_constraint_checking()
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(Badanie)
                editor.delete_model(Pacjent)
                editor.delete_model(Uzytkownik)
        finally:
            connection.enable_constraint_checking()

    def setUp(self):
        self.user = User.objects.create_user(
            username='login-not-clinician-name',
            password='test-password-123',
            first_name='Ada',
        )
        self.profile = Uzytkownik.objects.create(
            id_uzytkownika=900,
            imie='Different first name',
            nazwisko='Tester',
            specjalista='klinicysta',
            auth_user=self.user,
        )
        self.patient = Pacjent.objects.create(
            imie='Test',
            nazwisko='Pacjent',
            data_urodzenia='2000-01-01',
            plec='Inna',
            id_prowadzacego=self.profile,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['wybrany_pacjent'] = self.patient.pk
        session.save()

    def test_saves_color_results_using_linked_profile_not_auth_user_id(self):
        response = self.client.post(
            reverse('zapisz_wyniki'),
            data=json.dumps({
                'czas': '00:01:30',
                'wynik_r': 12.5,
                'wynik_g': 18.0,
                'wynik_b': 22.0,
                'wynik_ogolny': 17.5,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        examination = Badanie.objects.get()
        self.assertEqual(examination.id_prowadzacego_id, self.profile.pk)
        self.assertNotEqual(examination.id_prowadzacego_id, self.user.pk)
        self.assertEqual(examination.id_wykonujacego_id, self.profile.pk)
        self.assertEqual(examination.test_type, 'kolory')
        self.assertIsNone(examination.wyniki_json)

    def test_saves_face_results_as_json(self):
        response = self.client.post(
            reverse('zapisz_wyniki'),
            data=json.dumps({'czas': '00:00:20', 'wynik_1': 3, 'wynik_ogolny': 75}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        examination = Badanie.objects.get()
        self.assertEqual(examination.test_type, 'twarze')
        self.assertEqual(json.loads(examination.wyniki_json)['wynik_1'], 3)

    def test_face_export_uses_the_visible_age_group_label(self):
        response = self.client.post(
            reverse('zapisz_wyniki'),
            data=json.dumps({'czas': '00:00:20', 'wynik_d': 2}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('export_wyniki'),
            {'test_name': 'Test twarzy'},
        )
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.content)) as workbook:
            worksheet = workbook.read('xl/worksheets/sheet1.xml')

        self.assertIn('Osoby młode'.encode('utf-8'), worksheet)
        self.assertNotIn(b'Dzieci', worksheet)

    def test_does_not_save_results_for_another_clinicians_patient(self):
        other_profile = Uzytkownik.objects.create(
            imie='Inny',
            nazwisko='Klinicysta',
            specjalista='klinicysta',
        )
        other_patient = Pacjent.objects.create(
            imie='Obcy',
            nazwisko='Pacjent',
            data_urodzenia='2001-01-01',
            plec='Inna',
            id_prowadzacego=other_profile,
        )
        session = self.client.session
        session['wybrany_pacjent'] = other_patient.pk
        session.save()

        response = self.client.post(
            reverse('zapisz_wyniki'),
            data=json.dumps({'wynik_1': 1}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Badanie.objects.exists())

    def test_create_clinician_command_is_idempotent(self):
        password = 'long-unique-demo-password-2026'
        with patch(
            'app.management.commands.create_clinician.getpass',
            side_effect=[password, password],
        ), patch('builtins.input', return_value=''):
            call_command(
                'create_clinician',
                username='created-once',
                first_name='New',
                last_name='Clinician',
            )

        call_command('create_clinician', username='created-once')

        self.assertEqual(User.objects.filter(username='created-once').count(), 1)
        self.assertEqual(
            Uzytkownik.objects.filter(auth_user__username='created-once').count(),
            1,
        )
        self.assertTrue(self.client.login(username='created-once', password=password))
