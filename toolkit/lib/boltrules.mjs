// The launcher's install-time rules as code over schema/bolt-rules.json (the one rules file). Every check here mirrors a check the launcher
// makes when it loads an app file or installs a pack; each problem names the key and says the fix. Returns [{ code, message }].
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { get, str } from './yamlsubset.mjs';

export const RULES = JSON.parse(fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../schema/bolt-rules.json'), 'utf8'));
const entries = (n) => (n && n.t === 'm' ? n.entries : []);
const items = (n) => (n && n.t === 'l' ? n.items : []);
const scalar = (n) => (n && n.t === 's' ? n.v : undefined);
const num = (n) => (n && n.t === 's' && !n.q && /^-?\d+(\.\d+)?$/.test(n.v) ? Number(n.v) : undefined);
const kindWord = (t) => (t === 'm' ? 'a mapping' : t === 'l' ? 'a list' : 'text or a number');

// ---- 1, 2, 18: unknown keys and missing required keys at every level (the launcher refuses both)
function keys(node, spec, where, out) {
	if (!node || node.t !== 'm') return;
	const known = new Set(spec.all);
	for (const e of node.entries) if (!known.has(e.key)) out.push({ code: 'unknown_field', message: `${where}: "${e.key}" is not a field the launcher accepts here (it refuses the whole app file). Allowed: ${spec.all.join(', ')}` });
	for (const r of spec.required) if (!get(node, r)) out.push({ code: 'missing_field', message: `${where}: "${r}" is required` });
}
export function structureProblems(root) {
	const out = [], K = RULES.keys;
	// top-level keys and required fields are checked by verify (yaml_key_unknown, yaml_key_missing); this covers every nested level
	const rt = scalar(get(root, 'runtime')?.value);
	const bridge = get(root, 'bridge')?.value;
	if (rt === 'bridge') { if (!bridge) out.push({ code: 'missing_field', message: 'the app file: "bridge" is required for runtime bridge' }); else { keys(bridge, K.bridge, 'bridge', out); keys(get(bridge, 'command')?.value, K['bridge.command'], 'bridge.command', out); } }
	const http = get(root, 'http')?.value;
	if (rt === 'http_local') { if (!http) out.push({ code: 'missing_field', message: 'the app file: "http" is required for runtime http_local' }); else { keys(http, K.http, 'http', out); keys(get(http, 'request')?.value, K['http.request'], 'http.request', out); } }
	for (const [i, a] of items(get(root, 'args')?.value).entries()) keys(a, K['args[]'], `args[${i}]`, out);
	const pres = get(root, 'presentation')?.value;
	keys(pres, K.presentation, 'presentation', out);
	if (get(pres, 'right_widget')) keys(get(pres, 'right_widget').value, K.right_widget, 'presentation.right_widget', out);
	for (const v of entries(get(pres, 'views')?.value)) { keys(v.value, K['presentation.views.*'], `presentation.views.${v.key}`, out); if (get(v.value, 'right_widget')) keys(get(v.value, 'right_widget').value, K.right_widget, `presentation.views.${v.key}.right_widget`, out); }
	for (const [i, a] of items(get(root, 'actions')?.value).entries()) keys(a, K['actions[]'], `actions[${i}]`, out);
	if (get(root, 'dispatch')) keys(get(root, 'dispatch').value, K.dispatch, 'dispatch', out);
	for (const [i, a] of items(get(root, 'inputs')?.value).entries()) keys(a, K['inputs[]'], `inputs[${i}]`, out);
	if (get(root, 'submit')) keys(get(root, 'submit').value, K.submit, 'submit', out);
	return out;
}

// ---- 4: right_widget.bind per kind, as the launcher checks it (strict for schema_version 2 and for every pack)
function bindVal(node, spec, where, out) {
	const bad = (m) => out.push({ code: 'bind_invalid', message: `${where}: ${m}` });
	const t = spec.t;
	if (t === 'text') { if (!node || node.t !== 's') return bad(`must be text, got ${kindWord(node?.t)}`); if ([...node.v].length > spec.max) bad(`is longer than ${spec.max} characters`); }
	else if (t === 'textOrNumber') { if (!node || node.t !== 's') bad(`must be text or a number, got ${kindWord(node?.t)}`); else if ([...node.v].length > spec.max) bad(`is longer than ${spec.max} characters`); }
	else if (t === 'enum') { const v = scalar(node); if (v === undefined || !spec.values.includes(v)) bad(`must be one of ${spec.values.join(', ')}, got ${JSON.stringify(v ?? null)}`); }
	else if (t === 'bool') { const v = scalar(node); if (!(v === 'true' || v === 'false') || node.q) bad('must be true or false'); }
	else if (t === 'int') { const v = num(node); if (!Number.isInteger(v) || v < spec.lo || v > spec.hi) bad(`must be a whole number from ${spec.lo} to ${spec.hi}`); }
	else if (t === 'textList') { if (!node || node.t !== 'l') bad(`must be a list, got ${kindWord(node?.t)}`); else { if (node.items.length > spec.items) bad(`has more than ${spec.items} entries`); node.items.forEach((x, i) => { if (!x || x.t !== 's' || [...x.v].length > spec.max) bad(`entry ${i} must be text of at most ${spec.max} characters`); }); } }
	else if (t === 'list') { if (!node || node.t !== 'l') bad(`must be a list, got ${kindWord(node?.t)}`); else { if (node.items.length > spec.items) bad(`has more than ${spec.items} entries`); node.items.forEach((x, i) => bindMap(x, spec.keys, `${where}[${i}]`, out)); } }
	else if (t === 'map') bindMap(node, spec.keys, where, out);
}
function bindMap(node, keysSpec, where, out) {
	if (!node || node.t !== 'm') { out.push({ code: 'bind_invalid', message: `${where}: must be a mapping, got ${kindWord(node?.t)}` }); return; }
	for (const e of node.entries) {
		if (!Object.hasOwn(keysSpec, e.key)) out.push({ code: 'bind_unknown_key', message: `${where}.${e.key}: not a key this pane reads. Allowed: ${Object.keys(keysSpec).join(', ') || 'none'}` });
		else bindVal(e.value, keysSpec[e.key], `${where}.${e.key}`, out);
	}
	for (const [k, v] of Object.entries(keysSpec)) if (v.required && !get(node, k)) out.push({ code: 'bind_invalid', message: `${where}.${k}: is required` });
}
export function bindProblems(kind, bind, where) {
	const out = [], spec = RULES.right_widget.bind[kind];
	if (!spec || !bind) return out;
	bindMap(bind, spec, where, out);
	return out;
}

// ---- 5: environment variables
const isSecretName = (n) => RULES.env.secret_name_parts.some((p) => n.toUpperCase().includes(p));
export function envProblems(root) {
	const out = [], b = get(root, 'bridge')?.value, E = RULES.env;
	if (!b) return out;
	const pass = items(get(b, 'env_passthrough')?.value);
	if (pass.length > E.passthrough_max) out.push({ code: 'env_passthrough_max', message: `bridge.env_passthrough lists ${pass.length} names; at most ${E.passthrough_max} are allowed` });
	const check = (name, where) => {
		if (!new RegExp(E.name_pattern).test(name) || name.length > E.name_max_len) out.push({ code: 'env_name', message: `${where}: "${name}" must be 1 to ${E.name_max_len} uppercase letters, digits or _, starting with a letter` });
		else if (isSecretName(name)) out.push({ code: 'env_secret_name', message: `${where}: "${name}" looks like a secret (it contains ${E.secret_name_parts.join(', ')}). The launcher never forwards it to a personal or packed app. Keep keys in the system keychain or ~/.config/<id>/.env and read them in the script` });
		else if (!E.benign_passthrough.includes(name)) out.push({ code: 'env_not_allowed', message: `${where}: "${name}" is not on the launcher's list of variables an app may read (${E.benign_passthrough.join(', ')})` });
	};
	for (const [i, n] of pass.entries()) { const v = scalar(n); if (v !== undefined) check(v, `bridge.env_passthrough[${i}]`); }
	for (const e of entries(get(b, 'env')?.value)) {
		const v = scalar(e.value);
		if (v === undefined || !new RegExp(E.inline_value_pattern).test(v) || v !== '${env:' + e.key + '}') out.push({ code: 'env_inline_value', message: `bridge.env.${e.key}: the value must be exactly \${env:${e.key}} (a variable can be passed on, never set to a value or renamed)` });
		check(e.key, `bridge.env.${e.key}`);
	}
	return out;
}

// ---- 3, 13: timeouts and loopback services
export function timeoutProblems(root) {
	const out = [], T = RULES.timeouts, rt = scalar(get(root, 'runtime')?.value);
	const block = rt === 'bridge' ? get(root, 'bridge')?.value : rt === 'http_local' ? get(root, 'http')?.value : null;
	if (!block) return out;
	const raw = get(block, 'timeout_seconds')?.value, v = num(raw);
	if (raw === undefined) out.push({ code: 'timeout_default', level: 'warning', message: `${rt === 'bridge' ? 'bridge' : 'http'}.timeout_seconds is not set, so the launcher stops the app after ${T.default_s} seconds. Set it (${T.min_s} to ${T.max_s}) if the app can take longer` });
	else if (!Number.isInteger(v) || v < T.min_s || v > T.max_s) out.push({ code: 'timeout_out_of_range', message: `timeout_seconds must be a whole number from ${T.min_s} to ${T.max_s}, got ${JSON.stringify(scalar(raw) ?? null)}` });
	return out;
}
export function httpProblems(root) {
	const out = [], h = get(root, 'http')?.value, H = RULES.http_local;
	if (!h) return out;
	const p = num(get(h, 'port')?.value);
	if (!Number.isInteger(p) || p < 1 || p > 65535) out.push({ code: 'http_port', message: 'http.port must be a whole number from 1 to 65535 (0 is refused)' });
	else for (const [a, b] of H.reserved_ports) if (p >= a && p <= b) out.push({ code: 'http_port_reserved', message: `http.port ${p} is one of Bolt's own service ports (${H.reserved_ports.map((r) => r.join('-')).join(', ')}); the launcher refuses it. Use another port` });
	const host = scalar(get(h, 'host')?.value); if (host !== undefined && !H.hosts.includes(host)) out.push({ code: 'http_host_not_loopback', message: `http.host must be one of ${H.hosts.join(', ')}` });
	const m = scalar(get(get(h, 'request')?.value, 'method')?.value); if (m !== undefined && !H.methods.includes(m)) out.push({ code: 'http_method_not_allowed', message: `http.request.method must be GET or POST` });
	const pr = scalar(get(h, 'parse')?.value); if (pr !== undefined && !H.parse.includes(pr)) out.push({ code: 'http_parse', message: `http.parse must be json, lines or raw` });
	return out;
}

// ---- link hosts: parsed, not pattern-matched. Refuses userinfo, a placeholder host, and every spelling of a local or private address.
const IPV4_PRIVATE = (a, b) => a === 0 || a === 10 || a === 127 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
function ipv4Parts(h) {   // dotted, decimal, hex and octal spellings; null when h is not numeric
	const parts = h.split('.'); if (parts.length < 1 || parts.length > 4 || parts.some((p) => p === '')) return null;
	const nums = parts.map((p) => (/^0x[0-9a-f]+$/i.test(p) ? parseInt(p, 16) : /^0[0-7]+$/.test(p) ? parseInt(p, 8) : /^\d+$/.test(p) ? parseInt(p, 10) : NaN));
	if (nums.some((n) => Number.isNaN(n))) return null;
	let v = 0; for (let i = 0; i < nums.length - 1; i++) { if (nums[i] > 255) return null; v = v * 256 + nums[i]; }
	const last = nums[nums.length - 1], room = 256 ** (5 - nums.length); if (last >= room) return null;
	v = v * room + last; return [Math.floor(v / 2 ** 24) % 256, Math.floor(v / 2 ** 16) % 256, Math.floor(v / 256) % 256, v % 256];
}
export function hostProblem(u) {
	let url; try { url = new URL(u.replace(/\{[^}]*\}/g, 'x')); } catch { return { code: 'action_url', message: 'is not a valid https address' }; }
	if (url.protocol !== 'https:') return { code: 'action_url', message: 'must start with https://' };
	if (url.username || url.password) return { code: 'action_url', message: 'must not contain a user name or password before the host (user@host)' };
	if (/^https?:\/\/\{/i.test(u)) return { code: 'action_url', message: 'must have a literal host after https:// (a placeholder may not supply the host)' };
	let h = url.hostname.toLowerCase().replace(/\.$/, '');
	const bad = (why) => ({ code: 'action_url_internal', message: `host "${h}" is ${why}; the launcher refuses links to those` });
	if (!h) return { code: 'action_url', message: 'has no host' };
	if (h.startsWith('[')) { const v6 = h.slice(1, -1); const mapped = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/.exec(v6); if (mapped) { const q = ipv4Parts(mapped[1]); return q && IPV4_PRIVATE(q[0], q[1]) ? bad('a private address') : null; } return bad('an IPv6 address'); }
	const q = ipv4Parts(h);
	if (q) return IPV4_PRIVATE(q[0], q[1]) ? bad('a private or local address') : null;
	if (h === 'localhost' || h.endsWith('.localhost') || !h.includes('.') || RULES.actions.internal_host_suffixes.some((x) => h.endsWith(x))) return bad('a local or single-name host');
	return null;
}

// ---- 6, 12: action rules
export function actionProblems(root) {
	const out = [], A = RULES.actions, acts = items(get(root, 'actions')?.value);
	const seen = new Set(); let primary = 0;
	acts.forEach((a, i) => {
		const g = (k) => scalar(get(a, k)?.value), w = `actions[${i}]`;
		const id = g('id'), kind = g('kind'), label = g('label');
		if (id !== undefined) { if (!new RegExp(A.id_pattern).test(id) || A.forbidden_ids.includes(id)) out.push({ code: 'action_id', message: `${w}.id "${id}" must be 1 to 64 letters, digits, _ or -, and not ${A.forbidden_ids.join(', ')}` }); if (seen.has(id)) out.push({ code: 'action_id', message: `${w}.id "${id}" is used twice` }); seen.add(id); }
		if (kind !== undefined && !A.kinds.includes(kind)) out.push({ code: 'action_kind', message: `${w}.kind must be one of ${A.kinds.join(', ')}` });
		if (kind === 'url' && !g('url_template')) out.push({ code: 'action_field', message: `${w}: a url action needs url_template` });
		if (kind === 'composer' && !g('insert')) out.push({ code: 'action_field', message: `${w}: a composer action needs insert` });
		if (kind === 'utility' && !g('target_chip')) out.push({ code: 'action_field', message: `${w}: a utility action needs target_chip` });
		if (kind === 'run') { const q = g('query_template') ?? ''; if (!q.trim() || q.includes('{{')) out.push({ code: 'run_action_template', message: `${w}: a run action needs query_template with fixed text and no {{ }}; otherwise the button does nothing` }); }
		if (g('primary') === 'true') primary++;
		const icon = g('icon'); if (icon !== undefined && !A.icons.includes(icon)) out.push({ code: 'action_icon', message: `${w}.icon "${icon}" is not one of the ${A.icons.length} names the launcher allows for footer buttons: ${A.icons.join(', ')}` });
		if (label !== undefined && A.reserved_label_words.includes(label.trim().toLowerCase())) out.push({ code: 'action_label_reserved', level: 'warning', message: `${w}.label "${label}" is a word the launcher reserves for its own prompts; it shows "App: ${label}" instead. Use a more specific label` });
		const u = g('url_template');
		if (u !== undefined && kind === 'url' && /^https?:\/\//i.test(u)) { const hp = hostProblem(u); if (hp) out.push({ code: hp.code, message: `${w}.url_template ${hp.message}` }); }
	});
	if (primary > 1) out.push({ code: 'action_primary', message: 'at most one action may be primary' });
	return out;
}

// ---- 7, 8: row panes and nav
export function paneNavProblems(root) {
	const out = [], pres = get(root, 'presentation')?.value, views = entries(get(pres, 'views')?.value);
	const names = new Set(views.map((v) => v.key));
	const viewArg = scalar(get(pres, 'view_arg')?.value);
	if (viewArg) {
		const args = items(get(root, 'args')?.value);
		const arg = args.find((a) => scalar(get(a, 'name')?.value) === viewArg);
		const idx = Number(/^query\.word\(\s*(\d+)\s*\)$/.exec(scalar(get(arg, 'from')?.value) ?? '')?.[1]);
		if (Number.isInteger(idx) && idx > RULES.views.nav_word_max_index) out.push({ code: 'view_arg_index', message: `the view is read from query.word(${idx}); the launcher places at most ${RULES.views.nav_word_max_index} query words, so navigation is off` });
		for (let i = 0; Number.isInteger(idx) && i < idx; i++) {
			const holder = args.find((a) => a !== arg && new RegExp(`^query\\.word\\(\\s*${i}\\s*\\)$`).test(scalar(get(a, 'from')?.value) ?? ''));
			const d = get(holder, 'default')?.value;
			if (d && num(d) !== undefined) out.push({ code: 'view_arg_lead_default', message: `args default for query.word(${i}) is a number; quote it ("${d.v}"): a number default is not a nav token and turns navigation off` });
		}
	}
	return out;
}
export function paneProblem(pane, root) {
	if (typeof pane !== 'string' || !new RegExp(RULES.views.name_pattern).test(pane)) return `pane "${pane}" must match ${RULES.views.name_pattern}`;
	const views = entries(get(get(root, 'presentation')?.value, 'views')?.value);
	const v = views.find((e) => e.key === pane);
	if (!v) return `pane "${pane}" is not a view of this app (views: ${views.map((e) => e.key).join(', ') || 'none'})`;
	const rw = get(v.value, 'right_widget')?.value, kind = scalar(get(rw, 'kind')?.value), mode = scalar(get(rw, 'mode')?.value);
	if (!RULES.row_pane_kinds.includes(kind) || mode !== 'selected_row') return `pane "${pane}" must have a right_widget of kind ${RULES.row_pane_kinds.join(', ')} with mode selected_row (it is ${kind ?? 'none'}/${mode ?? 'default'})`;
	return null;
}

// ---- 11: pack version, parsed the way the launcher parses it
export function versionProblem(v) {
	let s = String(v).trim().replace(/^[vV]/, '').split('+')[0];
	const [core, pre] = [s.split('-')[0], s.includes('-') ? s.slice(s.indexOf('-') + 1) : null];
	if (!core || !core.split('.').every((p) => /^\d+$/.test(p))) return `version "${v}" is not a dotted number such as 1.0.1 (an optional leading v, a -prerelease and a +build are allowed)`;
	if (pre !== null && !/^[0-9A-Za-z.-]+$/.test(pre)) return `version "${v}" has an unreadable pre-release part`;
	return null;
}

// ---- 10: script layout, as the launcher installs it
export function layoutProblems(files) {
	const out = [], depth = RULES.pack.script_max_depth, lower = new Map();
	for (const f of files) {
		const parts = f.split('/');
		if (parts.length > depth + 1) out.push({ code: 'script_depth', message: `scripts/${f} is nested more than ${depth} folders deep; the launcher refuses it` });
		if (parts.some((p) => p === '..' || p === '.' || p === '')) out.push({ code: 'script_path', message: `scripts/${f} has a "." or ".." part; the launcher refuses it` });
		const l = f.toLowerCase(); if (lower.has(l) && lower.get(l) !== f) out.push({ code: 'script_case_clash', message: `scripts/${lower.get(l)} and scripts/${f} differ only in letter case; one would replace the other on macOS and Windows` }); lower.set(l, f);
	}
	const set = new Set(files);
	for (const f of files) { const parts = f.split('/'); for (let i = 1; i < parts.length; i++) if (set.has(parts.slice(0, i).join('/'))) out.push({ code: 'script_file_folder', message: `scripts/${parts.slice(0, i).join('/')} is both a file and a folder` }); }
	return out;
}
