// Run: node --test toolkit/test/no-dashes.test.mjs
// The repo's own source and docs never contain an em dash or an en dash. The launcher draws a dash placeholder for an empty field; say "dash placeholder" in words.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const DASH = new RegExp(`[${String.fromCharCode(0x2013)}${String.fromCharCode(0x2014)}]`);
function* walk(d) {
	for (const e of fs.readdirSync(d, { withFileTypes: true })) {
		if (e.name === 'node_modules' || e.name === '.git') continue;
		const p = path.join(d, e.name);
		if (e.isDirectory()) yield* walk(p); else if (/\.(mjs|js|json|md|py|yaml|yml|txt)$/.test(e.name)) yield p;
	}
}
test('no em dash or en dash in kit/, toolkit/ or docs/', () => {
	const bad = [];
	for (const top of ['kit', 'toolkit', 'docs']) for (const f of walk(path.join(REPO, top))) { const lines = fs.readFileSync(f, 'utf8').split('\n'); lines.forEach((l, i) => { if (DASH.test(l)) bad.push(`${path.relative(REPO, f)}:${i + 1}`); }); }
	assert.deepEqual(bad, [], 'replace the dash with plain words');
});
