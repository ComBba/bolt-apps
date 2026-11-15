"""Where an app finds its API key, and how it keeps the key out of everything else. Standard library only.

Lookup order (first hit wins):
  1. an environment variable (only reaches the script from a terminal or a test: Bolt starts a personal app's script
     with an empty environment and refuses to forward names that contain TOKEN, KEY, SECRET, PASS, AUTH and the like)
  2. the system keychain, through the system's own tool (macOS security, Linux secret-tool)
  3. a .env file at ~/.config/<app-id>/.env, readable by its owner only (never inside the app folder or a pack)

The key is returned to the caller and nowhere else: it is never printed, cached or put in a row. Use redact() on any
text that could carry it (an error message, a URL) before it is shown."""
import base64
import os
import re
import stat
import urllib.parse

from .probe import os_name, run

SERVICE_PREFIX = "bolt-app-"
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_APP = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")
# Both patterns are bounded so a hostile answer cannot make them slow: the scheme is anchored (it cannot start in the middle of a run of scheme
# characters) and at most 32 long, and the name runs around a credential word at most 40 each. Nothing caps a value or a user part: a cap that is
# exceeded must hide more, never less.
_SCHEME = re.compile(r"(?i)(?<![A-Za-z0-9+.-])[a-z][a-z0-9+.-]{0,31}://")
_AUTH_END = re.compile(r"[/?#\s]")
_QUERY_KEY = re.compile(r"(?i)([?&](?:[a-z_-]{0,40}(?:key|token|secret|pass(?:word)?|auth|sig(?:nature)?)[a-z_-]{0,40})=)[^&\s#]{1,2000}")
MIN_REDACT = 3


class Secret(object):
    """value is None when nothing was found. source is env, keychain or file. problem is a plain-words reason
    (for example the file is readable by others) when something was found but refused."""
    __slots__ = ("value", "source", "problem")

    def __init__(self, value=None, source="", problem=""):
        self.value, self.source, self.problem = value, source, problem

    def __bool__(self):
        return self.value is not None

    def __repr__(self):   # a Secret is never printed with its value
        return "Secret(source=%r, found=%r, problem=%r)" % (self.source, self.value is not None, self.problem)


def env_file_path(app_id):
    return os.path.join(os.path.expanduser("~"), ".config", app_id, ".env")


def _parse_value(raw):
    v = raw.strip()
    if v[:1] in ("'", '"'):
        end = v.find(v[0], 1)
        return v[1:end] if end > 0 else v[1:]
    return re.split(r"\s+#", v, 1)[0].strip()   # an unquoted value ends at a trailing comment


def _from_file(app_id, name, path=None):
    p = path or env_file_path(app_id)
    try:
        lst = os.lstat(p)
        if stat.S_ISLNK(lst.st_mode):
            return Secret(problem="%s is a link, which is not followed" % p)
        if not stat.S_ISREG(lst.st_mode):
            return Secret()
        if hasattr(os, "getuid") and lst.st_uid != os.getuid():
            return Secret(problem="%s is not owned by you" % p)
        if hasattr(os, "getuid") and lst.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            return Secret(problem="%s can be read by other users" % p)
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].lstrip()
                if line.startswith(name + "="):
                    v = _parse_value(line.split("=", 1)[1])
                    if v:
                        return Secret(v, "file")
    except (OSError, UnicodeDecodeError):
        pass
    return Secret()


def _from_keychain(app_id, name, tool_dirs=None, os_=None):
    osn = os_ or os_name()
    service = SERVICE_PREFIX + app_id
    if osn == "macos":
        cmd = ["security", "find-generic-password", "-s", service, "-a", name, "-w"]
        dirs = tool_dirs if tool_dirs is not None else ["/usr/bin"]
    elif osn == "linux":
        cmd = ["secret-tool", "lookup", "service", service, "account", name]
        dirs = tool_dirs
    else:
        return Secret()   # Windows: no keychain reader here; use the .env file
    r = run(cmd, timeout=5, dirs=dirs, os_=osn)
    v = r.out.strip() if r.ok else ""
    return Secret(v, "keychain") if v else Secret()


def _get_secret(app_id, name, env_names=(), env_file=None, tool_dirs=None, os_=None):
    """Find the key called `name` for app `app_id`. See the module text for the order."""
    if not _APP.match(app_id or "") or not _NAME.match(name or ""):
        raise ValueError("app id is lowercase letters, digits and hyphens; the key name is a plain identifier")
    for n in (name,) + tuple(env_names):
        v = os.environ.get(n, "").strip()
        if v:
            return Secret(v, "env")
    k = _from_keychain(app_id, name, tool_dirs, os_)
    if k:
        return k
    f = _from_file(app_id, name, env_file)
    return f if (f or f.problem) else Secret()


def get_secret(app_id, name, env_names=(), env_file=None, tool_dirs=None, os_=None):
    """Find the key called `name` for app `app_id`. See the module text for the order. A key shorter than MIN_REDACT characters is refused
    (problem set, no value): it cannot be hidden from an API answer, so it is not a key worth using."""
    s = _get_secret(app_id, name, env_names, env_file, tool_dirs, os_)
    if s and len(s.value) < MIN_REDACT:
        return Secret(problem="the key %s is shorter than %d characters, so it cannot be hidden from API answers; use a real key" % (name, MIN_REDACT))
    return s


def setup_hint(app_id, name, os_=None):
    """The one-line setup a person can paste, for an error row when the key is missing. Never contains a key."""
    osn = os_ or os_name()
    path = "~/.config/%s/.env" % app_id
    file_cmd = "mkdir -p ~/.config/%s && (umask 077; printf '%s=' >> %s)" % (app_id, name, path)   # a subshell: the umask of your terminal is left alone
    if osn == "macos":
        return "In Terminal: security add-generic-password -s %s%s -a %s -w   (it asks for the key). Or: %s then paste the key after the = sign" % (SERVICE_PREFIX, app_id, name, file_cmd)
    if osn == "linux":
        return "In a terminal: secret-tool store --label=%s service %s%s account %s   (it asks for the key). Or: %s then paste the key after the = sign" % (app_id, SERVICE_PREFIX, app_id, name, file_cmd)
    return "Put %s=<your key> in %s (only you may read it)" % (name, path)


def _forms(v):
    """Every way a key is likely to appear in an answer: as it is, URL-encoded (upper or lower case %xx), hex (either case), in any letter case,
    and base64 (standard and URL-safe, with and without padding). Remaining limits, said plainly: a key split across lines; base64 of a longer string
    (such as HTTP Basic "user:key") that holds the key at another alignment; HTML entities (&#x61;); colon-separated hex; a key stored as a JSON number;
    and a value encoded twice. A key under MIN_REDACT characters is refused by get_secret as invalid."""
    ci = {v, urllib.parse.quote(v, safe=""), urllib.parse.quote_plus(v), urllib.parse.quote(v), v.encode("utf-8").hex()}   # matched in any letter case
    exact = set()
    for enc in (base64.b64encode, base64.urlsafe_b64encode):
        b = enc(v.encode("utf-8")).decode("ascii")
        exact.add(b)
        exact.add(b.rstrip("="))
    return sorted((x for x in ci if len(x) >= MIN_REDACT), key=len, reverse=True), sorted((x for x in exact if len(x) >= MIN_REDACT), key=len, reverse=True)


def _hide_userinfo(t):
    """Hide the user:password part of every scheme://user:password@host in t. A string scan, not a pattern: the authority runs to the first / ? # or
    whitespace, and everything before the LAST @ in it is hidden, however long it is or how many @ it holds."""
    out, pos = [], 0
    for m in _SCHEME.finditer(t):
        if m.start() < pos:
            continue
        a = m.end()
        e = _AUTH_END.search(t, a)
        e = e.start() if e else len(t)
        at = t.rfind("@", a, e)
        if at >= 0:
            out.append(t[pos:a]); out.append("[hidden]"); pos = at
    out.append(t[pos:])
    return "".join(out)


def redact(text, secrets=(), limit=None):
    """Text that is safe to show: each secret value (in the forms _forms lists), any user:password@ in a web address, and key-like query values
    (?api_key=..., ?token=...) are replaced. `secrets` is a list of values or Secret objects. This is the looser pattern, meant for error text."""
    t = str(text)
    for s in secrets:
        v = s.value if isinstance(s, Secret) else s
        if isinstance(v, str) and len(v) >= MIN_REDACT:
            ci, exact = _forms(v)
            t = re.sub("|".join(re.escape(f) for f in ci), "[hidden]", t, flags=re.I)
            for form in exact:
                t = t.replace(form, "[hidden]")
    t = _hide_userinfo(t)
    t = _QUERY_KEY.sub(r"\1[hidden]", t)
    return t if limit is None else t[:limit]


# Which query parameters carry a credential. A name is split into segments on _ - and . and compared case-folded: it is redacted when any
# segment is a credential word (client_secret, session_key, access_key_id, x_api_token, refresh_token, id_token, X-Amz-Signature, sig, credential),
# or the name holds "apikey". Whole names that only look like credentials are excluded on purpose.
# Tradeoff, recorded: matching by segment catches the many spellings real APIs use, at the price of a few false positives (a plain "key" or
# "token" parameter that was not a secret is hidden). The explicit exclude list below removes the common benign names (keyword, monkey, author,
# page and cursor tokens, sort and database keys); add to it when a real API shows another. Hiding too much costs a field in one link; hiding
# too little leaks a key, so the rule errs toward hiding.
_CRED_SEGMENTS = frozenset(("key", "token", "secret", "pass", "password", "passwd", "pwd", "auth", "authorization", "sig", "signature", "credential",
                            "credentials", "session", "cookie", "bearer", "apikey", "access"))
_BENIGN_NAMES = frozenset(("keyword", "keywords", "monkey", "author", "authors", "next_page_token", "page_token", "nextpagetoken", "pagetoken", "next_token",
                           "cursor", "sort_key", "order_key", "primary_key", "foreign_key", "key_id", "session_count", "access_count", "pass_count"))
# The value stops at every delimiter (? & ; # and whitespace and quotes), so a credential parameter inside a nested address (?next=https://h/p?token=X),
# after a fragment (#access_token=X) or double-encoded (%3Ftoken%3DX) is found on its own: the scan restarts at each delimiter.
_PARAM = re.compile(r"([?&;#])([A-Za-z0-9_.\-]{1,64})=([^&;?#\s\"']+)")
_PARAM_ENC = re.compile(r"(%3[Ff]|%26|%3[Bb]|%23)([A-Za-z0-9_.\-]{1,64})(%3[Dd])((?:(?!%26|%3[Ff]|%3[Bb]|%23|&|;|\?|#)[^\s\"'])+)")


def _is_cred(raw, extra=frozenset()):
    """Does the parameter NAME carry a credential? Decided from the name alone: no value is parsed, so an `=` in a value cannot confuse it."""
    name = raw.lower()
    if name in extra:
        return True
    if name in _BENIGN_NAMES:
        return False
    return "apikey" in name or any(seg in _CRED_SEGMENTS for seg in re.split(r"[_.\-]", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw).lower()))


def _param_sub(extra):
    def one(m):
        return "%s%s=[hidden]" % (m.group(1), m.group(2)) if _is_cred(m.group(2), extra) else m.group(0)

    def enc(m):
        # the whole rest of an encoded value (up to the next encoded delimiter) is the credential, including any = or %3D padding inside it
        return "%s%s%s[hidden]" % (m.group(1), m.group(2), m.group(3)) if _is_cred(m.group(2), extra) else m.group(0)
    one.enc = enc
    return one


def redact_tree(value, secrets=(), auth_param=None, depth=0):
    """A copy of parsed JSON with every string cleaned of the secrets. APIs echo the key they were sent (in links such as ...&api_key=DEMO_KEY, in an
    error message, in a request echo), so call this on the whole answer BEFORE it is cached, logged or shown.

    Cost: the forms of each secret are computed once; a string that holds none of them and has no query string or address in it is returned as it is
    (so a 5 MB body is one pass of substring tests). Only the literal secret, its encoded forms, the configured `auth_param` and a short list of
    well-known credential parameter names (whole names: keyword, monkey and next_page_token stay) are replaced. Walks with a stack, depth 40. Not unwrapped, and said plainly: a credential parameter inside a value that is URL-encoded twice (%253F) and one that only an unknown name marks."""
    vals = [x.value if isinstance(x, Secret) else x for x in secrets]
    ci_forms, exact_forms = set(), set()
    for v in vals:
        if isinstance(v, str) and len(v) >= MIN_REDACT:
            c, e = _forms(v)
            ci_forms.update(c); exact_forms.update(e)
    ci_rx = re.compile("|".join(re.escape(f) for f in sorted(ci_forms, key=len, reverse=True)), re.I) if ci_forms else None
    exact_forms = sorted(exact_forms, key=len, reverse=True)
    sub = _param_sub(frozenset([auth_param.lower()]) if auth_param else frozenset())

    def clean(t):
        if ci_rx is not None:
            t = ci_rx.sub("[hidden]", t)
        for f in exact_forms:
            if f in t:
                t = t.replace(f, "[hidden]")
        if "=" in t and ("?" in t or "&" in t or ";" in t or "#" in t):
            t = _PARAM.sub(sub, t)
        if "%3" in t or "%2" in t:
            t = _PARAM_ENC.sub(sub.enc, t)
        if "://" in t and "@" in t:
            t = _hide_userinfo(t)
        return t

    def walk(node, d):
        if d > 40:
            return None
        if isinstance(node, str):
            return clean(node)
        if isinstance(node, list):
            return [walk(x, d + 1) for x in node]
        if isinstance(node, dict):
            return dict((clean(str(k)), walk(x, d + 1)) for k, x in node.items())
        return node
    return walk(value, depth)
