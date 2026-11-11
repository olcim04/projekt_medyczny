from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

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
