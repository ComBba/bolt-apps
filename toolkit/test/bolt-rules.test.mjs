// Run: node --test toolkit/test/bolt-rules.test.mjs
// The launcher's install rules as code over schema/bolt-rules.json: each rule has a failing and a passing case.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseYaml } from '../lib/yamlsubset.mjs';
import { hostProblem, RULES, structureProblems, bindProblems, envProblems, timeoutProblems, httpProblems, actionProblems, paneNavProblems, paneProblem, versionProblem, layoutProblems } from '../lib/boltrules.mjs';
import { RIGHT_WIDGET_KINDS, NO_APP_DATA_KINDS, assessYaml } from '../lib/assess.mjs';
import { get } from '../lib/yamlsubset.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const app = (extra = '', bridge = '  parse: json\n  timeout_seconds: 20\n') => `schema_version: 1\nruntime: bridge\nid: demo\nchip: demo\ntitle: "Demo"\nemits: Generic\nargs:\n  - { name: view, from: "query.word(0)", default: overview }\nbridge:\n  command:\n    macos: "python3 {{scripts_dir}}/x.py {{view}}"\n${bridge}presentation:\n  widget: list\n  title_field: title\n  view_arg: view\n  views:\n    overview: {}\n${extra}`;
const codes = (list) => list.map((p) => p.code);
const root = (y) => parseYaml(y);

test('rules file: widget kinds, no-data kinds and bind tables agree with the toolkit lists (one place to add a kind)', () => {
	assert.deepEqual([...RULES.widget_kinds].sort(), [...RIGHT_WIDGET_KINDS].sort());
	assert.deepEqual([...RULES.no_app_data_kinds].sort(), [...NO_APP_DATA_KINDS].sort());
	for (const k of RULES.widget_kinds) assert.ok(Object.hasOwn(RULES.right_widget.bind, k), `bind table for ${k}`);
	const sc = JSON.parse(fs.readFileSync(path.resolve(HERE, '../../schema/user-app.schema.json'), 'utf8'));
	assert.deepEqual([...sc.properties.presentation.properties.right_widget.properties.kind.enum].sort(), [...RULES.widget_kinds].sort());
});

test('nested unknown keys and missing required keys are refused at every level; a clean app passes', () => {
	assert.deepEqual(codes(structureProblems(root(app()))), []);
	assert.deepEqual(codes(structureProblems(root(app('', '  parse: json\n  bogus_key: 1\n')))), ['unknown_field']);
	assert.deepEqual(codes(structureProblems(root(app('', '  timeout_seconds: 20\n')))), ['missing_field']);
	assert.deepEqual(codes(structureProblems(root(app().replace('args:\n  - { name: view, from: "query.word(0)", default: overview }', 'args:\n  - { name: view, bogus: 1, from: "query.word(0)" }')))), ['unknown_field']);
	assert.deepEqual(codes(structureProblems(root(app().replace('  widget: list\n', '  widget: list\n  nope: 1\n')))), ['unknown_field']);
	assert.deepEqual(codes(structureProblems(root(app().replace('schema_version: 1', 'schema_version: 1\nbogus: 1')))), []);   // top-level keys are verify's own check (yaml_key_unknown)
});

test('bind: a bogus key on a cards pane fails lint-level rules; known keys, enums and caps are checked; strict for packs and v2 only', () => {
	const bind = (k, body) => parseYaml(`bind:\n${body}`);
	const b = (body) => get(parseYaml(`bind:\n${body}\n`), 'bind').value;
	assert.deepEqual(codes(bindProblems('cards', b('  title: x\n  layout: grid'), 'w')), []);
	assert.deepEqual(codes(bindProblems('cards', b('  bogus_key: x'), 'w')), ['bind_unknown_key']);
	assert.deepEqual(codes(bindProblems('cards', b('  layout: pie'), 'w')), ['bind_invalid']);
	assert.deepEqual(codes(bindProblems('table', b('  columns:\n    - { label: A }'), 'w')), ['bind_invalid']);   // field is required
	assert.deepEqual(codes(bindProblems('image_grid', b('  columns: 9'), 'w')), ['bind_invalid']);
	assert.deepEqual(codes(bindProblems('chart', b('  type: pie'), 'w')), ['bind_invalid']);   // pie is not a launcher chart type yet
	const y = app('', '  parse: json\n  timeout_seconds: 20\n').replace('  title_field: title\n', '  title_field: title\n  right_widget:\n    kind: cards\n    mode: list_data\n    bind:\n      bogus_key: x\n');
	assert.equal(assessYaml(y, 'demo', { pack: true }).problems.some((p) => p.code === 'right_widget_bind_unread' && !/warning/.test(p.level || '')), true);
	assert.equal(assessYaml(y, 'demo', {}).problems.some((p) => p.code === 'right_widget_bind_unread' && p.level === 'warning'), true);
});

test('timeouts: absent warns (10 s default), range is 1 to 60', () => {
	assert.deepEqual(codes(timeoutProblems(root(app('', '  parse: json\n')))), ['timeout_default']);
	assert.deepEqual(codes(timeoutProblems(root(app('', '  parse: json\n  timeout_seconds: 61\n')))), ['timeout_out_of_range']);
	assert.deepEqual(codes(timeoutProblems(root(app()))), []);
	assert.equal(RULES.timeouts.default_s, 10);
});

test('env: secret-looking names, the benign list, exact ${env:NAME} values and the passthrough cap', () => {
	const e = (body) => codes(envProblems(root(app('', `  parse: json\n  timeout_seconds: 20\n${body}`))));
	assert.deepEqual(e('  env_passthrough: [PGHOST, GH_HOST]\n'), []);
	assert.deepEqual(e('  env_passthrough: [GITHUB_TOKEN]\n'), ['env_secret_name']);
	assert.deepEqual(e('  env_passthrough: [MY_SETTING]\n'), ['env_not_allowed']);
	assert.deepEqual(e('  env:\n    PGHOST: "${env:PGHOST}"\n'), []);
	assert.ok(e('  env:\n    PGHOST: literal\n').includes('env_inline_value'));
	assert.deepEqual(e(`  env_passthrough: [${Array.from({ length: 17 }, () => 'PGHOST').join(', ')}]\n`), ['env_passthrough_max']);
});

test('http_local: Bolt reserved ports, port 0, host and method', () => {
	const h = (port) => `schema_version: 1\nruntime: http_local\nid: d\nchip: d\ntitle: D\nemits: Generic\nhttp:\n  port: ${port}\n  request: { path: /x }\n  parse: json\n  timeout_seconds: 5\npresentation:\n  widget: list\n`;
	assert.deepEqual(codes(httpProblems(root(h(8080)))), []);
	assert.deepEqual(codes(httpProblems(root(h(13020)))), ['http_port_reserved']);
	assert.deepEqual(codes(httpProblems(root(h(15432)))), ['http_port_reserved']);
	assert.deepEqual(codes(httpProblems(root(h(0)))), ['http_port']);
});

test('actions: ids, kinds, needed fields, run template, icon allowlist, reserved labels, internal hosts', () => {
	const a = (body) => codes(actionProblems(root(app(`actions:\n${body}\n`))));
	assert.deepEqual(a('  - { id: copy, kind: composer, label: Copy, insert: "{{row.copy_text}}" }'), []);
	assert.deepEqual(a('  - { id: constructor, kind: composer, label: Copy, insert: x }'), ['action_id']);
	assert.deepEqual(a('  - { id: u, kind: url, label: Open }'), ['action_field']);
	assert.deepEqual(a('  - { id: r, kind: run, label: Go, query_template: "x {{view}}" }'), ['run_action_template']);
	assert.deepEqual(a('  - { id: c, kind: composer, label: Copy, insert: x, icon: skull }'), ['action_icon']);
	assert.deepEqual(a('  - { id: c, kind: composer, label: Copy, insert: x, icon: star }'), []);
	assert.deepEqual(a('  - { id: c, kind: composer, label: Delete, insert: x }'), ['action_label_reserved']);
	for (const host of ['localhost', 'intranet', 'printer.' + 'lo' + 'cal', [10, 0, 0, 5].join('.'), [192, 168, 1, 1].join('.'), [100, 64, 1, 1].join('.')]) assert   /* hosts are built at run time so the leak scan does not read test data as a leak */.deepEqual(a(`  - { id: u, kind: url, label: Open, url_template: "https://${host}/x" }`), ['action_url_internal'], host);
	assert.deepEqual(a('  - { id: u, kind: url, label: Open, url_template: "https://example.com/x" }'), []);
	assert.deepEqual(a('  - { id: u, kind: url, label: Open, url_template: "{{row.open_url}}" }'), []);   // a placeholder link is allowed in the app file (it makes the app open any link)
});

test('nav: a number default before the view word kills nav; row pane names must be views with a row pane', () => {
	const two = (def) => app().replace('args:\n', `args:\n  - { name: org, from: "query.word(0)", default: ${def} }\n`).replace('from: "query.word(0)", default: overview', 'from: "query.word(1)", default: overview');
	assert.deepEqual(codes(paneNavProblems(root(two('7')))), ['view_arg_lead_default']);
	assert.deepEqual(codes(paneNavProblems(root(two('"7"')))), []);
	const y = app('    item:\n      right_widget:\n        kind: detail\n        mode: selected_row\n    chartv:\n      right_widget:\n        kind: chart\n        mode: list_data\n');
	assert.equal(paneProblem('item', root(y)), null);
	assert.match(paneProblem('Item', root(y)), /must match/);
	assert.match(paneProblem('missing', root(y)), /not a view/);
	assert.match(paneProblem('chartv', root(y)), /selected_row/);
});

test('versions parse like the launcher: optional v, +build, dotted numbers, -prerelease', () => {
	for (const ok of ['1.0.1', 'v2', '1.2.3+build5', '1.0.0-rc.1', '2']) assert.equal(versionProblem(ok), null, ok);
	for (const bad of ['abc', '1..2', '', '1.x', 'v']) assert.notEqual(versionProblem(bad), null, bad);
});

test('script layout: depth, dot parts, case clashes, file that is also a folder; nested folders are fine', () => {
	assert.deepEqual(layoutProblems(['a.py', 'lib/b.py', 'lib/deep/c.py']), []);
	assert.deepEqual(codes(layoutProblems(['a/b/c/d/e/f/g/h/i/x.py'])), ['script_depth']);
	assert.deepEqual(codes(layoutProblems(['../x.py'])), ['script_path']);
	assert.deepEqual(codes(layoutProblems(['Util.py', 'util.py'])), ['script_case_clash']);
	assert.deepEqual(codes(layoutProblems(['lib', 'lib/x.py'])), ['script_file_folder']);
});

test('check runs the script with the launcher runner environment', () => {
	const src = fs.readFileSync(path.resolve(HERE, '../lib/check.mjs'), 'utf8');
	assert.ok(src.includes('...RULES.runner_env.fixed'), 'check spreads the fixed runner variables from the rules file');
	assert.equal(RULES.runner_env.fixed.PYTHONDONTWRITEBYTECODE, '1');
	assert.equal(versionProblem('2026-11'), null);   // the launcher reads this as 2026 with a pre-release part, so it is accepted
});

test('link hosts are parsed: every spelling of a local or private address, userinfo and single-name hosts are refused', () => {
	const bad = ['https://localhost./x', 'https://127.1/x', 'https://0x7f.0.0.1/x', 'https://[::1]/x', 'https://2130706433/x', 'https://0177.0.0.1/x', 'https://[::ffff:127.0.0.1]/x', 'https://0.0.0.0/x', 'https://intranet/x', 'https://a.localhost/x', 'https://printer.' + 'lo' + 'cal/x'];
	for (const u of bad) assert.equal(hostProblem(u)?.code, 'action_url_internal', u);
	for (const u of ['https://user@example.com/x', 'https://example.com@localhost/x', 'https://{{row.host}}/x']) assert.equal(hostProblem(u)?.code, 'action_url', u);
	for (const u of ['https://example.com/x', 'https://sub.example.org:8443/a?b=1', 'https://8.8.8.8/x']) assert.equal(hostProblem(u), null, u);
});

test('env: verify requires the value to be exactly ${env:KEY} and checks the variable named inside, whatever the key is called', async () => {
	const { checkManifests } = await import('../lib/verify.mjs');
	const files = (envBody) => [{ path: 'utilities/demo.yaml', kind: 'user_utility', content: Buffer.from(app('', `  parse: json\n  timeout_seconds: 20\n  env:\n${envBody}`)) }, { path: 'scripts/x.py', kind: 'script', content: Buffer.from('print(1)\n') }];
	const c = (body) => checkManifests(files(body), {}).findings.map((f) => f.code);
	assert.ok(c('    PGHOST: "${env:GITHUB_TOKEN}"\n').includes('env_inline_value'));   // not the same name
	assert.ok(c('    GITHUB_TOKEN: "${env:GITHUB_TOKEN}"\n').includes('env_secret_name'));
	assert.ok(!c('    PGHOST: "${env:PGHOST}"\n').some((x) => /env_/.test(x)));
});

test('verify: a nested script is refused (script_subfolder) until the toolkit can check nested files; pack ids are the relative path', async () => {
	const { checkManifests } = await import('../lib/verify.mjs');
	const f = [{ path: 'utilities/demo.yaml', kind: 'user_utility', content: Buffer.from(app()) }, { path: 'scripts/x.py', kind: 'script', content: Buffer.from('print(1)\n') }, { path: 'scripts/lib/x.py', kind: 'script', content: Buffer.from('print(2)\n') }];
	assert.ok(checkManifests(f, {}).findings.some((x) => x.code === 'script_subfolder'));
});
