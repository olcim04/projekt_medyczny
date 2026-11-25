#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
MARKER='# Managed by projekt_medyczny MQTT setup'
MAIN_CONFIG=/etc/mosquitto/mosquitto.conf
BROKER_CONFIG=/etc/mosquitto/conf.d/99-projekt-medyczny.conf
FIREWALL_CONFIG=/etc/mosquitto/projekt-medyczny-mqtt.nft
SYSTEMD_DROPIN=/etc/systemd/system/mosquitto.service.d/90-projekt-medyczny.conf
WIFI_IFACE=
BROKER_ONLY=false

fail() {
    printf 'BŁĄD: %s\n' "$*" >&2
    exit 1
}

while (( $# )); do
    case "$1" in
        --wifi-interface)
            (( $# >= 2 )) || fail "Podaj nazwę interfejsu po --wifi-interface."
            WIFI_IFACE="$2"
            shift ;;
        --broker-only) BROKER_ONLY=true ;;
        -h|--help)
            printf 'Użycie: sudo bash %s [--wifi-interface wlan0] [--broker-only]\n' "$0"
            exit 0 ;;
        *) fail "Nieznany argument: $1." ;;
    esac
    shift
done
(( EUID == 0 )) || fail "Uruchom skrypt przez sudo."

if [[ -z "$WIFI_IFACE" ]]; then
    WIFI_IFACE="$(nmcli -g connection.interface-name connection show id Badania_RPi 2>/dev/null || true)"
    if [[ -z "$WIFI_IFACE" || "$WIFI_IFACE" == "--" ]]; then
        WIFI_IFACE="$(nmcli -g GENERAL.DEVICES connection show id Badania_RPi 2>/dev/null || true)"
    fi
fi
[[ "$WIFI_IFACE" =~ ^[[:alnum:]_.-]{1,15}$ ]] && [[ -d "/sys/class/net/$WIFI_IFACE" ]] &&
    [[ "$(nmcli -g GENERAL.TYPE device show "$WIFI_IFACE")" == "wifi" ]] ||
    fail "Nie znaleziono interfejsu Wi-Fi hotspotu. Podaj go przez --wifi-interface."

if ! $BROKER_ONLY; then
    APP_USER="$(systemctl show -p User --value projekt-medyczny.service)"
    APP_DIR="$(systemctl show -p WorkingDirectory --value projekt-medyczny.service)"
    [[ -n "$APP_USER" && "$APP_DIR" == "$PROJECT_DIR" && -x "$APP_DIR/.venv/bin/python" ]] ||
        fail "Uruchom skrypt z katalogu działającej instalacji Django wskazanej w projekt-medyczny.service."
fi

if ! command -v mosquitto >/dev/null || ! command -v mosquitto_pub >/dev/null ||
    ! command -v mosquitto_sub >/dev/null || ! command -v nft >/dev/null; then
    printf 'Brak pakietów MQTT lub nftables. Podłącz Raspberry Pi tymczasowo do internetu.\n'
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y mosquitto mosquitto-clients nftables
fi

configs=("$BROKER_CONFIG" "$FIREWALL_CONFIG" "$SYSTEMD_DROPIN")
for file in "${configs[@]}"; do
    if [[ -e "$file" || -L "$file" ]]; then
        [[ ! -L "$file" && -f "$file" && "$(head -n 1 -- "$file")" == "$MARKER" ]] ||
            fail "$file należy do istniejącej konfiguracji. Plik nie został nadpisany."
    fi
done

[[ -r "$MAIN_CONFIG" ]] &&
    grep -Eq '^[[:space:]]*include_dir[[:space:]]+/etc/mosquitto/conf\.d/?[[:space:]]*$' "$MAIN_CONFIG" ||
    fail "Konfiguracja Mosquitto musi wczytywać /etc/mosquitto/conf.d."

existing=("$MAIN_CONFIG")
for file in /etc/mosquitto/conf.d/*.conf; do
    if [[ -f "$file" && "$file" != "$BROKER_CONFIG" ]]; then existing+=("$file"); fi
done
awk '
    $1 == "include_dir" && $2 !~ /^\/etc\/mosquitto\/conf\.d\/?$/ { conflict = 1 }
    $1 ~ /^(listener|port)$/ && $2 ~ /^(1883|9001)$/ { conflict = 1 }
    $1 == "per_listener_settings" && $2 == "true" { per_listener = 1 }
    $1 == "per_listener_settings" && $2 != "true" { conflict = 1 }
    $1 ~ /^(allow_anonymous|allow_zero_length_clientid|auto_id_prefix|acl_file|password_file|psk_file|plugin|auth_plugin)$/ { auth = 1 }
    END { exit (conflict || (auth && !per_listener)) }
' "${existing[@]}" ||
    fail "Istniejąca konfiguracja Mosquitto koliduje z portami lub ustawieniami dostępu MQTT. Zachowano ją bez zmian."

stage_dir="$(mktemp -d)"
cleanup() {
    rm -f -- "$stage_dir"/{firewall,old-broker,old-firewall,old-dropin}
    rmdir -- "$stage_dir"
}
trap cleanup EXIT
sed "s/@WIFI_IFACE@/$WIFI_IFACE/" "$SCRIPT_DIR/mosquitto.nft" > "$stage_dir/firewall"
nft -c -f "$stage_dir/firewall" || fail "Nie można załadować reguł nftables dla MQTT."
[[ ! -f "$BROKER_CONFIG" ]] || cp -p "$BROKER_CONFIG" "$stage_dir/old-broker"
[[ ! -f "$FIREWALL_CONFIG" ]] || cp -p "$FIREWALL_CONFIG" "$stage_dir/old-firewall"
[[ ! -f "$SYSTEMD_DROPIN" ]] || cp -p "$SYSTEMD_DROPIN" "$stage_dir/old-dropin"

restore_config() {
    if [[ -f "$stage_dir/$1" ]]; then
        install -m 0644 "$stage_dir/$1" "$2"
    else
        rm -f -- "$2"
    fi
}

rollback() {
    restore_config old-broker "$BROKER_CONFIG"
    restore_config old-firewall "$FIREWALL_CONFIG"
    restore_config old-dropin "$SYSTEMD_DROPIN"
    systemctl daemon-reload
    systemctl restart mosquitto.service
    if [[ -f "$FIREWALL_CONFIG" ]]; then
        nft -f "$FIREWALL_CONFIG"
    elif nft list table inet projekt_medyczny_mqtt >/dev/null 2>&1; then
        nft delete table inet projekt_medyczny_mqtt
    fi
}

probe_broker() {
    python3 - <<'PYTHON'
from http.client import HTTPConnection
from socket import create_connection
from time import sleep

for attempt in range(10):
    conn = HTTPConnection("127.0.0.1", 9001, timeout=2)
    try:
        with create_connection(("127.0.0.1", 1883), timeout=2):
            pass
        conn.request("GET", "/mqtt", headers={
            "Connection": "Upgrade",
            "Upgrade": "websocket",
            "Sec-WebSocket-Version": "13",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            "Sec-WebSocket-Protocol": "mqtt",
        })
        response = conn.getresponse()
        if response.status == 101 and response.getheader("Sec-WebSocket-Protocol") == "mqtt":
            break
    except OSError:
        pass
    finally:
        conn.close()
    sleep(0.5)
else:
    raise SystemExit("Mosquitto nie udostępnia TCP 1883 i WebSocket MQTT na /mqtt:9001.")
PYTHON
}

if ! install -d -m 0755 "$(dirname -- "$SYSTEMD_DROPIN")" ||
    ! install -m 0644 "$stage_dir/firewall" "$FIREWALL_CONFIG" ||
    ! install -m 0644 "$SCRIPT_DIR/mosquitto.service.conf" "$SYSTEMD_DROPIN" ||
    ! install -m 0644 "$SCRIPT_DIR/mosquitto.conf" "$BROKER_CONFIG" ||
    ! systemctl daemon-reload ||
    ! systemctl restart mosquitto.service ||
    ! probe_broker; then
    journalctl -u mosquitto.service -n 20 --no-pager >&2 || true
    rollback
    fail "Przywrócono poprzednią konfigurację Mosquitto. Sprawdź logi i obsługę WebSocket w pakiecie."
fi
systemctl enable mosquitto.service

if ! $BROKER_ONLY; then
    runuser -u "$APP_USER" -- env PROJEKT_MEDYCZNY_ENV_FILE=/etc/projekt_medyczny.env \
        "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
    systemctl restart projekt-medyczny.service
    systemctl is-active --quiet projekt-medyczny.service || fail "Usługa Django nie działa."
fi

printf 'Mosquitto działa na portach 1883 i 9001 (/mqtt). Dostęp lokalny oraz przez %s w sieci Badania_RPi.\n' "$WIFI_IFACE"
