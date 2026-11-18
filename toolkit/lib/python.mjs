// Find a working Python 3.9+ once. `python3` is not the name everywhere: on Windows it is often a Microsoft Store stub or missing while
// `python` or `py -3` works. Each candidate is resolved to an ABSOLUTE path by walking the parent process PATH (never the spawn cwd, where
// Windows would look first: a downloaded app folder holding a python.exe must not win), proven by running `--version`, and the first that
// reports 3.9 or newer is cached. Everything then spawns that absolute path.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export const PYTHON_MISSING = 'Python 3.9 or newer was not found: install it from python.org and re-run';

export function candidates(platform = process.platform) {
	const c = [['python3'], ['python']];
	if (platform === 'win32') c.push(['py', '-3']);
	return c;
}

const versionOk = (text) => { const m = /Python\s+(\d+)\.(\d+)/i.exec(text || ''); return !!m && (Number(m[1]) > 3 || (Number(m[1]) === 3 && Number(m[2]) >= 9)); };
const same = (a, b) => path.resolve(a) === path.resolve(b);

// First executable file called `name` on PATH (PATHEXT on win32), skipping an empty entry, "." and any folder in `skip` (the cwd, the app folder).
export function resolveOnPath(name, { env = process.env, platform = process.platform, skip = [], isFile = (p) => { try { return fs.statSync(p).isFile(); } catch { return false; } } } = {}) {
	const win = platform === 'win32';
	const sep = win ? ';' : ':';
	const exts = win ? ['', ...(env.PATHEXT || '.COM;.EXE;.BAT;.CMD').split(';').filter(Boolean)] : [''];
	const join = win ? path.win32.join : path.join;
	for (const d of (env.PATH || env.Path || '').split(sep)) {
		if (!d || d === '.' || skip.some((s) => same(d, s))) continue;
		if (!(win ? path.win32.isAbsolute(d) : path.isAbsolute(d))) continue;   // a relative PATH entry means "the cwd" by another name
		for (const x of exts) { const p = join(d, name + x); if (isFile(p)) return p; }
	}
	return null;
}

// Returns { cmd (absolute path), args (leading arguments, such as ['-3'] for `py -3`), label } or null when none works.
// `spawn`, `resolve`, `env`, `platform` and `skip` are injectable for tests.
export function findPython({ spawn = spawnSync, platform = process.platform, env = process.env, skip = [process.cwd()], resolve = resolveOnPath } = {}) {
	for (const [name, ...args] of candidates(platform)) {
		const cmd = resolve(name, { env, platform, skip }); if (!cmd) continue;
		let r; try { r = spawn(cmd, [...args, '--version'], { encoding: 'utf8', timeout: 10000, cwd: path.dirname(cmd) }); } catch { continue; }
		if (r && !r.error && r.status === 0 && versionOk(`${r.stdout || ''} ${r.stderr || ''}`)) return { cmd, args, label: [name, ...args].join(' ') };
	}
	return null;
}

let cached;
// Cached for the process. Extra `skip` folders (the app folder) are honoured on the first call and when the cached answer lives inside one.
export function pythonCmd({ skip = [] } = {}) {
	if (cached === undefined || (cached && skip.some((s) => same(path.dirname(cached.cmd), s)))) cached = findPython({ skip: [process.cwd(), ...skip] });
	return cached;
}
export function resetPythonCache() { cached = undefined; }
// Run Python with the interpreter found above. When none works the result is a spawnSync-shaped failure carrying the clear message.
export function spawnPython(args, opts = {}, spawn = spawnSync) {
	const p = pythonCmd();
	if (!p) return { status: null, stdout: '', stderr: '', error: new Error(PYTHON_MISSING) };
	return spawn(p.cmd, [...p.args, ...args], opts);
}
