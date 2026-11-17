// Run: node --test toolkit/test/make-it-yours.test.mjs
// What `new` leaves for the author: a listing and README that say they are template text, a check.json that takes nothing from the template's
// words (engine apps), and one hint line from check when an old expectation fails after an edit.
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
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-myo-'));
const sh = (home, cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home } });
const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const templates = fs.readdirSync(EX).filter((n) => fs.existsSync(path.join(EX, n, 'check.json')));
const engineMode = (t) => { const f = path.join(EX, t, 'scripts', `${t}__config.json`); return fs.existsSync(f) && fs.existsSync(path.join(EX, t, 'scripts', `${t}__engine.py`)) ? (readJson(f).mode || 'views') : null; };   // the shared engine only: a script with its own config.json is not one

test('new: every template gets a TODO listing and a README note, and lint warns (not fails) about the listing', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	for (const t of templates) {
		const id = `my-${t}`.slice(0, 40);
		const n = sh(home, root, 'new', t, id); assert.equal(n.status, 0, `${t}: ${n.stdout}${n.stderr}`);
		const listing = readJson(path.join(root, id, 'bolt-app.json'));
		for (const k of ['summary', 'role', 'saves']) assert.match(listing[k], /^TODO /, `${t}: ${k} is ${listing[k]}`);
		assert.match(fs.readFileSync(path.join(root, id, 'README.md'), 'utf8'), /^> Template text below \(copied from /, t);
		assert.match(n.stdout, /Make it yours/, t);
		const l = sh(home, root, 'lint', id, '--personal'); assert.equal(l.status, 0, `${t}: ${l.stdout}`);
		assert.match(l.stdout, /warning listing_todo/, t);
	}
});

test('new: an engine app in views or lookup mode gets a check.json with one case per view and none of the template words', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	let seen = 0;
	for (const t of templates.filter((x) => ['views', 'lookup'].includes(engineMode(x)))) {
		const id = `my-${t}`.slice(0, 40);
		assert.equal(sh(home, root, 'new', t, id).status, 0, t);
		const ck = readJson(path.join(root, id, 'check.json'));
		assert.ok(ck.cases.length >= 2, t);
		for (const c of ck.cases) assert.ok(!c.expect && !c.golden, `${t}: case "${c.name}" carries an expectation or a golden`);
		assert.ok(!fs.existsSync(path.join(root, id, 'golden')) || fs.readdirSync(path.join(root, id, 'golden')).length === 0, `${t}: goldens were recorded`);
		if (engineMode(t) === 'views') {
			const cfg = readJson(path.join(root, id, 'scripts', `${id}__config.json`));
			for (const v of cfg.views) assert.ok(ck.cases.some((c) => c.args[0] === v.id), `${t}: no case for view ${v.id}`);
		}
		seen++;
	}
	assert.ok(seen >= 8, `only ${seen} engine templates were covered`);
});

test('new then an edit of the data: check still passes (the cold-run 2 failure), and the sample words may all change', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	assert.equal(sh(home, root, 'new', 'portal-template', 'habit-log').status, 0);
	const fx = path.join(root, 'habit-log', 'scripts', 'habit-log__fixtures.json');
	const rewrite = (v) => (typeof v === 'string' ? (/^[A-Z]/.test(v) ? `${v} (mine)` : v) : Array.isArray(v) ? v.map(rewrite) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, /^(id|status|project_id)$/.test(k) ? x : rewrite(x)])) : v);
	fs.writeFileSync(fx, JSON.stringify(rewrite(readJson(fx)), null, 1));
	const c = sh(home, root, 'check', 'habit-log'); assert.equal(c.status, 0, c.stdout);
	assert.ok(!/Hint:/.test(c.stdout));
});

test('check: a failed old expectation names check.json and the case, and ends with ONE hint line', () => {
	const root = tmp(), home = path.join(root, 'home'); fs.mkdirSync(home);
	assert.equal(sh(home, root, 'new', 'script-template', 'my-app').status, 0);
	const f = path.join(root, 'my-app', 'check.json'), ck = readJson(f);
	ck.cases[0].expect = { text_present: ['Words from the template that no longer exist'] };
	ck.cases[1].expect = { text_present: ['Another stale word'] };
	fs.writeFileSync(f, JSON.stringify(ck, null, 2));
	const c = sh(home, root, 'check', 'my-app');
	assert.equal(c.status, 1);
	assert.match(c.stdout, /check\.json, case "overview: tile, drill, Check again": output does not contain "Words from the template/);
	assert.equal((c.stdout.match(/Hint: check\.json still expects/g) || []).length, 1, c.stdout);
	assert.match(c.stdout, /--update-golden/);
});
