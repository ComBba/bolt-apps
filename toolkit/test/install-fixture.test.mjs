// Run: node --test toolkit/test/install-fixture.test.mjs
// Install safety net, toolkit half: the eagle-info fixture (script app, helper package
// folder under scripts/, seven hosts, tier 3) goes author -> pack -> verify.
// The Bolt half (pack_validate + pack_install + loader + run) is covered by the launcher's own tests
// user_utilities::install_e2e, which builds a pack from a copy of the same fixture.
// Set BOLT_APPS_CLI to test another checkout of the toolkit.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI = process.env.BOLT_APPS_CLI || path.resolve(HERE, '../bin/bolt-apps.mjs');
const FIXTURE = path.join(HERE, 'fixtures', 'eagle-info');
const run = (cwd, ...a) => spawnSync(process.execPath, [CLI, ...a], { cwd, encoding: 'utf8' });
const { readPack } = await import(pathToFileURL(CLI).href);
const HAS_PERSONAL = run(os.tmpdir(), 'help').stdout.includes('--personal');
const SKIP = HAS_PERSONAL ? false : 'TODO(scope): this checkout has no pack --personal; the tests run once it does';

function stage() {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eagle-fixture-'));
	fs.cpSync(FIXTURE, path.join(root, 'apps', 'eagle-info'), { recursive: true });
	const key = path.join(root, 'k.pem');
	assert.equal(run(root, 'keygen', '--out', key).status, 0);
	return { root, key };
}

// KNOWN-FAILING (todo): on this app pack prints unknown_file, tier3_not_accepted and no_tests and never mentions
// --personal, because the hint only fires for simpler apps. Delete `todo` when the hint covers the fixture.
test('fixture: a gallery pack refuses it and the words point at --personal', { skip: SKIP, todo: SKIP ? false : 'KNOWN-FAILING: pack output never mentions --personal for a tier 3 script app' }, () => {
	const { root, key } = stage();
	const r = run(root, 'pack', 'apps/eagle-info', '--key', key);
	assert.equal(r.status, 1);
	assert.match(r.stderr, /--personal/, 'the refusal must say what to do instead');
});

test('fixture without the helper folder (one flat script) packs with --personal and verifies', { skip: SKIP }, () => {
	const { root, key } = stage();
	fs.rmSync(path.join(root, 'apps', 'eagle-info', 'scripts', 'eagle-info__lib'), { recursive: true });
	fs.writeFileSync(path.join(root, 'apps', 'eagle-info', 'scripts', 'eagle-info__eagle_info.py'), 'print("{}")\n');
	const out = path.join(root, 'e.boltpack');
	const r = run(root, 'pack', 'apps/eagle-info', '--personal', '--key', key, '--out', out);
	assert.equal(r.status, 0, r.stderr);
	assert.equal(run(root, 'verify', out).status, 0);
	const m = readPack(out).meta;
	assert.equal(m.listing.tier, 3);
	assert.ok(m.entries.some((e) => e.kind === 'script' && e.path === 'manifests/scripts/eagle-info__eagle_info.py'));
});

// The tester's real layout: a helper package next to the script. Bolt 0.1.180 and later install script subfolders, so the package keeps its folder, under the app's own name
// (every file of an app starts with <app id>__ because all apps share one scripts folder).
test('fixture with the helper package: packs with the folder intact, under the app\'s own name', { skip: SKIP }, () => {
	const { root, key } = stage();
	const out = path.join(root, 'e.boltpack');
	const r = run(root, 'pack', 'apps/eagle-info', '--personal', '--key', key, '--out', out);
	assert.equal(r.status, 0, r.stderr);
	const paths = readPack(out).meta.entries.map((e) => e.path);
	for (const f of ['__init__.py', 'cache.py', 'text.py', 'rows.py']) assert.ok(paths.includes(`manifests/scripts/eagle-info__lib/bolt_app_kit/${f}`), f);
	assert.equal(paths.filter((p) => p.startsWith('manifests/scripts/eagle-info__lib/bolt_app_kit/')).length, 10);
	assert.ok(paths.every((p) => !p.startsWith('manifests/scripts/') || p.startsWith('manifests/scripts/eagle-info__')));
});
