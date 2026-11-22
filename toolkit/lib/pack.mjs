// Boltpack reading and integrity checks shared by verify and ship.
import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';

const isObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
export const PACK_MAX_BYTES = 50 * 1024 * 1024;
const PACK_LIMITS = { entries: 1024, unpacked: 64 * 1024 * 1024, inflated: 64 * 1024 * 1024 + 4 * 1024 * 1024 };
// Only these names exist in a pack: bundle.json, signature.bin and files under manifests/. Segments are plain: no empty, ., .., backslash or leading slash.
const canonicalName = (n) => (n === 'bundle.json' || n === 'signature.bin' || n.startsWith('manifests/') || n === 'manifests') && n.length > 0 && !n.includes('\\') && !n.startsWith('/') && n.split('/').every((seg) => seg !== '' && seg !== '.' && seg !== '..');
class PackError extends Error { constructor(code, message) { super(message); this.code = code; } }
function tarHeader(h) {
	const s = (a, b) => h.subarray(a, b).toString('utf8').replace(/\0.*$/s, '');
	const name = (s(345, 500) ? s(345, 500) + '/' : '') + s(0, 100), raw = s(124, 136).trim() || '0';
	const want = s(148, 156).trim(); let sum = 0; for (let k = 0; k < 512; k++) sum += k >= 148 && k < 156 ? 32 : h[k];
	if (!/^[0-7]+$/.test(want) || parseInt(want, 8) !== sum) throw new PackError('pack_malformed', 'a tar header checksum does not match');
	if (!/^[0-7]+$/.test(raw)) throw new PackError('pack_malformed', 'a file size in the archive is not a valid number');
	const size = parseInt(raw, 8), type = String.fromCharCode(h[156] || 48);
	if (type !== '0' && type !== '5') throw new PackError('pack_malformed', `an archive entry of type ${JSON.stringify(type)} (only plain files and folders are allowed)`);
	const bare = type === '5' ? name.replace(/\/$/, '') : name;
	if (!canonicalName(bare)) throw new PackError('pack_malformed', `an archive entry has a name Bolt does not accept: ${JSON.stringify(name.slice(0, 60))}`);
	if (!Number.isSafeInteger(size) || size < 0) throw new PackError('pack_malformed', 'a file size in the archive is invalid');
	return { name, size, type };
}

function untar(buf) {
	const files = new Map(); let off = 0, headers = 0, bytes = 0;
	while (off + 512 <= buf.length) {
		const h = buf.subarray(off, off + 512); if (h.every((b) => b === 0)) break;
		if (++headers > PACK_LIMITS.entries) throw new PackError('too_many_files', `more than ${PACK_LIMITS.entries} entries`);
		const { name, size, type } = tarHeader(h);
		bytes += size; if (bytes > PACK_LIMITS.unpacked) throw new PackError('pack_too_large', 'the pack unpacks to more than 64 MB');
		off += 512; if (off + size > buf.length) throw new PackError('pack_malformed', 'the archive ends inside a file');
		if (type === '0') { if (files.has(name)) throw new PackError('pack_duplicate_entry', `the archive holds ${name.slice(0, 80)} twice`); files.set(name, buf.subarray(off, off + size)); }
		off += Math.ceil(size / 512) * 512;
	}
	return files;
}
export function contentHash(manifests) {
	const h = crypto.createHash('sha256');
	for (const [p, c] of [...manifests].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))) {
		const pb = Buffer.from(p), pl = Buffer.alloc(4), cl = Buffer.alloc(8); pl.writeUInt32LE(pb.length); cl.writeBigUInt64LE(BigInt(c.length)); h.update(pl).update(pb).update(cl).update(c);
	}
	return h.digest('hex');
}
export const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
export function readPack(file) {
	let e;
	try {
		if (fs.statSync(file).size > PACK_MAX_BYTES) return { ok: false, code: 'pack_too_large', reason: 'the file is larger than 50 MB' };
		e = untar(zlib.gunzipSync(fs.readFileSync(file), { maxOutputLength: PACK_LIMITS.inflated }));
	} catch (x) {
		if (x instanceof PackError) return { ok: false, code: x.code, reason: x.message };
		if (x.code === 'ERR_BUFFER_TOO_LARGE') return { ok: false, code: 'pack_too_large', reason: 'the pack unpacks to more than 64 MB' };
		return { ok: false, code: 'pack_not_gzip_tar', reason: `not a gzip tar: ${x.message}` };
	}
	const bj = e.get('bundle.json'), sig = e.get('signature.bin'); if (!bj) return { ok: false, code: 'bundle_missing', reason: 'bundle.json is missing' };
	let meta; try { meta = JSON.parse(bj.toString()); } catch { return { ok: false, code: 'bundle_not_json', reason: 'bundle.json is not JSON' }; }
	if (!isObj(meta) || (meta.entries !== undefined && (!Array.isArray(meta.entries) || meta.entries.some((x) => !isObj(x) || typeof x.path !== 'string' || typeof x.sha256 !== 'string')))) return { ok: false, code: 'bundle_not_json', reason: 'bundle.json is not the object with an entries list of {path, sha256} that a pack has' };
	const man = new Map([...e].filter(([p]) => p.startsWith('manifests/')).map(([p, c]) => [p.slice(10), c]));
	const bad = (code, reason) => ({ ok: false, code, reason, meta, files: man, count: e.size });
	if (!sig || sig.length !== 64) return bad('signature_missing', 'signature.bin is missing or not 64 bytes');
	if (meta.signer_pubkey !== undefined && !/^[0-9a-f]{64}$/i.test(String(meta.signer_pubkey))) return bad('signature_mismatch', 'signer_pubkey is not 64 hexadecimal characters');
	if (!meta.signer_pubkey) return bad('signed_by_other_key', 'signed by a Sparcle or company key; only Bolt can verify that');
	let good = false; try { good = crypto.verify(null, bj, crypto.createPublicKey({ key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), Buffer.from(meta.signer_pubkey, 'hex')]), format: 'der', type: 'spki' }), sig); } catch { /* bad key */ }
	if (!good) return bad('signature_mismatch', 'the signature does not match bundle.json');
	if (contentHash(man) !== meta.content_sha256) return bad('content_hash_mismatch', 'files changed after signing (content hash mismatch)');
	for (const en of meta.entries || []) { if (!String(en.path).startsWith('manifests/')) continue; const c = man.get(String(en.path).replace(/^manifests\//, '')); if (!c || sha(c) !== en.sha256) return bad('entry_hash_mismatch', `entry ${en.path} does not match its hash`); }
	return { ok: true, meta, files: man, count: e.size };
}

// A version hint only. Ship verifies any pack it would use. Packs written by the CLI put bundle.json first;
// another member order or an unusually large bundle falls back to the full reader.
export async function readPackMetadata(file) {
	try {
		const st = fs.lstatSync(file);
		if (!st.isFile() || st.size > PACK_MAX_BYTES) return null;
	} catch { return null; }
	const input = fs.createReadStream(file, { highWaterMark: 16 * 1024 });
	const gzip = zlib.createGunzip();
	input.once('error', (error) => gzip.destroy(error));
	input.pipe(gzip);
	try {
		const header = Buffer.alloc(512);
		let headerBytes = 0, bundle, bundleBytes = 0;
		for await (const chunk of gzip) {
			let offset = 0;
			if (!bundle) {
				offset = chunk.copy(header, headerBytes);
				headerBytes += offset;
				if (headerBytes < header.length) continue;
				if (header.every((b) => b === 0)) return null;
				const { name, size, type } = tarHeader(header);
				if (name !== 'bundle.json' || type !== '0' || size > 1024 * 1024) return undefined;
				bundle = Buffer.alloc(size);
			}
			bundleBytes += chunk.copy(bundle, bundleBytes, offset);
			if (bundleBytes === bundle.length) {
				const meta = JSON.parse(bundle.toString('utf8'));
				return isObj(meta) ? meta : null;
			}
		}
		return null;
	} catch { return null; }
	finally {
		input.destroy();
		gzip.destroy();
	}
}
