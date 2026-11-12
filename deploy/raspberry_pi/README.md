# Instalacja na Raspberry Pi 4 i Raspberry Pi 5

Instalator przygotowuje Django, MariaDB, statyczne pliki, usługę Gunicorn i
lokalny hotspot Wi-Fi. Schemat aplikacyjny jest tworzony z
[`baza_danych.sql`](../../baza_danych.sql), a brakujące kolumny `BADANIE`
uzupełniane wyłącznie przez bezpieczne operacje dodające. Migracje Django
tworzą tabele `auth_*`, sesje i pozostałe tabele Django. Instalacja nie tworzy
pacjentów ani przykładowych wyników.
Modele aplikacji mają `managed = False`; `app/migrations/0001_initial.py`
rejestruje jedynie stan modeli i nie tworzy ich tabel. Za tabele własne odpowiada
wywoływany przez instalator `initialize_legacy_schema`.

## 1. Przygotowanie karty microSD

1. Zainstaluj **Raspberry Pi Imager** na komputerze.
2. Wybierz Raspberry Pi 4 lub Raspberry Pi 5 i Raspberry Pi OS Lite 64-bit
   (Bookworm lub nowszy, z Pythonem 3.10+).
3. W ustawieniach Imagera ustaw nazwę użytkownika i hasło. Włącz SSH tylko,
   jeśli jest potrzebne, oraz skonfiguruj dostęp do internetu do pobrania
   pakietów.
4. Zapisz obraz na karcie microSD, włóż kartę do Raspberry Pi i uruchom
   urządzenie.

Możesz użyć połączenia Ethernet albo Wi-Fi. Instalowanie NetworkManager może
przerwać połączenie Wi-Fi/SSH. Najpewniejsza jest instalacja z monitorem i
klawiaturą albo przez Ethernet.

## 2. Pobranie projektu i instalacja

Zaloguj się do Raspberry Pi jako utworzony użytkownik i w terminalu wykonaj:

```bash
git clone https://github.com/olcim04/projekt_medyczny.git
cd projekt_medyczny
sudo bash deploy/raspberry_pi/install.sh
```

W trakcie instalacji:

- potwierdź ostrzeżenie o możliwej utracie połączenia z internetem/SSH;
- ustaw i potwierdź hasło hotspotu `Badania_RPi` (8–63 znaki);
- nie zamykaj zasilania w trakcie instalacji.

Pakiety, zależności Pythona, migracje i `collectstatic` są wykonywane przed
aktywacją hotspotu. Instalator sprawdza model, architekturę i obsługę trybu AP
przez fizyczny interfejs Wi-Fi. Przerywa pracę, jeżeli sprzęt/sterownik nie
zgłasza trybu AP. Hotspot korzysta z kanału 6 w paśmie 2,4 GHz.

Instalator tworzy `.venv` dla systemu Raspberry Pi; środowiska `venv` z Windows
nie są kopiowane. Hasła bazy i `SECRET_KEY` są generowane przy instalacji i
zapisywane w `/etc/projekt_medyczny.env` (bez haseł w repozytorium). Hasło
hotspotu zapisuje NetworkManager. Baza danych i jej istniejące rekordy nie są
usuwane przy ponownym uruchomieniu instalatora.

## 3. Konta użytkowników i dane testowe

Po instalacji możesz utworzyć konto klinicysty:

```bash
./.venv/bin/python create_users.py
```

Skrypt poprosi o login, imię i nazwisko oraz dwukrotnie o hasło (wprowadzane
hasło nie jest wyświetlane). Możesz wskazać ID istniejącego, niepowiązanego
profilu `UZYTKOWNIK` albo utworzyć nowy profil. Powiązanie jest zapisywane
jednoznacznie przez `UZYTKOWNIK.auth_user_id`; login nie musi odpowiadać imieniu.
Ponowne uruchomienie dla istniejącego loginu nie zmienia jego hasła ani nie
tworzy duplikatu profilu. Dla istniejącego użytkownika z profilem użyj tego
samego loginu.

Konto administratora Django (panel `/admin/`) utworzysz oddzielnie:

```bash
./.venv/bin/python manage.py createsuperuser
```

Przykładowe dane medyczne są opcjonalne i nie są tworzone podczas instalacji.
Jeśli potrzebujesz ich wyłącznie do testów, użyj:

```bash
./.venv/bin/python add_test_data.py --username LOGIN --confirm-demo-data
```

Nie używaj przykładowych danych ani haseł testowych w pracy z prawdziwymi
pacjentami.

## 4. Połączenie z aplikacją

1. Na telefonie lub laptopie połącz się z Wi-Fi **Badania_RPi**.
2. Wpisz ustawione podczas instalacji hasło.
3. Otwórz **http://10.42.0.1:8000** i zaloguj się utworzonym kontem.

Sieć przydziela adresy DHCP z podsieci `10.42.0.0/24`, ale nie ogłasza bramy
ani serwera DNS. Zapewnia dostęp lokalny do aplikacji bez przekazywania ruchu
klientów do internetu.

Biblioteka Paho używana przez testy jest serwowana lokalnie, więc nie wymaga
CDN. Kod aplikacji nie konfiguruje jednak brokera MQTT; zewnętrzny kontroler
MQTT wymaga brokera WebSocket dostępnego w tej samej sieci na porcie 9001.
Sterowanie klawiaturą działa bez tego brokera.

Sprawdź usługi i pliki statyczne na Raspberry Pi:

```bash
sudo systemctl status mariadb projekt-medyczny NetworkManager dnsmasq
curl -I http://127.0.0.1:8000
curl -I http://127.0.0.1:8000/static/css/home.css
curl -I http://127.0.0.1:8000/static/js/mqtt-joystick.js
nmcli connection show Badania_RPi
```

## 5. Restart i diagnostyka

```bash
sudo reboot
```

Po uruchomieniu system sam włącza MariaDB, hotspot, DHCP i Gunicorn. Logi:

```bash
sudo journalctl -u projekt-medyczny -b
sudo journalctl -u mariadb -b
sudo journalctl -u dnsmasq -b
sudo journalctl -u NetworkManager -b
```

Jeśli hotspot nie działa, sprawdź też:

```bash
iw list
nmcli device status
nmcli connection show Badania_RPi
rfkill list
```

Jeżeli Pi nie zgłasza trybu AP lub NetworkManager nie może aktywować profilu,
nie próbuj wymuszać połączenia. Sprawdź aktualizacje Raspberry Pi OS, blokadę
rfkill, sterownik Wi-Fi i logi. Pi 4 i Pi 5 mają różne moduły/sterowniki;
faktyczna obsługa AP jest sprawdzana na konkretnym urządzeniu przez instalator.

## 6. Aktualizacja bez utraty danych

W katalogu repozytorium:

```bash
git pull --ff-only
sudo bash deploy/raspberry_pi/install.sh
```

Instalator ponownie używa tych samych haseł zapisanych w `/etc`, aktualizuje
pakiety aplikacji, uruchamia nowe migracje, ponownie zbiera pliki statyczne i
restartuje usługi. Nie usuwa tabel, nie kasuje rekordów i nie odtwarza bazy z
pliku SQL. Nie uruchamiaj `flush`, `dbshell` z poleceniami kasującymi ani
destrukcyjnych migracji, jeśli nie masz kopii zapasowej.

## Co sprawdzić na urządzeniu

Nie wykonano testów na fizycznym Raspberry Pi. Przed użyciem sprawdź na każdym
modelu: obsługę AP na dostarczonym systemie/sterowniku, przydzielanie adresów
DHCP, dostęp do strony bez internetu, pliki CSS/JavaScript, zapis badania,
autostart po restarcie i logi systemd.
