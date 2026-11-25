(function () {
    const DIRECTIONS = { left: -1, right: 1, up: 0, zatwierdz: 2 };
    const CONTROL_MESSAGES = { START: 'START', STOP: 'STOP', stop: 'stop' };
    const VALUES = [-1, 0, 1, 2];
    const KEYBOARD = {
        arrowleft: -1, a: -1, arrowright: 1, d: 1,
        arrowdown: 0, s: 0, arrowup: 2, w: 2, ' ': 2,
    };
    const DEFAULT_CONFIG = {
        enabled: true,
        host: window.MQTT_BROKER_HOST || window.location.hostname,
        port: 9001,
        path: '/mqtt',
        topic: 'esp32/arcade',
        legacyTopic: 'test/joystick',
        subscribeLegacy: false,
        broadcastTopic: 'rpi/broadcast',
        reconnectTimeout: 5000,
        confirmQuietPeriod: 500,
        simulateKeyboard: true,
        diagnostic: new URLSearchParams(window.location.search).get('mqtt_debug') === '1',
    };

    function parseMessage(payload, directionMap = DIRECTIONS, controlMessages = CONTROL_MESSAGES) {
        if (typeof payload === 'string') {
            const text = payload.trim();
            if (!text) return null;
            try {
                payload = JSON.parse(text);
            } catch {
                payload = text;
            }
        }
        if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
            payload = payload.value ?? payload.command ?? payload.direction ??
                payload.action ?? payload.data ?? payload.message;
        }
        if (typeof payload === 'string') {
            const text = payload.trim();
            const control = Object.hasOwn(controlMessages, text) && controlMessages[text];
            if (control) return { type: 'control', value: control };

            const battery = /^bateria\s*:\s*(.*)$/i.exec(text);
            if (battery) {
                const value = battery[1].trim();
                return value ? { type: 'battery', value } : null;
            }

            const key = text.toLowerCase();
            if (Object.hasOwn(directionMap, key)) {
                payload = directionMap[key];
            } else if (/^[+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(text)) {
                payload = Number(text);
            } else {
                return null;
            }
        }
        return VALUES.includes(payload) ? { type: 'joystick', value: payload } : null;
    }

    function createJoystickController(config = {}) {
        const settings = { ...DEFAULT_CONFIG, ...window.MQTT_JOYSTICK_CONFIG, ...config };
        const directionMap = { ...DIRECTIONS, ...settings.directionMap };
        const controlMessages = { ...CONTROL_MESSAGES, ...settings.controlMessages };
        const topics = new Set([settings.topic]);
        if (settings.subscribeLegacy) topics.add(settings.legacyTopic);
        topics.delete(settings.broadcastTopic);

        const status = document.querySelector('[data-mqtt-status]');
        const diagnostics = document.querySelector('[data-mqtt-diagnostics]');
        const diagnosticButtons = Array.from(diagnostics?.querySelectorAll('button') ?? []);
        const diagnosticResult = diagnostics?.querySelector('[data-mqtt-diagnostic-result]');
        const handlers = new Set();
        let client = null;
        let listening = false;
        let running = false;
        let connecting = false;
        let attempt = 0;
        let retryTimer = null;
        let connected = false;
        let received = false;
        let battery = null;
        let lastConfirm = -Infinity;

        function activeTab() {
            return document.visibilityState === 'visible' && document.hasFocus();
        }

        function renderStatus() {
            if (status) {
                const broker = connected ? 'Połączono z brokerem MQTT' : 'Brak połączenia z brokerem MQTT';
                const controller = received ? 'Odebrano wiadomość z kontrolera' : 'Oczekiwanie na wiadomość z kontrolera';
                const batteryText = battery === null ? '' : ' · Bateria: ' + battery;
                const tab = activeTab() ? '' : ' · Sterowanie w aktywnej karcie';
                const text = broker + ' · ' + controller + batteryText + tab;
                if (status.textContent !== text) status.textContent = text;
            }
            diagnosticButtons.forEach(button => { button.disabled = !connected; });
        }

        function notify(value, source) {
            for (const handler of handlers) handler(value, { source });
        }

        function onMessage(message) {
            if (!running || !connected || message.retained || !topics.has(message.destinationName)) return;

            let decoded;
            try {
                decoded = parseMessage(message.payloadString, directionMap, controlMessages);
            } catch (error) {
                console.debug('MQTT: nieprawidłowy format wiadomości.', error);
                return;
            }
            if (!decoded) {
                console.debug('MQTT: nierozpoznana wiadomość na', message.destinationName);
                return;
            }

            received = true;
            if (decoded.type === 'battery') battery = decoded.value;
            renderStatus();
            if (decoded.type === 'control') {
                console.debug('MQTT: odebrano polecenie diagnostyczne', decoded.value);
                return;
            }
            if (decoded.type !== 'joystick') return;

            if (decoded.value === 2) {
                const now = performance.now();
                const elapsed = now - lastConfirm;
                lastConfirm = now;
                if (message.duplicate || elapsed < settings.confirmQuietPeriod) return;
            }
            if (activeTab()) notify(decoded.value, 'mqtt');
        }

        function scheduleRetry(reason, error) {
            connecting = false;
            connected = false;
            received = false;
            renderStatus();
            console.warn('MQTT: ' + reason, error?.errorMessage || error);
            if (client?.isConnected()) client.disconnect();
            if (running && retryTimer === null) {
                retryTimer = window.setTimeout(() => {
                    retryTimer = null;
                    connect();
                }, settings.reconnectTimeout);
            }
        }

        function connect() {
            if (!running || !settings.enabled || connecting || connected || retryTimer !== null) return;
            const mqtt = window.Paho?.MQTT;
            if (!mqtt) {
                console.warn('MQTT: nie załadowano lokalnej biblioteki Paho.');
                return;
            }
            try {
                if (!client) {
                    const clientId = 'test_' + Math.random().toString(16).slice(2);
                    client = new mqtt.Client(settings.host, Number(settings.port), settings.path, clientId);
                    client.onMessageArrived = onMessage;
                    client.onConnectionLost = error => {
                        if (error.errorCode) scheduleRetry('utracono połączenie.', error);
                    };
                }
                connecting = true;
                const currentAttempt = ++attempt;
                const options = {
                    mqttVersion: 4,
                    cleanSession: true,
                    timeout: 5,
                    useSSL: settings.useSSL ?? window.location.protocol === 'https:',
                    onSuccess() {
                        connecting = false;
                        if (!running) {
                            client.disconnect();
                            return;
                        }
                        connected = true;
                        received = false;
                        renderStatus();
                        console.info('MQTT: połączono z brokerem', settings.host, settings.port);
                        for (const topic of topics) {
                            client.subscribe(topic, {
                                qos: 0,
                                timeout: 5,
                                onSuccess: () => console.info('MQTT: subskrypcja', topic),
                                onFailure(error) {
                                    if (connected && currentAttempt === attempt) {
                                        scheduleRetry('błąd subskrypcji ' + topic, error);
                                    }
                                },
                            });
                        }
                    },
                    onFailure: error => scheduleRetry('nie udało się połączyć.', error),
                };
                if (settings.username) options.userName = settings.username;
                if (settings.password) options.password = settings.password;
                client.connect(options);
            } catch (error) {
                scheduleRetry('błąd inicjalizacji.', error);
            }
        }

        function publishCommand(command) {
            if (!settings.diagnostic || !connected || !['START', 'STOP'].includes(command)) return false;
            try {
                const message = new window.Paho.MQTT.Message(command);
                message.destinationName = settings.broadcastTopic;
                message.qos = 0;
                message.retained = false;
                client.send(message);
                console.info('MQTT: wysłano', command, 'na', settings.broadcastTopic);
                return true;
            } catch (error) {
                console.warn('MQTT: publikacja nie powiodła się.', error);
                return false;
            }
        }

        function onDiagnosticClick(event) {
            const command = event.currentTarget.value;
            const sent = publishCommand(command);
            diagnosticResult.textContent = sent ? 'Wysłano ' + command + '.' : 'Nie udało się wysłać polecenia.';
        }

        function onKeydown(event) {
            if (!running || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
                event.target.closest?.('textarea, select, [contenteditable], input:not([type="range"])')) return;
            const key = event.key.toLowerCase();
            if (!Object.hasOwn(KEYBOARD, key) || (key === ' ' && event.target.closest?.('button'))) return;

            const value = KEYBOARD[key];
            event.preventDefault();
            if (value !== 2 || !event.repeat) notify(value, 'keyboard');
        }

        function start() {
            if (running) return;
            running = true;
            renderStatus();
            connect();
        }

        function stop() {
            running = false;
            window.clearTimeout(retryTimer);
            retryTimer = null;
            connected = false;
            received = false;
            lastConfirm = -Infinity;
            // A pending Paho handshake closes in onSuccess or times out in onFailure.
            if (client?.isConnected()) client.disconnect();
            renderStatus();
        }

        return {
            init() {
                if (listening) return;
                listening = true;
                window.addEventListener('pagehide', stop);
                window.addEventListener('pageshow', start);
                window.addEventListener('focus', renderStatus);
                window.addEventListener('blur', renderStatus);
                document.addEventListener('visibilitychange', renderStatus);
                if (settings.simulateKeyboard) document.addEventListener('keydown', onKeydown);
                if (diagnostics && settings.diagnostic) {
                    diagnostics.hidden = false;
                    diagnosticButtons.forEach(button => button.addEventListener('click', onDiagnosticClick));
                }
                start();
            },
            subscribe(handler) {
                if (typeof handler === 'function') handlers.add(handler);
            },
            send(value) {
                if (VALUES.includes(value)) notify(value, 'manual');
            },
            disconnect() {
                listening = false;
                window.removeEventListener('pagehide', stop);
                window.removeEventListener('pageshow', start);
                window.removeEventListener('focus', renderStatus);
                window.removeEventListener('blur', renderStatus);
                document.removeEventListener('visibilitychange', renderStatus);
                document.removeEventListener('keydown', onKeydown);
                diagnosticButtons.forEach(button => button.removeEventListener('click', onDiagnosticClick));
                if (diagnostics) diagnostics.hidden = true;
                stop();
            },
            getClient() {
                return running ? client : null;
            },
            publishCommand,
        };
    }

    window.MQTTJoystick = {
        create: createJoystickController,
        init(config = {}, handler) {
            const controller = createJoystickController(config);
            controller.subscribe(handler);
            controller.init();
            return controller;
        },
        send(value) {
            window.__mqttJoystick?.send(value);
        },
    };
})();
