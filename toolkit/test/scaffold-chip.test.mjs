// Run: node --test toolkit/test/scaffold-chip.test.mjs
// `new <id> --type transform|recognizer` keeps the app's identity: the chip is the id, even for an id that starts with a digit or is longer than 24 characters.
// Bolt only runs an app whose chip equals its id, so a scaffold that rewrites the chip fails its own lint (chip_not_id).
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const CLI = fileURLToPath(new URL('../bin/bolt-apps.mjs', import.meta.url));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-scaffold-chip-'));
const run = (...args) => spawnSync(process.execPath, [CLI, ...args], { encoding: 'utf8', env: { ...process.env, HOME: TMP } });
test.after(() => { if (path.basename(TMP).startsWith('bolt-scaffold-chip-')) fs.rmSync(TMP, { recursive: true, force: true }); });

const IDS = ['demo-app', '1-demo', '123', 'a'.repeat(25), '1'.repeat(64)];
for (const type of ['transform', 'recognizer']) {
	for (const id of IDS) {
		test(`${type}: id ${id.length > 30 ? id.slice(0, 6) + '... (' + id.length + ' chars)' : id} keeps chip equal to id and passes lint`, () => {
			const dir = path.join(TMP, type);
			const made = run('new', id, '--type', type, '--dir', dir, '--author', 'Test');
			assert.equal(made.status, 0, made.stdout + made.stderr);
			const yaml = fs.readFileSync(path.join(dir, id, 'utilities', id + '.yaml'), 'utf8');
			assert.match(yaml, new RegExp(`^id: "${id}"$`, 'm'));
			assert.match(yaml, new RegExp(`^chip: "?${id}"?$`, 'm'));
			if (type === 'transform') assert.ok(JSON.parse(fs.readFileSync(path.join(dir, id, 'bolt-app.json'), 'utf8')).summary.includes(`=${id},`), 'the summary names the chip the person types');
			const lint = run('lint', '--personal', path.join(dir, id));
			assert.equal(lint.status, 0, lint.stdout + lint.stderr);
			assert.ok(!/chip_not_id/.test(lint.stdout + lint.stderr));
		});
	}
}

test('snippet and search keep their own key rules (a letter first, short)', () => {
	const id = '1' + 'a'.repeat(30);
	for (const [type, re] of [['snippet', /^[a-z][a-z0-9_-]{0,23}$/], ['search', /^[a-z][a-z0-9]{0,11}$/]]) {
		const dir = path.join(TMP, type);
		const made = run('new', id, '--type', type, '--dir', dir, '--author', 'Test');
		assert.equal(made.status, 0, made.stdout + made.stderr);
		const listing = JSON.parse(fs.readFileSync(path.join(dir, id, 'bolt-app.json'), 'utf8'));
		assert.match(listing.tests[0].target, re);
	}
});
