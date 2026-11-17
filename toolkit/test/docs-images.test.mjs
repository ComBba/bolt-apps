// Run: node --test toolkit/test/docs-images.test.mjs
// The picture docs: every image exists and is small, has alt text, the anatomy snippets are real lines of the example files,
// and every example id and capability row they name exists.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const read = (f) => fs.readFileSync(path.join(REPO, f), 'utf8');
const exists = (f) => fs.existsSync(path.join(REPO, f));
const DOC_FILES = ['README.md', 'docs/anatomy.md', 'docs/gallery.md'];
const NEW_DOCS = ['docs/anatomy.md', 'docs/gallery.md', 'docs/gallery.json'];
const IMG_DIR = path.join(REPO, 'docs/images');
const CAPS = new Set(JSON.parse(read('kit/examples/capabilities.json')).rows.map((r) => r.id));

// ![alt](target) with a local target
const imageRefs = (file) => [...read(file).matchAll(/!\[([^\]]*)\]\(([^)\s]+)\)/g)].map((m) => ({ file, alt: m[1], target: m[2] }))
	.filter((r) => !/^https?:/.test(r.target));

test('every image referenced in README and docs exists and has alt text', () => {
	let n = 0;
	for (const f of DOC_FILES) for (const r of imageRefs(f)) {
		n++;
		const abs = path.normalize(path.join(path.dirname(f), r.target));
		assert.ok(exists(abs), `${f}: missing ${r.target}`);
		assert.ok(r.alt.trim().length >= 20, `${f}: alt text too short for ${r.target}`);
	}
	assert.ok(n >= 25, `expected the pictures to be referenced, found ${n}`);
});

test('every file in docs/images is used by a doc, and sizes are capped', () => {
	const used = new Set(DOC_FILES.flatMap((f) => imageRefs(f).map((r) => path.basename(r.target))));
	let total = 0;
	for (const name of fs.readdirSync(IMG_DIR)) {
		const size = fs.statSync(path.join(IMG_DIR, name)).size;
		total += size;
		assert.ok(size < 1.5 * 1024 * 1024, `${name} is ${size} bytes (cap 1.5 MB)`);
		assert.ok(used.has(name), `${name} is not referenced by any doc`);
		assert.ok(!/\.(mp4|mov|webm)$/i.test(name), `${name}: no video files in the repo`);
		assert.match(name, /^[a-z0-9]+(-[a-z0-9]+)+\.(png|gif)$/, `${name}: name must be <app>-<what>.png or .gif`);
	}
	assert.ok(total < 5 * 1024 * 1024, `docs/images is ${total} bytes (cap 5 MB)`);
});

test('the new docs have no em dash or en dash and no non-ASCII', () => {
	for (const f of NEW_DOCS) assert.ok(!/[^\x00-\x7f]/.test(read(f)), `${f} has a non-ASCII character`);
	assert.ok(!/[–—]/.test(read('README.md')), 'README.md has a dash character');
});

test('gallery.md equals what gallery.json says, and every entry is real', () => {
	const g = JSON.parse(read('docs/gallery.json')), md = read('docs/gallery.md');
	assert.ok(g.entries.length >= 10);
	assert.equal(g.anatomy.length, 4);
	for (const a of g.anatomy) { assert.ok(exists(`docs/images/${a.src}`), `anatomy image ${a.src}`); assert.ok(a.alt.length >= 20 && a.title, `anatomy ${a.src}`); assert.ok(read('docs/anatomy.md').includes(`![${a.alt}](images/${a.src})`)); }
	for (const e of g.entries) {
		assert.ok(exists(`kit/examples/${e.example}`), `example ${e.example}`);
		assert.ok(e.caption && e.how, `${e.id}: caption and how`);
		for (const c of e.caps) assert.ok(CAPS.has(c), `capability row ${c}`);
		for (const i of e.images) {
			assert.ok(exists(`docs/images/${i.src}`), `image ${i.src}`);
			assert.ok(i.alt.length >= 20, `alt for ${i.src}`);
			assert.ok(md.includes(`![${i.alt}](images/${i.src})`), `gallery.md lacks ${i.src}`);
		}
	}
});

test('anatomy.md: quoted lines are real lines of the named example file, and every example id and capability row exists', () => {
	const md = read('docs/anatomy.md');
	const blocks = [...md.matchAll(/Source: `([^`]+)`\n\n```yaml\n([\s\S]*?)```/g)];
	assert.equal(blocks.length, 4, 'four snippets');
	for (const [, file, body] of blocks) {
		assert.ok(exists(file), `${file} exists`);
		const lines = new Set(read(file).split('\n').map((l) => l.trim()));
		for (const line of body.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#'))) {
			assert.ok(lines.has(line.trim()), `${file} has no line: ${line.trim()}`);
			const key = line.trim().replace(/^- /, '').match(/^\{?\s*([a-z_]+):/);
			if (key) assert.ok(read(file).includes(`${key[1]}:`), `${file}: key ${key[1]}`);
		}
	}
	for (const [, id] of md.matchAll(/kit\/examples\/([a-z][a-z0-9-]+)(?=[`)/])/g)) assert.ok(exists(`kit/examples/${id}`), `example ${id}`);
	const capCells = [...md.matchAll(/^\|.*\| ((?:`[a-z_]+\.[a-z_]+`(?:, )?)+) \|$/gm)].flatMap((m) => [...m[1].matchAll(/`([^`]+)`/g)].map((x) => x[1]));
	assert.ok(capCells.length >= 15);
	for (const c of capCells) assert.ok(CAPS.has(c), `capability row ${c}`);
});

test('anatomy.md: dotted keys named in the tables exist in the example file or the schema', () => {
	const md = read('docs/anatomy.md');
	const haystack = read('schema/bolt-app.schema.json') + read('schema/bolt-rules.json') + read('kit/examples/acme-dash/utilities/acme-dash.yaml')
		+ read('kit/examples/pulse-feed/utilities/pulse-feed.yaml') + read('kit/examples/unit-convert/utilities/unit-convert.yaml');
	for (const [, cell] of md.matchAll(/^\| \d \|[^|]*\| ([^|]*) \|[^|]*\|$/gm))
		for (const [, tok] of cell.matchAll(/`([a-z_][a-z_.]*)(?::[^`]*)?`/g))
			for (const part of tok.split('.')) assert.ok(haystack.includes(part), `key ${part} (from ${tok}) not found in the example files or schemas`);
});
