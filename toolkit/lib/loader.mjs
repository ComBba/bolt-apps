// The one source of the Python loader block every kit-built script carries (Bolt 182, shared kit).
//
// Each script keeps its own header lines (`_sys.dont_write_bytecode`, `_SELF`, `_PFX`) and then this block, which
// ends in the name `kit`. Order of preference, decided here and nowhere else:
//   1. the kit module already imported (the test suite does this; a normal run never has);
//   2. Bolt's shared kit, ONLY when Bolt offered it (env BOLT_APP_SHARED_DIR) and every one of these holds:
//        - the folder's manifest.json is format 1 and its kit entry has the api this loader knows (KIT_API),
//        - the kit file named there is a plain file whose SHA-256 equals the manifest's (read once; the bytes that
//          were hashed are the bytes that run),
//        - its __version__ equals the manifest's,
//        - and either the app's own vendored kit has the very same bytes, or the app says WANT_SHARED = True and the
//          shared version is at least KIT_MIN;
//   3. the app's own vendored kit beside the script, <id>__bolt_app_kit.py (what every app did before Bolt 182);
//   4. a bolt_app_kit package folder beside the script (old apps).
// Any failure in step 2 is silent (a Ctrl-C is not a failure: it stops the app) and falls through: the rows must not depend on which copy ran.
// A manifest cannot set BOLT_APP_SHARED_DIR (names starting BOLT_ are refused), so only Bolt chooses the folder.
export const LOADER_VERSION = 1;

export const LOADER_PORTABLE = String.raw`import importlib.util as _ilu
KIT_API = 1   # the kit interface this app was written for; Bolt's shared kit must offer the same
KIT_MIN = (0, 3, 10)   # with WANT_SHARED: the oldest shared kit this app accepts
WANT_SHARED = False   # True: prefer Bolt's shared kit (when it verifies and is new enough) over this app's own copy
_KIT_DIR = _os.path.dirname(_os.path.abspath(__file__))


def _load_kit_bytes(data, origin):
    import types
    mod = types.ModuleType("bolt_app_kit")
    mod.__file__ = origin
    _sys.modules["bolt_app_kit"] = mod
    try:
        exec(compile(data, origin, "exec"), mod.__dict__)
    except BaseException:
        _sys.modules.pop("bolt_app_kit", None)
        raise
    return mod


def _abs_dir(d, nt=_os.name == "nt"):
    """An absolute local folder. On Windows that means a drive letter and a root: a rooted path with no drive (it would follow the current drive) and a network share are refused."""
    if nt:
        import ntpath
        return bool(ntpath.splitdrive(d)[0]) and d[:1] not in "\\/" and ntpath.isabs(d)
    return _os.path.isabs(d)


def _shared_kit(own_path):
    """Bolt's shared kit, verified, or None. Never raises: any doubt means use the app's own copy (a real Ctrl-C still stops the app)."""
    d = _os.environ.get("BOLT_APP_SHARED_DIR")
    if not d or not _abs_dir(d):
        return None
    try:
        import hashlib, json
        def plain(p):
            return _os.path.isfile(p) and not _os.path.islink(p) and _os.path.getsize(p) <= 8 * 1024 * 1024
        mp = _os.path.join(d, "manifest.json")
        if not plain(mp):
            return None
        with open(mp, "rb") as f:
            m = json.loads(f.read().decode("utf-8"))
        k = m["kit"]
        name, want, ver = k["file"], k["sha256"], k["version"]
        if m.get("format") != 1 or k.get("api") != KIT_API or name != _os.path.basename(name) or not name.endswith(".py"):
            return None
        sp = _os.path.join(d, name)
        if not plain(sp):
            return None
        with open(sp, "rb") as f:
            data = f.read()
        have = hashlib.sha256(data).hexdigest()
        if have != want:
            return None
        same = False
        if _os.path.isfile(own_path):
            with open(own_path, "rb") as f:
                same = hashlib.sha256(f.read()).hexdigest() == have
        if not same and not (WANT_SHARED and tuple(int(x) for x in ver.split(".")) >= KIT_MIN):
            return None
        if not data.startswith(('"""bolt_app_kit %s, ' % ver).encode("utf-8")):
            return None   # the file does not say it is the version the manifest names: do not run it
        mod = _load_kit_bytes(data, sp)
        if getattr(mod, "__version__", None) != ver:
            _sys.modules.pop("bolt_app_kit", None)
            return None
        return mod
    except KeyboardInterrupt:
        raise   # the person pressed Ctrl-C: stop, do not carry on with another copy
    except BaseException:   # including SystemExit raised by the kit at import: the app's own copy still runs
        _sys.modules.pop("bolt_app_kit", None)
        return None


_own_kit = _os.path.join(_KIT_DIR, _PFX + "bolt_app_kit.py")   # the kit sits beside the script under this app's own name (python -I drops the script folder from the path, so it is loaded by path)
kit = _sys.modules.get("bolt_app_kit")   # already imported: the test suite does this; a normal run never has
if kit is None:
    kit = _shared_kit(_own_kit)
if kit is None and _os.path.exists(_own_kit):
    _spec = _ilu.spec_from_file_location("bolt_app_kit", _own_kit)
    kit = _ilu.module_from_spec(_spec)
    _sys.modules["bolt_app_kit"] = kit
    _spec.loader.exec_module(kit)
elif kit is None and _os.path.isdir(_os.path.join(_KIT_DIR, "bolt_app_kit")):   # a bolt_app_kit package folder beside the script
    _sys.path.insert(0, _KIT_DIR)
    import bolt_app_kit as kit
elif kit is None:
    raise SystemExit("script files must be named <app id>__<name>: this one is %s and %s was not found beside it. Rename the files back, and do not run the script through a link." % (_SELF, _PFX + "bolt_app_kit.py"))
`;

// The block a script carried before 182: from its `import importlib.util as _ilu` line through the SystemExit that ends the chain.
const LEGACY = /^import importlib\.util as _ilu\n[\s\S]*?^elif kit is None:\n    raise SystemExit\([^\n]*\)\n/m;
export const hasLoader = (src) => src.includes(LOADER_PORTABLE);
export const hasLegacyLoader = (src) => LEGACY.test(src);
// A script's loader block, rewritten to this toolkit's. Returns the source unchanged when it has no known block.
export function applyLoader(src) {
	if (hasLoader(src)) return src;
	return LEGACY.test(src) ? src.replace(LEGACY, () => LOADER_PORTABLE) : src;
}
