# Instalacja na Raspberry Pi 4 i Raspberry Pi 5

Instalator przygotowuje Django, MariaDB, statyczne pliki, usługę Gunicorn,
broker Mosquitto i lokalny hotspot Wi-Fi. Schemat aplikacyjny jest tworzony z
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

Pakiety (w tym `mosquitto`, `mosquitto-clients` i `nftables`), zależności Pythona,
migracje i `collectstatic` są przygotowywane przed aktywacją hotspotu. Instalator sprawdza model, architekturę i obsługę trybu AP
przez fizyczny interfejs Wi-Fi. Przerywa pracę, jeżeli sprzęt/sterownik nie
zgłasza trybu AP. Hotspot korzysta z WPA2-PSK i kanału 6 w paśmie 2,4 GHz.

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
CDN. Broker obsługuje kontroler przez TCP 1883 i przeglądarkę przez
WebSocket 9001. Sterowanie myszą i dotychczasowa obsługa klawiatury działają
także podczas niedostępności brokera.

Sprawdź usługi i pliki statyczne na Raspberry Pi:

```bash
sudo systemctl status mariadb projekt-medyczny NetworkManager dnsmasq mosquitto
curl -I http://127.0.0.1:8000
curl -I http://127.0.0.1:8000/static/css/home.css
curl -I http://127.0.0.1:8000/static/js/mqtt-joystick.js
nmcli connection show Badania_RPi
```

## 5. Restart i diagnostyka

```bash
sudo reboot
```

Po uruchomieniu system sam włącza MariaDB, hotspot, DHCP, Gunicorn i Mosquitto. Logi:

```bash
sudo journalctl -u projekt-medyczny -b
sudo journalctl -u mariadb -b
sudo journalctl -u dnsmasq -b
sudo journalctl -u NetworkManager -b
sudo journalctl -u mosquitto -b
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

## 6. Aktualizacja istniejącej instalacji do obsługi MQTT

Najpierw przenieś zaktualizowane pliki do katalogu projektu wskazanego przez
`WorkingDirectory` usługi `projekt-medyczny`. Jeśli aktualizacja jest już na
gałęzi Git używanej przez Raspberry Pi, pobierz ją przez `git pull --ff-only`.

```bash
cd /ścieżka/do/projekt_medyczny
sudo bash deploy/raspberry_pi/setup_mqtt.sh
sudo systemctl is-active mosquitto projekt-medyczny
```

Jeśli brakuje pakietów `mosquitto`, `mosquitto-clients` lub `nftables`, połącz
Pi tymczasowo z internetem, najlepiej przez Ethernet. Skrypt wykrywa interfejs
z istniejącego profilu `Badania_RPi`. Gdy nie może go ustalić, podaj
`--wifi-interface wlan0` z właściwą nazwą interfejsu.

Skrypt zapisuje konfigurację MQTT, włącza autostart brokera, restartuje go
i sprawdza TCP 1883 oraz uzgodnienie WebSocket MQTT na `/mqtt`. Następnie
wykonuje `collectstatic` jako użytkownik usługi i restartuje Gunicorna.
Aktualizacja korzysta z dotychczasowych danych, kont, ustawień Django i
profilu Wi-Fi. Po aktualizacji odśwież stronę badania.

## 7. Komunikacja ESP, Mosquitto i Django

FireBeetle 2 ESP32-C6 V1.2 łączy się z Wi-Fi `Badania_RPi` i używa MQTT
TCP pod `10.42.0.1:1883`. Przeglądarka otwiera aplikację Django na porcie
8000 i łączy się z tym samym brokerem przez `ws://10.42.0.1:9001/mqtt`
z podprotokołem `mqtt`. Django serwuje lokalną bibliotekę Paho JS
i wspólny moduł `mqtt-joystick.js`. Sterowanie w przeglądarce korzysta
z widocznej karty badania, która ma fokus.

| Temat | Wiadomość | Działanie w aplikacji |
| --- | --- | --- |
| `esp32/arcade` | `left`, `-1` | Krok suwaka w lewo lub poprzednia odpowiedź |
| `esp32/arcade` | `right`, `1` | Krok suwaka w prawo lub następna odpowiedź |
| `esp32/arcade` | `up`, `0` | Środek suwaka lub środkowa odpowiedź. Mapowanie `up` wymaga potwierdzenia na ESP |
| `esp32/arcade` | `zatwierdz`, `2` | Aktywny przycisk START lub DALEJ |
| `esp32/arcade` | `bateria: 3456` | Ostatnia odebrana wartość w statusie, bez przypisanej jednostki |
| `esp32/arcade` | `START`, `STOP`, `stop` | Odrębne komunikaty widoczne w konsoli diagnostycznej |
| `rpi/broadcast` | `START`, `STOP` | Ręczna publikacja z aplikacji w trybie diagnostycznym |
| `test/joystick` | Dotychczasowe wartości liczbowe lub JSON | Opcjonalna subskrypcja dla starszego nadawcy |

Moduł obsługuje też JSON, np. `{"value": -1}` lub `{"direction": "right"}`.
Dla kierunków i prefiksu baterii wielkość liter jest dowolna. W konfiguracji
`controlMessages` pisownia rozróżnia `START`, `STOP` i `stop`.
Włącz zgodność przez `subscribeLegacy: true` w `DEFAULT_CONFIG` wspólnego
modułu. W tym samym miejscu ustawisz port, temat, `directionMap` oraz
`confirmQuietPeriod` (domyślnie 500 ms ciszy między zatwierdzeniami MQTT).
Domyślny adres brokera pochodzi z adresu otwartej strony. Możliwe są także
nadpisania przez `window.MQTT_JOYSTICK_CONFIG` ustawione przed załadowaniem
modułu. Pakiety zachowane jako retained są pomijane.

Status brokera informuje o połączeniu przeglądarki. Status kontrolera zmienia
się po odebraniu rozpoznanej wiadomości w bieżącym połączeniu, także z
symulatora. Po utracie połączenia przeglądarka ponawia próbę i subskrypcje.
Po zakończeniu prób wynik zapisuje się dotychczasowym przyciskiem końcowym.

Dodaj `?mqtt_debug=1` do adresu otwartego badania, np.
`http://10.42.0.1:8000/info/test/?mqtt_debug=1`. Po rozwinięciu
**Diagnostyka MQTT** możesz ręcznie wysłać `START` lub `STOP` na
`rpi/broadcast`. Otwarcie i zamknięcie strony oraz przyciski badania
nie publikują tych wiadomości. Aplikacja nie subskrybuje tematu poleceń
wychodzących. Do prób używaj danych testowych.

### Broker i izolacja sieci

Instalator kopiuje `mosquitto.conf` do
`/etc/mosquitto/conf.d/99-projekt-medyczny.conf`. Reguły z `mosquitto.nft`
lądują w `/etc/mosquitto/projekt-medyczny-mqtt.nft`, a `mosquitto.service.conf`
jest instalowany jako plik rozszerzający usługę Mosquitto w
`/etc/systemd/system/mosquitto.service.d/90-projekt-medyczny.conf`.
Własna tabela nftables przepuszcza porty 1883 i 9001 przez loopback oraz
przez interfejs hotspotu z `10.42.0.0/24` do `10.42.0.1`. Systemd ładuje
filtr przed uruchomieniem brokera. Nasłuch działa, zanim hotspot ma adres,
i nie wymaga restartowania Mosquitto po ponownej aktywacji Wi-Fi.
Gunicorn uruchamia się niezależnie od brokera.

Tryb zgodności używa MQTT bez kont i szyfrowania protokołu. Każde urządzenie
dopuszczone do hotspotu może nasłuchiwać i publikować zdarzenia. Używaj go
wyłącznie w odizolowanej sieci, zabezpiecz hotspot hasłem WPA2-PSK i
udostępniaj hasło tylko zaufanym urządzeniom. Zachowaj reguły tej tabeli,
jeśli osobno zarządzasz zaporą. Jeśli konfiguracja zapory usuwa wszystkie
tabele przy przeładowaniu, uwzględnij tabelę MQTT w tym procesie. W przypadku
kolizji z istniejącą konfiguracją Mosquitto skrypt pozostawia pliki użytkownika.

## 8. Symulator i test trzech badań bez ESP

Zainstaluj zależność jednorazowo z dostępem do internetu. Później wystarczy
połączenie z Wi-Fi `Badania_RPi`.

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv-esp32
.\.venv-esp32\Scripts\python.exe -m pip install -r tools\requirements.txt
.\.venv-esp32\Scripts\python.exe tools\esp32_simulator.py --listen --delay 3
```

**Raspberry Pi**

```bash
python3 -m venv .venv-esp32
./.venv-esp32/bin/python -m pip install -r tools/requirements.txt
./.venv-esp32/bin/python tools/esp32_simulator.py --host 127.0.0.1 --listen
```

Opcje `--host`, `--port`, `--topic` zmieniają domyślne
`10.42.0.1:1883` i `esp32/arcade`. Przełącznik `--listen` pokazuje
wiadomości z `rpi/broadcast`. Każde uruchomienie używa osobnego ID MQTT.
Menu 1–4 wysyła kierunki i zatwierdzenie. Pozycja 5 wysyła baterię, 6 i 7
testują komunikaty diagnostyczne, a 0 kończy program.

Otwórz badanie dla pacjenta testowego. Na jednym komputerze użyj
`--delay 3`, wybierz pozycję w menu i wróć do karty badania przed publikacją.
Jeśli symulator działa na osobnym urządzeniu, pozostaw kartę badania
aktywną na komputerze pacjenta.

1. **Kolory.** Pozycja 4 uruchamia badanie. Sprawdź pozycje 1 i 2 (krok 5),
   pozycję 3 (środek 50), a następnie przejdź rozgrzewkę i 18 prób. Podczas
   pauzy kierunki i zatwierdzenie nie zmieniają stanu.
2. **Twarze.** Pozycja 4 przechodzi przez instrukcję. Podczas trzysekundowej
   prezentacji wyślij kierunek i zatwierdzenie. Opcje pojawią się po pełnym
   czasie. Kolejne zatwierdzenie wymaga wcześniejszego wyboru. Sprawdź
   przejęcie wyboru wskazanego myszą, powrót na środek oraz wyczyszczenie
   wyboru przy nowej próbie. Sprawdź rozgrzewkę i 30 właściwych prób.
3. **Ishihara.** Pozycja 4 przechodzi przez instrukcję. Na planszy sprawdź
   blokadę przed wyborem, użyj pozycji 1–3, a potem zatwierdź pozycją 4.
   Sprawdź blokadę podczas pauzy i po przejściu do nowej planszy.
4. W każdym badaniu pozycja 5 aktualizuje tylko status baterii. Pozycje 6/7
   nie przesuwają testu. Sprawdź też drugą kartę z innym badaniem oraz
   serię szybkich kierunków. Zakończ badanie przyciskiem interfejsu i
   sprawdź zapis wyniku oraz eksport z panelu pacjenta.

### Test bez symulatora i diagnostyka

W osobnych terminalach. Na Raspberry Pi możesz używać również `127.0.0.1`.

```bash
mosquitto_sub -h 10.42.0.1 -p 1883 -t esp32/arcade -t rpi/broadcast -v
mosquitto_pub -h 10.42.0.1 -p 1883 -t esp32/arcade -m left
mosquitto_pub -h 10.42.0.1 -p 1883 -t esp32/arcade -m zatwierdz
mosquitto_pub -h 10.42.0.1 -p 1883 -t esp32/arcade -m 'bateria: 3456'
```

Publikuj zdarzenia bez flagi `-r`. Otwórz tryb diagnostyczny, naciśnij
**Wyślij START** lub **Wyślij STOP** i sprawdź odbiór na `rpi/broadcast`
w symulatorze lub w `mosquitto_sub`.

```bash
sudo systemctl status mosquitto
sudo systemctl is-enabled mosquitto
sudo ss -ltnp '( sport = :1883 or sport = :9001 )'
sudo nft list table inet projekt_medyczny_mqtt
sudo journalctl -u mosquitto -b
sudo tail -n 50 /var/log/mosquitto/mosquitto.log
```

Port 1883 potwierdź publikacją i subskrypcją. Port 9001 sprawdź w narzędziach
przeglądarki w zakładce **Sieć → WS**. Połączenie z `/mqtt` powinno mieć
kod 101 i podprotokół `mqtt`. Aby sprawdzić ponowne połączenie, obserwuj
status na karcie testowej podczas `sudo systemctl restart mosquitto`.
Następnie wyślij nową wiadomość. Z konsoli lokalnej lub sesji Ethernet
sprawdź również `sudo nmcli connection down Badania_RPi`, a następnie
`sudo nmcli connection up Badania_RPi`. Po ponownym dołączeniu do Wi-Fi
przeglądarka powinna odzyskać połączenie bez restartowania Mosquitto.
Po restarcie Pi sprawdź autostart i obydwa porty z klienta hotspotu oraz
brak dostępu przez adres Pi w sieci Ethernet.

Testy automatyczne warstwy JavaScript bez zewnętrznych modułów uruchom
z katalogu projektu za pomocą `node --test tests/mqtt_joystick.test.cjs`.

## 9. Weryfikacja na fizycznym ESP i Raspberry Pi

- Na Pi uruchom `mosquitto_sub -h 127.0.0.1 -p 1883 -t esp32/arcade -t rpi/broadcast -v`.
  Podłącz ESP i w logu brokera sprawdź połączenie klienta
  `ESP32_klient_arcade_rpi4`. Zweryfikuj port, tematy i to, czy firmware
  wymaga uwierzytelniania.
- Po podłączeniu przycisków sprawdź treść publikacji każdego z nich,
  znaczenie `up` oraz zachowanie przy trzymaniu zatwierdzenia. Sprawdź
  też, czy firmware używa flagi retained.
- Zapisz przykładowe wiadomości baterii, ich częstotliwość i jednostkę.
  Sprawdź kierunek i znaczenie `START`, `STOP` oraz `stop` przed
  włączeniem ich do pracy z pacjentem.
- Na każdym modelu Pi potwierdź tryb AP, DHCP, dostęp offline do aplikacji,
  autostart, restart hotspotu, izolację portów, zapis badania i eksport.
