// Run with Node.js 18+: node --test tests/demo.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function demo() {
  const window = {};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../lumi-web-app/static/demo-api.js'), 'utf8'), { window, URL, Date });
  return window;
}

test('demo supplies labeled sample data without fetch or geolocation', async () => {
  const window = demo();
  assert.equal(window.LUMI_DEMO, true);
  const weather = await window.lumiDemoRequest('/api/weather');
  assert.equal(weather.source, 'demo-sample');
  const places = await window.lumiDemoRequest('/api/places');
  assert.equal(places.candidate_places.length, 3);
  assert.ok(places.candidate_places.every(place => place.name.startsWith('Sample ')));
});

test('rejection adapts a demo nudge and chat is explicitly scripted', async () => {
  const window = demo();
  const places = await window.lumiDemoRequest('/api/places');
  const context = { places, recent_behavior: { skip_reasons: ['busy'] } };
  const nudge = await window.lumiDemoRequest('/api/agent/recommend', context);
  assert.equal(nudge.suggested_duration_min, 5);
  assert.equal(nudge.place_recommendations.length, 3);
  assert.match(nudge.provider, /demo/);
  const reply = await window.lumiDemoRequest('/api/bloom/chat', { message: 'I am tired' });
  assert.match(reply.provider, /scripted/);
  assert.match(reply.reply, /rest|pause/i);
  await assert.rejects(window.lumiDemoRequest('/api/unknown'));
});
