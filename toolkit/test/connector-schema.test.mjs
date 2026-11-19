// Run: node --test toolkit/test/connector-schema.test.mjs
// The connector schema must accept what the connector spec and the connectors page describe,
// so the samples published on sparcle.app validate against it.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const sc = JSON.parse(fs.readFileSync(path.join(REPO, 'schema/connector.schema.json'), 'utf8'));
const rules = JSON.parse(fs.readFileSync(path.join(REPO, 'schema/bolt-rules.json'), 'utf8'));

test('every right-widget kind in bolt-rules.json is a connector right-widget kind', () => {
	const kinds = sc.$defs.RightWidget.properties.kind.enum;
	for (const k of rules.widget_kinds) assert.ok(kinds.includes(k), `${k} is missing from RightWidget.kind`);
	assert.ok(kinds.includes('entity'), 'entity (connector spec table) stays allowed');
});

test('action kinds are the spec list, and a clipboard action needs a value', () => {
	assert.deepEqual(sc.$defs.Action.properties.kind.enum, ['url', 'tool', 'utility', 'composer', 'clipboard']);
	assert.equal(sc.$defs.Action.properties.value.type, 'string');
	const rule = sc.$defs.Action.allOf.find((x) => x.if.properties.kind.const === 'clipboard');
	assert.deepEqual(rule.then.required, ['value']);
});

test('the manifest parts the connectors page lists are top-level properties, and unknown keys stay refused', () => {
	for (const k of ['bare', 'provisioning_mode', 'departments', 'roles', 'groups', 'dispatch', 'placeholder_examples', 'enabled'])
		assert.ok(k in sc.properties, `${k} is missing`);
	for (const k of ['departments', 'roles', 'groups']) assert.deepEqual(sc.properties[k].items, { type: 'string' });
	assert.equal(sc.additionalProperties, false);
});

test('dispatch allows confirm and auto, and choices exclude confirm_label and confirm_hint', () => {
	const d = sc.$defs.Dispatch;
	assert.deepEqual(d.properties.mode.enum, ['confirm', 'auto']);
	assert.equal(d.additionalProperties, false);
	assert.deepEqual(d.then.not.anyOf.map((x) => x.required[0]), ['confirm_label', 'confirm_hint']);
});

test('a bare recogniser needs at least one pattern with a regex', () => {
	const b = sc.$defs.Bare;
	assert.deepEqual(b.required, ['patterns']);
	assert.equal(b.properties.patterns.minItems, 1);
	assert.deepEqual(b.properties.patterns.items.required, ['regex']);
});
