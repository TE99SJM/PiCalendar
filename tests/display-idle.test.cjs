const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const {runInNewContext} = require('node:vm');

const app = readFileSync(join(__dirname, '../static/app.js'), 'utf8');
const tenMinutes = 10 * 60 * 1000;

function setup(t) {
  t.mock.timers.enable({apis: ['setTimeout']});
  const button = new EventTarget();
  const overlay = new EventTarget();
  const document = new EventTarget();
  const powerCalls = [];
  let asleep = false;

  overlay.classList = {toggle: (_name, active) => { asleep = active; }};
  overlay.setAttribute = () => {};
  overlay.focus = () => {};
  document.body = {classList: {toggle() {}}};
  document.getElementById = id => ({'sleep-button': button, 'sleep-overlay': overlay})[id];
  document.querySelectorAll = () => [];

  runInNewContext(app + `
    displayPower = async action => { powerCalls.push(action); };
    updateClock = getEverything = renderWeather = () => {};
    initializeSleep();
  `, {document, powerCalls, setTimeout, clearTimeout, performance});

  return {
    button, document, overlay, powerCalls,
    isAsleep: () => asleep,
    tick: ms => t.mock.timers.tick(ms),
  };
}

test('starts awake and sleeps at ten minutes of inactivity', t => {
  const display = setup(t);
  display.tick(tenMinutes - 1);
  assert.equal(display.isAsleep(), false);
  assert.deepEqual(display.powerCalls, []);
  display.tick(1);
  assert.equal(display.isAsleep(), true);
  assert.deepEqual(display.powerCalls, ['sleep']);
});

test('touch, keyboard, wheel and text input restart the countdown', t => {
  const display = setup(t);
  for (const type of ['pointerdown', 'pointerup', 'touchend', 'keydown', 'wheel', 'input']) {
    display.tick(tenMinutes - 1);
    assert.equal(display.isAsleep(), false, `must be awake before ${type}`);
    display.document.dispatchEvent(new Event(type));
  }
  display.tick(tenMinutes - 1);
  assert.equal(display.isAsleep(), false);
  display.tick(1);
  assert.deepEqual(display.powerCalls, ['sleep']);
});

test('manual sleep clears the timer and double-tap wake starts a new one', async t => {
  const display = setup(t);
  display.tick(tenMinutes - 1);
  display.button.dispatchEvent(new Event('click'));
  assert.equal(display.isAsleep(), true);
  display.tick(tenMinutes);
  assert.deepEqual(display.powerCalls, ['sleep']);

  const tap = () => {
    for (const type of ['pointerdown', 'pointerup']) {
      display.overlay.dispatchEvent(Object.assign(new Event(type), {
        pointerType: 'touch', pointerId: 1, clientX: 50, clientY: 50,
      }));
    }
  };
  tap();
  assert.equal(display.isAsleep(), true);
  tap();
  await new Promise(setImmediate);
  assert.equal(display.isAsleep(), false);
  assert.deepEqual(display.powerCalls, ['sleep', 'wake']);

  display.tick(tenMinutes - 1);
  assert.equal(display.isAsleep(), false);
  display.tick(1);
  assert.equal(display.isAsleep(), true);
  assert.deepEqual(display.powerCalls, ['sleep', 'wake', 'sleep']);
});
