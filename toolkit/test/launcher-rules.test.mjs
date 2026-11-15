// Run: node --test toolkit/test/launcher-rules.test.mjs
// Rules the real Bolt launcher enforces that the toolkit used to miss. Each rule has a failing and a passing case, and the
// comment names the launcher file it mirrors (the launcher's own rules).
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assessYaml, RIGHT_WIDGET_KINDS, NO_APP_DATA_KINDS } from '../lib/assess.mjs';
import { checkRows } from '../lib/check.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.resolve(HERE, '../bin/bolt-apps.mjs');
const run = (cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8' });
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-rules-'));
const write = (f, c) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, c); };
const cmd = (o) => `"${o === 'windows' ? 'python' : 'python3'} {{scripts_dir}}/demo__run.py {{view}}"`;

// A bridge app file. opts: views (array of names), viewArg, argFrom, oses, rightWidget (yaml text), extra (top-level text).
function appYaml(o = {}) {
	const oses = o.oses || ['macos', 'linux', 'windows'], views = o.views ?? ['overview', 'list'];
	const argFrom = o.argFrom ?? 'query.word(0)';
	const L = ['schema_version: ' + (o.schemaVersion || 1), 'runtime: bridge', 'id: demo', 'chip: demo', 'title: "Demo"', 'icon: globe', 'description: "Demo"', 'emits: Generic',
		'args:', `  - { name: view, from: "${argFrom}", default: overview }`,
		'bridge:', '  command:', ...oses.map((x) => `    ${x}: ${cmd(x)}`), '  parse: json', '  timeout_seconds: 20',
		'presentation:', '  widget: list', '  title_field: title'];
	if (o.viewArg !== null && views.length) L.push(`  view_arg: ${o.viewArg ?? 'view'}`);
	if (o.rightWidget) L.push(...o.rightWidget.split('\n'));
	if (views.length) { L.push('  views:'); for (const v of views) L.push(`    ${v}: {}`); }
	return L.join('\n') + '\n' + (o.extra || '');
}
const codes = (y, opts) => assessYaml(y, 'demo', opts).problems.map((p) => p.code).sort();
const only = (y, code, opts) => assessYaml(y, 'demo', opts).problems.filter((p) => p.code === code);
const PLATFORMS = ['macos', 'linux', 'windows'];

// ---- views (the launcher validate_views, MAX_VIEWS) ----
test('views: more than 8 including the overview is refused; exactly 8 passes', () => {
	const nine = ['overview', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], eight = nine.slice(0, 8);
	assert.deepEqual(codes(appYaml({ views: nine })), ['views_too_many']);
	assert.deepEqual(codes(appYaml({ views: eight })), []);
});
test('views: a view name must match ^[a-z][a-z0-9_-]{0,23}$ and not be constructor or prototype', () => {
	for (const bad of ['Overview', 'aB', 'x'.repeat(25), 'constructor', 'prototype']   // (a name starting with a digit or holding a dot is outside the readable YAML subset: yaml_unreadable_here)
	) assert.deepEqual(codes(appYaml({ views: ['overview', bad] })).filter((c) => c === 'view_name_invalid'), ['view_name_invalid'], bad);
	for (const ok of ['overview', 'x'.repeat(24), 'a-b_c9']) assert.deepEqual(codes(appYaml({ views: [ok] })), [], ok);
});
test('views: view_arg is required, must be a declared arg, and must be bound with query.word(N)', () => {
	assert.deepEqual(codes(appYaml({ viewArg: null })), ['view_arg_missing']);
	assert.deepEqual(codes(appYaml({ viewArg: 'nope' })), ['view_arg_unknown']);
	assert.deepEqual(codes(appYaml({ argFrom: 'clipboard' })), ['view_arg_not_query_word']);
	assert.deepEqual(codes(appYaml({ views: [], viewArg: 'view' }).replace('  widget: list\n', '  widget: list\n  view_arg: view\n')), ['view_arg_without_views']);
	assert.deepEqual(codes(appYaml({ argFrom: 'query.word( 2 )' })), ['view_arg_lead_default']);   // binds fine, but words 0 and 1 have no default, so nav is dead (tested below)
	assert.deepEqual(codes(appYaml({ argFrom: 'query.word( 0 )' })), []);
});

test('views: a word before the view word needs a nav-token default; "-" there kills drill and Back, "-" after it is fine', () => {
	const two = (def) => appYaml({ argFrom: 'query.word(1)' }).replace('args:\n', `args:\n  - { name: org, from: "query.word(0)", default: ${def} }\n`);
	assert.deepEqual(codes(two('"-"')), ['view_arg_lead_default']);
	assert.deepEqual(codes(two('"-x"')), ['view_arg_lead_default']);
	assert.deepEqual(codes(appYaml({ argFrom: 'query.word(1)' })), ['view_arg_lead_default']);   // nothing is bound to word 0 at all
	assert.deepEqual(codes(two('all')), []);
	assert.deepEqual(codes(appYaml().replace('args:\n', 'args:\n  - { name: q, from: "query.word(1)", default: "-" }\n')), []);   // after the view word: fine
});

// ---- escapes (the launcher read_file_set) ----
test('escapes: \\x, \\u and \\U in the app file are refused by lint --personal and verify; plain text passes', () => {
	for (const [name, text] of [['\\x', '# hello \\x7b\n'], ['\\u', 'x_note: "a \\u007b b"\n'], ['\\U', '# \\U0000007b\n']]) {
		const d = personalApp(tmp(), { extra: text });
		for (const c of ['lint', 'verify']) { const r = run(d.root, c, d.dir, '--personal', '--json'); assert.equal(r.status, 1, `${name} ${c}`); assert.match(r.stdout, /yaml_escape/); }
	}
	const ok = personalApp(tmp(), { extra: '# a path C:\\Users is fine, so is a backslash-n written as text\n' });
	assert.equal(run(ok.root, 'lint', ok.dir, '--personal').status, 0);
	const v = run(ok.root, 'verify', ok.dir, '--json'); assert.doesNotMatch(v.stdout, /yaml_escape/);
});

// ---- scripts folder (the launcher) ----
test('scripts: a script over 2 MB is an error when named, a warning when not; a small one passes', () => {
	const d = personalApp(tmp()); write(path.join(d.dir, 'scripts', 'demo__run.py'), '#!/usr/bin/env python3\n' + 'x = 1\n'.repeat(450000));
	for (const c of ['lint', 'verify']) { const r = run(d.root, c, d.dir, '--personal', '--json'); assert.equal(r.status, 1, c); assert.match(r.stdout, /script_too_large/); }
	const e = personalApp(tmp()); write(path.join(e.dir, 'scripts', 'demo__unused.dat.py'), '#' + 'x'.repeat(2 * 1024 * 1024));
	const r = run(e.root, 'lint', e.dir, '--personal', '--json'); const j = JSON.parse(r.stdout);
	assert.equal(r.status, 0, r.stdout); assert.ok(j.reports[0].findings.some((f) => f.code === 'script_too_large' && f.level === 'warning'));
	const ok = personalApp(tmp()); assert.ok(!/script_too_large/.test(run(ok.root, 'lint', ok.dir, '--personal', '--json').stdout));
});
test('scripts: a symlink or a non-plain file in scripts/ is refused with its own code', { skip: process.platform === 'win32' }, () => {
	const d = personalApp(tmp()); fs.symlinkSync('/etc/hosts', path.join(d.dir, 'scripts', 'demo__link.py'));
	let r = run(d.root, 'lint', d.dir, '--personal', '--json'); assert.equal(r.status, 1); assert.match(r.stdout, /script_symlink/);
	const e = personalApp(tmp()); assert.equal(spawnSync('mkfifo', [path.join(e.dir, 'scripts', 'demo__pipe.py')]).status, 0);
	r = run(e.root, 'lint', e.dir, '--personal', '--json'); assert.equal(r.status, 1); assert.match(r.stdout, /script_not_plain/);
	const ok = personalApp(tmp()); assert.doesNotMatch(run(ok.root, 'lint', ok.dir, '--personal', '--json').stdout, /script_symlink|script_not_plain/);
});

// ---- no command for a platform (warning, not error) ----
test('bridge command: a missing OS is a warning per OS, never an error; all three is clean; platforms limits it', () => {
	const w = only(appYaml({ oses: ['macos'] }), 'command_os_missing'); assert.equal(w.length, 2); assert.ok(w.every((x) => x.level === 'warning'));
	assert.deepEqual(w.map((x) => /no (\w+) entry/.exec(x.message)[1]).sort(), ['linux', 'windows']);
	assert.equal(only(appYaml(), 'command_os_missing').length, 0);
	assert.equal(only(appYaml({ oses: ['macos'] }), 'command_os_missing', { platforms: ['macos'] }).length, 0);
	const d = personalApp(tmp(), { oses: ['macos'] });
	const r = run(d.root, 'verify', d.dir, '--json'), j = JSON.parse(r.stdout);
	assert.equal(r.status, 0); assert.equal(j.findings.filter((f) => f.code === 'command_os_missing').length, 2);
});

// ---- right panes (the launcher kinds BIND_NONE chart types; the launcher NO_APP_DATA) ----
test('right_widget: image, color, weather, date and calc show no app data (warning); the others do not warn', () => {
	for (const k of ['image', 'color', 'weather', 'date', 'calc']) assert.deepEqual(codes(appYaml({ rightWidget: `  right_widget:\n    kind: ${k}\n    mode: selected_row` })), ['right_widget_no_data'], k);
	for (const k of ['table', 'detail', 'cards', 'chart', 'markdown', 'map', 'image_grid']) assert.deepEqual(codes(appYaml({ rightWidget: `  right_widget:\n    kind: ${k}\n    mode: selected_row` })), [], k);
	assert.equal(only(appYaml({ rightWidget: '  right_widget:\n    kind: weather' }), 'right_widget_no_data')[0].level, 'warning');
});
test('right_widget: map takes no bind keys (warning in schema 1, error in schema 2); unknown kind and chart type are refused', () => {
	const map = (v) => appYaml({ schemaVersion: v, rightWidget: '  right_widget:\n    kind: map\n    bind:\n      points: "{{row.x}}"' });
	assert.equal(only(map(1), 'right_widget_bind_unread')[0].level, 'warning');
	assert.equal(only(map(2), 'right_widget_bind_unread')[0].level, 'error');
	assert.match(only(map(2), 'right_widget_bind_unread')[0].message, /Open in Maps/);
	assert.deepEqual(codes(appYaml({ rightWidget: '  right_widget:\n    kind: globe' })), ['right_widget_kind_invalid']);
	assert.deepEqual(codes(appYaml({ rightWidget: '  right_widget:\n    kind: entity' })), ['right_widget_kind_invalid']);
	assert.deepEqual(codes(appYaml({ rightWidget: '  right_widget:\n    kind: chart\n    bind:\n      type: donut' })), ['right_widget_bind_unread']);
	for (const t of ['line', 'bar', 'sparkline']) assert.deepEqual(codes(appYaml({ rightWidget: `  right_widget:\n    kind: chart\n    bind:\n      type: ${t}` })), [], t);
});
test('actions: a manifest run action needs fixed text (the launcher)', () => {
	assert.deepEqual(codes(appYaml({ extra: 'actions:\n  - { id: again, kind: run, label: Again, query_template: "{{view}}" }\n' })), ['run_action_template']);
	assert.deepEqual(codes(appYaml({ extra: 'actions:\n  - { id: again, kind: run, label: Again, query_template: refresh }\n' })), []);
});

// ---- rows: nav tokens and row action kinds (the launcher) ----
test('rows: nav view and arg follow NAV_ARG_RE and carry no ".."; a row action of kind run is named as such', () => {
	const row = (nav) => [{ title: 'x', nav }];
	const errs = (rows) => checkRows(rows).filter((f) => f.level === 'error').map((f) => f.code);
	assert.deepEqual(errs(row({ view: 'list', arg: 'abc-1.2_x' })), []);
	assert.deepEqual(errs(row({ view: 'list', arg: 'a'.repeat(64) })), []);
	assert.ok(errs(row({ view: 'list', arg: 'a..b' })).includes('nav_token_invalid'));   // matches the schema pattern, but the launcher refuses ".."
	assert.ok(errs(row({ view: 'list', arg: '-all' })).includes('schema_invalid'));
	assert.ok(errs(row({ view: 'list', arg: 'a'.repeat(65) })).includes('schema_invalid'));
	assert.ok(errs(row({ view: 'x..y' })).includes('nav_token_invalid'));
	const withRun = [{ title: 'x', actions: [{ id: 'again', kind: 'run', label: 'Again', query_template: 'refresh' }] }];
	assert.ok(errs(withRun).includes('row_action_run'));
	assert.deepEqual(errs([{ title: 'x', actions: [{ id: 'open', kind: 'url', label: 'Open', url_template: 'https://example.com' }] }]), []);
});

// ---- pack ----
test('pack: the version-order refusal is explained, and the pack never lands inside the app folder', () => {
	const d = personalApp(tmp()), key = path.join(d.root, 'k.pem'); assert.equal(run(d.root, 'keygen', '--out', key).status, 0);
	const r = run(d.dir, 'pack', '.', '--personal', '--key', key);   // run from inside the app folder, no --out
	assert.equal(r.status, 0, r.stderr); assert.match(r.stdout, /same_or_older_version/); assert.match(r.stdout, /bump --version/);
	assert.ok(!fs.existsSync(path.join(d.dir, 'demo.boltpack')), 'default output must not be inside the app folder');
	assert.ok(fs.existsSync(path.join(d.root, 'apps', 'demo.boltpack')) || fs.existsSync(path.join(d.root, 'demo.boltpack')));
	const again = run(d.dir, 'pack', '.', '--personal', '--key', key); assert.equal(again.status, 0, again.stderr + again.stdout);   // a second pack does not fail
	// even an explicit --out inside the folder cannot poison the next pack (a *.boltpack there is ignored) and it is warned about
	const inside = run(d.dir, 'pack', '.', '--personal', '--key', key, '--out', 'demo-1.0.0.boltpack'); assert.equal(inside.status, 0); assert.match(inside.stderr, /inside the app folder/);
	assert.equal(run(d.dir, 'pack', '.', '--personal', '--key', key, '--version', '1.0.1').status, 0);
});

// ---- helper files (the launcher read_file_set hashes only the manifest and {{scripts_dir}}/<file> names) ----
test('helper files: a data file a script reads but no command names is warned about; naming it clears the warning', () => {
	const helper = (named) => { const d = personalApp(tmp(), { cmdExtra: named ? ' {{scripts_dir}}/demo__config.json' : '' }); write(path.join(d.dir, 'scripts', 'demo__config.json'), '{}'); write(path.join(d.dir, 'scripts', 'demo__run.py'), '#!/usr/bin/env python3\nimport json\njson.load(open("config.json"))  # "config.json"\n'); return d; };
	const w = (d) => JSON.parse(run(d.root, 'verify', d.dir, '--json').stdout).findings.filter((f) => f.code === 'helper_not_hashed');
	const bad = w(helper(false)); assert.equal(bad.length, 1); assert.equal(bad[0].level, 'warning'); assert.match(bad[0].message, /approval hash/);
	assert.equal(w(helper(true)).length, 0);
});

// A personal app: listing, one app file, one script. opts feed appYaml, plus cmdExtra (words added to every command) and extra.
function personalApp(root, o = {}) {
	const dir = path.join(root, 'apps', 'demo');
	let y = appYaml(o); if (o.cmdExtra) y = y.replace(/(\{\{scripts_dir\}\}\/demo__run\.py \{\{view\}\})/g, `$1${o.cmdExtra}`);
	write(path.join(dir, 'bolt-app.json'), JSON.stringify({ schema_version: 1, id: 'demo', title: 'Demo', role: 'Me', saves: 'A lookup', summary: 'Demo.', author: { name: 'Tester' }, tier: 3, permissions: ['runs_commands'], platforms: o.platformsListing, tests: [] }));
	write(path.join(dir, 'utilities', 'demo.yaml'), y);
	write(path.join(dir, 'scripts', 'demo__run.py'), '#!/usr/bin/env python3\nprint("[]")\n');
	return { root, dir };
}

test('a stale app file left beside the regenerated one is refused by lint and pack; one app file passes', () => {
	const d = personalApp(tmp(), {});
	assert.equal(run(d.root, 'lint', d.dir, '--personal').status, 0);
	write(path.join(d.dir, 'utilities', 'old.yaml'), appYaml({}).replace('id: demo', 'id: old-demo').replace('chip: demo', 'chip: olddemo'));
	const r = run(d.root, 'lint', d.dir, '--personal', '--json');
	assert.equal(r.status, 1); assert.match(r.stdout, /utilities_stale_copy/);
	const p = run(d.root, 'pack', d.dir, '--personal', '--out', path.join(d.root, 'x.boltpack'));
	assert.notEqual(p.status, 0);
});

// ---- schema/user-app.schema.json ----
test('schema: every right_widget kind is described, the enum still equals the launcher list, and data-less kinds say so', () => {
	const sc = JSON.parse(fs.readFileSync(path.resolve(HERE, '../../schema/user-app.schema.json'), 'utf8'));
	const kind = sc.properties.presentation.properties.right_widget.properties.kind;
	assert.deepEqual([...kind.enum].sort(), [...RIGHT_WIDGET_KINDS].sort());
	assert.deepEqual(kind.oneOf.map((x) => x.const).sort(), [...kind.enum].sort());
	assert.ok(kind.oneOf.every((x) => x.description.length > 20));
	for (const k of NO_APP_DATA_KINDS) assert.match(kind.oneOf.find((x) => x.const === k).description, /cannot show app data/);
	assert.match(kind.oneOf.find((x) => x.const === 'map').description, /Open in Maps/);
	assert.match(kind.oneOf.find((x) => x.const === 'chart').description, /line, bar or sparkline/);
});
