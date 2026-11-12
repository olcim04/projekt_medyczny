import argparse
import os
import random
from datetime import date, time

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

from app.models import Badanie, Pacjent, Uzytkownik


def main():
    parser = argparse.ArgumentParser(description='Add fictional data for local testing only.')
    parser.add_argument('--username', required=True, help='Login linked to the clinician profile.')
    parser.add_argument(
        '--confirm-demo-data',
        action='store_true',
        help='Confirm that the target database is not being used for real patient data.',
    )
    args = parser.parse_args()
    if not args.confirm_demo_data:
        parser.error('Dodawanie danych wymaga flagi --confirm-demo-data.')

    user = User.objects.get(username=args.username)
    prowadzacy = Uzytkownik.objects.get(auth_user=user)
    pacjenci_data = [
        ('Pacjent', 'Testowy 1', date(1990, 1, 15), 'K', 'DEMO-001'),
        ('Pacjent', 'Testowy 2', date(1985, 5, 20), 'M', 'DEMO-002'),
        ('Pacjent', 'Testowy 3', date(1992, 3, 10), 'K', 'DEMO-003'),
        ('Pacjent', 'Testowy 4', date(1988, 7, 25), 'M', 'DEMO-004'),
    ]

    for imie, nazwisko, data_urodzenia, plec, numer_dokumentu in pacjenci_data:
        Pacjent.objects.get_or_create(
            id_prowadzacego=prowadzacy,
            imie=imie,
            nazwisko=nazwisko,
            defaults={
                'data_urodzenia': data_urodzenia,
                'plec': plec,
                'numer_dokumentu': numer_dokumentu,
            },
        )

    for pacjent in Pacjent.objects.filter(id_prowadzacego=prowadzacy):
        if not Badanie.objects.filter(id_pacjenta=pacjent).exists():
            Badanie.objects.create(
                id_pacjenta=pacjent,
                id_prowadzacego=prowadzacy,
                data_badania=date.today(),
                czas_trwania=time(0, random.randint(5, 15), random.randint(0, 59)),
                wynik_ogolny=round(random.uniform(70, 95), 2),
                wynik_r=round(random.uniform(60, 90), 2),
                wynik_g=round(random.uniform(65, 92), 2),
                wynik_b=round(random.uniform(70, 95), 2),
                test_type='kolory',
            )

    print('Dodano/zweryfikowano fikcyjne dane testowe. Nie używaj ich w produkcji.')


if __name__ == '__main__':
    main()
