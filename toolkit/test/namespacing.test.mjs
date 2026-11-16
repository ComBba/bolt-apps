// Run: node --test toolkit/test/namespacing.test.mjs
// Bolt installs every pack's scripts into ONE shared folder and refuses (owned_by_other) a file whose path already belongs to another installed pack.
// These tests simulate that ownership rule on real packs: two apps built from the public examples must never share a script path, and a copy made
// with `new` must carry its own names and none of the template's.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readPack } from '../bin/bolt-apps.mjs';
import { clockVersion, newer } from '../lib/workflow.mjs';
import { BOLT_SAYS, markdownTable } from '../lib/boltsays.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const CLI = path.resolve(HERE, '../bin/bolt-apps.mjs');
const EX = path.join(REPO, 'kit', 'examples');
const tmp = (p) => fs.mkdtempSync(path.join(os.tmpdir(), p));
const cli = (home, cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home } });
const KEY = (() => { const d = tmp('ns-key-'); const k = path.join(d, 'key.pem'); const r = spawnSync(process.execPath, [CLI, 'keygen', '--out', k], { encoding: 'utf8' }); assert.equal(r.status, 0, r.stderr); return k; })();
const examples = fs.readdirSync(EX, { withFileTypes: true }).filter((e) => e.isDirectory() && fs.existsSync(path.join(EX, e.name, 'bolt-app.json'))).map((e) => e.name);

// What Bolt would write under scripts/ for this pack: the path of every script entry, relative to scripts/.
function installedScripts(pack) {
	const r = readPack(pack); assert.ok(r.ok, `${pack}: ${r.reason}`);
	return r.meta.entries.filter((e) => e.kind === 'script').map((e) => e.path.replace(/^manifests\/scripts\//, ''));
}
function packOf(dir, out) { const r = cli(os.homedir(), REPO, 'pack', dir, '--personal', '--key', KEY, '--out', out); assert.equal(r.status, 0, `${dir}\n${r.stdout}${r.stderr}`); return out; }
// Bolt's ownership by path, case-insensitive (one file on macOS and Windows), and a name that is a file in one pack and a folder in the other.
function clashes(a, b) {
	const out = [], low = (x) => x.toLowerCase();
	for (const x of a) for (const y of b) { const p = low(x), q = low(y); if (p === q || p.startsWith(`${q}/`) || q.startsWith(`${p}/`)) out.push(`${x} vs ${y}`); }
	return out;
}

test('every public example ships only files named for its own app id', () => {
	const out = tmp('ns-all-');
	const sets = new Map(examples.map((n) => [n, installedScripts(packOf(path.join(EX, n), path.join(out, `${n}.boltpack`)))]));
	for (const [n, files] of sets) for (const f of files) assert.ok(f.startsWith(`${n}__`), `${n}: scripts/${f} is not named ${n}__<name>`);
	assert.ok(examples.length >= 21, `expected all 21 examples, found ${examples.length}`);
});

test('any two public examples are pairwise disjoint (Bolt would refuse the second install with owned_by_other)', () => {
	const out = tmp('ns-pairs-');
	const sets = examples.map((n) => [n, installedScripts(packOf(path.join(EX, n), path.join(out, `${n}.boltpack`)))]);
	let pairs = 0;
	for (let i = 0; i < sets.length; i++) for (let j = i + 1; j < sets.length; j++) { pairs++; assert.deepEqual(clashes(sets[i][1], sets[j][1]), [], `${sets[i][0]} and ${sets[j][0]} would collide in Bolt's shared scripts folder`); }
	assert.ok(pairs >= 210);
});

test('the check at the heart of it: two apps that share a bare file name are told apart by the toolkit', () => {
	const d = tmp('ns-bare-'), home = tmp('ns-home-');
	for (const id of ['bare-one', 'bare-two']) {
		const r = cli(home, d, 'new', 'script-template', id, '--dir', d); assert.equal(r.status, 0, r.stderr);
		// undo the namespacing the way an old app would have it
		const sd = path.join(d, id, 'scripts');
		for (const f of fs.readdirSync(sd)) fs.renameSync(path.join(sd, f), path.join(sd, f.replace(`${id}__`, '')));
	}
	const v = cli(home, d, 'lint', path.join(d, 'bare-one'), '--personal'); assert.notEqual(v.status, 0);
	assert.match(v.stdout, /script_not_namespaced/);
	assert.match(v.stdout, /owned_by_other/);
	const p = cli(home, d, 'pack', path.join(d, 'bare-one'), '--personal', '--key', KEY); assert.notEqual(p.status, 0);
});

test('`new` from the same template with two ids gives disjoint paths, and so does a different template', () => {
	const d = tmp('ns-new-'), home = tmp('ns-home-');
	const made = [['portal-template', 'one-app'], ['portal-template', 'two-app'], ['pulse-feed', 'three-app'], ['script-template', 'four-app'], ['expense-tracker', 'five-app']];
	const sets = made.map(([t, id]) => { const r = cli(home, d, 'new', t, id, '--dir', d); assert.equal(r.status, 0, `${t} ${id}\n${r.stdout}${r.stderr}`); return [id, installedScripts(packOf(path.join(d, id), path.join(d, `${id}.boltpack`)))]; });
	for (const [id, files] of sets) { assert.ok(files.length, id); for (const f of files) assert.ok(f.startsWith(`${id}__`), `${id}: ${f}`); }
	for (let i = 0; i < sets.length; i++) for (let j = i + 1; j < sets.length; j++) assert.deepEqual(clashes(sets[i][1], sets[j][1]), []);
});

test('a copy made with `new` keeps none of the template\'s chip, id or title in what the person reads', () => {
	const d = tmp('ns-words-'), home = tmp('ns-home-');
	for (const t of ['branch-explorer', 'acme-dash', 'portal-template', 'script-template', 'pulse-feed', 'around', 'repo-radar', 'cli-wrapper-template', 'unit-convert', 'widget-gallery']) {
		const yamlT = fs.readFileSync(path.join(EX, t, 'utilities', fs.readdirSync(path.join(EX, t, 'utilities'))[0]), 'utf8');
		const oldChip = /^chip: (\S+)/m.exec(yamlT)[1];
		const id = `${t.slice(0, 8).replace(/-$/, '')}-copy`;
		const r = cli(home, d, 'new', t, id, '--dir', d); assert.equal(r.status, 0, `${t}\n${r.stdout}${r.stderr}`);
		const files = [];
		const walk = (x) => { for (const e of fs.readdirSync(x, { withFileTypes: true })) { const f = path.join(x, e.name); if (e.isDirectory()) walk(f); else if (/\.(md|json|yaml)$/.test(e.name) && !/fixtures\.json$|^golden$/.test(e.name) && !f.includes(`${path.sep}golden${path.sep}`)) files.push(f); } };
		walk(path.join(d, id));
		const newChip = /^chip: (\S+)/m.exec(fs.readFileSync(path.join(d, id, 'utilities', `${id}.yaml`), 'utf8'))[1];
		for (const f of files) {
			const text = fs.readFileSync(f, 'utf8'), rel = path.relative(path.join(d, id), f);
			if (oldChip !== newChip) assert.ok(!new RegExp(`=${oldChip}(?![A-Za-z0-9_-])`).test(text), `${t}: ${rel} still tells the person to type =${oldChip}`);
			assert.ok(!new RegExp(`(?<![A-Za-z0-9_-])${t}(?![A-Za-z0-9_]|-[A-Za-z0-9])`).test(text) || /README\.md$/.test(rel) === false, `${t}: ${rel} still names the template ${t}`);
			assert.ok(!text.includes(`${t}__`), `${t}: ${rel} still has the template's file prefix`);
		}
		const lint = cli(home, d, 'lint', path.join(d, id), '--personal'); assert.equal(lint.status, 0, lint.stdout);
		assert.ok(!/description_chip_mismatch/.test(lint.stdout), `${t}: ${lint.stdout}`);
	}
});

test('lint and verify warn when the description names a =chip that is not the app\'s chip', () => {
	const d = tmp('ns-chip-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'branch-explorer', 'chipcheck', '--dir', d).status, 0);
	const y = path.join(d, 'chipcheck', 'utilities', 'chipcheck.yaml');
	fs.writeFileSync(y, fs.readFileSync(y, 'utf8').replace(/^description: "/m, 'description: "Type =branch, then Enter. '));
	for (const a of [['lint', path.join(d, 'chipcheck'), '--personal'], ['verify', path.join(d, 'chipcheck')]]) { const r = cli(home, d, ...a); assert.match(r.stdout, /description_chip_mismatch/, a[0]); assert.match(r.stdout, /=branch/); assert.match(r.stdout, /warning/i); }
});

test('the toolkit refuses a bare shared name; verify says what to do', () => {
	const d = tmp('ns-verify-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'script-template', 'vtest', '--dir', d).status, 0);
	const sd = path.join(d, 'vtest', 'scripts');
	fs.renameSync(path.join(sd, 'vtest__config.json'), path.join(sd, 'config.json'));
	const r = cli(home, d, 'verify', path.join(d, 'vtest'), '--json'); const j = JSON.parse(r.stdout);
	const f = j.findings.find((x) => x.code === 'script_not_namespaced'); assert.ok(f, r.stdout); assert.match(f.fix, /<app id>__/);
});

test('ship: a lost ship.json cannot make a lower version; --version still wins; the reason is printed', async () => {
	const d = tmp('ns-ship-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'script-template', 'shipper', '--dir', d).status, 0);
	const ver = (r) => { assert.equal(r.status, 0, r.stdout + r.stderr); return /Shipped shipper (\S+):/.exec(r.stdout)[1]; };
	const v1 = ver(cli(home, d, 'ship', path.join(d, 'shipper')));
	assert.match(v1, /^1\.0\.\d+$/);
	const r2 = cli(home, d, 'ship', path.join(d, 'shipper')); const v2 = ver(r2); assert.ok(newer(v2, v1), `${v2} must be higher than ${v1}`);
	// lose every note this computer kept
	fs.rmSync(path.join(home, '.bolt-apps', 'ship.json')); fs.rmSync(path.join(home, '.bolt-apps', 'packs'), { recursive: true });
	await new Promise((r) => setTimeout(r, 1100));
	const r3 = cli(home, d, 'ship', path.join(d, 'shipper')); const v3 = ver(r3); assert.ok(newer(v3, v2), `${v3} must be higher than ${v2} after ship.json was deleted`);
	assert.match(r3.stdout, /version \S+: taken from the clock/);
	assert.match(r3.stdout, /HIGH risk/); assert.match(r3.stdout, /owned_by_other/);
	const forced = cli(home, d, 'ship', path.join(d, 'shipper'), '--version', '9.9.9'); assert.equal(ver(forced), '9.9.9');
	const after = cli(home, d, 'ship', path.join(d, 'shipper')); assert.ok(newer(ver(after), '9.9.9'));
	const bad = cli(home, d, 'ship', path.join(d, 'shipper'), '--version', 'abc'); assert.notEqual(bad.status, 0);
});

test('clockVersion follows the rules of Bolt\'s own version order', () => {
	const a = clockVersion(Date.UTC(2026, 10, 15)), b = clockVersion(Date.UTC(2026, 10, 15, 0, 0, 1));
	assert.ok(newer(b, a)); assert.ok(newer('1.0.1000000', '1.0.999999')); assert.ok(!newer('1.0', '1.0.0'));
	assert.match(a, /^1\.0\.[1-9]\d*$/);
});

test('"Bolt said X, do Y": every code has a plain fix, and the table for the docs is generated from the same list', () => {
	const codes = new Set(BOLT_SAYS.map((r) => r[0]));
	for (const c of ['same_or_older_version', 'owned_by_other', 'version_unreadable', 'file_exists', 'file_and_folder', 'case_collision', 'too_deep', 'unsafe_path', 'in_the_way', 'write_failed', 'ledger_unreadable', 'signature_recheck', 'unverified', 'outside_pack', 'cancelled', 'org_policy']) assert.ok(codes.has(c), c);
	for (const [c, said, fix] of BOLT_SAYS) { assert.ok(said.length > 8 && fix.length > 20, c); assert.ok(!/[\u2013\u2014]/.test(said + fix), `${c}: no dashes`); }
	assert.ok(markdownTable().split('\n').length === BOLT_SAYS.length + 2);
	const r = spawnSync(process.execPath, [CLI, 'doctor', '--bolt-says'], { encoding: 'utf8' }); assert.equal(r.status, 0); assert.match(r.stdout, /same_or_older_version/);
});

test('docs/verify-rules.md holds the same "Bolt said X, do Y" table the toolkit prints', () => {
	assert.ok(fs.readFileSync(path.join(REPO, 'docs', 'verify-rules.md'), 'utf8').includes(markdownTable()));
});

test('`new` with an id that contains the template name (X-2, X-2-a, X itself, a prefix, a suffix) never doubles a name', () => {
	const d = tmp('ns-ids-'), home = tmp('ns-home-');
	for (const id of ['script-template-2', 'script-template-2-a', 'script-template', 'script', 'template', 'x-script-template']) {
		const r = cli(home, d, 'new', 'script-template', id, '--dir', d); assert.equal(r.status, 0, `${id}\n${r.stdout}${r.stderr}`);
		const files = fs.readdirSync(path.join(d, id, 'scripts'));
		assert.ok(files.length && files.every((f) => f.startsWith(`${id}__`) && !f.slice(id.length + 2).includes('__')), `${id}: ${files}`);
		const l = cli(home, d, 'lint', path.join(d, id), '--personal'); assert.equal(l.status, 0, `${id}\n${l.stdout}`);
		for (const f of fs.readdirSync(path.join(d, id), { recursive: true })) { const p = path.join(d, id, f); if (fs.statSync(p).isFile() && /\.(md|json|yaml)$/.test(f) && !/fixtures\.json$/.test(f) && !f.includes('golden')) assert.ok(!new RegExp(`${id}-\\d+__|${id}-${id}`).test(fs.readFileSync(p, 'utf8')), `${id}: ${f}`); }
	}
});

test('`new` removes the half-made folder when it fails (no python to generate the app file)', () => {
	const d = tmp('ns-fail-'), id = 'half-made';
	const r = spawnSync(process.execPath, [CLI, 'new', 'portal-template', id, '--dir', d], { encoding: 'utf8', env: { HOME: d, PATH: '/nonexistent' } });
	assert.notEqual(r.status, 0); assert.match(r.stderr, /could not generate/);
	assert.ok(!fs.existsSync(path.join(d, id)), 'no half-made folder is left');
});

test('a pack path over 100 characters is refused by lint with the plain fix', () => {
	const d = tmp('ns-long-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'script-template', 'longer', '--dir', d).status, 0);
	fs.writeFileSync(path.join(d, 'longer', 'scripts', `longer__${'x'.repeat(80)}.py`), 'x');
	const l = cli(home, d, 'lint', path.join(d, 'longer'), '--personal'); assert.equal(l.status, 1); assert.match(l.stdout, /too long for a pack/); assert.match(l.stdout, /shorten the file name or the app id/);
});

test('lint refuses ".." inside a script name (the launcher refuses any path part containing ..)', () => {
	const d = tmp('ns-dots-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'script-template', 'dots', '--dir', d).status, 0);
	fs.writeFileSync(path.join(d, 'dots', 'scripts', 'dots__a..b.py'), 'x');
	const l = cli(home, d, 'lint', path.join(d, 'dots'), '--personal'); assert.equal(l.status, 1); assert.match(l.stdout, /script_path/);
});

test('a script run under another name says what is wrong in one sentence, not a traceback', () => {
	const d = tmp('ns-rename-'), home = tmp('ns-home-');
	assert.equal(cli(home, d, 'new', 'script-template', 'renamed', '--dir', d).status, 0);
	const sd = path.join(d, 'renamed', 'scripts'); fs.renameSync(path.join(sd, 'renamed__app.py'), path.join(sd, 'app.py'));
	const r = spawnSync('/usr/bin/python3', ['-I', path.join(sd, 'app.py')], { encoding: 'utf8', env: { HOME: home, PATH: '/usr/bin:/bin' } });
	assert.notEqual(r.status, 0); assert.match(r.stderr, /script files must be named <app id>__<name>/); assert.doesNotMatch(r.stderr, /Traceback|ModuleNotFoundError/);
});
