import io
import struct
import unittest
import zipfile

from apk_calistirici import apk, kaynak_tablosu as kt
from tests.test_apk import _dizgi_havuzu, _eleman

YAPILANDIRMA_BOYU = 64
UYGULAMA_ADI = 0x7F010000
TAKMA_AD = 0x7F010001  # @string/app_name -> @string/ad zinciri


def _girdi(veri_turu, deger, kompakt=False):
    if kompakt:
        return struct.pack("<HHI", 0, kt.KOMPAKT | (veri_turu << 8), deger)
    return struct.pack("<HHI", 8, 0, 0) + struct.pack("<HBBI", 8, 0, veri_turu, deger)


def _tur_parcasi(dil, girdiler, ofset16=False):
    """girdiler: girdi numarasi sirasiyla bayt dizileri ya da None (girdi yok)."""
    yapilandirma = struct.pack("<I4x", YAPILANDIRMA_BOYU) + dil.ljust(2, b"\0")
    yapilandirma = yapilandirma.ljust(YAPILANDIRMA_BOYU, b"\0")
    baslik_boyu = 20 + YAPILANDIRMA_BOYU
    ofsetler, govde = [], b""
    for g in girdiler:
        if g is None:
            ofsetler.append(kt.GIRDI_YOK16 if ofset16 else kt.GIRDI_YOK)
        else:
            ofsetler.append(len(govde) // 4 if ofset16 else len(govde))
            govde += g
    dizin = struct.pack(f"<{len(ofsetler)}{'H' if ofset16 else 'I'}", *ofsetler)
    dizin += b"\0" * (-len(dizin) % 4)
    girdi_basi = baslik_boyu + len(dizin)
    bayrak = kt.OFSET16 if ofset16 else 0
    baslik = struct.pack("<HHIBBHII", kt.TUR, baslik_boyu, girdi_basi + len(govde), 1, bayrak, 0,
                         len(girdiler), girdi_basi)
    return baslik + yapilandirma + dizin + govde


def ornek_tablo():
    havuz = _dizgi_havuzu(["App", "Uygulama"], utf8=True)
    turler = (
        _tur_parcasi(b"", [_girdi(kt.TUR_STRING, 0), _girdi(kt.TUR_REFERANS, UYGULAMA_ADI)])
        + _tur_parcasi(b"tr", [_girdi(kt.TUR_STRING, 1, kompakt=True), None], ofset16=True)
    )
    paket = struct.pack("<HHII", kt.PAKET, 288, 288 + len(turler), 0x7F).ljust(288, b"\0") + turler
    govde = havuz + paket
    return struct.pack("<HHII", kt.TABLO, 12, 12 + len(govde), 1) + govde


def etiketli_manifest():
    dizgiler = ["", "package", "manifest", "com.ornek", "application"]
    kaynaklar = [0x01010001]
    govde = _dizgi_havuzu(dizgiler, utf8=False)
    govde += struct.pack("<HHI", 0x0180, 8, 12) + struct.pack("<I", *kaynaklar)
    govde += _eleman(2, [(1, 3, apk.TUR_STRING, 3)])
    govde += _eleman(4, [(0, 0xFFFFFFFF, apk.TUR_REFERANS, TAKMA_AD)])
    return struct.pack("<HHI", 0x0003, 8, 8 + len(govde)) + govde


class KaynakTablosuTesti(unittest.TestCase):
    def setUp(self):
        self.tablo = kt.KaynakTablosu(ornek_tablo())

    def test_dil_tercihi(self):
        self.assertEqual(self.tablo.dizgi(UYGULAMA_ADI, ("tr", "en")), "Uygulama")
        self.assertEqual(self.tablo.dizgi(UYGULAMA_ADI, ("en",)), "App")  # dilsiz varsayilan

    def test_referans_zinciri(self):
        self.assertEqual(self.tablo.dizgi(TAKMA_AD, ("tr",)), "Uygulama")

    def test_olmayan_kaynak(self):
        self.assertIsNone(self.tablo.dizgi(0x7F010009))
        self.assertIsNone(self.tablo.dizgi(0x7F020000))

    def test_apk_etiketi(self):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("AndroidManifest.xml", etiketli_manifest())
            z.writestr("resources.arsc", ornek_tablo())
        bilgi = apk.oku(tampon, diller=("tr",))
        self.assertEqual((bilgi.paket, bilgi.etiket, bilgi.ad), ("com.ornek", "Uygulama", "Uygulama"))

    def test_bozuk_tablo_paket_adina_duser(self):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("AndroidManifest.xml", etiketli_manifest())
            z.writestr("resources.arsc", b"bozuk")
        self.assertEqual(apk.oku(tampon).ad, "com.ornek")


if __name__ == "__main__":
    unittest.main()
