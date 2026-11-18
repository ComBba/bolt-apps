// `bolt-apps kit export-shared <dir>`: the ONE producer of the folder Bolt ships read-only in its bundle
// (a folder named bolt-apps-shared inside the app bundle) and hands to apps as BOLT_APP_SHARED_DIR.
// Deterministic: two exports of one source tree are byte-equal. Files: manifest.json, bolt_app_kit.py, LICENSE.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { flatKitSource, kitVersion, KIT_ROOT } from './check.mjs';

export const SHARED_FORMAT = 1;
// The kit interface level. A loader refuses a shared kit of another level. Bump only with a breaking kit change,
// and ship the new level beside the old one for several Bolt releases.
export const KIT_API = 1;
export const SHARED_FILES = ['LICENSE', 'bolt_app_kit.py', 'manifest.json'];
const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');
const LICENSE_PATH = path.join(KIT_ROOT, '..', 'LICENSE');

export function sharedFiles(opts = {}) {
	if (opts.sourceSha !== undefined && !/^[0-9a-f]{40}$/.test(opts.sourceSha)) throw new Error('--source-sha must be a full 40-character git commit id');
	const kit = Buffer.from(flatKitSource());
	const manifest = { format: SHARED_FORMAT, kit: { api: KIT_API, file: 'bolt_app_kit.py', sha256: sha256(kit), version: kitVersion() } };
	if (opts.sourceSha) manifest.source = { repo: 'SparcleHQ/bolt-apps', sha: opts.sourceSha };
	// keys sorted, two-space indent, trailing newline: what Bolt's table is generated from
	const sorted = (o) => Array.isArray(o) || o === null || typeof o !== 'object' ? o : Object.fromEntries(Object.keys(o).sort().map((k) => [k, sorted(o[k])]));
	return { 'bolt_app_kit.py': kit, LICENSE: fs.readFileSync(LICENSE_PATH), 'manifest.json': Buffer.from(JSON.stringify(sorted(manifest), null, 2) + '\n') };
}

// Writes the files into `dir`. Refuses a dir that holds anything else than a previous export (never clobbers a
// user folder) and any link. Writes through a staged copy and a rename so a failure never leaves a half export.
export function exportShared(dir, opts = {}) {
	if (!dir) throw new Error('usage: ./bolt-apps kit export-shared <dir> [--source-sha <40 hex>]');
	const files = sharedFiles(opts), target = path.resolve(dir);
	if (fs.existsSync(target)) {
		const st = fs.lstatSync(target);
		if (!st.isDirectory()) throw new Error(`${dir} exists and is not a folder; refusing`);
		const have = fs.readdirSync(target);
		const stray = have.filter((n) => !SHARED_FILES.includes(n));
		if (stray.length) throw new Error(`${dir} holds files that are not a previous export (${stray.slice(0, 3).join(', ')}); refusing to write into it. Use an empty folder`);
		for (const n of have) if (!fs.lstatSync(path.join(target, n)).isFile()) throw new Error(`${dir}/${n} is not a plain file; refusing`);
	}
	const stage = `${target}.export-${process.pid}`;
	fs.rmSync(stage, { recursive: true, force: true });
	fs.mkdirSync(stage, { recursive: true });
	for (const [n, b] of Object.entries(files)) fs.writeFileSync(path.join(stage, n), b);
	fs.mkdirSync(path.dirname(target), { recursive: true });
	const old = `${target}.old-${process.pid}`;
	if (fs.existsSync(target)) fs.renameSync(target, old);
	try { fs.renameSync(stage, target); } catch (e) { if (fs.existsSync(old)) fs.renameSync(old, target); throw e; }
	fs.rmSync(old, { recursive: true, force: true });
	return { dir: target, manifest: JSON.parse(files['manifest.json'].toString()), files: Object.keys(files).sort() };
}
