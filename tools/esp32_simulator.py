#!/usr/bin/env python3
"""Interaktywny symulator kontrolera FireBeetle ESP32 przez MQTT."""

import argparse
from math import isfinite
from threading import Event
from time import sleep
from uuid import uuid4

from paho.mqtt import client as mqtt


COMMANDS = {
    "1": "left",
    "2": "right",
    "3": "up",
    "4": "zatwierdz",
    "5": "bateria: 3456",
    "6": "START",
    "7": "STOP",
}
BROADCAST_TOPIC = "rpi/broadcast"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="10.42.0.1", help="Adres brokera MQTT")
    parser.add_argument("--port", type=int, default=1883, help="Port MQTT TCP")
    parser.add_argument("--topic", default="esp32/arcade", help="Temat publikacji")
    parser.add_argument("--listen", action="store_true", help=f"Nasłuchuj {BROADCAST_TOPIC}")
    parser.add_argument("--delay", type=float, default=0, help="Opóźnienie publikacji w sekundach")
    args = parser.parse_args()
    if not isfinite(args.delay) or args.delay < 0:
        parser.error("Opóźnienie musi być skończoną liczbą nieujemną.")
    if not 1 <= args.port <= 65535:
        parser.error("Port musi mieścić się w zakresie 1–65535.")
    if not args.topic or any(character in args.topic for character in "+#\0"):
        parser.error("Podaj poprawną nazwę tematu publikacji.")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{uuid4().hex[:18]}")
    connack = Event()

    def on_connect(connection, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            print(f"\nBroker odrzucił połączenie: {reason_code}", flush=True)
        else:
            print(f"\nPołączono z {args.host}:{args.port}. Temat: {args.topic}", flush=True)
            if args.listen:
                connection.subscribe(BROADCAST_TOPIC)
                print(f"Nasłuch: {BROADCAST_TOPIC}", flush=True)
        connack.set()

    def on_message(_client, _userdata, message):
        payload = message.payload.decode("utf-8", errors="replace")
        print(f"\nOdebrano {message.topic}: {payload}", flush=True)

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(args.host, args.port, keepalive=30)
    except OSError as error:
        print(f"Błąd połączenia z brokerem {args.host}:{args.port}: {error}")
        return 1

    client.loop_start()
    try:
        if not connack.wait(timeout=5) or not client.is_connected():
            print("Brak potwierdzonego połączenia z brokerem.")
            return 1

        print("1 – left | 2 – right | 3 – up | 4 – zatwierdz | 5 – bateria")
        print("6 – START (diagnostyka) | 7 – STOP (diagnostyka) | 0 – wyjście")
        while True:
            choice = input("Wybór: ").strip()
            if choice == "0":
                return 0
            payload = COMMANDS.get(choice)
            if payload is None:
                print("Wybierz pozycję menu 0–7.")
                continue
            if args.delay:
                print(f"Wysyłka za {args.delay:g} s. Przejdź do karty badania.", flush=True)
                sleep(args.delay)
            if not client.is_connected():
                print("Brak połączenia z brokerem. Poczekaj na ponowne połączenie.")
                continue
            try:
                result = client.publish(args.topic, payload, qos=0, retain=False)
                result.wait_for_publish(timeout=2)
                if not result.is_published():
                    print("Upłynął czas oczekiwania na publikację.")
                    continue
                print(f"Wysłano {args.topic}: {payload}")
            except (RuntimeError, ValueError) as error:
                print(f"Błąd publikacji: {error}")
    except (KeyboardInterrupt, EOFError):
        print()
        return 0
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    raise SystemExit(main())
