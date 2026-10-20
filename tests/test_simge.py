import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image

from apk_calistirici import apk, ayarlar, kaynak_tablosu as kt, simge
from tests.test_apk import _dizgi_havuzu, _eleman
from tests.test_kaynak_tablosu import _girdi, _tur_parcasi

SIMGE = 0x7F010000  # mipmap: 240 dpi, 640 dpi ve anydpi XML
UYARLANABILIR = 0x7F010001  # yalnizca anydpi <adaptive-icon>
ON_PLAN = 0x7F020000  # drawable: on plan PNG'si

YOLLAR = ["res/a.png", "res/b.png", "res/c.xml", "res/on.png", "res/uyarlanabilir.xml"]


def _png(renk, boyut=(48, 48), bicim="PNG", kip="RGBA"):
    cikti = io.BytesIO()
    Image.new(kip, boyut, renk).save(cikti, bicim)
    return cikti.getvalue()


def _tablo():
    def dizgi(no):
        return _girdi(kt.TUR_STRING, no)

    turler = (
        _tur_parcasi(b"", [dizgi(0), None], yogunluk=240)
        + _tur_parcasi(b"", [dizgi(1), None], yogunluk=640)
        + _tur_parcasi(b"", [dizgi(2), dizgi(4)], yogunluk=kt.YOGUNLUK_HER)
        + _tur_parcasi(b"", [dizgi(3)], tur_no=2)
    )
    paket = struct.pack("<HHII", kt.PAKET, 288, 288 + len(turler), 0x7F).ljust(288, b"\0") + turler
    govde = _dizgi_havuzu(YOLLAR, utf8=True) + paket
    return struct.pack("<HHII", kt.TABLO, 12, 12 + len(govde), 1) + govde


def _uyarlanabilir_simge():
    govde = _dizgi_havuzu(["drawable", "adaptive-icon", "foreground"], utf8=False)
    govde += _eleman(1, [])
    govde += _eleman(2, [(0, 0xFFFFFFFF, apk.TUR_REFERANS, ON_PLAN)])
    return struct.pack("<HHI", 0x0003, 8, 8 + len(govde)) + govde


def _apk():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("resources.arsc", _tablo())
        z.writestr("res/a.png", _png("red"))
        z.writestr("res/b.png", _png("blue"))
        z.writestr("res/c.xml", b"")
        z.writestr("res/on.png", _png("green"))
        z.writestr("res/uyarlanabilir.xml", _uyarlanabilir_simge())
    tampon.seek(0)
    return zipfile.ZipFile(tampon)


class SimgeSecimiTesti(unittest.TestCase):
    def setUp(self):
        self.z = _apk()
        self.tablo = kt.KaynakTablosu(self.z.read("resources.arsc"))

    def test_en_yuksek_yogunluk(self):
        self.assertEqual(apk._simge_coz(self.z, self.tablo, SIMGE), "res/b.png")

    def test_uyarlanabilir_simgenin_on_plani(self):
        self.assertEqual(apk._simge_coz(self.z, self.tablo, UYARLANABILIR), "res/on.png")

    def test_olmayan_simge(self):
        self.assertEqual(apk._simge_coz(self.z, self.tablo, 0x7F030000), "")


class PngYapTesti(unittest.TestCase):
    def _dogrula(self, veri):
        with Image.open(io.BytesIO(simge.png_yap(veri))) as resim:
            self.assertEqual((resim.format, resim.mode, resim.size), ("PNG", "RGBA", (256, 256)))

    def test_webp(self):
        self._dogrula(_png("red", bicim="WEBP"))

    def test_paletli_png(self):
        self._dogrula(_png(3, kip="P"))

    def test_bozuk_veri(self):
        self.assertIsNone(simge.png_yap(b"bozuk"))


class HazirlaTesti(unittest.TestCase):
    def test_klasor(self):
        with tempfile.TemporaryDirectory() as gecici:
            kok, scrcpy = Path(gecici) / "kok", Path(gecici) / "scrcpy"
            scrcpy.mkdir()
            (scrcpy / simge.BAGLANTI_YOK_DOSYASI).write_bytes(b"x")
            apk_yolu = Path(gecici) / "a.apk"
            with zipfile.ZipFile(apk_yolu, "w") as z:
                z.writestr("res/b.png", _png("blue"))
            bilgi = apk.ApkBilgisi(paket="com.ornek", simge="res/b.png")
            with mock.patch.object(ayarlar, "KOK", kok), mock.patch.object(ayarlar, "SCRCPY_KLASORU", scrcpy):
                klasor = simge.hazirla(apk_yolu, bilgi)
                self.assertEqual(klasor, kok / "simgeler" / "com.ornek")
                self.assertTrue((klasor / simge.SIMGE_DOSYASI).read_bytes().startswith(simge.PNG_IMZASI))
                self.assertTrue((klasor / simge.BAGLANTI_YOK_DOSYASI).exists())
                self.assertIsNone(simge.hazirla(apk_yolu, apk.ApkBilgisi(paket="com.simgesiz")))


if __name__ == "__main__":
    unittest.main()
