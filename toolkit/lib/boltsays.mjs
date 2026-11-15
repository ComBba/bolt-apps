// "Bolt said X, do Y": every refusal Bolt's installer and loader can give a personal pack, with the fix in plain words. Read from the installer's own
// messages (pack install and pack check); `code` is the short failure code Bolt logs and shows for support. A test keeps this table and docs/QUICKSTART.md equal.
export const BOLT_SAYS = [
	['same_or_older_version', 'version X is already installed, and a pack is only replaced by a newer version', 'Run bolt-apps ship again: it picks a higher version by itself. If you passed --version, use a higher number than the one installed.'],
	['version_unreadable', 'it cannot tell whether this is newer than the installed version', 'A version is numbers with dots, such as 1.0.5. Run bolt-apps ship without --version.'],
	['owned_by_other', 'a script file already belongs to another app', 'Two apps use the same script file name. Rebuild with the current bolt-apps: every file is named <app id>__<name>. Or remove the other app first.'],
	['file_exists', 'a file is already there and no pack installed it', 'A file with that name in your scripts folder was added by hand or came with Bolt. Open it (Settings, Desktop, User Apps, Open folder) and delete it, or rename yours.'],
	['file_and_folder', 'a name is both a file and a folder', 'Rename the file or the folder inside scripts/ so one name is not both.'],
	['case_collision', 'two names differ only in letter case', 'Rename one of the two files: macOS and Windows treat them as one file.'],
	['too_deep', 'a script is nested more than 8 folders deep', 'Keep scripts flat, directly in scripts/ (bolt-apps new does this).'],
	['unsafe_path', 'a script path is not safe', 'Remove . or .. or odd characters from the script name; use letters, digits, . _ and -.'],
	['in_the_way', 'a script cannot be placed because something else is in its way in your scripts folder', 'Open your folder (Settings, Desktop, User Apps, Open folder) and remove the file, folder or link that has the same name.'],
	['scripts_is_a_file', 'a file named scripts is in your user apps folder', 'Move that file away from your user apps folder, then drop the pack again.'],
	['write_failed', 'it could not write a file', 'Free some disk space or check you can write to your Bolt folder, then drop the pack again.'],
	['ledger_unreadable', 'its list of installed packs could not be read', 'Do not delete anything. Ask for help with the file .boltpack-installs.json in your user apps folder.'],
	['signature_recheck', 'it could not confirm the pack\'s signature a second time', 'Build the pack again with bolt-apps ship and drop the new file; do not copy a pack between folders while Bolt reads it.'],
	['unverified', 'a file does not match the pack\'s signed listing / pack rejected', 'The pack was changed or damaged after signing. Run bolt-apps ship again and drop the new file; never edit a .boltpack.'],
	['outside_pack', 'it lists a file outside the pack', 'Build the pack with bolt-apps ship, not by hand.'],
	['cancelled', 'Install cancelled: the pack is signed by its author, not by a key built into Bolt', 'You chose Cancel, or did not approve the second prompt. Drop the pack again and approve both prompts if you trust the app.'],
	['org_policy', 'Your organization\'s policy on this device installs only packs signed with a key built into Bolt', 'A company policy blocks personal apps on this computer. Nothing is wrong with the app; ask your admin, or use a computer without that policy.'],
	['not_loaded_changed', 'Not loaded: this app\'s files do not match the signed pack Bolt recorded for it', 'A script was edited after install. Run bolt-apps ship again and drop the new pack; it replaces the changed files.'],
	['scripts_direct', 'this app\'s command names a file in Bolt\'s scripts folder directly', 'Write every script as {{scripts_dir}}/<app id>__<file> in the app file, never a full path. bolt-apps lint --personal shows the line.'],
	['cannot_check', 'the app names its scripts in a form Bolt cannot resolve to one file each / is missing / is a link / is too large to check', 'Name each script once as {{scripts_dir}}/<app id>__<file>, keep each under 2 MB, no links, and make sure the file is in scripts/. bolt-apps verify names the file.'],
	['pack_too_big', 'pack rejected: it unpacks to more than 64 MB / holds more than 1024 files / the file is over 50 MB', 'An app is small text and scripts. Remove big files from the app folder.'],
	['pack_unreadable', 'pack rejected: the archive cannot be read', 'The file is not a .boltpack or is damaged. Run bolt-apps ship again and drop the new file.'],
	['not_valid_app', 'pack rejected: a file is not a valid app', 'Run bolt-apps verify on the app folder: it names the line in the app file to fix.'],
];
export function formatBoltSays(only) {
	const rows = only ? BOLT_SAYS.filter((r) => only.includes(r[0])) : BOLT_SAYS;
	return rows.map(([code, said, fix]) => `  Bolt says "${said}" (${code})\n      do: ${fix}`).join('\n');
}
export const markdownTable = () => ['| Bolt says | Code | What to do |', '|---|---|---|', ...BOLT_SAYS.map(([c, s, f]) => `| ${s.replace(/\|/g, '/')} | \`${c}\` | ${f.replace(/\|/g, '/')} |`)].join('\n');
