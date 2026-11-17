"""Hero picture rows (Bolt 182 and later): turn one small picture into the row fields an entity_preview `hero` reads.

A Bolt pane never loads a web address, so the picture travels inside the row as an inline data: image. A row text field is cut at
4,000 characters, so the base64 text is split over img1, img2, ... and the app file joins them back:

    hero:
      src: "{{row.img1}}{{row.img2}}...{{row.imgN}}"

Limits (from the Bolt 182 pane): at most 16 `{{` references in the src template, so at most 16 parts (about 47 KB of picture); at most 1 MiB per
image; png, jpeg, gif or webp (Bolt also takes avif and bmp: the stdlib cannot sniff or resize them, so this helper refuses avif and bmp BYTES; pass a data:image/avif;base64,... string instead and it is trusted and split as it is). The stdlib cannot resize a picture, so hand this an already small one. A picture that needs more than 16 parts
is refused with a message that says so: use a smaller picture (fewer pixels or a higher JPEG compression). Bolt 0.1.181 refuses a whole pack
that uses `hero`: mark the app as needing Bolt 182 (see ENGINE.md, "Hero picture (Bolt 182)")."""
import base64

from .rows import KitError

HERO_MAX_BYTES = 1 << 20     # Bolt 182: 1 MiB per inline image
HERO_MAX_PARTS = 16          # Bolt 182: at most 16 {{ }} references in the hero src template
FIELD_CHARS = 4000           # a row text field is cut here
_TYPES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))


_DECLARED = ("png", "jpeg", "jpg", "gif", "webp", "avif", "bmp")   # the mime types a Bolt pane takes


def _mime(raw):
    for magic, mime in _TYPES:
        if raw.startswith(magic):
            return mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def hero_src_template(parts, prefix="img"):
    """The hero `src` template for `parts` fields: "{{row.img1}}{{row.img2}}...". Put it in the app file under bind.hero.src."""
    if not isinstance(parts, int) or isinstance(parts, bool) or not 1 <= parts <= HERO_MAX_PARTS:
        raise KitError("parts must be a whole number from 1 to %d (the hero src may hold at most %d references)" % (HERO_MAX_PARTS, HERO_MAX_PARTS))
    return "".join("{{row.%s%d}}" % (prefix, i + 1) for i in range(parts))


def hero_fields(image, prefix="img", max_parts=HERO_MAX_PARTS):
    """Row fields {prefix1: ..., prefix2: ...} holding the picture as a data: URI, split into pieces of at most 4,000 characters.

    `image` is the picture's bytes (png, jpeg, gif or webp) or a data:image/(png|jpeg|jpg|gif|webp|avif|bmp);base64, string. Raises KitError for a picture that is not one of those,
    is over 1 MiB, or needs more than `max_parts` (at most 16) pieces; the message says what to do. A bad picture is an error, never a silent {}: the
    caller decides whether the row goes without a hero (catch KitError and emit the row without the fields)."""
    if not isinstance(max_parts, int) or isinstance(max_parts, bool) or not 1 <= max_parts <= HERO_MAX_PARTS:
        raise KitError("max_parts must be a whole number from 1 to %d" % HERO_MAX_PARTS)
    if isinstance(image, str):
        head, sep, b64 = image.partition(",")
        declared = head[len("data:image/"):-len(";base64")].lower() if head.lower().startswith("data:image/") and head.lower().endswith(";base64") else ""
        if not sep or declared not in _DECLARED:
            raise KitError("hero picture must be image bytes or a data:image/<png|jpeg|gif|webp|avif|bmp>;base64, string; a web address is never loaded by a Bolt pane")
        if len(b64) > (HERO_MAX_BYTES * 4) // 3 + 8:
            raise KitError("hero picture is over 1 MiB; use a smaller picture")
        try:
            raw = base64.b64decode(b64, validate=True)
        except ValueError:
            raise KitError("hero picture is not valid base64")
    elif isinstance(image, (bytes, bytearray, memoryview)):
        raw = bytes(image)
    else:
        raise KitError("hero picture must be bytes or a data: URI string, got %s" % type(image).__name__)
    if not raw:
        raise KitError("hero picture is empty")
    if len(raw) > HERO_MAX_BYTES:
        raise KitError("hero picture is %d bytes; Bolt takes at most 1 MiB, and a row carries far less (see max_parts). Use a smaller picture" % len(raw))
    mime = ("image/" + ("jpeg" if declared == "jpg" else declared)) if isinstance(image, str) else _mime(raw)   # a data URI is trusted for avif and bmp, which the stdlib cannot sniff; Bolt checks the picture itself
    if mime is None:
        raise KitError("hero picture must be png, jpeg, gif or webp (checked from its first bytes)")
    uri = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))
    n = -(-len(uri) // FIELD_CHARS)
    if n > max_parts:
        raise KitError("hero picture needs %d parts of %d characters but at most %d are allowed (the hero src holds at most %d references, about %d KB of picture). "
                       "Use a smaller picture: fewer pixels or stronger compression" % (n, FIELD_CHARS, max_parts, HERO_MAX_PARTS, (max_parts * FIELD_CHARS - 40) * 3 // 4 // 1000))
    return dict(("%s%d" % (prefix, i + 1), uri[i * FIELD_CHARS:(i + 1) * FIELD_CHARS]) for i in range(n))
