import base64, os, struct, sys, unittest, zlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bolt_app_kit as k


def png(w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class HeroTests(unittest.TestCase):
    def test_png_bytes_split_and_rejoin(self):
        raw = png(40, 20, (10, 120, 200))
        f = k.hero_fields(raw)
        self.assertEqual(list(f), ["img%d" % (i + 1) for i in range(len(f))])
        self.assertTrue(all(0 < len(v) <= 4000 for v in f.values()))
        uri = "".join(f.values())
        self.assertTrue(uri.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), raw)

    def test_data_uri_input_equals_bytes_input(self):
        raw = png(8, 8, (1, 2, 3))
        uri = "data:image/png;base64," + base64.b64encode(raw).decode()
        self.assertEqual(k.hero_fields(uri), k.hero_fields(raw))

    def test_jpeg_gif_webp_accepted(self):
        for blob, mime in ((b"\xff\xd8\xff\xe0" + b"x" * 20, "jpeg"), (b"GIF89a" + b"x" * 20, "gif"), (b"RIFF\0\0\0\0WEBPVP8 " + b"x" * 10, "webp")):
            self.assertIn("data:image/%s;base64," % mime, k.hero_fields(blob)["img1"])

    def test_over_one_mib_refused(self):
        with self.assertRaisesRegex(k.KitError, "1 MiB"):
            k.hero_fields(b"\xff\xd8\xff" + b"0" * (1 << 20))
        big = "data:image/png;base64," + "A" * (1 << 21)
        with self.assertRaisesRegex(k.KitError, "1 MiB"):
            k.hero_fields(big)

    def test_more_than_sixteen_parts_refused_with_advice(self):
        ok = b"\xff\xd8\xff" + os.urandom(47000)
        self.assertEqual(len(k.hero_fields(ok)), 16)
        with self.assertRaisesRegex(k.KitError, "smaller picture"):
            k.hero_fields(b"\xff\xd8\xff" + os.urandom(48200))

    def test_max_parts_lower_cap(self):
        with self.assertRaises(k.KitError):
            k.hero_fields(b"\xff\xd8\xff" + os.urandom(9000), max_parts=2)
        with self.assertRaises(k.KitError):
            k.hero_fields(b"\xff\xd8\xff", max_parts=17)

    def test_bad_input_refused(self):
        for bad in (b"", b"not a picture", "https://example.com/a.png", "data:text/plain;base64,AAAA", "data:image/png;base64,@@@", 5, None):
            with self.assertRaises(k.KitError):
                k.hero_fields(bad)

    def test_template(self):
        self.assertEqual(k.hero_src_template(3), "{{row.img1}}{{row.img2}}{{row.img3}}")
        self.assertEqual(k.hero_src_template(16).count("{{"), 16)
        for bad in (0, 17, True, "2"):
            with self.assertRaises(k.KitError):
                k.hero_src_template(bad)

    def test_fields_pass_row_validation(self):
        r = k.row("A picture", "x", icon="Image", **k.hero_fields(png(8, 8, (9, 9, 9))))
        self.assertIn("img1", r)


if __name__ == "__main__":
    unittest.main()
