"""APK icindeki ikili AndroidManifest.xml'den paket bilgisini okur (aapt gerekmez)."""

import ctypes
import locale
import logging
import struct
import zipfile
from dataclasses import dataclass, field

from . import dizgi_havuzu
from .kaynak_tablosu import KaynakTablosu

log = logging.getLogger(__name__)

XML = 0x0003
XML_RESOURCE_MAP = 0x0180
XML_START_ELEMENT = 0x0102

DEGER_YOK = 0xFFFFFFFF
TUR_REFERANS = 0x01
TUR_STRING = 0x03

# android:* ozniteliklerinin kaynak kimlikleri (isimleri karartilmis APK'larda da gecerli)
KAYNAK_KIMLIKLERI = {
    0x0101021B: "versionCode",
    0x0101021C: "versionName",
    0x0101020C: "minSdkVersion",
    0x01010001: "label",
}


class Referans(int):
    """@string/app_name gibi bir kaynak kimligi."""


@dataclass
class ApkBilgisi:
    paket: str
    surum_kodu: int = 0
    surum_adi: str = ""
    min_sdk: int = 0
    etiket: str = ""  # uygulamanin gorunen adi; bulunamazsa bos
    abiler: list = field(default_factory=list)

    @property
    def ad(self):
        return self.etiket or self.paket

    def x86_destekli(self):
        """Yerel kutuphanesi yoksa ya da x86 icin derlenmisse ceviri gerekmez."""
        return not self.abiler or any(a.startswith("x86") for a in self.abiler)


class ApkHatasi(Exception):
    pass


def sistem_dilleri():
    """Windows arayuz dili ve Ingilizce, tercih sirasiyla ("tr", "en")."""
    try:
        kod = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
    except (AttributeError, OSError):
        kod = ""
    dil = kod.split("_")[0]
    return tuple(dict.fromkeys(d for d in (dil, "en") if d))


def oku(yol, diller=None):
    try:
        with zipfile.ZipFile(yol) as z:
            manifest = z.read("AndroidManifest.xml")
            abiler = sorted({ad.split("/")[1] for ad in z.namelist() if ad.startswith("lib/") and ad.count("/") >= 2})
            bilgi = manifest_coz(manifest)
            bilgi.abiler = abiler
            if isinstance(bilgi.etiket, Referans):
                bilgi.etiket = _etiket_coz(z, bilgi.etiket, sistem_dilleri() if diller is None else diller)
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise ApkHatasi(f"Geçerli bir APK değil: {e}") from e
    return bilgi


def _etiket_coz(z, kimlik, diller):
    # Uygulama adi bulunamazsa paket adi kullanilir; APK'yi acmaya engel degil.
    try:
        return KaynakTablosu(z.read("resources.arsc")).dizgi(kimlik, diller) or ""
    except (KeyError, ValueError, struct.error, IndexError):
        log.warning("Uygulama adı okunamadı (%#x)", kimlik, exc_info=True)
        return ""


def manifest_coz(veri):
    tur, baslik_boyu, _ = struct.unpack_from("<HHI", veri, 0)
    if tur != XML:
        raise ApkHatasi("AndroidManifest.xml ikili XML değil.")
    dizgiler, kaynaklar = [], []
    oznitelikler = {}
    etiket = ""
    konum = baslik_boyu
    while konum + 8 <= len(veri):
        tur, baslik_boyu, boyut = struct.unpack_from("<HHI", veri, konum)
        if boyut < 8:
            break
        if tur == dizgi_havuzu.TUR:
            dizgiler = dizgi_havuzu.oku(veri, konum, baslik_boyu)
        elif tur == XML_RESOURCE_MAP:
            kaynaklar = list(struct.unpack_from(f"<{(boyut - baslik_boyu) // 4}I", veri, konum + baslik_boyu))
        elif tur == XML_START_ELEMENT:
            ad, ozellikler = _eleman(veri, konum, baslik_boyu, dizgiler, kaynaklar)
            if ad in ("manifest", "uses-sdk"):
                oznitelikler.update(ozellikler)
            if ad == "application":
                etiket = ozellikler.get("label", "")
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
        etiket=etiket if isinstance(etiket, Referans) else str(etiket),
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
        elif veri_turu == TUR_REFERANS:
            ozellikler[oz_ad] = Referans(deger)
        else:
            ozellikler[oz_ad] = deger
    return _dizgi(dizgiler, ad_no), ozellikler


def _dizgi(dizgiler, no):
    return dizgiler[no] if no < len(dizgiler) else ""
