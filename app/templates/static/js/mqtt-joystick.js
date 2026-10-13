(function () {
    const DEFAULT_CONFIG = {
        enabled: true,
        host: 'localhost',
        port: 9001,
        path: '/mqtt',
        topic: 'test/joystick',
        username: '',
        password: '',
        reconnectTimeout: 5000,
        simulateKeyboard: true,
    };

    function normalizeJoystickValue(payload) {
        if (payload === null || payload === undefined) return null;

        let value = Number(payload);
        if (Number.isNaN(value)) {
            try {
                const parsed = JSON.parse(payload);
                value = Number(parsed.value ?? parsed.command ?? parsed.direction ?? parsed.action ?? parsed.data ?? parsed.message);
            } catch (error) {
                return null;
            }
        }

        if (Number.isNaN(value)) return null;
        return Math.round(value);
    }

    function createJoystickController(config = {}) {
        const settings = { ...DEFAULT_CONFIG, ...config };
        let client = null;
        let handlers = [];

        function notify(value) {
            handlers.forEach((handler) => {
                if (typeof handler === 'function') {
                    handler(value);
                }
            });
        }

        function onMessage(payload) {
            const value = normalizeJoystickValue(payload);
            if (value === null) return;
            notify(value);
        }

        function emit(value) {
            if (value === null || value === undefined) return;
            notify(value);
        }

        function connect() {
            if (!settings.enabled) {
                console.warn('MQTT joystick disabled.');
                return null;
            }

            if (typeof Paho === 'undefined' || typeof Paho.MQTT === 'undefined') {
                console.warn('Paho MQTT library not loaded.');
                return null;
            }

            try {
                const clientId = `mqtt_joystick_${Math.random().toString(16).slice(2)}`;
                client = new Paho.MQTT.Client(settings.host, Number(settings.port), settings.path, clientId);

                client.onConnectionLost = function (responseObject) {
                    console.warn('MQTT connection lost:', responseObject && responseObject.errorMessage ? responseObject.errorMessage : 'unknown');
                    window.setTimeout(() => {
                        try {
                            connect();
                        } catch (err) {
                            console.warn('MQTT reconnect failed:', err);
                        }
                    }, settings.reconnectTimeout);
                };

                client.onMessageArrived = function (message) {
                    onMessage(message.payloadString);
                };

                client.connect({
                    onSuccess: function () {
                        client.subscribe(settings.topic);
                        console.log('MQTT joystick subscribed to:', settings.topic);
                    },
                    userName: settings.username || undefined,
                    password: settings.password || undefined,
                    reconnect: true,
                });

                return client;
            } catch (error) {
                console.warn('MQTT joystick initialization failed:', error);
                return null;
            }
        }

        function disconnect() {
            if (client && client.isConnected && client.isConnected()) {
                client.disconnect();
            }
            client = null;
        }

        function attachKeyboardSimulation() {
            if (!settings.simulateKeyboard) return;

            document.addEventListener('keydown', function (event) {
                if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'a') {
                    emit(-1);
                }
                if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'd') {
                    emit(1);
                }
                if (event.key === 'ArrowUp' || event.key === ' ' || event.key.toLowerCase() === 'w') {
                    emit(2);
                }
                if (event.key === 'ArrowDown' || event.key.toLowerCase() === 's') {
                    emit(0);
                }
            });
        }

        return {
            init() {
                connect();
                attachKeyboardSimulation();
            },
            subscribe(handler) {
                if (typeof handler === 'function') {
                    handlers.push(handler);
                }
            },
            send(value) {
                emit(value);
            },
            disconnect,
            getClient() {
                return client;
            },
        };
    }

    window.MQTTJoystick = {
        create: createJoystickController,
        init(config = {}, handler) {
            const controller = createJoystickController(config);
            if (typeof handler === 'function') {
                controller.subscribe(handler);
            }
            controller.init();
            return controller;
        },
        send(value) {
            if (window.__mqttJoystick) {
                window.__mqttJoystick.send(value);
            }
        },
    };
})();
