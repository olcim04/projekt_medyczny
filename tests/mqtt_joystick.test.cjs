const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const templates = path.join(__dirname, '..', 'app', 'templates');
const mqttSource = fs.readFileSync(path.join(templates, 'static/js/mqtt-joystick.js'), 'utf8');

class Element extends EventTarget {
    constructor(textContent = '') {
        super();
        this.textContent = textContent;
        this.style = {};
        this.attributes = new Map();
        const classes = new Set();
        this.classList = { add: value => classes.add(value), remove: value => classes.delete(value) };
    }

    setAttribute(name, value) { this.attributes.set(name, value); }
    click() {
        if (!this.disabled) this.dispatchEvent(new Event('click'));
    }
    showModal() { this.open = true; }
    close() {
        this.open = false;
        this.dispatchEvent(new Event('close'));
    }
}

function environment(config = {}, filename) {
    let now = 0;
    let nextTimer = 0;
    const timers = new Map();
    const setTimeout = (callback, delay) => {
        const id = ++nextTimer;
        timers.set(id, { callback, at: now + delay });
        return id;
    };

    function tick(milliseconds) {
        const target = now + milliseconds;
        while (true) {
            const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
            if (!next || next[1].at > target) break;
            const [id, timer] = next;
            now = timer.at;
            timers.delete(id);
            timer.callback();
        }
        now = target;
    }

    const clients = [];
    class Client {
        constructor(host, port, route, id) {
            Object.assign(this, { host, port, route, id, attempts: 0, topics: [], sent: [] });
            clients.push(this);
        }
        connect(options) { this.options = options; this.attempts++; }
        isConnected() { return !!this.connected; }
        connectOk() { this.connected = true; this.options.onSuccess(); }
        fail() { this.connected = false; this.options.onFailure({ errorMessage: 'test' }); }
        lose() {
            this.connected = false;
            this.onConnectionLost({ errorCode: 1, errorMessage: 'test' });
        }
        disconnect() { this.connected = false; }
        subscribe(topic, options) { this.topics.push(topic); this.subscriptionOptions = options; }
        send(message) { this.sent.push(message); }
        publish(payloadString, options = {}) {
            this.onMessageArrived({ payloadString, destinationName: 'esp32/arcade', ...options });
        }
    }

    const document = new EventTarget();
    document.visibilityState = 'visible';
    document.focused = true;
    document.hasFocus = () => document.focused;
    const status = new Element();
    document.querySelector = selector => selector === '[data-mqtt-status]' ? status : null;
    const elements = new Map();
    document.getElementById = id => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    };
    const answerButtons = [new Element(), new Element(), new Element()];
    document.querySelectorAll = () => answerButtons;

    const window = new EventTarget();
    const savedResults = new Map();
    Object.assign(window, {
        MQTT_JOYSTICK_CONFIG: config,
        Paho: { MQTT: { Client, Message: class { constructor(payload) { this.payload = payload; } } } },
        location: { hostname: '10.42.0.1', protocol: 'http:', search: '' },
        sessionStorage: { setItem: (key, value) => savedResults.set(key, value) },
        setTimeout,
        clearTimeout: id => timers.delete(id),
    });
    const context = vm.createContext({
        window, document, URLSearchParams, setTimeout, clearTimeout: window.clearTimeout,
        setInterval() {}, performance: { now: () => now }, sessionStorage: window.sessionStorage,
        console: { info() {}, warn() {}, debug() {}, log() {} },
    });
    const run = script => vm.runInContext(script, context);
    run(mqttSource);

    if (filename) {
        const html = fs.readFileSync(path.join(templates, filename), 'utf8');
        // Use the actual DOM states and inline button callbacks from the template.
        const markup = html.slice(0, html.indexOf('<script'));
        for (const match of markup.matchAll(/<\w+\b([^>]*\bid="([^"]+)"[^>]*)>([^<]*)/g)) {
            const [, attributes, id, label] = match;
            const element = document.getElementById(id);
            element.textContent = label.trim();
            element.disabled = /\sdisabled\b/.test(attributes);
            element.hidden = /\shidden\b/.test(attributes);
            element.value = /\svalue="([^"]*)"/.exec(attributes)?.[1];
            element.style.display = /display:\s*([^;"]+)/.exec(attributes)?.[1];
            const callback = /onclick="([^"]+)"/.exec(attributes)?.[1];
            if (callback) element.addEventListener('click', () => run(callback));
        }
        const faceImages = ['a.png', 'b.png', 'c.png'];
        const writeFixture = (id, value) => { document.getElementById(id).textContent = JSON.stringify(value); };
        writeFixture('face-test-trials', Array.from({ length: 30 }, (_, index) => ({
            set_number: Math.floor(index / 6) + 1,
            gender: index % 2 ? 'M' : 'F',
            age_group: String(Math.floor(index / 2) % 3 + 1),
            images: faceImages,
        })));
        writeFixture('face-test-warmup-trials', [faceImages]);
        writeFixture('ishihara-answers', Array.from({ length: 13 }, () => ['12', '17', '8']));
        writeFixture('ishihara-patient', 42);
        run(/<script>([\s\S]*?)<\/script>/.exec(html)[1].replace(/{%[^%]*%}/g, '/fixture/'));
        if (filename !== 'ishihara.html') run('Setup()');
        clients[0].connectOk();
    }

    return {
        window, document, clients, status, tick, run, savedResults, answerButtons,
        element: id => document.getElementById(id),
        pendingTimers: () => timers.size,
        event: name => window.dispatchEvent(new Event(name)),
    };
}

test('parser accepts firmware text, old numeric inputs and JSON with a known field', () => {
    const env = environment({ confirmQuietPeriod: 0 });
    const actions = [];
    env.window.MQTTJoystick.init({}, value => actions.push(value));
    const client = env.clients[0];
    client.connectOk();
    for (const [payload, expected] of [
        [' left ', -1], ['RIGHT', 1], [' Up\n', 0], ['ZaTwIeRdZ', 2],
        [-1, -1], ['0', 0], ['1', 1], ['2', 2], ['"2"', 2],
        ['{"value":-1}', -1], ['{"command":"right"}', 1], ['{"data":0}', 0],
    ]) {
        client.publish(payload);
        assert.equal(actions.pop(), expected, String(payload));
    }
    for (const payload of [
        '', '  ', 'unknown', 'constructor', 'Infinity', 0.5, 3, null, undefined,
        'true', '[]', '{}', '{"value":""}', '{"action":false}', '{"direction":',
        '0x2', 'START', 'STOP', 'stop', 'bateria: 3456', 'bateria: ',
    ]) {
        client.publish(payload);
        assert.deepEqual(actions, [], String(payload));
    }
});

test('bundled Paho accepts the connection options and opens the expected WebSocket route', () => {
    const connections = [];
    const document = Object.assign(new EventTarget(), {
        querySelector: () => null,
        visibilityState: 'visible',
        hasFocus: () => true,
    });
    const globals = Object.assign(new EventTarget(), {
        document, URLSearchParams, localStorage: {},
        setTimeout() { return 1; },
        clearTimeout() {},
        console: { warn() {} },
        location: { hostname: '127.0.0.1', protocol: 'http:', search: '' },
        WebSocket: class {
            constructor(url) { connections.push(url); }
        },
    });
    globals.window = globals;
    const context = vm.createContext(globals);
    const paho = fs.readFileSync(path.join(templates, 'static/js/paho-mqtt.min.js'), 'utf8');
    vm.runInContext(paho, context);
    vm.runInContext(mqttSource, context);

    const controller = globals.MQTTJoystick.init();
    assert.deepEqual(connections, ['ws://127.0.0.1:9001/mqtt']);
    controller.disconnect();
});

test('one MQTT client retries failures, resubscribes and disconnects across page lifecycle', () => {
    const env = environment({ subscribeLegacy: true, reconnectTimeout: 100 });
    const actions = [];
    const controller = env.window.MQTTJoystick.init({}, value => actions.push(value));
    controller.init();
    const client = env.clients[0];
    assert.equal(client.host, '10.42.0.1');
    assert.equal(client.port, 9001);
    assert.equal(client.route, '/mqtt');
    assert.equal(Object.hasOwn(client.options, 'reconnect'), false);
    client.fail();
    assert.equal(env.pendingTimers(), 1);
    env.tick(100);
    assert.equal(client.attempts, 2);
    client.connectOk();
    assert.deepEqual(client.topics, ['esp32/arcade', 'test/joystick']);

    client.publish('left', { retained: true });
    assert.deepEqual(actions, []);
    client.publish('-1', { destinationName: 'test/joystick' });
    assert.deepEqual(actions, [-1]);
    const previousSubscription = client.subscriptionOptions;
    client.lose();
    env.tick(100);
    client.connectOk();
    assert.deepEqual(client.topics, ['esp32/arcade', 'test/joystick', 'esp32/arcade', 'test/joystick']);
    assert.equal(env.clients.length, 1);
    previousSubscription.onFailure({ errorMessage: 'stale subscription' });
    assert.equal(env.pendingTimers(), 0);

    client.subscriptionOptions.onFailure({ errorMessage: 'subscription denied' });
    env.tick(100);
    assert.equal(client.attempts, 4);
    client.connectOk();
    env.event('pagehide');
    assert.equal(client.isConnected(), false);
    env.event('pageshow');
    assert.equal(client.attempts, 5);
    env.event('pagehide');
    client.connectOk();
    assert.equal(client.isConnected(), false);
    env.event('pageshow');
    client.fail();
    env.event('pagehide');
    env.tick(100);
    assert.equal(client.attempts, 6);
    controller.disconnect();
    env.event('pageshow');
    assert.equal(client.attempts, 6);
});

test('controller status, telemetry, diagnostics, duplicate confirmations and tab focus', () => {
    const actions = [];
    const env = environment({ diagnostic: true, directionMap: { up: 1 }, controlMessages: { stop: 'other-stop' } });
    const controller = env.window.MQTTJoystick.init({}, value => actions.push(value));
    const client = env.clients[0];
    assert.match(env.status.textContent, /Brak połączenia/);
    assert.equal(controller.publishCommand('START'), false);
    client.connectOk();
    assert.match(env.status.textContent, /Połączono.*Oczekiwanie/);
    client.publish('bateria: 3456', { retained: true });
    client.publish('bateria: ');
    client.publish('unknown');
    assert.match(env.status.textContent, /Oczekiwanie/);
    client.publish(' BaTeRiA: 3456 ');
    assert.match(env.status.textContent, /Odebrano.*Bateria: 3456/);

    ['START', 'STOP', 'stop'].forEach(command => client.publish(command));
    client.publish('right', { destinationName: 'rpi/broadcast' });
    client.publish('right', { destinationName: 'test/joystick' });
    assert.deepEqual(actions, []);
    assert.equal(controller.publishCommand('stop'), false);
    assert.equal(controller.publishCommand('STOP'), true);
    assert.deepEqual(client.sent.map(({ payload, destinationName, qos, retained }) =>
        [payload, destinationName, qos, retained]), [['STOP', 'rpi/broadcast', 0, false]]);

    env.document.focused = false;
    client.publish('left');
    env.document.focused = true;
    env.document.visibilityState = 'hidden';
    client.publish('right');
    env.document.visibilityState = 'visible';
    client.publish('up');
    client.publish('zatwierdz', { duplicate: true });
    env.tick(501);
    client.publish('zatwierdz');
    client.publish('2');
    client.publish('right');
    client.publish('right');
    env.tick(501);
    client.publish('zatwierdz');
    assert.deepEqual(actions, [1, 2, 1, 1, 2]);
    client.lose();
    assert.match(env.status.textContent, /Brak połączenia.*Oczekiwanie.*3456/);
});

test('color test gates pause and instructions and completes 18 trials with the existing calculation', () => {
    const env = environment({}, 'test.html');
    const client = env.clients[0];
    const send = value => { client.publish(value); env.tick(501); };
    const picker = env.element('picker');
    assert.equal(env.window.__mqttJoystick.publishCommand('START'), false);

    send('right');
    assert.equal(picker.value, '50');
    env.element('paz').click();
    send('zatwierdz');
    assert.equal(env.run('stage'), 0);
    env.run('resumeTest()');
    client.publish('zatwierdz');
    client.publish('zatwierdz');
    assert.equal(env.run('stage'), 1);
    env.tick(501);
    client.publish('right');
    client.publish('right');
    assert.equal(picker.value, '60');
    client.publish('left');
    assert.equal(picker.value, '55');
    send('up');
    assert.equal(picker.value, '50');
    const press = key => env.document.dispatchEvent(Object.assign(new Event('keydown', { cancelable: true }), { key }));
    press('ArrowLeft');
    assert.equal(picker.value, '45');
    press('ArrowDown');
    assert.equal(picker.value, '50');

    for (let stage = 1; stage <= 4; stage++) send('zatwierdz');
    for (let trial = 0; trial < 18; trial++) {
        picker.value = env.run('String(R)');
        env.run('Match()');
        send('zatwierdz');
    }
    assert.equal(env.run('stage'), 23);
    send('zatwierdz');
    assert.equal(env.savedResults.has('wyniki'), false);
    env.element('dal').click();
    assert.equal(JSON.parse(env.savedResults.get('Karta')).length, 18);
    assert.equal(JSON.parse(env.savedResults.get('wyniki')).wynik_ogolny, 0);
});

test('face test preserves preview and pause, resets selection and scores all 30 trials', () => {
    const env = environment({}, 'test2.html');
    const client = env.clients[0];
    const send = value => { client.publish(value); env.tick(501); };
    send('zatwierdz');
    send('zatwierdz');
    assert.equal(env.run('stage'), 2);
    send('right');
    send('zatwierdz');
    assert.equal(env.run('choice'), 0);

    env.element('paz').click();
    env.tick(5000);
    assert.equal(env.run('showingFace'), true);
    send('up');
    send('zatwierdz');
    assert.equal(env.run('choice'), 0);
    env.run('resumeTest()');
    env.tick(1496);
    assert.equal(env.run('showingFace'), true);
    env.tick(1);
    assert.equal(env.run('showingFace'), false);
    send('zatwierdz');
    assert.equal(env.run('stage'), 2);
    env.element('t1').click();
    send('right');
    assert.equal(env.run('choice'), 2);
    send('left');
    assert.equal(env.run('choice'), 1);
    send('zatwierdz');
    assert.equal(env.run('stage'), 3);
    send('zatwierdz');

    for (let trial = 0; trial < 30; trial++) {
        env.tick(3000);
        assert.equal(env.run('choice'), 0);
        assert.equal(env.element('dal').disabled, true);
        send('zatwierdz');
        assert.equal(env.run('progress'), trial + 2);
        const buttonByChoice = { 1: 'left', 2: 'up', 3: 'right' };
        send(buttonByChoice[env.run('Kolej')]);
        send('zatwierdz');
    }
    assert.equal(env.run('stage'), 34);
    send('zatwierdz');
    assert.equal(env.savedResults.has('wyniki'), false);
    env.element('dal').click();
    assert.equal(JSON.parse(env.savedResults.get('wyniki')).wynik_ogolny, 30);
});

test('Ishihara requires a chosen answer and respects pause, warmup, scoring and patient', () => {
    const env = environment({}, 'ishihara.html');
    const client = env.clients[0];
    const send = value => { client.publish(value); env.tick(501); };
    send('zatwierdz');
    send('zatwierdz');
    send('zatwierdz');
    assert.equal(env.run('roundIndex'), 0);
    env.element('ishihara-pause').click();
    send('up');
    send('zatwierdz');
    assert.equal(env.run('selectedAnswer'), null);
    env.element('ishihara-resume').click();

    send('up');
    assert.equal(env.answerButtons[1].attributes.get('aria-pressed'), 'true');
    send('zatwierdz');
    send('zatwierdz');
    assert.equal(env.run('roundIndex'), 1);
    for (let trial = 1; trial < 13; trial++) {
        send('zatwierdz');
        assert.equal(env.run('roundIndex'), trial);
        const index = env.answerButtons.findIndex(button => button.textContent === '12');
        send(['left', 'up', 'right'][index]);
        send('zatwierdz');
    }
    send('zatwierdz');
    assert.equal(env.savedResults.has('wyniki'), false);
    env.element('ishihara-next').click();
    const result = JSON.parse(env.savedResults.get('wyniki'));
    assert.deepEqual([result.test_type, result.pacjent_id, result.wynik_ogolny], ['ishihara', 42, 12]);
});
