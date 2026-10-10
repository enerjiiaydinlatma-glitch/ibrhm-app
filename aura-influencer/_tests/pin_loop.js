// Regresyon: PIN'siz halde asistan arka plan sorgusu (agTick) ASLA prompt acmamali (pencere kapanmiyordu).
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
let prompts = 0;
const store = {};
global.localStorage = {getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; }};
global.prompt = () => { prompts++; return null; };
global.fetch = async () => ({status: 403, json: async () => ({ok: false})});
const els = {};
const mk = id => els[id] || (els[id] = {style: {}, classList: {contains: () => true}, textContent: '', disabled: false, addEventListener() {}, appendChild() {}, value: ''});
global.document = {getElementById: mk, addEventListener() {}, querySelectorAll: () => [], querySelector: () => null, createElement: () => mk('x' + Math.random())};
global.window = global; global.location = {}; global.confirm = () => true; global.alert = () => {};
global.setInterval = () => 0; global.setTimeout = () => 0; global.navigator = {};
process.on('unhandledRejection', () => {});
process.on('uncaughtException', () => {});
const fn = new Function(src + ';return {agTick};');
(async () => { const {agTick} = fn(); for (let i = 0; i < 5; i++) await agTick(); console.log('RESULT ' + JSON.stringify({prompts})); })();
