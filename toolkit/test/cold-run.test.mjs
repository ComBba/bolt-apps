// Cold-run fixes: what a first-time author hits. new then check for every template, a failed --emit-yaml, an app file that is not YAML.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const CLI = path.join(REPO, 'toolkit/bin/bolt-apps.mjs');
const EX = path.join(REPO, 'kit/examples');
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-coldrun-'));
const sh = (home, cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home } });
const templates = fs.readdirSync(EX).filter((n) => fs.existsSync(path.join(EX, n, 'check.json')));

test('new then check passes for EVERY template, and again after --emit-yaml for engine templates', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	assert.ok(templates.length >= 15, `found ${templates.length} templates`);
	for (const t of templates) {
		const id = `cr-${t}`.slice(0, 40);
		const n = sh(home, root, 'new', t, id); assert.equal(n.status, 0, `${t}: ${n.stdout}${n.stderr}`);
		assert.match(n.stdout, /check passes/, `${t}: new must say check passes (and mean it): ${n.stdout}`);
		const eng = path.join(root, id, 'scripts', `${id}__engine.py`);
		if (fs.existsSync(eng) && fs.readFileSync(eng, 'utf8').includes('--emit-yaml')) {
			const e = spawnSync('python3', [eng, '--emit-yaml'], { cwd: path.join(root, id, 'scripts'), encoding: 'utf8' });
			assert.equal(e.status, 0, `${t}: ${e.stderr}`);
			fs.writeFileSync(path.join(root, id, 'utilities', `${id}.yaml`), e.stdout);
			const c2 = sh(home, root, 'check', id); assert.equal(c2.status, 0, `${t} after --emit-yaml: ${c2.stdout}`);
		}
	}
});

test('new says honestly when check does not pass (never "passes")', () => {
	const src = fs.readFileSync(path.join(REPO, 'toolkit/lib/workflow.mjs'), 'utf8');
	assert.match(src, /CHECK DOES NOT PASS YET/);
	assert.match(src, /bolt\(\['check', dir\]\)/);   // a plain second run, not only --update-golden
});

test('new: sample words of the template stay out of check.json, so the first edit of the data does not break check', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	assert.equal(sh(home, root, 'new', 'portal-template', 'quote-box').status, 0);
	const cfg = JSON.parse(fs.readFileSync(path.join(root, 'quote-box', 'check.json'), 'utf8'));
	const text = JSON.stringify(cfg);
	for (const w of ['Example Co', 'Example Service', 'Crash on startup']) assert.ok(!JSON.stringify(cfg.cases.map((c) => c.expect && c.expect.text_present)).includes(w), w);
	assert.ok(text.includes('Enter to retry'), 'the engine own words are kept');
	// the author puts their own words in config and fixtures, then re-records the goldens: check passes
	const f = path.join(root, 'quote-box', 'scripts', 'quote-box__fixtures.json'); fs.writeFileSync(f, fs.readFileSync(f, 'utf8').replaceAll('Example Co', 'Quote Co').replaceAll('Crash on startup', 'Boom'));
	const g = path.join(root, 'quote-box', 'scripts', 'quote-box__config.json'); fs.writeFileSync(g, fs.readFileSync(g, 'utf8').replaceAll('Example Service', 'Quotes'));
	const bad = sh(home, root, 'check', 'quote-box'); assert.notEqual(bad.status, 0); assert.match(bad.stdout, /golden_mismatch[^\n]*--update-golden/);
	const up = sh(home, root, 'check', 'quote-box', '--update-golden'); assert.equal(up.status, 0, up.stdout);
	assert.equal(sh(home, root, 'check', 'quote-box').status, 0);
});

const ENGINE_APP = (root, home, id = 'lk') => { assert.equal(sh(home, root, 'new', 'lookup-template', id).status, 0); return path.join(root, id); };

test('--emit-yaml with a bad icon exits non-zero, writes nothing to stdout, names the problem and lists valid icons', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	const app = ENGINE_APP(root, home), cf = path.join(app, 'scripts', 'lk__config.json');
	const c = JSON.parse(fs.readFileSync(cf, 'utf8')); c.app.icon = 'tag'; fs.writeFileSync(cf, JSON.stringify(c));
	for (const py of ['python3', '/usr/bin/python3']) {
		const r = spawnSync(py, [path.join(app, 'scripts', 'lk__engine.py'), '--emit-yaml'], { cwd: path.join(app, 'scripts'), encoding: 'utf8' });
		assert.equal(r.status, 1, py); assert.equal(r.stdout, '', py);
		assert.match(r.stderr, /icon "tag"/); assert.match(r.stderr, /Valid icons: .*git-commit/); assert.match(r.stderr, /no app file was written/);
	}
	// an unreadable config is a failure too, not an error row
	fs.writeFileSync(cf, '{ not json');
	const r2 = spawnSync('python3', [path.join(app, 'scripts', 'lk__engine.py'), '--emit-yaml'], { cwd: path.join(app, 'scripts'), encoding: 'utf8' });
	assert.equal(r2.status, 1); assert.equal(r2.stdout, ''); assert.match(r2.stderr, /Could not read/);
});

test('run, lint and check say the app file is not YAML, and run shows the real cause from the engine', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	const app = ENGINE_APP(root, home), yf = path.join(app, 'utilities', 'lk.yaml');
	fs.writeFileSync(yf, '[{"title":"This app is not set up correctly"}]\n');
	const l = sh(home, root, 'lint', app, '--personal'); assert.equal(l.status, 1); assert.match(l.stdout, /yaml_unreadable_here[^\n]*is JSON, not YAML[^\n]*--emit-yaml/);
	const c = sh(home, root, 'check', app); assert.equal(c.status, 1); assert.match(c.stdout, /app_file_not_yaml[^\n]*JSON, not YAML/);
	const cf = path.join(app, 'scripts', 'lk__config.json'); const cfg = JSON.parse(fs.readFileSync(cf, 'utf8')); cfg.app.icon = 'tag'; fs.writeFileSync(cf, JSON.stringify(cfg));
	const r = sh(home, root, 'run', app, 'x', '--sample'); assert.equal(r.status, 1);
	assert.match(r.stderr, /The real cause, from the engine/); assert.match(r.stderr, /icon "tag"/);
	fs.writeFileSync(yf, '');
	assert.match(sh(home, root, 'check', app).stdout, /app file is empty/);
});

test('check warns (config_copy_ignored) when a chained lookup declares copy on a row, and not for the shipped lookup-template', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	const app = ENGINE_APP(root, home), cf = path.join(app, 'scripts', 'lk__config.json');
	assert.doesNotMatch(sh(home, root, 'check', app).stdout, /config_copy_ignored/);
	const c = JSON.parse(fs.readFileSync(cf, 'utf8')); assert.ok(Array.isArray(c.lookup.rows), 'the template is a chained lookup');
	c.lookup.rows[0].copy = 'serde = "1"'; fs.writeFileSync(cf, JSON.stringify(c, null, 2));
	const r = sh(home, root, 'check', app); assert.match(r.stdout, /warning config_copy_ignored: lookup\.rows\[0\]/); assert.equal(r.status, 0, 'a warning, not a failure');
});
