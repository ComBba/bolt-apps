// Run: node --test toolkit/test/examples-copy.test.mjs
// Every example under kit/examples that has a utilities/ folder is copied to a fresh temp dir and used the way its README says:
//   A) the fenced shell commands of its README run verbatim (a line or block marked "# needs-network" is skipped);
//   B) only id, chip and title are changed, then check, pack --personal and verify must pass.
// The temp dir is laid out like this repo (toolkit/ and kit/ beside the example) because some READMEs run `node toolkit/bin/bolt-apps.mjs ... kit/examples/<id>`
// from the repo root and others run `bolt-apps ... .` from inside the app folder (a `bolt-apps` shim is put on PATH for those).
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const EXAMPLES = path.join(REPO, 'kit', 'examples');
const names = fs.readdirSync(EXAMPLES, { withFileTypes: true }).filter((e) => e.isDirectory() && fs.existsSync(path.join(EXAMPLES, e.name, 'utilities'))).map((e) => e.name).sort();

// A repo-shaped temp tree holding one example, a HOME with a signing key, and the bolt-apps shim.
function sandbox(name, folder = name) {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-ex-'));
	fs.cpSync(path.join(REPO, 'toolkit'), path.join(root, 'toolkit'), { recursive: true, filter: (s) => !s.includes(`${path.sep}test`) && !s.includes('node_modules') });
	fs.cpSync(path.join(REPO, 'kit', 'python'), path.join(root, 'kit', 'python'), { recursive: true, filter: (s) => !s.includes('__pycache__') });
	for (const d of ['schema', 'conformance']) if (fs.existsSync(path.join(REPO, 'kit', d))) fs.cpSync(path.join(REPO, 'kit', d), path.join(root, 'kit', d), { recursive: true });
	fs.cpSync(path.join(REPO, 'schema'), path.join(root, 'schema'), { recursive: true });
	const app = path.join(root, 'kit', 'examples', folder);
	fs.cpSync(path.join(EXAMPLES, name), app, { recursive: true, filter: (s) => !s.includes('__pycache__') });
	const home = path.join(root, 'home'), bin = path.join(root, 'bin');
	fs.mkdirSync(home); fs.mkdirSync(bin);
	const cli = path.join(root, 'toolkit', 'bin', 'bolt-apps.mjs');
	fs.writeFileSync(path.join(bin, 'bolt-apps'), `#!/bin/sh\nexec "${process.execPath}" "${cli}" "$@"\n`, { mode: 0o755 });
	const env = { PATH: `${bin}:${process.env.PATH}`, HOME: home, LANG: 'C.UTF-8' };
	const keygen = spawnSync(process.execPath, [cli, 'keygen'], { env, encoding: 'utf8' });
	assert.equal(keygen.status, 0, keygen.stderr);
	return { root, app, env, cli };
}
const sh = (cmd, cwd, env) => spawnSync('bash', ['-ec', cmd], { cwd, env, encoding: 'utf8', timeout: 240000 });
const bolt = (s, cwd, ...a) => spawnSync(process.execPath, [s.cli, ...a], { cwd, env: s.env, encoding: 'utf8', timeout: 240000 });

// Fenced blocks of a README as { text, cwd-kind }. A line marked "# needs-network" is dropped; a block whose first line is that marker is dropped.
export function readmeBlocks(md) {
	const out = []; let cur = null;
	for (const line of md.split('\n')) {
		if (/^```/.test(line)) { if (cur) { out.push(cur); cur = null; } else cur = []; continue; }
		if (cur) cur.push(line);
	}
	return out.map((lines) => (lines[0] || '').trim() === '# needs-network' ? null : lines.filter((l) => !/# needs-network/.test(l)).join('\n')).filter((t) => t && t.trim());
}
test('readmeBlocks: skips needs-network lines and blocks, keeps the rest', () => {
	const md = 'x\n```\na\nb # needs-network\nc\n```\ntext\n```sh\n# needs-network\nd\n```\n```\ne\n```\n';
	assert.deepEqual(readmeBlocks(md), ['a\nc', 'e']);
});

for (const name of names) {
	const readme = path.join(EXAMPLES, name, 'README.md');
	if (fs.existsSync(readme)) {
		const blocks = readmeBlocks(fs.readFileSync(readme, 'utf8'));
		test(`${name}: the README's shell commands run verbatim in a fresh copy`, { skip: blocks.length ? false : 'the README has no fenced shell commands' }, () => {
			const s = sandbox(name);
			for (const b of blocks) {
				// a block that names kit/examples/<id> is written for the repo root; any other is written for the app folder
				const r = sh(b, b.includes(`kit/examples/${name}`) ? s.root : s.app, s.env);
				assert.equal(r.status, 0, `${name} README block failed:\n${b}\n--- stdout\n${r.stdout.slice(-1500)}\n--- stderr\n${r.stderr.slice(-1500)}`);
			}
		});
	} else test(`${name}: has a README with commands`, { todo: 'no README.md yet' }, () => assert.fail('no README.md'));

	test(`${name}: a copy with only id, chip and title changed passes check, pack --personal and verify`, () => {
		const id = `copy-${name}`.slice(0, 60), s = sandbox(name, id), app = s.app;
		// id, chip, title: in the listing, and in scripts/config.json (engine apps) or the app file (hand-written apps)
		const bj = path.join(app, 'bolt-app.json'), b = JSON.parse(fs.readFileSync(bj, 'utf8')); b.id = id; b.title = `Copy of ${name}`; fs.writeFileSync(bj, JSON.stringify(b, null, 2) + '\n');
		const cfgFile = path.join(app, 'scripts', 'config.json'), cfg = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : null;
		const yamls = fs.readdirSync(path.join(app, 'utilities')).filter((f) => /\.ya?ml$/.test(f));
		const scriptsDir = path.join(app, 'scripts'); // an http_local app has no scripts/ folder
		const emitter = (fs.existsSync(scriptsDir) ? fs.readdirSync(scriptsDir) : [])
			.filter((f) => f.endsWith('.py') && f !== 'bolt_app_kit.py').find((f) => fs.readFileSync(path.join(scriptsDir, f), 'utf8').includes('--emit-yaml'));
		const chip = `${id}`.slice(0, 40);
		if (cfg && cfg.app && emitter) {
			cfg.app.id = id; cfg.app.chip = chip; cfg.app.title = `Copy of ${name}`; fs.writeFileSync(cfgFile, JSON.stringify(cfg, null, 2) + '\n');
			for (const y of yamls) fs.rmSync(path.join(app, 'utilities', y));
			const r = sh(`python3 scripts/${emitter} --emit-yaml > utilities/${id}.yaml`, app, s.env);
			assert.equal(r.status, 0, `${name}: emit-yaml failed: ${r.stderr}`);
		} else {
			for (const y of yamls) { const f = path.join(app, 'utilities', y); fs.writeFileSync(f, fs.readFileSync(f, 'utf8').replace(/^id: .*$/m, `id: ${id}`).replace(/^chip: .*$/m, `chip: ${chip}`).replace(/^title: .*$/m, `title: "Copy of ${name}"`)); }
		}
		let r;
		if (fs.existsSync(path.join(app, 'check.json'))) {   // `check` runs script apps only; an app with no check.json (http_local) goes straight to lint, pack and verify
			// no --update-golden: a golden that drifts after the copy (output that depends on the id, chip or title, or a stale golden) must fail here, not be rewritten
			r = bolt(s, app, 'check', '.'); assert.equal(r.status, 0, `${name}: check (goldens must hold after a copy)\n${r.stdout.slice(-2500)}${r.stderr}`);
		}
		r = bolt(s, app, 'lint', '.', '--personal'); assert.equal(r.status, 0, `${name}: lint --personal\n${r.stdout}${r.stderr}`);
		const out = path.join(s.root, `${id}-1.0.1.boltpack`);
		r = bolt(s, app, 'pack', '.', '--personal', '--version', '1.0.1', '--out', out); assert.equal(r.status, 0, `${name}: pack --personal\n${r.stdout}${r.stderr}`);
		r = bolt(s, app, 'verify', out); assert.equal(r.status, 0, `${name}: verify of the pack\n${r.stdout}${r.stderr}`);
		r = bolt(s, app, 'verify', '.'); assert.equal(r.status, 0, `${name}: verify of the folder\n${r.stdout}${r.stderr}`);
		// a second pack of the same folder must not fail (the first pack must not sit inside it)
		r = bolt(s, app, 'pack', '.', '--personal', '--version', '1.0.2'); assert.equal(r.status, 0, `${name}: second pack\n${r.stdout}${r.stderr}`);
		assert.ok(!fs.readdirSync(app).some((f) => f.endsWith('.boltpack')), `${name}: pack landed inside the app folder`);
	});
}
