// Behavioral tests for Windows support in python.mjs, workflow.mjs (run/doctor), and script-template.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveAllOnPath } from '../lib/python.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const CLI = path.join(REPO, 'toolkit', 'bin', 'bolt-apps.mjs');
const cli = (home, args, extra = {}) =>
	spawnSync(process.execPath, [CLI, ...args], {
		encoding: 'utf8',
		timeout: 60000,
		env: { ...process.env, HOME: home, USERPROFILE: home, ...extra },
	});

test('doctor: handles loose .env and clash removal advice per OS', () => {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-doc-'));
	const home = path.join(root, 'home');
	fs.mkdirSync(home);
	const id = 'windoctor';
	const dir = path.join(root, id);
	fs.mkdirSync(dir);
	fs.writeFileSync(
		path.join(dir, 'bolt-app.json'),
		JSON.stringify({
			schema_version: 1,
			id,
			title: 'T',
			role: 'r',
			saves: 's',
			summary: 's',
			author: { name: 'T' },
			tier: 2,
			permissions: [],
		})
	);
	const envFile = path.join(home, '.config', id, '.env');
	fs.mkdirSync(path.dirname(envFile), { recursive: true });
	fs.writeFileSync(envFile, 'X=1\n');
	try {
		fs.chmodSync(envFile, 0o666);
	} catch {
		/* win32 ignores POSIX mode bits */
	}
	const uu = path.join(root, 'uu');
	fs.mkdirSync(path.join(uu, 'scripts'), { recursive: true });
	fs.writeFileSync(path.join(uu, `${id}.yaml`), 'x');

	const d = cli(home, ['doctor', dir], { BOLT_USER_UTILS_DIR: uu });
	if (process.platform === 'win32') {
		assert.doesNotMatch(d.stdout, /chmod 600/);
		assert.doesNotMatch(d.stdout, /chmod 700/);
		assert.match(d.stdout, /Windows ACLs|icacls/);
		assert.match(d.stdout, /del "/);
		assert.doesNotMatch(d.stdout, /del '/);
	} else {
		assert.match(d.stdout, /chmod 600/);
		assert.match(d.stdout, /rm /);
	}
	fs.rmSync(root, { recursive: true, force: true });
});

test('run: script-template runs in sample mode on this host (including Windows bridge command)', () => {
	const home = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-run-'));
	const r = cli(home, ['run', path.join(REPO, 'kit', 'examples', 'script-template'), '--sample', '--json']);
	assert.equal(r.status, 0, r.stdout + r.stderr);
	const rows = JSON.parse(r.stdout);
	assert.ok(Array.isArray(rows) && rows.length > 0);
	fs.rmSync(home, { recursive: true, force: true });
});

test('resolveAllOnPath: POSIX platform resolution uses POSIX paths even on Windows hosts', () => {
	const hits = resolveAllOnPath('python3', {
		platform: 'linux',
		env: { PATH: '/usr/local/bin:/usr/bin:relative/dir' },
		skip: ['/usr/local/bin'],
		isFile: (p) => p === '/usr/local/bin/python3' || p === '/usr/bin/python3',
	});
	assert.deepEqual(hits, ['/usr/bin/python3']);
});
