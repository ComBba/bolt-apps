// Run: node --test toolkit/test/python.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { findPython, candidates, PYTHON_MISSING } from '../lib/python.mjs';

// A fake spawn: `works` maps "cmd arg..." (without --version) to the version text it prints; anything else fails like a missing program.
const fake = (works) => (cmd, args) => {
	const key = [cmd, ...args.filter((a) => a !== '--version')].join(' ');
	return key in works ? { status: 0, stdout: works[key], stderr: '' } : { status: null, error: new Error('ENOENT') };
};

test('only python works: it is picked', () => {
	const p = findPython({ spawn: fake({ python: 'Python 3.11.4\n' }), platform: 'linux' });
	assert.deepEqual([p.cmd, p.args], ['python', []]);
});
test('only py -3 works on Windows: it is picked with its -3 argument', () => {
	const p = findPython({ spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'win32' });
	assert.deepEqual([p.cmd, p.args, p.label], ['py', ['-3'], 'py -3']);
});
test('py is not tried off Windows', () => {
	assert.equal(findPython({ spawn: fake({ 'py -3': 'Python 3.12.1\n' }), platform: 'linux' }), null);
	assert.deepEqual(candidates('linux').map((c) => c[0]), ['python3', 'python']);
});
test('python3 wins when it works', () => {
	assert.equal(findPython({ spawn: fake({ python3: 'Python 3.10.0', python: 'Python 3.12.0' }), platform: 'win32' }).cmd, 'python3');
});
test('a Store stub that exits non-zero is skipped', () => {
	const spawn = (cmd) => (cmd === 'python3' ? { status: 9009, stdout: '', stderr: 'Python was not found' } : { status: 0, stdout: 'Python 3.9.0', stderr: '' });
	assert.equal(findPython({ spawn, platform: 'win32' }).cmd, 'python');
});
test('none works: null, and the message is the clear one', () => {
	assert.equal(findPython({ spawn: fake({}), platform: 'win32' }), null);
	assert.match(PYTHON_MISSING, /^Python 3\.9 or newer was not found: install it from python\.org and re-run$/);
});
test('Python 3.8 is refused, 3.9 and 4.0 are accepted; Python 2 is refused', () => {
	assert.equal(findPython({ spawn: fake({ python3: 'Python 3.8.18' }), platform: 'linux' }), null);
	assert.ok(findPython({ spawn: fake({ python3: 'Python 3.9.0' }), platform: 'linux' }));
	assert.ok(findPython({ spawn: fake({ python3: 'Python 4.0.0' }), platform: 'linux' }));
	assert.equal(findPython({ spawn: fake({ python: 'Python 2.7.18' }), platform: 'linux' }), null);
});
test('version printed on stderr (old Python 2 style) is still read', () => {
	const spawn = () => ({ status: 0, stdout: '', stderr: 'Python 3.10.2' });
	assert.ok(findPython({ spawn, platform: 'linux' }));
});
