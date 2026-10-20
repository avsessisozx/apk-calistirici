"""APK icindeki ikili AndroidManifest.xml'den paket bilgisini okur (aapt gerekmez)."""

import struct
import zipfile
from dataclasses import dataclass, field

STRING_POOL = 0x0001
XML = 0x0003
XML_RESOURCE_MAP = 0x0180
XML_START_ELEMENT = 0x0102

UTF8_BAYRAGI = 0x100
DEGER_YOK = 0xFFFFFFFF
TUR_STRING = 0x03

# android:* ozniteliklerinin kaynak kimlikleri (isimleri karartilmis APK'larda da gecerli)
KAYNAK_KIMLIKLERI = {
    0x0101021B: "versionCode",
    0x0101021C: "versionName",
    0x0101020C: "minSdkVersion",
}


@dataclass
class ApkBilgisi:
    paket: str
    surum_kodu: int = 0
    surum_adi: str = ""
    min_sdk: int = 0
    abiler: list = field(default_factory=list)

    def x86_destekli(self):
        """Yerel kutuphanesi yoksa ya da x86 icin derlenmisse ceviri gerekmez."""
        return not self.abiler or any(a.startswith("x86") for a in self.abiler)


class ApkHatasi(Exception):
    pass


def oku(yol):
    try:
        with zipfile.ZipFile(yol) as z:
            manifest = z.read("AndroidManifest.xml")
            abiler = sorted({ad.split("/")[1] for ad in z.namelist() if ad.startswith("lib/") and ad.count("/") >= 2})
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise ApkHatasi(f"Geçerli bir APK değil: {e}") from e
    bilgi = manifest_coz(manifest)
    bilgi.abiler = abiler
    return bilgi


def manifest_coz(veri):
    tur, baslik_boyu, _ = struct.unpack_from("<HHI", veri, 0)
    if tur != XML:
        raise ApkHatasi("AndroidManifest.xml ikili XML değil.")
    dizgiler, kaynaklar = [], []
    oznitelikler = {}
    konum = baslik_boyu
    while konum + 8 <= len(veri):
        tur, baslik_boyu, boyut = struct.unpack_from("<HHI", veri, konum)
        if boyut < 8:
            break
        if tur == STRING_POOL:
            dizgiler = _dizgi_havuzu(veri, konum, baslik_boyu)
        elif tur == XML_RESOURCE_MAP:
            kaynaklar = list(struct.unpack_from(f"<{(boyut - baslik_boyu) // 4}I", veri, konum + baslik_boyu))
        elif tur == XML_START_ELEMENT:
            ad, ozellikler = _eleman(veri, konum, baslik_boyu, dizgiler, kaynaklar)
            if ad in ("manifest", "uses-sdk"):
                oznitelikler.update(ozellikler)
            if ad == "application":
                break
        konum += boyut

    paket = oznitelikler.get("package")
    if not paket:
        raise ApkHatasi("Manifest'te paket adı yok.")
    return ApkBilgisi(
        paket=str(paket),
        surum_kodu=_tamsayi(oznitelikler.get("versionCode")),
        surum_adi=str(oznitelikler.get("versionName") or ""),
        min_sdk=_tamsayi(oznitelikler.get("minSdkVersion")),
    )


def _tamsayi(deger):
    try:
        return int(deger)
    except (TypeError, ValueError):
        return 0


def _eleman(veri, konum, baslik_boyu, dizgiler, kaynaklar):
    _, ad_no, bas, oz_boyu, sayi = struct.unpack_from("<IIHHH", veri, konum + baslik_boyu)
    ozellikler = {}
    oz_konum = konum + baslik_boyu + bas
    for i in range(sayi):
        _, ad, ham, _, _, veri_turu, deger = struct.unpack_from("<IIIHBBI", veri, oz_konum + i * oz_boyu)
        if ad < len(kaynaklar) and kaynaklar[ad] in KAYNAK_KIMLIKLERI:
            oz_ad = KAYNAK_KIMLIKLERI[kaynaklar[ad]]
        else:
            oz_ad = _dizgi(dizgiler, ad)
        if ham != DEGER_YOK:
            ozellikler[oz_ad] = _dizgi(dizgiler, ham)
        elif veri_turu == TUR_STRING:
            ozellikler[oz_ad] = _dizgi(dizgiler, deger)
        else:
            ozellikler[oz_ad] = deger
    return _dizgi(dizgiler, ad_no), ozellikler


def _dizgi(dizgiler, no):
    return dizgiler[no] if no < len(dizgiler) else ""


def _dizgi_havuzu(veri, konum, baslik_boyu):
    sayi, _, bayraklar, dizgi_basi, _ = struct.unpack_from("<IIIII", veri, konum + 8)
    konumlar = struct.unpack_from(f"<{sayi}I", veri, konum + baslik_boyu)
    taban = konum + dizgi_basi
    utf8 = bayraklar & UTF8_BAYRAGI
    return [_utf8_dizgi(veri, taban + k) if utf8 else _utf16_dizgi(veri, taban + k) for k in konumlar]


def _utf8_dizgi(veri, k):
    def uzunluk(k):
        n = veri[k]
        if n & 0x80:
            return ((n & 0x7F) << 8) | veri[k + 1], k + 2
        return n, k + 1

    _, k = uzunluk(k)  # karakter sayisi
    bayt, k = uzunluk(k)
    return veri[k : k + bayt].decode("utf-8", "replace")


def _utf16_dizgi(veri, k):
    (n,) = struct.unpack_from("<H", veri, k)
    k += 2
    if n & 0x8000:
        (alt,) = struct.unpack_from("<H", veri, k)
        n = ((n & 0x7FFF) << 16) | alt
        k += 2
    return veri[k : k + n * 2].decode("utf-16-le", "replace")
