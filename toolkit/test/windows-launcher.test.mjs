// Windows root launcher (bolt-apps.cmd) tests, including CWD binary-hijack hardening.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const CMD = path.join(REPO, 'bolt-apps.cmd');
const COMSPEC = process.env.COMSPEC || path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'cmd.exe');

test('bolt-apps.cmd help runs the toolkit on Windows', { skip: process.platform !== 'win32' }, () => {
	assert.ok(fs.existsSync(CMD));
	const r = spawnSync(COMSPEC, ['/d', '/c', CMD, 'help'], { encoding: 'utf8', timeout: 30000, windowsHide: true });
	assert.equal(r.status, 0, r.stdout + r.stderr);
	assert.match(r.stdout, /bolt-apps: author toolkit/);
});

test('bolt-apps.cmd ignores planted node/where binaries in the current working directory', { skip: process.platform !== 'win32' }, () => {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-cmd-cwd-'));
	try {
		fs.writeFileSync(path.join(dir, 'where.cmd'), '@echo off\r\necho HIJACKED_WHERE\r\nexit /b 99\r\n');
		fs.writeFileSync(path.join(dir, 'node.cmd'), '@echo off\r\necho HIJACKED_NODE_CMD\r\nexit /b 99\r\n');
		fs.writeFileSync(path.join(dir, 'node.exe'), 'not a real executable');
		const r = spawnSync(COMSPEC, ['/d', '/c', CMD, 'help'], {
			cwd: dir,
			encoding: 'utf8',
			timeout: 30000,
			windowsHide: true,
		});
		assert.equal(r.status, 0, r.stdout + r.stderr);
		assert.match(r.stdout, /bolt-apps: author toolkit/);
		assert.doesNotMatch(r.stdout + r.stderr, /HIJACKED/);
	} finally {
		fs.rmSync(dir, { recursive: true, force: true });
	}
});
