// Run: node --test toolkit/test/schema-agree.test.mjs
// schema/user-app.schema.json mirrors schema/bolt-rules.json (the one rules file) and the toolkit lists. A difference fails here.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { RULES } from '../lib/boltrules.mjs';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const load = (f) => JSON.parse(fs.readFileSync(path.join(REPO, f), 'utf8'));
const sc = load('schema/user-app.schema.json');
const P = sc.properties, D = sc.$defs;
const sorted = (a) => [...a].sort();

test('every schema has an https://sparcle.app/schemas/ $id with a version and the ids are distinct', () => {
	const ids = ['user-app', 'bolt-app', 'boltpack-manifest', 'connector'].map((n) => load(`schema/${n}.schema.json`).$id);
	for (const id of ids) assert.match(id, /^https:\/\/[a-z]+\.app\/schemas\/[a-z-]+-v\d+\.json$/);
	assert.equal(new Set(ids).size, ids.length);
	assert.match(fs.readFileSync(path.join(REPO, 'schema/README.md'), 'utf8'), /user-app-v1\.json/);
});

test('top-level keys, schema_version, timeouts and view limits equal the rules file', () => {
	assert.deepEqual(sorted(Object.keys(P)), sorted(RULES.keys.top));
	assert.deepEqual(P.schema_version.enum, RULES.schema_versions);
	assert.equal(P.bridge.properties.timeout_seconds.maximum, RULES.timeouts.max_s);
	assert.equal(P.bridge.properties.timeout_seconds.minimum, RULES.timeouts.min_s);
	assert.equal(P.http.properties.timeout_seconds.maximum, RULES.timeouts.max_s);
	const views = D.presentation.properties.views;
	assert.equal(views.maxProperties, RULES.views.max);
	assert.equal(views.propertyNames.pattern, RULES.views.name_pattern);
	assert.deepEqual(sorted(P.http.properties.host.enum), sorted(RULES.http_local.hosts));
	assert.deepEqual(sorted(P.bridge.properties.cwd.enum), ['home']);
});

test('widget kinds: the schema enum, the per-kind notes and the bind schemas equal the rules file', () => {
	const kind = D.presentation.properties.right_widget.properties.kind;
	assert.deepEqual(sorted(kind.enum), sorted(RULES.widget_kinds));
	assert.deepEqual(sorted(kind.oneOf.map((x) => x.const)), sorted(RULES.widget_kinds));
	assert.deepEqual(sorted(D.presentation.properties.right_widget.properties.mode.enum), sorted(RULES.right_widget.modes));
	const bound = D.presentation.properties.right_widget.allOf.map((x) => x.if.properties.kind.const);
	assert.deepEqual(sorted(bound), sorted(RULES.widget_kinds.filter((k) => !RULES.no_app_data_kinds.includes(k) && k !== 'map')));
	const defName = (k) => 'bind' + k.split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join('');
	for (const k of bound) assert.deepEqual(sorted(Object.keys(D[defName(k)].properties)), sorted(Object.keys(RULES.right_widget.bind[k])), `bind keys of ${k}`);
	assert.deepEqual(sorted(D.bindChart.properties.type.enum), sorted(RULES.right_widget.bind.chart.type.values));
});

test('actions: kinds, icons, id pattern, footer count and the label notes equal the rules file', () => {
	const a = D.action;
	assert.deepEqual(sorted(a.properties.kind.enum), sorted(RULES.actions.kinds));
	assert.deepEqual(sorted(a.properties.icon.enum), sorted(RULES.actions.icons));
	assert.equal(a.properties.id.pattern, RULES.actions.id_pattern);
	assert.equal(P.actions.maxItems, undefined);   // the footer cap is stated in the description only: Bolt refuses neither more actions nor fewer, it shows up to the footer cap
	assert.ok(String(P.actions.description).includes(String(RULES.actions.footer_max_bolt)));
	assert.match(a.properties.label.description, new RegExp(`${RULES.actions.label_kept_bolt} characters`));
	assert.match(a.properties.label.description, new RegExp(`first ${RULES.actions.label_shown}\\b`));
	assert.deepEqual(sorted(Object.keys(a.properties)), sorted(RULES.keys['actions[]'].all.filter((k) => k !== 'flow' && k !== 'confirm')));
});

test('environment: the passthrough list, its cap and the pattern equal the rules file', () => {
	const e = P.bridge.properties.env_passthrough;
	assert.deepEqual(sorted(e.items.enum), sorted(RULES.env.benign_passthrough));
	assert.equal(e.maxItems, RULES.env.passthrough_max);
	assert.deepEqual(sorted(Object.keys(P.bridge.properties.env.properties)), sorted(RULES.env.benign_passthrough));
	assert.ok(new RegExp(RULES.env.inline_value_pattern).test('${env:GH_HOST}'));
});

test('the listing schema names the same permission words the toolkit computes', () => {
	const listing = load('schema/bolt-app.schema.json').properties.permissions.items.pattern;
	const src = fs.readFileSync(path.join(REPO, 'toolkit/bin/bolt-apps.mjs'), 'utf8');
	const perms = JSON.parse(/const PERMS = (\[.*?\]);/.exec(src)[1].replace(/'/g, '"'));
	for (const p of perms) assert.ok(new RegExp(listing).test(p), p);
	assert.ok(new RegExp(listing).test('opens_links:example.com'));
});

test('bridge and http blocks allow exactly the keys the rules file lists', () => {
	assert.deepEqual(sorted(Object.keys(P.bridge.properties)), sorted(RULES.keys.bridge.all));
	assert.deepEqual(sorted(Object.keys(P.http.properties)), sorted(RULES.keys.http.all));
});

// ---- constraints that must not loosen when the schema is edited (each one is something Bolt refuses)
const install = JSON.parse(read('schema/install-rules.json')).contract;
function read(f) { return fs.readFileSync(path.join(REPO, f), 'utf8'); }

test('http.headers: a value has no ${ in it, or is exactly ${env:NAME} with NAME from the rules list; names match the rules pattern', () => {
	const h = P.http.properties.headers;
	assert.equal(h.propertyNames.pattern, RULES.http_local.header_name_pattern);
	const v = h.additionalProperties;
	assert.equal(v.type, 'string');
	const [plain, exact] = v.anyOf;
	const m = /^\^\\\$\\\{env:\(([A-Z0-9_|]+)\)\\\}\$$/.exec(exact.pattern);
	assert.ok(m, `header value pattern shape: ${exact.pattern}`);
	assert.deepEqual(sorted(m[1].split('|')), sorted(RULES.env.benign_passthrough), 'the header env list is the rules list');
	const ok = (s) => !new RegExp(plain.not.pattern).test(s) || new RegExp(exact.pattern).test(s);
	for (const good of ['text/plain', '${env:AWS_PROFILE}', '${env:PGHOST}']) assert.ok(ok(good), good);
	for (const bad of ['${env:SECRET_TOKEN}', '${env:AWS_PROFILE}x', 'x${env:AWS_PROFILE}', '${HOME}', '${env:aws_profile}', '${env:}']) assert.ok(!ok(bad), bad);
});

test('the required keys, the title, the arg binding, the action fields and the detect binary keep the shape Bolt checks', () => {
	assert.deepEqual(sorted(sc.required), sorted(install.required_keys));
	assert.equal(P.title.minLength, 1); assert.match('x', new RegExp(P.title.pattern)); assert.doesNotMatch('  ', new RegExp(P.title.pattern));
	const from = new RegExp(P.args.items.properties.from.pattern);   // the launcher is_supported_arg_from: query.word(N), spaces around N tolerated
	for (const g of ['query.word(0)', 'query.word( 12 )']) assert.match(g, from);
	for (const b of ['query.word()', 'query.word(x)', 'query.line(0)', 'query.word(-1)']) assert.doesNotMatch(b, from);
	assert.deepEqual(sorted(D.action.required), ['id', 'kind', 'label']);
	assert.deepEqual(sorted(P.http.properties.request.properties.method.enum.map((x) => x.toUpperCase())), ['GET', 'GET', 'POST', 'POST']);   // the launcher uppercases the method before it checks
	const bin = new RegExp(P.detect.properties.binary.pattern);
	for (const g of ['git', 'my-tool.exe']) assert.match(g, bin);
	for (const b of ['/usr/bin/git', 'a/b', 'a\\b', '', ' git']) assert.doesNotMatch(b, bin);
	assert.equal(P.http.properties.port.minimum, 1); assert.equal(P.http.properties.port.maximum, 65535);
});

test('transform steps equal the launcher lists (the launcher lists ALLOWED_TRANSFORM_NOARG and ALLOWED_TRANSFORM_PARAM)', () => {
	const NOARG = ['lines', 'sort', 'dedupe', 'reverse', 'trim', 'upper', 'lower', 'title', 'camel', 'snake', 'kebab', 'slug', 'table', 'markdown', 'csv', 'aligned', 'sql', 'json', 'yaml', 'toml', 'env', 'properties', 'transpose', 'flatten', 'redact_secrets', 'sanitize'];
	const PARAM = ['split', 'join', 'filter', 'head', 'tail', 'slice', 'replace', 'prefix', 'suffix', 'template', 'sortcol', 'dedupecol', 'rename_cols', 'pick', 'omit'];
	const items = P.transform.properties.pipe.items.oneOf;
	assert.deepEqual(sorted(items[0].enum), sorted(NOARG));
	assert.deepEqual(sorted(items.slice(1).map((x) => x.required[0])), sorted(PARAM));
	assert.equal(P.transform.properties.pipe.maxItems, 32);
});

test('every object with named properties refuses unknown keys, except the open bind maps', () => {
	const open = new Set(['bind']);   // each kind's bind is checked by its own bind schema
	const bad = [];
	const walk = (o, where) => {
		if (!o || typeof o !== 'object') return;
		if (Array.isArray(o)) return o.forEach((x, i) => walk(x, `${where}[${i}]`));
		if (o.properties && o.type === 'object' && o.additionalProperties === undefined && !open.has(where.split('.').pop())) bad.push(where);
		for (const [k, v] of Object.entries(o)) walk(v, `${where}.${k}`);
	};
	walk(sc, '');
	assert.deepEqual(bad, [], 'objects that accept unknown keys');
});
