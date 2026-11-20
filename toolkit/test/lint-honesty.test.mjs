// Run: node --test toolkit/test/lint-honesty.test.mjs
// 1. A transform step the runtime recognizes but does not run yet is a warning (the app loads; the step fails when it runs).
// 2. The install-prompt scan does not fire on comments or on description text, and still fires on a real command.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assessYaml, scanMentions } from '../lib/assess.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.resolve(HERE, '../bin/bolt-apps.mjs');
const run = (cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8' });
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-lint-'));
const RESERVED = ['yaml', 'toml', 'env', 'properties', 'camel', 'snake', 'kebab', 'slug', 'flatten', 'rename_cols', 'redact_secrets'];

const app = (pipe, extra = '') => `schema_version: 1\nruntime: transform\nid: demo\nchip: demo\ntitle: "Demo"\nicon: globe\ndescription: Demo\nemits: Generic\npresentation:\n  widget: detail\ntransform:\n  pipe:\n${pipe}\n${extra}`;
const reserved = (y) => assessYaml(y, 'demo', {}).problems.filter((p) => p.code === 'pipe_step_not_supported');

test('a reserved pipe step is warned about by name, in the plain words the runtime uses', () => {
	for (const name of RESERVED) {
		const y = app(`    - trim\n    - ${name}`);
		const p = reserved(y); assert.equal(p.length, 1, name);
		assert.equal(p[0].level, 'warning', name);
		assert.match(p[0].message, new RegExp(`'${name}'`)); assert.match(p[0].message, /recognized but not yet supported/);
		assert.match(p[0].message, /step 2/);
	}
	const obj = reserved(app('    - { rename_cols: { a: b } }'));
	assert.equal(obj.length, 1); assert.match(obj[0].message, /'rename_cols'/);
});

test('supported steps and look-alike words do not warn', () => {
	assert.deepEqual(reserved(app('    - trim\n    - upper\n    - { replace: { from: a, to: b } }\n    - sanitize')), []);
	assert.deepEqual(reserved(app('    - trim', 'description2: "camel snake yaml"')), []);
	// a step named only in a comment or a description is not a step
	assert.deepEqual(reserved(app('    - trim\n    # - slug').replace('description: Demo', 'description: "use slug or yaml here"')), []);
});

test('lint (gallery app) and verify (its pack) both warn and exit 0', () => {
	const d = tmp(); assert.equal(run(d, 'new', 'demo-app', '--type', 'transform').status, 0);
	const f = path.join(d, 'apps/demo-app/utilities/demo-app.yaml');
	fs.writeFileSync(f, fs.readFileSync(f, 'utf8').replace('    - upper', '    - upper\n    - redact_secrets'));
	const l = run(d, 'lint', 'apps/demo-app', '--json'); assert.equal(l.status, 0, l.stdout + l.stderr);
	assert.ok(JSON.parse(l.stdout).reports[0].findings.some((x) => x.code === 'pipe_step_not_supported' && x.level === 'warning' && /redact_secrets/.test(x.message)), l.stdout);
	const key = path.join(d, 'k.pem'), out = path.join(d, 'x.boltpack');
	assert.equal(run(d, 'keygen', '--out', key).status, 0);
	assert.equal(run(d, 'pack', 'apps/demo-app', '--key', key, '--out', out).status, 0);
	const v = run(d, 'verify', out, '--json'); assert.equal(v.status, 0, v.stdout + v.stderr);
	assert.ok(JSON.parse(v.stdout).findings.some((x) => x.code === 'pipe_step_not_supported' && x.level === 'warning'), v.stdout);
});

const f = (name, text) => [{ name, text }];
test('scan: comments and description text do not trigger open or curl, a real command still does', () => {
	assert.deepEqual(scanMentions(f('a.sh', '# open /var/log in your editor\n# curl https://x.example.com/y\n')), []);
	assert.deepEqual(scanMentions(f('a.py', '  # open "/tmp/x" to see it\n')), []);
	assert.deepEqual(scanMentions(f('app.yaml', 'description: "Wraps curl so you can fetch pages"\n')), []);
	assert.deepEqual(scanMentions(f('app.yaml', 'description: "open /var/log in your editor"\n')), []);
	assert.deepEqual(scanMentions(f('app.yaml', 'placeholder_examples: ["curl it"]\ndescription: Wraps wget\n')), []);
	// true positives stay
	assert.deepEqual(scanMentions(f('a.sh', '# note\nopen /tmp/x\n')), ['open (starts other programs or documents) (in a.sh)']);
	assert.deepEqual(scanMentions(f('a.sh', '# note\ncurl https://api.example.com/x\n')), ['curl or wget to api.example.com, which it does not declare (in a.sh)']);
	assert.deepEqual(scanMentions(f('app.yaml', 'bridge:\n  command:\n    macos: "curl https://api.example.com/x"\n')), ['curl or wget to api.example.com, which it does not declare (in app.yaml)']);
	assert.deepEqual(scanMentions(f('app.yaml', 'description: Demo\ncommand: "open /tmp/x"\n')), ['open (starts other programs or documents) (in app.yaml)']);
});
