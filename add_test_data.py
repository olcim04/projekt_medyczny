import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from app.models import Pacjent, Badanie, Uzytkownik
from datetime import date, time
import random

# Pobranie klinicysty
prowadzacy = Uzytkownik.objects.get(imie='Jan')

# Dodawanie pacjentów
pacjenci_data = [
    ('Anna', 'Nowak', date(1990, 1, 15), 'K', '12345678901'),
    ('Piotr', 'Zieliński', date(1985, 5, 20), 'M', '98765432109'),
    ('Maria', 'Lewkowska', date(1992, 3, 10), 'K', '55555555555'),
    ('Jan', 'Mazur', date(1988, 7, 25), 'M', '11111111111'),
]

for imie, nazwisko, data_ur, plec, doc in pacjenci_data:
    if not Pacjent.objects.filter(imie=imie, nazwisko=nazwisko).exists():
        Pacjent.objects.create(
            imie=imie,
            nazwisko=nazwisko,
            data_urodzenia=data_ur,
            plec=plec,
            id_prowadzacego=prowadzacy,
            numer_dokumentu=doc
        )
        print(f'Dodany pacjent: {imie} {nazwisko}')

# Dodawanie przykładowych wyników badań
pacjenci = Pacjent.objects.filter(id_prowadzacego=prowadzacy)
for pacjent in pacjenci:
    if not Badanie.objects.filter(id_pacjenta=pacjent).exists():
        Badanie.objects.create(
            id_pacjenta=pacjent,
            id_prowadzacego=prowadzacy,
            data_badania=date.today(),
            czas_trwania=time(0, random.randint(5, 15), random.randint(0, 59)),
            wynik_ogolny=round(random.uniform(70, 95), 2),
            wynik_r=round(random.uniform(60, 90), 2),
            wynik_g=round(random.uniform(65, 92), 2),
            wynik_b=round(random.uniform(70, 95), 2)
        )
        print(f'Dodany wynik dla pacjenta: {pacjent.imie} {pacjent.nazwisko}')

print('Gotowe!')
