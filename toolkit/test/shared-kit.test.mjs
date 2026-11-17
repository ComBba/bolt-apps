// Run: node --test toolkit/test/shared-kit.test.mjs
// Bolt 182 shared kit, public side: `kit export-shared` (the one producer of Bolt's read-only folder), the Python loader chain every kit-built
// script carries (toolkit/lib/loader.mjs), and `check --shared`. The loader is run by real Python: a loader that is only read proves nothing.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportShared, sharedFiles, SHARED_FILES, KIT_API } from '../lib/shared.mjs';
import { LOADER_PORTABLE, hasLoader, applyLoader, hasLegacyLoader } from '../lib/loader.mjs';
import { flatKitSource, kitVersion, checkApp, reportOk } from '../lib/check.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const EX = path.join(REPO, 'kit', 'examples');
const CLI = path.resolve(HERE, '../bin/bolt-apps.mjs');
const tmp = (p) => fs.mkdtempSync(path.join(os.tmpdir(), p));
const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
const HEADER = `import os as _os\nimport sys as _sys\n_sys.dont_write_bytecode = True\n_SELF = _os.path.basename(__file__)\n_PFX = _SELF.partition("__")[0] + "__" if "__" in _SELF else ""\n`;

test('export-shared writes manifest, kit and licence, deterministically, and the manifest hash is the vendored lock hash', () => {
	const a = tmp('shared-a-'), b = tmp('shared-b-');
	const r = exportShared(path.join(a, 'bolt-apps-shared'), { sourceSha: 'a'.repeat(40) });
	exportShared(path.join(b, 'bolt-apps-shared'), { sourceSha: 'a'.repeat(40) });
	assert.deepEqual(r.files, [...SHARED_FILES].sort());
	for (const n of SHARED_FILES) assert.ok(fs.readFileSync(path.join(a, 'bolt-apps-shared', n)).equals(fs.readFileSync(path.join(b, 'bolt-apps-shared', n))), `${n} differs between two exports`);
	const m = JSON.parse(fs.readFileSync(path.join(a, 'bolt-apps-shared', 'manifest.json'), 'utf8'));
	assert.deepEqual(Object.keys(m), ['format', 'kit', 'source']);
	assert.equal(m.format, 1); assert.equal(m.kit.api, KIT_API); assert.equal(m.kit.version, kitVersion());
	assert.equal(m.kit.sha256, sha(fs.readFileSync(path.join(a, 'bolt-apps-shared', 'bolt_app_kit.py'))));
	// the same bytes `kit vendor --flat` writes: every example's lock at this version names this hash
	const lock = JSON.parse(fs.readFileSync(path.join(EX, 'unit-convert', 'bolt_app_kit.lock.json'), 'utf8'));
	assert.equal(lock.version, kitVersion());
	assert.equal(m.kit.sha256, lock.sha256);
	assert.ok(fs.readFileSync(path.join(a, 'bolt-apps-shared', 'LICENSE'), 'utf8').includes('Apache License'));
});

test('export-shared without a source sha has no source key; a malformed sha is refused', () => {
	assert.equal('source' in JSON.parse(sharedFiles()['manifest.json'].toString()), false);
	assert.throws(() => sharedFiles({ sourceSha: 'main' }), /40-character/);
});

test('export-shared refuses a folder that is not a previous export, a file and a link, and never touches it', () => {
	const d = tmp('shared-refuse-');
	fs.writeFileSync(path.join(d, 'notes.txt'), 'mine');
	assert.throws(() => exportShared(d), /not a previous export/);
	assert.equal(fs.readFileSync(path.join(d, 'notes.txt'), 'utf8'), 'mine');
	const f = path.join(d, 'afile'); fs.writeFileSync(f, 'x');
	assert.throws(() => exportShared(f), /not a folder/);
	const target = tmp('shared-target-'), link = path.join(d, 'lnk'); fs.symlinkSync(target, link);
	assert.throws(() => exportShared(link), /not a folder/);
	assert.deepEqual(fs.readdirSync(target), []);
	const prev = path.join(d, 'prev'); exportShared(prev);
	fs.rmSync(path.join(prev, 'LICENSE')); fs.symlinkSync('/etc/hosts', path.join(prev, 'LICENSE'));
	assert.throws(() => exportShared(prev), /not a plain file/);
});

test('the CLI exports and prints the version and a short hash', () => {
	const d = path.join(tmp('shared-cli-'), 'out');
	const r = spawnSync(process.execPath, [CLI, 'kit', 'export-shared', d, '--source-sha', 'b'.repeat(40)], { encoding: 'utf8' });
	assert.equal(r.status, 0, r.stderr);
	assert.match(r.stdout, /exported the shared kit \d+\.\d+\.\d+ \(api 1/);
	assert.equal(JSON.parse(fs.readFileSync(path.join(d, 'manifest.json'), 'utf8')).source.sha, 'b'.repeat(40));
});

// ---- the loader, run by Python ----------------------------------------------------------------

const PY = spawnSync('python3', ['--version']).status === 0 ? 'python3' : null;
// A script folder with the loader and a probe that prints which kit ran. `own` is the app's vendored kit (bytes), or null for none.
function app(own, loaderTweak = (s) => s) {
	const dir = tmp('shared-app-');
	fs.writeFileSync(path.join(dir, 'probe__app.py'), HEADER + loaderTweak(LOADER_PORTABLE) + `print(kit.__file__ + "|" + kit.__version__)\nprint(kit.clean_text("a\\u200bb"))\n`);
	if (own !== null) fs.writeFileSync(path.join(dir, 'probe__bolt_app_kit.py'), own);
	return dir;
}
function run(dir, env) {
	const r = spawnSync(PY, ['-I', path.join(dir, 'probe__app.py')], { encoding: 'utf8', env: { PATH: process.env.PATH, ...env } });
	return { rc: r.status, out: r.stdout.trim().split('\n'), err: r.stderr };
}
const OWN_OTHER = '__version__ = "0.0.1"\ndef clean_text(s):\n    return "own:" + s\n';
const shared = () => { const d = path.join(tmp('shared-dir-'), 'bolt-apps-shared'); exportShared(d); return d; };
const ownKit = () => flatKitSource();
const usedShared = (r, d) => r.out[0].startsWith(path.join(d, 'bolt_app_kit.py') + '|');

test('loader: variable absent uses the app\'s own copy', { skip: !PY }, () => {
	const a = app(ownKit()), r = run(a, {});
	assert.equal(r.rc, 0, r.err);
	assert.ok(r.out[0].startsWith(path.join(a, 'probe__bolt_app_kit.py')), r.out[0]);
});

test('loader: identical bytes (the app\'s lock hash matches Bolt\'s) use the shared copy and give the same rows', { skip: !PY }, () => {
	const a = app(ownKit()), d = shared();
	const withShared = run(a, { BOLT_APP_SHARED_DIR: d }), without = run(a, {});
	assert.equal(withShared.rc, 0, withShared.err);
	assert.ok(usedShared(withShared, d), withShared.out[0]);
	assert.equal(withShared.out[0].split('|')[1], without.out[0].split('|')[1]);
	assert.equal(withShared.out[1], without.out[1]);
});

test('loader: a different own copy is NOT replaced unless the app asks for shared', { skip: !PY }, () => {
	const a = app(OWN_OTHER), d = shared();
	const r = run(a, { BOLT_APP_SHARED_DIR: d });
	assert.ok(r.out[0].startsWith(path.join(a, 'probe__bolt_app_kit.py')), r.out[0]);
	assert.equal(r.out[1], 'own:a​b');
});

test('loader: WANT_SHARED prefers the shared copy when it verifies and is new enough', { skip: !PY }, () => {
	const want = (s) => s.replace('WANT_SHARED = False', 'WANT_SHARED = True');
	const d = shared();
	assert.ok(usedShared(run(app(OWN_OTHER, want), { BOLT_APP_SHARED_DIR: d }), d));
	const tooNew = (s) => want(s).replace('KIT_MIN = (0, 3, 10)', 'KIT_MIN = (99, 0, 0)');
	const r = run(app(OWN_OTHER, tooNew), { BOLT_APP_SHARED_DIR: d });
	assert.ok(!usedShared(r, d) && r.out[1] === 'own:a​b', r.out.join('|'));
	const otherApi = (s) => want(s).replace('KIT_API = 1', 'KIT_API = 2');
	const r2 = run(app(OWN_OTHER, otherApi), { BOLT_APP_SHARED_DIR: d });
	assert.ok(!usedShared(r2, d), 'an api level the loader does not know must not load');
});

test('loader: a thin app (no own copy) runs on the shared kit, and says what is wrong when there is none', { skip: !PY }, () => {
	const want = (s) => s.replace('WANT_SHARED = False', 'WANT_SHARED = True');
	const d = shared(), a = app(null, want);
	assert.ok(usedShared(run(a, { BOLT_APP_SHARED_DIR: d }), d));
	const r = run(a, {});
	assert.notEqual(r.rc, 0);
	assert.match(r.err, /script files must be named/);
});

// Every way the shared folder can be wrong falls back to the app's own copy with the same rows and no traceback.
const broken = {
	'one byte of the kit changed': (d) => { const p = path.join(d, 'bolt_app_kit.py'); fs.appendFileSync(p, '\n# x\n'); },
	'manifest is not JSON': (d) => fs.writeFileSync(path.join(d, 'manifest.json'), '{nope'),
	'manifest names another api': (d) => rewrite(d, (m) => { m.kit.api = 2; }),
	'manifest format is unknown': (d) => rewrite(d, (m) => { m.format = 2; }),
	'manifest names a path out of the folder': (d) => rewrite(d, (m) => { m.kit.file = '../bolt_app_kit.py'; }),
	'manifest names a file that is not there': (d) => rewrite(d, (m) => { m.kit.file = 'gone.py'; }),
	'manifest version differs from the kit': (d) => rewrite(d, (m) => { m.kit.version = '0.0.1'; }),
	'manifest hash differs from the kit': (d) => rewrite(d, (m) => { m.kit.sha256 = '0'.repeat(64); }),
	'the kit is a link': (d) => { const p = path.join(d, 'bolt_app_kit.py'); const t = path.join(path.dirname(d), 'real.py'); fs.renameSync(p, t); fs.symlinkSync(t, p); },
	'the manifest is a link': (d) => { const p = path.join(d, 'manifest.json'); const t = path.join(path.dirname(d), 'm.json'); fs.renameSync(p, t); fs.symlinkSync(t, p); },
	'the kit does not run': (d) => { const p = path.join(d, 'bolt_app_kit.py'); fs.writeFileSync(p, 'raise RuntimeError("boom")\n'); rewrite(d, (m) => { m.kit.sha256 = sha(fs.readFileSync(p)); }); },
};
function rewrite(d, f) { const p = path.join(d, 'manifest.json'); const m = JSON.parse(fs.readFileSync(p, 'utf8')); f(m); fs.writeFileSync(p, JSON.stringify(m)); }
for (const [name, break_] of Object.entries(broken)) {
	test(`loader: falls back to the app's own copy when ${name}`, { skip: !PY }, () => {
		const want = (s) => s.replace('WANT_SHARED = False', 'WANT_SHARED = True');
		for (const tweak of [(s) => s, want]) {
			const a = app(ownKit(), tweak), d = shared();
			break_(d);
			const r = run(a, { BOLT_APP_SHARED_DIR: d });
			assert.equal(r.rc, 0, r.err);
			assert.ok(r.out[0].startsWith(path.join(a, 'probe__bolt_app_kit.py')), r.out[0]);
			assert.equal(r.out[1], 'ab');
			assert.equal(r.err, '');
		}
	});
}

test('loader: a relative or empty BOLT_APP_SHARED_DIR is ignored', { skip: !PY }, () => {
	const a = app(ownKit()), d = shared();
	for (const v of ['', path.relative(a, d), 'bolt-apps-shared']) {
		const r = run(a, { BOLT_APP_SHARED_DIR: v });
		assert.equal(r.rc, 0, r.err);
		assert.ok(r.out[0].startsWith(path.join(a, 'probe__bolt_app_kit.py')), `${v}: ${r.out[0]}`);
	}
});

test('loader: a shared folder path with spaces works', { skip: !PY }, () => {
	const a = app(ownKit()), d = path.join(tmp('shared sp-'), 'Application Support', 'bolt-apps-shared');
	exportShared(d);
	assert.ok(usedShared(run(a, { BOLT_APP_SHARED_DIR: d }), d));
});

test('loader: a failed shared load leaves no half-imported module behind (the own copy still imports)', { skip: !PY }, () => {
	const a = app(ownKit()), d = shared();
	broken['the kit does not run'](d);
	const r = run(a, { BOLT_APP_SHARED_DIR: d });
	assert.equal(r.rc, 0, r.err);
	assert.equal(r.out[1], 'ab');
});

// ---- one loader everywhere ---------------------------------------------------------------------

test('the loader is one block: applyLoader is idempotent and converts the previous block', () => {
	const old = fs.readFileSync(path.join(EX, 'around', 'scripts', 'around__around.py'), 'utf8');
	assert.ok(hasLegacyLoader(old) || hasLoader(old));
	const once = applyLoader(old);
	assert.ok(hasLoader(once));
	assert.equal(applyLoader(once), once);
	assert.equal(applyLoader('print(1)\n'), 'print(1)\n');
});

test('every script that carries the loader carries exactly the toolkit\'s, and its header lines the loader needs', () => {
	let seen = 0;
	for (const e of fs.readdirSync(EX, { withFileTypes: true }).filter((x) => x.isDirectory())) {
		const sd = path.join(EX, e.name, 'scripts');
		if (!fs.existsSync(sd)) continue;
		for (const f of fs.readdirSync(sd).filter((n) => n.endsWith('.py') && !n.endsWith('bolt_app_kit.py'))) {
			const src = fs.readFileSync(path.join(sd, f), 'utf8');
			if (!src.includes('def _shared_kit(')) continue;
			seen++;
			assert.ok(hasLoader(src), `${e.name}/${f}: the loader block differs from toolkit/lib/loader.mjs (run applyLoader)`);
			assert.ok(src.includes('_PFX =') && src.includes('_SELF =') && src.includes('import os as _os'), `${e.name}/${f}: missing the header lines the loader uses`);
		}
	}
	assert.ok(seen >= 1, 'no example adopted the loader');
});

test('unit-convert runs through check in the shared mode with the same rows as its goldens', { skip: !PY, timeout: 300000 }, async () => {
	const plain = await checkApp(path.join(EX, 'unit-convert'), {});
	assert.ok(reportOk(plain), JSON.stringify(plain.findings));
	const sh = await checkApp(path.join(EX, 'unit-convert'), { shared: true });
	assert.ok(reportOk(sh), JSON.stringify(sh.findings.concat(sh.cases.filter((c) => c.findings?.length))));
	assert.equal(sh.cases.length, plain.cases.length);
});

test('the shared mode really hands the script the variable (the check env is the only place besides Bolt that sets it)', { skip: !PY }, () => {
	const src = fs.readFileSync(path.join(REPO, 'toolkit', 'lib', 'check.mjs'), 'utf8');
	assert.match(src, /opts\.sharedDir \? \{ BOLT_APP_SHARED_DIR: opts\.sharedDir \}/);
});
