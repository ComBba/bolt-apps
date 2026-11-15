// The one-command-per-job workflow: new <template> <id>, run, ship, doctor. Each command writes only inside the app folder or ~/.bolt-apps,
// never prints a secret, and ends every problem with the exact fix. They call the other commands as child processes so there is one
// implementation of lint, check, pack and verify.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parseYaml, get, str } from './yamlsubset.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.resolve(HERE, '../bin/bolt-apps.mjs');
const EXAMPLES = path.resolve(HERE, '../../kit/examples');
const STATE = path.join(os.homedir(), '.bolt-apps');
const DOCS = 'https://sparcle.app/docs/extend/agent-guide.md';
const q = (p) => (/^[A-Za-z0-9_./:@%+=,~-]+$/.test(p) ? p : `'${String(p).replace(/'/g, `'\\''`)}'`);   // a path with spaces is printed in quotes so it can be pasted
const die = (m, code = 1) => { console.error(`bolt-apps: ${m}`); process.exit(code); };
const bolt = (args, opts = {}) => spawnSync(process.execPath, [CLI, ...args], { encoding: 'utf8', ...opts });

// A value that looks like a real secret in any file of the app. Only high-confidence shapes: an app may legitimately hold made-up sample keys.
const SECRET_SHAPES = [/\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{20,})/, /-----BEGIN [A-Z ]*PRIVATE KEY-----/, /Authorization['":\s]+Bearer\s+[A-Za-z0-9._~+\/-]{24,}/i];
export function keyLooking(dir) {
	const hits = [];
	const walk = (d) => {
		for (const e of fs.readdirSync(d, { withFileTypes: true })) {
			if (e.name === '__pycache__' || e.name === '.git' || e.name.endsWith('.boltpack')) continue;
			const f = path.join(d, e.name);
			if (e.isDirectory()) walk(f); else if (e.isFile() && fs.statSync(f).size < 2e6) {
				const b = fs.readFileSync(f); if (b.includes(0)) continue;
				const t = b.toString('utf8'); for (const re of SECRET_SHAPES) if (re.test(t)) { hits.push(path.relative(dir, f)); break; }
			}
		}
	};
	walk(dir);
	return hits;
}
const refuseSecrets = (dir) => { const h = keyLooking(dir); if (h.length) die(`${h.join(', ')} holds something shaped like a real key or token. Remove it from the app folder: keys go in the system keychain or ~/.config/<id>/.env (mode 600), never in a file you pack or share. See ${DOCS}#secrets`); };

// ---------------------------------------------------------------- new <template> <id>  and  new --list
export const listTemplates = () => { try { return JSON.parse(fs.readFileSync(path.join(EXAMPLES, 'index.json'), 'utf8')).apps; } catch { return []; } };
export const hasTemplate = (name) => /^[a-z0-9][a-z0-9-]*$/.test(name) && fs.existsSync(path.join(EXAMPLES, name, 'bolt-app.json'));
export function newList() {
	const apps = listTemplates();
	console.log('Templates (bolt-apps new <template> <id>):\n');
	for (const a of apps) console.log(`  ${a.id.padEnd(24)} ${a.need || a.layout}\n  ${''.padEnd(24)} edit: ${(a.edit || []).join(', ')}`);
	console.log(`\nStart with the one whose "need" matches. Not sure: ${DOCS}`);
}
export function newFromTemplate(template, id, root) {
	const src = path.join(EXAMPLES, template);
	if (!fs.existsSync(path.join(src, 'bolt-app.json'))) die(`no template "${template}". Run: bolt-apps new --list`);
	if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) die('the id is lowercase letters, digits and hyphens, at most 64 characters, for example my-tool');
	const dir = path.join(root, id);
	if (fs.existsSync(dir) || (() => { try { fs.lstatSync(dir); return true; } catch { return false; } })()) die(`${q(dir)} already exists (or is a link). Choose another id, or delete it first`);
	fs.cpSync(src, dir, { recursive: true, filter: (f) => !/__pycache__|\.boltpack$|[\\/]golden([\\/]|$)/.test(f) });
	const chip = id.replace(/[^a-z0-9]/g, '').slice(0, 20) || id.slice(0, 20);
	fs.rmSync(path.join(dir, 'golden'), { recursive: true, force: true });   // the template's goldens belong to the template; check --update-golden writes new ones
	const title = id.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
	const edit = (f, fn) => { const p = path.join(dir, f); if (fs.existsSync(p)) fs.writeFileSync(p, fn(fs.readFileSync(p, 'utf8'))); };
	edit('bolt-app.json', (t) => { const j = JSON.parse(t); j.id = id; j.title = title; return JSON.stringify(j, null, 2) + '\n'; });
	edit('scripts/config.json', (t) => { const j = JSON.parse(t); if (j.app) { j.app.id = id; j.app.chip = chip; j.app.title = title; } return JSON.stringify(j, null, 2) + '\n'; });
	// regenerate the app file from the config when the template has an emitter, else rewrite id, chip and title in place
	const sd = path.join(dir, 'scripts');
	const emitter = fs.existsSync(sd) ? fs.readdirSync(sd).filter((f) => f.endsWith('.py') && f !== 'bolt_app_kit.py').find((f) => fs.readFileSync(path.join(sd, f), 'utf8').includes('--emit-yaml')) : null;
	const ud = path.join(dir, 'utilities');
	if (emitter) {
		const r = spawnSync('python3', [`scripts/${emitter}`, '--emit-yaml'], { cwd: dir, encoding: 'utf8' });
		if (r.status !== 0) die(`could not generate the app file: ${r.stderr.slice(-300)}`);
		for (const y of fs.readdirSync(ud)) fs.rmSync(path.join(ud, y));
		fs.writeFileSync(path.join(ud, `${id}.yaml`), r.stdout);
	} else if (fs.existsSync(ud)) for (const y of fs.readdirSync(ud)) { const p = path.join(ud, y); fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace(/^id: .*$/m, `id: ${id}`).replace(/^chip: .*$/m, `chip: ${chip}`).replace(/^title: .*$/m, `title: "${title}"`)); }
	let note = '';
	if (fs.existsSync(path.join(dir, 'check.json'))) {   // goldens were not copied: record them for the new app and show that it passes
		const r = bolt(['check', dir, '--update-golden']);
		note = r.status === 0 ? 'check passes on the sample data' : `check did not pass yet:\n${r.stdout.slice(-900)}`;
	}
	console.log(`created ${q(dir)} from ${template} (id ${id}, chip =${chip}). ${note}\n\nNext:\n  1. edit: ${(listTemplates().find((a) => a.id === template)?.edit || ['the files its README names']).join(', ')}\n  2. bolt-apps run ${q(dir)} --sample      (see the rows) and  bolt-apps check ${q(dir)}\n  3. bolt-apps ship ${q(dir)}              (lint, check, pack, verify, then drop the .boltpack on Bolt)`);
}

// ---------------------------------------------------------------- run
function bridgeCommand(dir0, words) {
	const dir = path.resolve(dir0);
	const ud = path.join(dir, 'utilities');
	let y; try { y = fs.readdirSync(ud).find((f) => /\.ya?ml$/.test(f)); } catch { die(`${q(ud)} is missing. An app folder has utilities/<id>.yaml`); } if (!y) die(`${q(ud)} has no app file`);
	let root; try { root = parseYaml(fs.readFileSync(path.join(ud, y), 'utf8')); } catch (e) { die(`${q(path.join(ud, y))} cannot be read as an app file (${String(e.message).slice(0, 120)}). Fix the YAML, or regenerate it from config.json`); }
	const osKey = process.platform === 'darwin' ? 'macos' : process.platform === 'win32' ? 'windows' : 'linux';
	const tpl = str(get(get(get(root, 'bridge')?.value, 'command')?.value, osKey)?.value);
	if (!tpl) return { root, error: `the app file has no bridge command for ${osKey}` };
	const vars = {};
	for (const a of get(root, 'args')?.value?.items || []) {
		const m = /^query\.word\(\s*(\d+)\s*\)$/.exec((str(get(a, 'from')?.value) ?? '').trim());
		if (m) vars[str(get(a, 'name')?.value)] = words[Number(m[1])] ?? String(str(get(a, 'default')?.value) ?? '-');
	}
	// split the command into words first, then fill each word: a folder with spaces in its path stays one word, and a query word can never add words
	const argv = tpl.split(/\s+/).filter(Boolean).map((w) => w.replace(/\{\{scripts_dir\}\}/g, path.join(dir, 'scripts')).replace(/\{\{\s*(\w+)\s*(?:\|\s*default:\s*([^}]*?)\s*)?\}\}/g, (_, n, d) => vars[n] ?? d ?? '-'));
	return { root, argv };
}
function paneOf(root, view) {
	const pres = get(root, 'presentation')?.value, v = get(get(pres, 'views')?.value, view)?.value;
	const rw = get(v, 'right_widget')?.value || get(pres, 'right_widget')?.value;
	return rw ? `${str(get(rw, 'kind')?.value)} (${str(get(rw, 'mode')?.value) || 'default mode'})` : 'none';
}
export function runApp(args) {
	const flags = args.filter((a) => a.startsWith('--')), rest = args.filter((a) => !a.startsWith('--'));
	const dir = rest[0]; if (!dir || !fs.existsSync(path.join(dir, 'bolt-app.json'))) die('usage: bolt-apps run <app-folder> [view [word]] [--sample | --live] [--json]\n  Runs the app about as Bolt would (an approximation: the launcher is the final judge) and shows the rows. Note: it executes the app\'s own command on your computer with your real HOME and PATH; --live reads your real keychain and ~/.config/<id>/.env. Run only code you have read.');
	refuseSecrets(dir);
	const words = rest.slice(1);
	const b = bridgeCommand(dir, words); if (b.error) die(b.error);
	const env = { PATH: process.env.PATH, HOME: os.homedir(), USER: os.userInfo().username, LOGNAME: os.userInfo().username, LANG: process.env.LANG || 'en_US.UTF-8', PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1', BOLT_APP_DEBUG: '1' };   // an approximation of the launcher's runner environment: the launcher is the final judge
	if (flags.includes('--sample')) env.BOLT_APP_FIXTURE = '1'; else if (flags.includes('--live')) env.BOLT_APP_FIXTURE = '0';
	const r = spawnSync(b.argv[0], b.argv.slice(1), { env, cwd: path.join(dir, 'scripts'), encoding: 'utf8', input: '', timeout: 30000 });
	if (r.error || r.status !== 0) die(`the script failed (exit ${r.status}). ${r.stderr ? 'Its error output:\n' + r.stderr.trim().split('\n').slice(-12).join('\n') : (r.error ? String(r.error.message) : '')}\n  Command: ${b.argv.map(q).join(' ')}`);
	let rows; try { rows = JSON.parse(r.stdout); } catch { die(`the script did not print JSON rows. It printed: ${r.stdout.slice(0, 300)}${r.stderr ? '\nstderr: ' + r.stderr.trim().slice(-300) : ''}`); }
	if (flags.includes('--json')) { console.log(JSON.stringify(rows, null, 2)); return; }
	const view = words[0] || 'overview';
	console.log(`${path.basename(path.resolve(dir))} · view ${view} · ${env.BOLT_APP_FIXTURE === '1' ? 'sample data' : env.BOLT_APP_FIXTURE === '0' ? 'live' : "the app's default mode"} · right pane: ${paneOf(b.root, view)}\n`);
	rows.forEach((x, i) => {
		const badges = [x.kpi_badge, ...((x.badges || []).map((q) => q.label))].filter(Boolean);
		console.log(`${String(i + 1).padStart(2)}. ${x.title}${badges.length ? '  [' + badges.join(', ') + ']' : ''}${x.nav ? (x.nav.back ? '   <- Back' : `   -> ${x.nav.view}${x.nav.arg ? ' ' + x.nav.arg : ''}`) : ''}`);
		if (x.subtitle) console.log(`      ${x.subtitle}`);
		if (x.kpi_label) console.log(`      tile: ${x.kpi_label} = ${x.kpi_value}${x.kpi_unit ? ' ' + x.kpi_unit : ''}${x.kpi_max !== '' && x.kpi_max !== undefined ? ' of ' + x.kpi_max : ''}${x.kpi_note ? ' (' + x.kpi_note + ')' : ''}`);
		const extras = Object.keys(x).filter((k) => !['title', 'subtitle', 'icon', 'body', 'nav', 'actions', 'pane', 'copy_text', 'open_url', 'url', 'badges', 'id', 'category', 'data', 'trend', 'multiline'].includes(k) && !k.startsWith('kpi_') && x[k] !== '');
		if (extras.length) console.log(`      fields: ${extras.map((k) => `${k}=${String(x[k]).slice(0, 40)}`).join(', ')}`);
		if (x.open_url || x.url) console.log(`      opens: ${x.open_url || x.url}`);
		if (x.copy_text) console.log(`      copies: ${String(x.copy_text).replace(/\n/g, ' / ').slice(0, 80)}`);
		for (const a of x.actions || []) console.log(`      action: ${a.label} (${a.kind})`);
		if (x.trend) console.log(`      trend: ${x.trend.length} points`);
		if (x.body) console.log(`      body: ${String(x.body).split('\n')[0].slice(0, 80)}`);
	});
	if (rows.some((x) => x.title === 'This app could not run' || x.title === 'This app is not set up correctly')) console.log('\nThe app printed its own error row (above). BOLT_APP_DEBUG=1 is set, so the script wrote the real error to its error output; run with --json to see it as data.');
}

// ---------------------------------------------------------------- ship
const notLink = (f) => { try { if (fs.lstatSync(f).isSymbolicLink()) die(`${f} is a link, which is not followed. Replace it with a real file or folder you own`); } catch (e) { if (e.code !== 'ENOENT') throw e; } };
const loadShip = () => { try { const j = JSON.parse(fs.readFileSync(path.join(STATE, 'ship.json'), 'utf8')); return j && typeof j === 'object' && !Array.isArray(j) ? Object.assign(Object.create(null), j) : Object.create(null); } catch { return Object.create(null); } };
const bump = (v) => { const p = String(v).split('.').map(Number); if (p.length !== 3 || p.some((n) => !Number.isInteger(n))) return '1.0.1'; p[2] += 1; return p.join('.'); };
export function ship(args) {
	const dir = args.find((a) => !a.startsWith('--')); if (!dir || !fs.existsSync(path.join(dir, 'bolt-app.json'))) die('usage: bolt-apps ship <app-folder>   (lint, check, pack, verify, with the next version picked for you)');
	refuseSecrets(dir);
	let app; try { app = JSON.parse(fs.readFileSync(path.join(dir, 'bolt-app.json'), 'utf8')); } catch (e) { die(`${q(path.join(dir, 'bolt-app.json'))} is not valid JSON (${e.message}). Fix it, then run ship again`); }
	if (!app || typeof app !== 'object' || Array.isArray(app)) die(`${q(path.join(dir, 'bolt-app.json'))} must be a JSON object with an id, title and so on, not ${app === null ? 'null' : Array.isArray(app) ? 'a list' : typeof app}. Fix it, then run ship again`);
	if (typeof app.id !== 'string' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(app.id)) die(`bolt-app.json needs an "id" of lowercase letters, digits and hyphens (got ${JSON.stringify(app.id ?? null)})`);
	const step = (name, r) => { if (r.status !== 0) { console.error(`${r.stdout}${r.stderr}`.trim().split('\n').slice(-25).join('\n')); die(`${name} failed. Fix the lines above (each says what to change), then run ship again`); } console.log(`ok ${name}`); };
	step('lint --personal', bolt(['lint', dir, '--personal']));
	if (fs.existsSync(path.join(dir, 'check.json'))) step('check', bolt(['check', dir]));
	notLink(STATE); notLink(path.join(STATE, 'key.pem')); notLink(path.join(STATE, 'ship.json')); notLink(path.join(STATE, 'packs'));
	const key = path.join(STATE, 'key.pem');
	if (!fs.existsSync(key)) { const k = bolt(['keygen']); if (k.status !== 0) die(`could not make your signing key: ${k.stderr || k.stdout}`); console.log('ok made your signing key in ~/.bolt-apps/key.pem (keep it private, never share it)'); }
	const state = loadShip(), version = typeof state[app.id] === 'string' ? bump(state[app.id]) : '1.0.0';
	fs.mkdirSync(path.join(STATE, 'packs'), { recursive: true, mode: 0o700 });
	const out = path.join(STATE, 'packs', `${app.id}-${version}.boltpack`);
	step(`pack ${version}`, bolt(['pack', dir, '--personal', '--version', version, '--out', out]));
	step('verify', bolt(['verify', out]));
	state[app.id] = version; fs.mkdirSync(STATE, { recursive: true, mode: 0o700 }); fs.writeFileSync(path.join(STATE, 'ship.json'), JSON.stringify(Object.fromEntries(Object.entries(state)), null, 2) + '\n');
	const chip = (() => { try { const y = fs.readdirSync(path.join(dir, 'utilities')).find((f) => /\.ya?ml$/.test(f)); return str(get(parseYaml(fs.readFileSync(path.join(dir, 'utilities', y), 'utf8')), 'chip')?.value) || app.id; } catch { return app.id; } })();
	console.log(`\nShipped ${app.id} ${version}: ${out}\nInstall: drop that file on the Bolt launcher (or Bolt Apps), read the prompt, approve it, then type =${chip}.\nThis app runs as you: only install code you have read. Next time run ship again and the version rises by itself.`);
}

// ---------------------------------------------------------------- doctor
export function doctor(args) {
	const dir = args.find((a) => !a.startsWith('--'));
	const line = (ok, what, fix) => console.log(`${ok ? 'ok  ' : 'FIX '} ${what}${ok ? '' : `\n       ${fix}`}`);
	let bad = 0; const chk = (ok, what, fix) => { if (!ok) bad++; line(ok, what, fix); };
	const nodeMajor = Number(process.versions.node.split('.')[0]); chk(nodeMajor >= 18, `node ${process.versions.node}`, 'Install Node 18 or newer (https://nodejs.org).');
	const py = spawnSync('python3', ['--version'], { encoding: 'utf8' }); const pv = /(\d+)\.(\d+)/.exec(py.stdout || py.stderr || '');
	chk(!!pv && (Number(pv[1]) > 3 || (Number(pv[1]) === 3 && Number(pv[2]) >= 9)), `python3 ${pv ? pv[0] : 'not found'}`, 'Install Python 3.9 or newer; script apps run with python3.');
	chk(fs.existsSync(path.join(STATE, 'key.pem')), `signing key (${q(path.join(STATE, 'key.pem'))})`, 'Run: bolt-apps keygen   (once; ship also makes it for you)');
	try { fs.mkdirSync(STATE, { recursive: true, mode: 0o700 }); fs.accessSync(STATE, fs.constants.W_OK); chk(true, '~/.bolt-apps is writable'); } catch { chk(false, '~/.bolt-apps is writable', `Run: mkdir -p ${q(STATE)} && chmod 700 ${q(STATE)}`); }
	if (dir && fs.existsSync(path.join(dir, 'bolt-app.json'))) {
		let id; try { const j = JSON.parse(fs.readFileSync(path.join(dir, 'bolt-app.json'), 'utf8')); if (!j || typeof j !== 'object' || Array.isArray(j)) { chk(false, 'bolt-app.json is a JSON object', `Make ${q(path.join(dir, 'bolt-app.json'))} an object like { "id": "my-tool", ... } (it is ${j === null ? 'null' : 'not an object'})`); console.log(`\n${bad} thing(s) to fix.`); process.exit(1); } id = j.id; } catch (e) { chk(false, 'bolt-app.json is valid JSON', `Fix ${path.join(dir, 'bolt-app.json')}: ${e.message}`); console.log(`\n${bad} thing(s) to fix.`); process.exit(1); }
		if (typeof id !== 'string' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) { chk(false, 'bolt-app.json has an id', 'Add "id": "my-tool" (lowercase letters, digits, hyphens) to bolt-app.json.'); console.log(`\n${bad} thing(s) to fix.`); process.exit(1); }
		const env = path.join(os.homedir(), '.config', id, '.env');
		if (fs.existsSync(env)) chk((fs.statSync(env).mode & 0o077) === 0, `~/.config/${id}/.env is private`, `Run: chmod 600 ${q(env)}`);
		const hits = keyLooking(dir); chk(!hits.length, 'no real-looking key in the app folder', `Remove the key from ${hits.map(q).join(', ')}; keys go in the keychain or ~/.config/${id}/.env.`);
		const l = bolt(['lint', dir, '--personal']); chk(l.status === 0, 'lint --personal (what blocks a dropped pack)', `Run: bolt-apps lint ${q(dir)} --personal   and fix each line it prints.`);
		if (l.status === 0) { const v = bolt(['verify', dir]); chk(v.status === 0, 'verify (what Bolt checks at install)', `Run: bolt-apps verify ${q(dir)}   and fix each line it prints.`); }
	} else console.log('\n(give an app folder to also check its key file, lint and verify: bolt-apps doctor <app-folder>)');
	console.log(bad ? `\n${bad} thing(s) to fix.` : '\nAll good.');
	process.exit(bad ? 1 : 0);
}
