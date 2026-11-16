// Run: node --test toolkit/test/schema-honesty.test.mjs
// The YAML schema must say what Bolt does, no more and no less.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const sc = JSON.parse(fs.readFileSync(path.join(REPO, 'schema/user-app.schema.json'), 'utf8'));

test('a reserved action label is shown as "App: <word>" and warned about, not refused', () => {
	const d = sc.$defs.action.properties.label.description;
	assert.match(d, /App: <word>/); assert.match(d, /action_label_reserved/); assert.doesNotMatch(d, /\brefused\b/);
});

test('the actions list has no item cap (6 is the footer cap, stated in the description only)', () => {
	assert.equal(sc.properties.actions.maxItems, undefined);
	assert.match(sc.properties.actions.description, /at most 6 footer buttons/);
});

test('a run action is never primary and holds no placeholder; view_arg needs an arg bound to query.word(N)', () => {
	const run = sc.$defs.action.allOf.find((x) => x.if.properties.kind.const === 'run').then;
	assert.deepEqual(run.properties.primary, { not: { const: true } });
	assert.ok(new RegExp(run.properties.query_template.not.pattern).test('go {{x}}'));
	assert.ok(!new RegExp(run.properties.query_template.not.pattern).test('save now'));
	const va = sc.allOf.find((x) => x.if.properties.presentation);
	assert.deepEqual(va.then.required, ['args']);
	assert.ok(new RegExp(va.then.properties.args.contains.properties.from.pattern).test('query.word(0)'));
});

test('searchable is documented as inert, and the root says Bolt checks more than a schema can', () => {
	assert.match(sc.$defs.presentation.properties.searchable.description, /does nothing/);
	assert.match(sc.$defs.presentation.properties.searchable.description, /dispatch\.choices/);
	assert.match(sc.description, /duplicate action ids/);
});
