import io
import struct
import unittest
import zipfile

from apk_calistirici import apk

TUR_TAMSAYI = 0x10


def _dizgi_havuzu(dizgiler, utf8):
    veri = b""
    konumlar = []
    for d in dizgiler:
        konumlar.append(len(veri))
        if utf8:
            b = d.encode("utf-8")
            veri += bytes([len(d), len(b)]) + b + b"\0"
        else:
            veri += struct.pack("<H", len(d)) + d.encode("utf-16-le") + b"\0\0"
    veri += b"\0" * (-len(veri) % 4)
    baslik = 28
    dizgi_basi = baslik + 4 * len(dizgiler)
    boyut = dizgi_basi + len(veri)
    return (
        struct.pack("<HHIIIIII", 1, baslik, boyut, len(dizgiler), 0, 0x100 if utf8 else 0, dizgi_basi, 0)
        + struct.pack(f"<{len(dizgiler)}I", *konumlar)
        + veri
    )


def _eleman(ad, oznitelikler):
    govde = struct.pack("<IIHHHHHH", 0xFFFFFFFF, ad, 20, 20, len(oznitelikler), 0, 0, 0)
    for ad_no, ham, tur, deger in oznitelikler:
        govde += struct.pack("<IIIHBBI", 0xFFFFFFFF, ad_no, ham, 8, 0, tur, deger)
    return struct.pack("<HHIII", 0x0102, 16, 16 + len(govde), 1, 0xFFFFFFFF) + govde


def ornek_manifest(utf8=False):
    dizgiler = ["", "", "package", "manifest", "com.ornek.uygulama", "1.2", "application", "uses-sdk", ""]
    kaynaklar = [0x0101021B, 0x0101021C, 0, 0, 0, 0, 0, 0, 0x0101020C]
    govde = _dizgi_havuzu(dizgiler, utf8)
    govde += struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(kaynaklar)) + struct.pack(f"<{len(kaynaklar)}I", *kaynaklar)
    govde += _eleman(3, [
        (0, 0xFFFFFFFF, TUR_TAMSAYI, 42),
        (1, 5, apk.TUR_STRING, 5),
        (2, 4, apk.TUR_STRING, 4),
    ])
    govde += _eleman(7, [(8, 0xFFFFFFFF, TUR_TAMSAYI, 24)])
    govde += _eleman(6, [])
    return struct.pack("<HHI", 0x0003, 8, 8 + len(govde)) + govde


class ManifestTesti(unittest.TestCase):
    def test_utf16(self):
        bilgi = apk.manifest_coz(ornek_manifest())
        self.assertEqual(bilgi.paket, "com.ornek.uygulama")
        self.assertEqual(bilgi.surum_kodu, 42)
        self.assertEqual(bilgi.surum_adi, "1.2")
        self.assertEqual(bilgi.min_sdk, 24)

    def test_utf8(self):
        self.assertEqual(apk.manifest_coz(ornek_manifest(utf8=True)).paket, "com.ornek.uygulama")

    def test_ikili_olmayan_xml(self):
        with self.assertRaises(apk.ApkHatasi):
            apk.manifest_coz(b"<?xml version='1.0'?><manifest/>")

    def test_apk_ve_abiler(self):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("AndroidManifest.xml", ornek_manifest())
            z.writestr("lib/arm64-v8a/libx.so", b"")
            z.writestr("lib/armeabi-v7a/libx.so", b"")
        tampon.seek(0)
        bilgi = apk.oku(tampon)
        self.assertEqual(bilgi.abiler, ["arm64-v8a", "armeabi-v7a"])
        self.assertFalse(bilgi.x86_destekli())

    def test_zip_degil(self):
        with self.assertRaises(apk.ApkHatasi):
            apk.oku(io.BytesIO(b"bu bir apk degil"))


if __name__ == "__main__":
    unittest.main()
