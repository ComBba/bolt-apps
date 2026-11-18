// Find a working Python 3.9+ once. `python3` is not the name everywhere: on Windows it is often a Microsoft Store stub or missing while
// `python` or `py -3` works. Each candidate is proven by running `--version`; the first that reports 3.9 or newer wins and is cached.
import { spawnSync } from 'node:child_process';

export const PYTHON_MISSING = 'Python 3.9 or newer was not found: install it from python.org and re-run';

export function candidates(platform = process.platform) {
	const c = [['python3'], ['python']];
	if (platform === 'win32') c.push(['py', '-3']);
	return c;
}

const versionOk = (text) => { const m = /Python\s+(\d+)\.(\d+)/i.exec(text || ''); return !!m && (Number(m[1]) > 3 || (Number(m[1]) === 3 && Number(m[2]) >= 9)); };

// Returns { cmd, args, label } (args are leading arguments, such as ['-3'] for `py -3`) or null when none works. `spawn` is injectable for tests.
export function findPython({ spawn = spawnSync, platform = process.platform } = {}) {
	for (const [cmd, ...args] of candidates(platform)) {
		let r; try { r = spawn(cmd, [...args, '--version'], { encoding: 'utf8', timeout: 10000 }); } catch { continue; }
		if (r && !r.error && r.status === 0 && versionOk(`${r.stdout || ''} ${r.stderr || ''}`)) return { cmd, args, label: [cmd, ...args].join(' ') };
	}
	return null;
}

let cached;
export function pythonCmd() { if (cached === undefined) cached = findPython(); return cached; }
export function resetPythonCache() { cached = undefined; }
// Run a Python script (or arguments) with the interpreter found above. When none works the result is a spawnSync-shaped failure with the clear message.
export function spawnPython(args, opts = {}, spawn = spawnSync) {
	const p = pythonCmd();
	if (!p) return { status: null, stdout: '', stderr: '', error: new Error(PYTHON_MISSING) };
	return spawn(p.cmd, [...p.args, ...args], opts);
}
