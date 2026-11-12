#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="/etc/projekt_medyczny.env"
SERVICE_FILE="/etc/systemd/system/projekt-medyczny.service"
SSID="Badania_RPi"
HOTSPOT_NAME="Badania_RPi"
DB_NAME="projekt_medyczny"
DB_USER="projekt_medyczny"

fail() {
    printf 'BŁĄD: %s\n' "$*" >&2
    exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
    fail "Uruchom instalator przez sudo: sudo bash deploy/raspberry_pi/install.sh"
fi
for required_tool in apt-get systemctl runuser; do
    command -v "$required_tool" >/dev/null 2>&1 ||
        fail "Wymagane narzędzie nie jest dostępne: $required_tool."
done

[[ -f "$PROJECT_DIR/manage.py" ]] || fail "Nie znaleziono manage.py w $PROJECT_DIR."
[[ -f "$PROJECT_DIR/requirements.txt" ]] || fail "Nie znaleziono requirements.txt."
[[ -f "$PROJECT_DIR/baza_danych.sql" ]] || fail "Nie znaleziono baza_danych.sql."
[[ -f "$PROJECT_DIR/deploy/raspberry_pi/projekt-medyczny.service" ]] ||
    fail "Nie znaleziono szablonu usługi systemd."
[[ -f /etc/os-release ]] || fail "Nie można rozpoznać systemu operacyjnego."

if [[ -z "${SUDO_USER:-}" || "$SUDO_USER" == "root" ]]; then
    fail "Uruchom instalator z konta użytkownika Raspberry Pi przez sudo."
fi
APP_USER="$SUDO_USER"
id "$APP_USER" >/dev/null 2>&1 || fail "Nie znaleziono użytkownika $APP_USER."
APP_GROUP="$(id -gn "$APP_USER")"

source /etc/os-release
MODEL_FILE="/proc/device-tree/model"
[[ -r "$MODEL_FILE" ]] || MODEL_FILE="/sys/firmware/devicetree/base/model"
MODEL="$(tr -d '\000' < "$MODEL_FILE" 2>/dev/null || true)"
case "$MODEL" in
    *"Raspberry Pi 4"*|*"Raspberry Pi 5"*) ;;
    *) fail "Obsługiwane są Raspberry Pi 4 i 5; wykryto: ${MODEL:-nieznany model}." ;;
esac

case "$(uname -m)" in
    aarch64|armv7l) ;;
    *) fail "Nieobsługiwana architektura $(uname -m); użyj 64-bitowego lub 32-bitowego Raspberry Pi OS." ;;
esac

if [[ ! -f /etc/rpi-issue && "${PRETTY_NAME:-}" != *"Raspberry Pi"* ]]; then
    fail "Wymagany jest Raspberry Pi OS. Wykryto: ${PRETTY_NAME:-nieznany system}."
fi

if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 10 -o /dev/null https://deb.debian.org/ ||
        fail "Brak połączenia z internetem. Połącz Raspberry Pi z internetem i uruchom instalator ponownie."
elif command -v python3 >/dev/null 2>&1; then
    python3 -c "from urllib.request import urlopen; urlopen('https://deb.debian.org/', timeout=10).close()" ||
        fail "Brak połączenia z internetem. Połącz Raspberry Pi z internetem i uruchom instalator ponownie."
else
    fail "Brak curl i Python 3; nie można sprawdzić połączenia z internetem."
fi

printf 'Wykryto: %s (%s), użytkownik aplikacji: %s\n' "$MODEL" "$(uname -m)" "$APP_USER"
printf 'Instalacja NetworkManager może przerwać bieżące połączenie Wi-Fi lub SSH.\n'
if [[ ! -t 0 ]]; then
    fail "Instalator wymaga terminala do potwierdzenia zmian sieci."
fi
read -r -p "Kontynuować instalację? [t/N] " CONFIRM_INSTALL
case "$CONFIRM_INSTALL" in
    t|T|tak|TAK|y|Y|yes|YES) ;;
    *) printf 'Instalacja anulowana.\n'; exit 0 ;;
esac

printf 'Instalowanie pakietów systemowych (wymagane połączenie z internetem)...\n'
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    curl \
    dnsmasq \
    git \
    iw \
    libmariadb-dev \
    libmariadb-dev-compat \
    mariadb-server \
    network-manager \
    openssl \
    pkg-config \
    python3 \
    python3-dev \
    python3-venv \
    rfkill

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' ||
    fail "Python $PYTHON_VERSION jest za stary; wymagany jest Python 3.10 lub nowszy."
command -v nmcli >/dev/null 2>&1 || fail "NetworkManager (nmcli) nie został zainstalowany."
command -v iw >/dev/null 2>&1 || fail "Narzędzie iw nie zostało zainstalowane."
command -v mariadb >/dev/null 2>&1 || fail "Klient MariaDB nie został zainstalowany."
command -v dnsmasq >/dev/null 2>&1 || fail "dnsmasq nie został zainstalowany."
command -v systemd-analyze >/dev/null 2>&1 || fail "systemd-analyze nie jest dostępny."
command -v openssl >/dev/null 2>&1 || fail "openssl nie został zainstalowany."

WIFI_IFACE="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2 == "wifi" { print $1; exit }')"
[[ -n "$WIFI_IFACE" ]] || fail "Nie znaleziono interfejsu Wi-Fi. Sprawdź sprzęt oraz rfkill."
WIFI_PHY="$(iw dev "$WIFI_IFACE" info | awk '$1 == "wiphy" { print "phy" $2; exit }')"
[[ -n "$WIFI_PHY" ]] || fail "Nie można odczytać fizycznego interfejsu Wi-Fi $WIFI_IFACE."
if ! iw phy "$WIFI_PHY" info |
    sed -n '/Supported interface modes:/,/Band [0-9]/p' |
    grep -Eq '^[[:space:]]*\*[[:space:]]+AP([[:space:]]|$)'; then
    fail "Interfejs $WIFI_IFACE ($WIFI_PHY) nie zgłasza obsługi trybu AP."
fi

VENV="$PROJECT_DIR/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
    [[ ! -e "$VENV" ]] || fail "$VENV istnieje, ale nie jest prawidłowym środowiskiem Linux. Nie usunięto go; przenieś lub zmień jego nazwę."
    runuser -u "$APP_USER" -- python3 -m venv "$VENV"
fi
runuser -u "$APP_USER" -- "$VENV/bin/python" -m pip install --upgrade pip
runuser -u "$APP_USER" -- "$VENV/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"

DB_PASSWORD=""
DJANGO_SECRET_KEY=""
if [[ -f "$ENV_FILE" ]]; then
    DB_PASSWORD="$(sed -n 's/^DB_PASSWORD=//p' "$ENV_FILE" | head -n 1)"
    DJANGO_SECRET_KEY="$(sed -n 's/^DJANGO_SECRET_KEY=//p' "$ENV_FILE" | head -n 1)"
fi
[[ -n "$DB_PASSWORD" ]] || DB_PASSWORD="$(openssl rand -hex 24)"
[[ -n "$DJANGO_SECRET_KEY" ]] || DJANGO_SECRET_KEY="$(openssl rand -hex 50)"

TMP_ENV="$(mktemp /etc/projekt_medyczny.env.XXXXXX)"
chmod 0600 "$TMP_ENV"
cat > "$TMP_ENV" <<EOF
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,10.42.0.1
CSRF_TRUSTED_ORIGINS=http://127.0.0.1,http://localhost,http://10.42.0.1:8000
DB_ENGINE=django.db.backends.mysql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306
EOF
chown "root:$APP_GROUP" "$TMP_ENV"
chmod 0640 "$TMP_ENV"
mv -f "$TMP_ENV" "$ENV_FILE"
unset DJANGO_SECRET_KEY

systemctl enable --now mariadb
mariadb --protocol=socket -uroot <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
unset DB_PASSWORD

run_project_python() {
    runuser -u "$APP_USER" -- env PROJEKT_MEDYCZNY_ENV_FILE="$ENV_FILE" \
        "$VENV/bin/python" "$PROJECT_DIR/manage.py" "$@"
}

run_project_python migrate --noinput
run_project_python initialize_legacy_schema
run_project_python collectstatic --noinput
run_project_python check
for asset in css/home.css js/mqtt-joystick.js testimg/1test.png; do
    [[ -s "$PROJECT_DIR/staticfiles/$asset" ]] ||
        fail "collectstatic nie wygenerował pliku $asset."
done

escape_sed_replacement() {
    printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}
sed \
    -e "s|@APP_USER@|$(escape_sed_replacement "$APP_USER")|g" \
    -e "s|@APP_GROUP@|$(escape_sed_replacement "$APP_GROUP")|g" \
    -e "s|@PROJECT_DIR@|$(escape_sed_replacement "$PROJECT_DIR")|g" \
    "$PROJECT_DIR/deploy/raspberry_pi/projekt-medyczny.service" > "$SERVICE_FILE"
chmod 0644 "$SERVICE_FILE"
systemd-analyze verify "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable --now projekt-medyczny.service
systemctl restart projekt-medyczny.service

systemctl enable --now NetworkManager

printf '\nOSTRZEŻENIE: konfiguracja i aktywacja hotspotu może odłączyć Raspberry Pi od internetu\n'
printf 'oraz przerwać bieżącą sesję SSH. Wszystkie pobieranie pakietów i migracje są już zakończone.\n'
if [[ ! -t 0 ]]; then
    fail "Instalator wymaga terminala do potwierdzenia zmiany sieci i ustawienia hasła hotspotu."
fi
read -r -p "Kontynuować konfigurację Wi-Fi? [t/N] " CONFIRM_NETWORK
case "$CONFIRM_NETWORK" in
    t|T|tak|TAK|y|Y|yes|YES) ;;
    *)
        printf 'Aplikacja została zainstalowana. Hotspot nie został skonfigurowany; uruchom instalator ponownie, aby dokończyć.\n'
        exit 0
        ;;
esac

while true; do
    read -r -s -p "Hasło sieci Wi-Fi $SSID (8-63 znaków): " WIFI_PASSWORD
    printf '\n'
    read -r -s -p "Powtórz hasło: " WIFI_PASSWORD_CONFIRM
    printf '\n'
    [[ "$WIFI_PASSWORD" == "$WIFI_PASSWORD_CONFIRM" ]] || {
        printf 'Hasła nie są takie same.\n' >&2
        continue
    }
    [[ "${#WIFI_PASSWORD}" -ge 8 && "${#WIFI_PASSWORD}" -le 63 ]] || {
        printf 'Hasło musi mieć od 8 do 63 znaków.\n' >&2
        continue
    }
    break
done

PROFILE_UUIDS="$(nmcli -g UUID connection show "$HOTSPOT_NAME" 2>/dev/null || true)"
[[ "$PROFILE_UUIDS" != *$'\n'* ]] ||
    fail "Znaleziono kilka profili NetworkManager o nazwie $HOTSPOT_NAME; nie zmieniono ich."
PROFILE_UUID="$PROFILE_UUIDS"
if ! grep -Eq '^[[:space:]]*conf-dir=/etc/dnsmasq.d' /etc/dnsmasq.conf; then
    printf '\n# Added by projekt_medyczny installer\nconf-dir=/etc/dnsmasq.d,.dpkg-dist,.dpkg-old,.dpkg-new\n' >> /etc/dnsmasq.conf
fi
if [[ -n "$PROFILE_UUID" ]]; then
    PROFILE_TYPE="$(nmcli -g connection.type connection show "$PROFILE_UUID")"
    PROFILE_SSID="$(nmcli -g 802-11-wireless.ssid connection show "$PROFILE_UUID" 2>/dev/null || true)"
    [[ "$PROFILE_TYPE" == "802-11-wireless" && "$PROFILE_SSID" == "$SSID" ]] ||
        fail "Istnieje inne połączenie NetworkManager o nazwie $HOTSPOT_NAME. Nie zmieniono go."
    nmcli connection modify "$PROFILE_UUID" \
        connection.interface-name "$WIFI_IFACE" \
        connection.autoconnect yes \
        connection.autoconnect-priority 100 \
        802-11-wireless.mode ap \
        802-11-wireless.band bg \
        802-11-wireless.channel 6 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$WIFI_PASSWORD" \
        ipv4.method manual \
        ipv4.addresses 10.42.0.1/24 \
        ipv4.never-default yes \
        ipv6.method disabled
else
    nmcli connection add type wifi ifname "$WIFI_IFACE" con-name "$HOTSPOT_NAME" ssid "$SSID" \
        802-11-wireless.mode ap \
        802-11-wireless.band bg \
        802-11-wireless.channel 6 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$WIFI_PASSWORD" \
        ipv4.method manual \
        ipv4.addresses 10.42.0.1/24 \
        ipv4.never-default yes \
        ipv6.method disabled \
        connection.autoconnect yes \
        connection.autoconnect-priority 100
    PROFILE_UUID="$(nmcli -g UUID connection show "$HOTSPOT_NAME" | head -n 1)"
fi
unset WIFI_PASSWORD WIFI_PASSWORD_CONFIRM

install -d -m 0755 /etc/dnsmasq.d
DHCP_CONFIG="/etc/dnsmasq.d/99-badania-rpi.conf"
if [[ -e "$DHCP_CONFIG" ]] &&
    ! head -n 1 "$DHCP_CONFIG" | grep -qx '# Managed by projekt_medyczny installer'; then
    fail "$DHCP_CONFIG istnieje i nie jest zarządzany przez ten instalator; nie nadpisano pliku."
fi
TMP_DHCP_CONFIG="$(mktemp /etc/dnsmasq.d/99-badania-rpi.conf.XXXXXX)"
cat > "$TMP_DHCP_CONFIG" <<EOF
# Managed by projekt_medyczny installer
interface=$WIFI_IFACE
bind-dynamic
except-interface=lo
port=0
no-resolv
dhcp-authoritative
dhcp-range=10.42.0.20,10.42.0.200,255.255.255.0,12h
dhcp-option=3
dhcp-leasefile=/var/lib/misc/badania-rpi.leases
EOF
chmod 0644 "$TMP_DHCP_CONFIG"
mv -f "$TMP_DHCP_CONFIG" "$DHCP_CONFIG"
if [[ ! -e /var/lib/misc/badania-rpi.leases ]]; then
    install -o dnsmasq -g nogroup -m 0640 /dev/null /var/lib/misc/badania-rpi.leases
fi

dnsmasq --test --conf-file=/etc/dnsmasq.conf
systemctl daemon-reload
systemctl enable --now dnsmasq
systemctl restart dnsmasq
nmcli radio wifi on
nmcli connection modify "$PROFILE_UUID" connection.autoconnect yes
systemctl is-active --quiet mariadb ||
    fail "MariaDB nie działa."
systemctl is-active --quiet projekt-medyczny.service ||
    fail "Usługa Django nie działa."
systemctl is-active --quiet dnsmasq ||
    fail "Usługa DHCP dnsmasq nie działa."
systemctl is-enabled --quiet projekt-medyczny.service ||
    fail "Usługa Django nie ma włączonego autostartu."
systemctl is-enabled --quiet dnsmasq ||
    fail "Usługa DHCP dnsmasq nie ma włączonego autostartu."
nmcli -g connection.autoconnect connection show "$PROFILE_UUID" | grep -qx yes ||
    fail "Profil hotspotu nie ma włączonego autostartu."

printf '\nHotspot Wi-Fi jest skonfigurowany: SSID %s, adres 10.42.0.1/24.\n' "$SSID"
printf 'DHCP przydziela adresy lokalnie; nie jest ogłaszana brama internetowa.\n'
printf 'Aplikacja: http://10.42.0.1:8000\n'
printf 'Usługi: sudo systemctl status projekt-medyczny mariadb dnsmasq\n'
printf 'Aktywuję hotspot. Bieżące połączenie sieciowe może zostać przerwane.\n'
nmcli connection up "$PROFILE_UUID"
