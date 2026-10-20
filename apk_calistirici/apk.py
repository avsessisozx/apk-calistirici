"""APK icindeki ikili AndroidManifest.xml'den paket bilgisini okur (aapt gerekmez)."""

import ctypes
import locale
import logging
import struct
import zipfile
from dataclasses import dataclass, field

from . import dizgi_havuzu
from .kaynak_tablosu import YOGUNLUK_HER, KaynakTablosu

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
    0x01010002: "icon",
}

# Pencere simgesi olarak kullanilabilecek bitmap'ler (uyarlanabilir simge XML'leri degil)
BITMAP_UZANTILARI = (".png", ".webp")
# Simge XML'inde izlenecek (eleman, oznitelik) ciftleri, tercih sirasiyla. Uyarlanabilir
# simgenin arka plani cogunlukla duz renk oldugundan on plan katmani tek basina kullanilir.
XML_SIMGE_KATMANLARI = (("foreground", "drawable"), ("bitmap", "src"), ("background", "drawable"))
EN_DERIN_XML = 3


class Referans(int):
    """@string/app_name gibi bir kaynak kimligi."""


@dataclass
class ApkBilgisi:
    paket: str
    surum_kodu: int = 0
    surum_adi: str = ""
    min_sdk: int = 0
    etiket: str = ""  # uygulamanin gorunen adi; bulunamazsa bos
    simge: str = ""  # APK icindeki en buyuk simge bitmap'inin yolu; bulunamazsa bos
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
            if isinstance(bilgi.etiket, Referans) or isinstance(bilgi.simge, Referans):
                tablo = _kaynak_tablosu(z)
                if isinstance(bilgi.etiket, Referans):
                    bilgi.etiket = _etiket_coz(tablo, bilgi.etiket, sistem_dilleri() if diller is None else diller)
                if isinstance(bilgi.simge, Referans):
                    bilgi.simge = _simge_coz(z, tablo, bilgi.simge)
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise ApkHatasi(f"Geçerli bir APK değil: {e}") from e
    return bilgi


# Ad ve simge bulunamazsa paket adi ve scrcpy'nin simgesi kullanilir; APK'yi acmaya engel degil.
OKUMA_HATALARI = (KeyError, ValueError, struct.error, IndexError)


def _kaynak_tablosu(z):
    try:
        return KaynakTablosu(z.read("resources.arsc"))
    except OKUMA_HATALARI:
        log.warning("resources.arsc okunamadı", exc_info=True)
        return None


def _etiket_coz(tablo, kimlik, diller):
    try:
        return (tablo and tablo.dizgi(kimlik, diller)) or ""
    except OKUMA_HATALARI:
        log.warning("Uygulama adı okunamadı (%#x)", kimlik, exc_info=True)
        return ""


def _simge_coz(z, tablo, kimlik):
    try:
        return _simge_bitmapi(z, tablo, kimlik, set(z.namelist())) if tablo else ""
    except OKUMA_HATALARI + (ApkHatasi,):
        log.warning("Uygulama simgesi okunamadı (%#x)", kimlik, exc_info=True)
        return ""


def _simge_bitmapi(z, tablo, kimlik, zip_icindekiler, derinlik=0):
    """Simgenin en yuksek yogunluklu bitmap'i.

    Yalnizca XML varsa (<adaptive-icon>, <bitmap src>) gosterdigi cizimler izlenir; vektor
    cizimler (<vector>) cizilemedigi icin atlanir.
    """
    dosyalar = [(y, yol) for y, yol in tablo.dosyalar(kimlik) if yol in zip_icindekiler]
    bitmapler = [
        (yogunluk if yogunluk < YOGUNLUK_HER else 0, yol)
        for yogunluk, yol in dosyalar
        if yol.lower().endswith(BITMAP_UZANTILARI)
    ]
    if bitmapler:
        return max(bitmapler)[1]
    if derinlik >= EN_DERIN_XML:
        return ""
    for _, yol in sorted(dosyalar, reverse=True):
        if not yol.lower().endswith(".xml"):
            continue
        katmanlar = {ad: oz for ad, oz in xml_elemanlari(z.read(yol))}
        for eleman, oznitelik in XML_SIMGE_KATMANLARI:
            hedef = katmanlar.get(eleman, {}).get(oznitelik)
            if isinstance(hedef, Referans):
                bulunan = _simge_bitmapi(z, tablo, hedef, zip_icindekiler, derinlik + 1)
                if bulunan:
                    return bulunan
    return ""


def xml_elemanlari(veri):
    """Ikili XML'deki elemanlari (ad, oznitelikler) olarak sirayla verir."""
    tur, baslik_boyu, _ = struct.unpack_from("<HHI", veri, 0)
    if tur != XML:
        raise ApkHatasi("İkili XML değil.")
    dizgiler, kaynaklar = [], []
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
            yield _eleman(veri, konum, baslik_boyu, dizgiler, kaynaklar)
        konum += boyut


def manifest_coz(veri):
    oznitelikler = {}
    etiket = simge = ""
    try:
        for ad, ozellikler in xml_elemanlari(veri):
            if ad in ("manifest", "uses-sdk"):
                oznitelikler.update(ozellikler)
            if ad == "application":
                etiket = ozellikler.get("label", "")
                simge = ozellikler.get("icon", "")
                break
    except ApkHatasi:
        raise ApkHatasi("AndroidManifest.xml ikili XML değil.") from None

    paket = oznitelikler.get("package")
    if not paket:
        raise ApkHatasi("Manifest'te paket adı yok.")
    return ApkBilgisi(
        paket=str(paket),
        surum_kodu=_tamsayi(oznitelikler.get("versionCode")),
        surum_adi=str(oznitelikler.get("versionName") or ""),
        min_sdk=_tamsayi(oznitelikler.get("minSdkVersion")),
        etiket=etiket if isinstance(etiket, Referans) else str(etiket),
        simge=simge if isinstance(simge, Referans) else "",
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
