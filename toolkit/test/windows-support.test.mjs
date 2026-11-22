// Native Windows support for check.mjs: stubs, metacharacter-safe args, hang, hostile UTF-8, USERPROFILE isolation, and stub file containment.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkApp, formatReport, hostOs, reportOk, vendorKit } from '../lib/check.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../..');
const HOSTILE = 'a\u202eb\u200bc{{x}}\u{E0041}d\u2028e\u0007f\u3164g\u2800h';
const codes = (f) => f.map((x) => x.code);

function tinyApp(script, cases) {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bolt-win-'));
	const id = 'wintiny';
	const dir = path.join(root, id);
	fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
	fs.writeFileSync(
		path.join(dir, 'bolt-app.json'),
		JSON.stringify({
			schema_version: 1,
			id,
			title: 'Win Tiny',
			role: 'test',
			saves: 'test',
			summary: 'test',
			author: { name: 'Test' },
			tier: 3,
			permissions: ['runs_commands'],
		})
	);
	fs.writeFileSync(path.join(dir, 'scripts', `${id}__app.py`), script);
	fs.writeFileSync(
		path.join(dir, 'check.json'),
		JSON.stringify({ script: `scripts/${id}__app.py`, interpreter: 'python3', kit: `scripts/${id}__bolt_app_kit.py`, cases })
	);
	vendorKit(dir, { flat: true });
	return dir;
}

test('formatReport: a Windows host omits Windows from the Not run footer', () => {
	const win = formatReport({ app: 'x', host_os: 'windows', findings: [], cases: [{ name: 'a', os: 'windows', ok: true, findings: [] }] });
	assert.match(win, /Not run: the real launcher, macOS, Linux, other OS tools\./);
	assert.doesNotMatch(win, /Not run: the real launcher, Windows,/);
	const mac = formatReport({ app: 'x', host_os: 'macos', findings: [], cases: [{ name: 'a', os: 'macos', ok: true, findings: [] }] });
	assert.match(mac, /Not run: the real launcher, Windows, other OS tools\./);
});

test('checkApp: portal-template and system-glance pass on this host', async () => {
	for (const name of ['portal-template', 'system-glance']) {
		const r = await checkApp(path.join(REPO, 'kit', 'examples', name));
		assert.equal(r.findings.filter((x) => x.level === 'error').length, 0, `${name} findings: ${JSON.stringify(r.findings)}`);
		assert.ok(r.cases.length, name);
		for (const c of r.cases) assert.ok(c.ok, `${name} ${c.name}: ${JSON.stringify(c.findings)}`);
		assert.ok(reportOk(r), name);
	}
});

test('check stubs: by_args (including cmd.exe metacharacters), hang, and hostile UTF-8 bytes', async () => {
	const osName = hostOs() === 'other' ? 'linux' : hostOs();
	const script = `import os, json, subprocess
sep = os.pathsep
stubdir = os.environ["PATH"].split(sep)[0]
ext = ".cmd" if os.path.isfile(os.path.join(stubdir, "mytool.cmd")) else ""
stub = os.path.join(stubdir, "mytool" + ext)
def run(args):
    return subprocess.run([stub] + args, capture_output=True)
r1, r2, r3, r4 = run(["status"]), run(["log"]), run(["a&b", "%PATH%"]), run(["other"])
print(json.dumps([{"title": "|".join([
    r1.stdout.decode("utf-8").strip(),
    r2.stdout.decode("utf-8").strip(),
    r3.stdout.decode("utf-8").strip(),
    r4.stdout.decode("utf-8").strip(),
    str(r2.returncode),
]), "subtitle": "by"}]))
`;
	const d = tinyApp(script, [
		{
			name: 'by_args',
			os: osName,
			stubs: {
				mytool: {
					stdout: 'default',
					by_args: [
						{ args: ['status'], stdout: 'clean' },
						{ args: ['log'], stdout: 'two', rc: 3 },
						{ args: ['a&b', '%PATH%'], stdout: 'meta-ok' },
					],
				},
			},
			expect: { text_present: ['clean|two|meta-ok|default|3'] },
		},
	]);
	const r = await checkApp(d);
	assert.ok(r.cases[0].ok, JSON.stringify(r.cases[0].findings));

	// Use bolt_app_kit.run() so POSIX process groups (#!/bin/sh -> /bin/sleep 60) and Windows stubs are both killed cleanly on timeout.
	const hangScript = `import json, os, time
import wintiny__bolt_app_kit as kit
stubdir = os.environ["PATH"].split(os.pathsep)[0]
t0 = time.monotonic()
res = kit.run(["slow"], timeout=1.0, dirs=[stubdir])
dt = time.monotonic() - t0
ok = res.timed_out and (0.5 <= dt < 8)
print(json.dumps([{"title": "hung-ok" if ok else "hung-bad", "subtitle": str(dt)}]))
`;
	const dh = tinyApp(hangScript, [{ name: 'hang', os: osName, hang: ['slow'], expect: { text_present: ['hung-ok'], max_seconds: 10 } }]);
	const rh = await checkApp(dh);
	assert.ok(rh.cases[0].ok, JSON.stringify(rh.cases[0].findings));

	const hex = Buffer.from(HOSTILE, 'utf8').toString('hex');
	const hostileScript = `import os, json, subprocess
stubdir = os.environ["PATH"].split(os.pathsep)[0]
ext = ".cmd" if os.path.isfile(os.path.join(stubdir, "mytool.cmd")) else ""
stub = os.path.join(stubdir, "mytool" + ext)
r = subprocess.run([stub], capture_output=True)
print(json.dumps([{"title": r.stdout.hex(), "subtitle": "h"}]))
`;
	const df = tinyApp(hostileScript, [{ name: 'hostile', os: osName, hostile: true, stubs: { mytool: { stdout: '@@HOSTILE@@' } }, expect: { text_present: [hex] } }]);
	const rf = await checkApp(df);
	assert.ok(rf.cases[0].ok, JSON.stringify(rf.cases[0].findings));
});

test('home_absent: expanduser(~) stays inside the temp home (USERPROFILE equals HOME on Windows)', async () => {
	const osName = hostOs() === 'other' ? 'linux' : hostOs();
	const leak = `import os, json
p = os.path.join(os.path.expanduser("~"), "leaked.txt")
with open(p, "w", encoding="utf-8") as f:
    f.write("SECRET-LEAK-VALUE-42")
same = True if os.name != "nt" else os.environ.get("USERPROFILE") == os.environ.get("HOME")
print(json.dumps([{"title": "ok", "subtitle": "same" if same else "USERPROFILE-mismatch"}]))
`;
	const d = tinyApp(leak, [{ name: 'leak', os: osName, expect: { text_present: ['same'], home_absent: ['SECRET-LEAK-VALUE-42'] } }]);
	const r = await checkApp(d);
	assert.ok(!codes(r.cases[0].findings).includes('expected_text_missing'), JSON.stringify(r.cases[0].findings));
	assert.ok(codes(r.cases[0].findings).includes('text_on_disk'), JSON.stringify(r.cases[0].findings));
	assert.equal(r.cases[0].findings.find((x) => x.code === 'text_on_disk').message.includes('SECRET-LEAK-VALUE-42'), true);
});

test('check stubs: stub file outside the app folder is refused', async () => {
	const osName = hostOs() === 'other' ? 'linux' : hostOs();
	const d = tinyApp('print("[]")', [{ name: 'escape', os: osName, stubs: { mytool: { file: '../outside.txt' } } }]);
	fs.writeFileSync(path.join(path.dirname(d), 'outside.txt'), 'secret');
	const r = await checkApp(d);
	assert.ok(codes(r.cases[0].findings).includes('check_error'), JSON.stringify(r.cases[0].findings));
	assert.match(r.cases[0].findings.find((x) => x.code === 'check_error').message, /points outside the app folder/);
});
