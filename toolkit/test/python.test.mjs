// Run: node --test toolkit/test/python.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { findPython, candidates, PYTHON_MISSING, resolveOnPath } from '../lib/python.mjs';

// A fake spawn: `works` maps "cmd arg..." (without --version) to the version text it prints; anything else fails like a missing program.
const fake = (works) => (cmd, args) => {
	const key = [cmd.replace(/^\/bin\//, ''), ...args.filter((a) => a !== '--version')].join(' ');
	return key in works ? { status: 0, stdout: works[key], stderr: '' } : { status: null, error: new Error('ENOENT') };
};

test('only python works: it is picked', () => {
	const p = findPython({ resolve: (n) => n, spawn: fake({ python: 'Python 3.11.4\n' }), platform: 'linux' });
	assert.deepEqual([p.cmd, p.args], ['python', []]);
});
test('only py -3 works on Windows: it is picked with its -3 argument', () => {
	const p = findPython({ resolve: (n) => n, spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'win32' });
	assert.deepEqual([p.cmd, p.args, p.label], ['py', ['-3'], 'py -3']);
});
test('py is not tried off Windows', () => {
	assert.equal(findPython({ resolve: (n) => n, spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'linux' }), null);
	assert.deepEqual(candidates('linux').map((c) => c[0]), ['python3', 'python']);
});
test('python3 wins when it works', () => {
	assert.equal(findPython({ resolve: (n) => n, spawn: fake({ python3: 'Python 3.10.0', python: 'Python 3.12.0' }), platform: 'win32' }).cmd, 'python3');
});
test('a Store stub that exits non-zero is skipped', () => {
	const spawn = (cmd) => (cmd === 'python3' ? { status: 9009, stdout: '', stderr: 'Python was not found' } : { status: 0, stdout: 'Python 3.9.0', stderr: '' });
	assert.equal(findPython({ resolve: (n) => n, spawn, platform: 'win32' }).cmd, 'python');
});
test('none works: null, and the message is the clear one', () => {
	assert.equal(findPython({ resolve: (n) => n, spawn: fake({}), platform: 'win32' }), null);
	assert.match(PYTHON_MISSING, /^Python 3\.9 or newer was not found: install it from python\.org and re-run$/);
});
test('Python 3.8 is refused, 3.9 and 4.0 are accepted; Python 2 is refused', () => {
	assert.equal(findPython({ resolve: (n) => n, spawn: fake({ python3: 'Python 3.8.18' }), platform: 'linux' }), null);
	assert.ok(findPython({ resolve: (n) => n, spawn: fake({ python3: 'Python 3.9.0' }), platform: 'linux' }));
	assert.ok(findPython({ resolve: (n) => n, spawn: fake({ python3: 'Python 4.0.0' }), platform: 'linux' }));
	assert.equal(findPython({ resolve: (n) => n, spawn: fake({ python: 'Python 2.7.18' }), platform: 'linux' }), null);
});
test('version printed on stderr (old Python 2 style) is still read', () => {
	const spawn = () => ({ status: 0, stdout: '', stderr: 'Python 3.10.2' });
	assert.ok(findPython({ resolve: (n) => n, spawn, platform: 'linux' }));
});

// ---- hardening: absolute path from the parent PATH, never the cwd or the app folder
const fsOf = (files) => (p) => files.includes(p);
test('a python in the app folder (cwd) is NOT chosen over the one on PATH, and the absolute path is what is spawned', () => {
	const files = ['/apps/evil/python3', '/usr/bin/python3'];
	const seen = [];
	const spawn = (cmd, args) => { seen.push(cmd); return { status: 0, stdout: 'Python 3.11.0', stderr: '' }; };
	const resolve = (name, o) => resolveOnPath(name, { ...o, isFile: fsOf(files) });
	const p = findPython({ resolve: (n) => n, spawn, platform: 'linux', env: { PATH: '/apps/evil:/usr/bin' }, skip: ['/apps/evil'], resolve });
	assert.equal(p.cmd, '/usr/bin/python3');
	assert.deepEqual(seen, ['/usr/bin/python3']);
});
test('relative and empty PATH entries (the cwd by another name) are never searched', () => {
	const files = ['python3', './python3', 'bin/python3', '/usr/bin/python3'];
	const r = resolveOnPath('python3', { env: { PATH: ':.:bin:/usr/bin' }, platform: 'linux', isFile: fsOf(files) });
	assert.equal(r, '/usr/bin/python3');
});
test('only a cwd-planted python exists: none is found, with the clear error', () => {
	const resolve = (name, o) => resolveOnPath(name, { ...o, isFile: fsOf(['C:\\app\\python.exe']) });
	assert.equal(findPython({ resolve: (n) => n, spawn: () => { throw new Error('must not spawn'); }, platform: 'win32', env: { PATH: 'C:\\app;C:\\empty', PATHEXT: '.EXE' }, skip: ['C:\\app'], resolve }), null);
	assert.match(PYTHON_MISSING, /not found: install it from python\.org/);
});
test('win32 PATHEXT is honoured: python.EXE and py.EXE are found by bare name', () => {
	const files = ['C:\\Python312\\python.EXE', 'C:\\Windows\\py.EXE'];
	assert.equal(resolveOnPath('python', { env: { PATH: 'C:\\Python312;C:\\Windows', PATHEXT: '.COM;.EXE' }, platform: 'win32', isFile: fsOf(files) }), 'C:\\Python312\\python.EXE');
	assert.equal(resolveOnPath('py', { env: { PATH: 'C:\\Python312;C:\\Windows', PATHEXT: '.COM;.EXE' }, platform: 'win32', isFile: fsOf(files) }), 'C:\\Windows\\py.EXE');
});
test('the Microsoft Store stub (python3.exe under WindowsApps, exits non-zero and prints nothing) is refused; py -3 is used, keeping its -3', () => {
	const files = ['C:\\Users\\a\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe', 'C:\\Windows\\py.exe'];
	const spawn = (cmd) => (/WindowsApps/.test(cmd) ? { status: 9009, stdout: '', stderr: '' } : { status: 0, stdout: 'Python 3.12.2', stderr: '' });
	const resolve = (name, o) => resolveOnPath(name, { ...o, isFile: fsOf(files) });
	const p = findPython({ resolve: (n) => n, spawn, platform: 'win32', env: { PATH: 'C:\\Users\\a\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Windows', PATHEXT: '.exe' }, skip: [], resolve });
	assert.deepEqual([p.cmd, p.args, p.label], ['C:\\Windows\\py.exe', ['-3'], 'py -3']);
});
