// Run: node --test toolkit/test/python.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { findPython, candidates, PYTHON_MISSING, resolveOnPath, resolveAllOnPath } from '../lib/python.mjs';

// A fake spawn: `works` maps "cmd arg..." (without --version) to the version text it prints; anything else fails like a missing program.
const fake = (works) => (cmd, args) => {
	const key = [cmd.replace(/^\/bin\//, ''), ...args.filter((a) => a !== '--version')].join(' ');
	return key in works ? { status: 0, stdout: works[key], stderr: '' } : { status: null, error: new Error('ENOENT') };
};

test('only python works: it is picked', () => {
	const p = findPython({ resolve: (n) => [n], spawn: fake({ python: 'Python 3.11.4\n' }), platform: 'linux' });
	assert.deepEqual([p.cmd, p.args], ['python', []]);
});
test('only py -3 works on Windows: it is picked with its -3 argument', () => {
	const p = findPython({ resolve: (n) => [n], spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'win32' });
	assert.deepEqual([p.cmd, p.args, p.label], ['py', ['-3'], 'py -3']);
});
test('py is not tried off Windows', () => {
	assert.equal(findPython({ resolve: (n) => [n], spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'linux' }), null);
	assert.deepEqual(candidates('linux').map((c) => c[0]), ['python3', 'python']);
});
test('python3 wins when it works', () => {
	assert.equal(findPython({ resolve: (n) => [n], spawn: fake({ python3: 'Python 3.10.0', python: 'Python 3.12.0' }), platform: 'win32' }).cmd, 'python3');
});
test('a Store stub that exits non-zero is skipped', () => {
	const spawn = (cmd) => (cmd === 'python3' ? { status: 9009, stdout: '', stderr: 'Python was not found' } : { status: 0, stdout: 'Python 3.9.0', stderr: '' });
	assert.equal(findPython({ resolve: (n) => [n], spawn, platform: 'win32' }).cmd, 'python');
});
test('none works: null, and the message is the clear one', () => {
	assert.equal(findPython({ resolve: (n) => [n], spawn: fake({}), platform: 'win32' }), null);
	assert.match(PYTHON_MISSING, /^Python 3\.9 or newer was not found: install it from python\.org and re-run$/);
});
test('Python 3.8 is refused, 3.9 and 4.0 are accepted; Python 2 is refused', () => {
	assert.equal(findPython({ resolve: (n) => [n], spawn: fake({ python3: 'Python 3.8.18' }), platform: 'linux' }), null);
	assert.ok(findPython({ resolve: (n) => [n], spawn: fake({ python3: 'Python 3.9.0' }), platform: 'linux' }));
	assert.ok(findPython({ resolve: (n) => [n], spawn: fake({ python3: 'Python 4.0.0' }), platform: 'linux' }));
	assert.equal(findPython({ resolve: (n) => [n], spawn: fake({ python: 'Python 2.7.18' }), platform: 'linux' }), null);
});
test('version printed on stderr (old Python 2 style) is still read', () => {
	const spawn = () => ({ status: 0, stdout: '', stderr: 'Python 3.10.2' });
	assert.ok(findPython({ resolve: (n) => [n], spawn, platform: 'linux' }));
});

// ---- hardening: absolute path from the parent PATH, never the cwd or the app folder
const fsOf = (files) => (p) => files.includes(p);
test('a python in the app folder (cwd) is NOT chosen over the one on PATH, and the absolute path is what is spawned', () => {
	const files = ['/apps/evil/python3', '/usr/bin/python3'];
	const seen = [];
	const spawn = (cmd, args) => { seen.push(cmd); return { status: 0, stdout: 'Python 3.11.0', stderr: '' }; };
	const resolve = (name, o) => resolveAllOnPath(name, { ...o, isFile: fsOf(files) });
	const p = findPython({ spawn, platform: 'linux', env: { PATH: '/apps/evil:/usr/bin' }, skip: ['/apps/evil'], resolve });
	assert.equal(p.cmd, '/usr/bin/python3');
	assert.deepEqual(seen, ['/usr/bin/python3']);
});
test('relative and empty PATH entries (the cwd by another name) are never searched', () => {
	const files = ['python3', './python3', 'bin/python3', '/usr/bin/python3'];
	const r = resolveOnPath('python3', { env: { PATH: ':.:bin:/usr/bin' }, platform: 'linux', isFile: fsOf(files) });
	assert.equal(r, '/usr/bin/python3');
});
test('only a cwd-planted python exists: none is found, with the clear error', () => {
	const resolve = (name, o) => resolveAllOnPath(name, { ...o, isFile: fsOf(['C:\\app\\python.exe']) });
	assert.equal(findPython({ spawn: () => { throw new Error('must not spawn'); }, platform: 'win32', env: { PATH: 'C:\\app;C:\\empty', PATHEXT: '.EXE' }, skip: ['C:\\app'], resolve }), null);
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
	const resolve = (name, o) => resolveAllOnPath(name, { ...o, isFile: fsOf(files) });
	const p = findPython({ spawn, platform: 'win32', env: { PATH: 'C:\\Users\\a\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Windows', PATHEXT: '.exe' }, skip: [], resolve });
	assert.deepEqual([p.cmd, p.args, p.label], ['C:\\Windows\\py.exe', ['-3'], 'py -3']);
});

// ---- review hardening
test('win32: .bat and .cmd are never resolved, even if PATHEXT lists them; only .exe and .com', () => {
	const files = ['C:\\bin\\python.bat', 'C:\\bin\\python.cmd', 'C:\\bin\\python.exe'];
	assert.deepEqual(resolveAllOnPath('python', { env: { PATH: 'C:\\bin', PATHEXT: '.bat;.cmd;.exe' }, platform: 'win32', isFile: fsOf(files) }), ['C:\\bin\\python.exe']);
	assert.deepEqual(resolveAllOnPath('python', { env: { PATH: 'C:\\bin', PATHEXT: '.bat;.cmd' }, platform: 'win32', isFile: fsOf(['C:\\bin\\python.bat']) }), []);
});
test('win32: UNC PATH entries are refused', () => {
	const files = ['\\\\srv\\share\\python.exe', '//srv/share/python.exe'];
	assert.deepEqual(resolveAllOnPath('python', { env: { PATH: '\\\\srv\\share;//srv/share' }, platform: 'win32', isFile: fsOf(files) }), []);
});
test('win32: the skip comparison is case-insensitive', () => {
	const r = resolveAllOnPath('python', { env: { PATH: 'C:\\App\\Evil' }, platform: 'win32', skip: ['c:\\app\\EVIL'], isFile: () => true });
	assert.deepEqual(r, []);
});
test('a quoted absolute PATH entry is unquoted; a quoted relative one is still refused', () => {
	assert.deepEqual(resolveAllOnPath('python', { env: { PATH: '"C:\\Py"', PATHEXT: '.exe' }, platform: 'win32', isFile: fsOf(['C:\\Py\\python.exe']) }), ['C:\\Py\\python.exe']);
	assert.deepEqual(resolveAllOnPath('python', { env: { PATH: '"bin"' }, platform: 'win32', isFile: () => true }), []);
});
// ---- version-manager shims (pyenv, asdf, mise): `#!/usr/bin/env bash` scripts that fail under check's stub-only PATH
const shimSpawn = (answers) => (cmd, args, opts) => {
	const seen = { cmd, args, env: opts && opts.env };
	shimSpawn.calls.push(seen);
	const key = `${cmd} ${args.join(' ')}`;
	return key in answers ? { status: 0, stdout: answers[key], stderr: '' } : { status: 1, stdout: '', stderr: 'no' };
};
const shimOpts = (files, scripts, answers) => {
	shimSpawn.calls = [];
	return { spawn: shimSpawn(answers), platform: 'darwin', env: { PATH: '/opt/.pyenv/shims:/usr/bin' }, skip: ['/apps/demo'], resolve: (name, o) => resolveAllOnPath(name, { ...o, isFile: fsOf(files) }), isFile: fsOf(files), isScript: (p) => scripts.includes(p) };
};
const SHIM = '/opt/.pyenv/shims/python3', REAL = '/opt/.pyenv/versions/3.12.4/bin/python3';
test('a pyenv shim resolves to the interpreter it runs, proven with an empty PATH', () => {
	const o = shimOpts([SHIM, REAL], [SHIM], { [`${SHIM} --version`]: 'Python 3.12.4', [`${SHIM} -c import sys; print(sys.executable)`]: `${REAL}\n`, [`${REAL} --version`]: 'Python 3.12.4' });
	const p = findPython(o);
	assert.deepEqual([p.cmd, p.args, p.label], [REAL, [], 'python3']);
	assert.deepEqual(shimSpawn.calls.at(-1).env, { PATH: '' });
});
test('a shim whose interpreter fails without PATH is kept, as before', () => {
	const o = shimOpts([SHIM, REAL], [SHIM], { [`${SHIM} --version`]: 'Python 3.12.4', [`${SHIM} -c import sys; print(sys.executable)`]: REAL });
	assert.equal(findPython(o).cmd, SHIM);
});
test('a shim pointing into the skipped app folder, at a relative path, at a missing file or at another script is kept', () => {
	for (const real of ['/apps/demo/python3', 'python3', '/nowhere/python3', '/opt/other-shim']) {
		const o = shimOpts([SHIM, '/apps/demo/python3', '/opt/other-shim'], [SHIM, '/opt/other-shim'], { [`${SHIM} --version`]: 'Python 3.12.4', [`${SHIM} -c import sys; print(sys.executable)`]: real, [`${real} --version`]: 'Python 3.12.4' });
		assert.equal(findPython(o).cmd, SHIM, real);
	}
});
test('a real binary is not probed again: one spawn, the path found on PATH', () => {
	const o = shimOpts(['/usr/bin/python3'], [], { '/usr/bin/python3 --version': 'Python 3.9.6' });
	assert.equal(findPython(o).cmd, '/usr/bin/python3');
	assert.equal(shimSpawn.calls.length, 1);
});
test('isShebangScript reads only the first two bytes', async () => {
	const fs = await import('node:fs'), os = await import('node:os'), path = await import('node:path');
	const { isShebangScript } = await import('../lib/python.mjs');
	const d = fs.mkdtempSync(path.join(os.tmpdir(), 'py-shim-'));
	try {
		fs.writeFileSync(path.join(d, 'shim'), '#!/usr/bin/env bash\nexec python "$@"\n');
		fs.writeFileSync(path.join(d, 'bin'), Buffer.from([0xcf, 0xfa, 0xed, 0xfe]));
		assert.equal(isShebangScript(path.join(d, 'shim')), true);
		assert.equal(isShebangScript(path.join(d, 'bin')), false);
		assert.equal(isShebangScript(path.join(d, 'missing')), false);
	} finally { fs.rmSync(d, { recursive: true, force: true }); }
});

test('a stub first on PATH does not hide a real python behind it: every hit is tried', () => {
	const files = ['/stub/python3', '/real/python3'];
	const resolve = (name, o) => resolveAllOnPath(name, { ...o, isFile: fsOf(files) });
	const spawn = (cmd) => (cmd === '/stub/python3' ? { status: 9009, stdout: '', stderr: '' } : { status: 0, stdout: 'Python 3.11.0', stderr: '' });
	assert.equal(findPython({ spawn, platform: 'linux', env: { PATH: '/stub:/real' }, skip: [], resolve }).cmd, '/real/python3');
});
