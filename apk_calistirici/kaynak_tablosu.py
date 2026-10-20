"""resources.arsc'den bir kaynagin degerini (ornegin @string/app_name) okur."""

import struct
from typing import NamedTuple

from . import dizgi_havuzu

TABLO = 0x0002
PAKET = 0x0200
TUR = 0x0201

TUR_REFERANS = 0x01
TUR_STRING = 0x03

# ResTable_type bayraklari
SEYREK = 0x01
OFSET16 = 0x02
GIRDI_YOK = 0xFFFFFFFF
GIRDI_YOK16 = 0xFFFF

# ResTable_entry bayraklari
KARMASIK = 0x0001
KOMPAKT = 0x0008

# @string/a -> @string/b -> ... zincirinin en fazla uzunlugu
EN_UZUN_ZINCIR = 8

# ResTable_config.density ozel degerleri
YOGUNLUK_HER = 0xFFFE  # anydpi (genelde uyarlanabilir simge XML'i)
YOGUNLUK_YOK = 0xFFFF  # nodpi


class Aday(NamedTuple):
    """Bir kaynagin tek bir yapilandirmadaki degeri."""

    dil: str
    yogunluk: int
    veri_turu: int
    deger: int


class KaynakTablosu:
    def __init__(self, veri):
        self.veri = veri
        self.dizgiler = []
        self.turler = {}  # (paket no, tur no) -> tur parcalarinin konumlari (her yapilandirma icin bir tane)
        tur, baslik_boyu, _ = struct.unpack_from("<HHI", veri, 0)
        if tur != TABLO:
            raise ValueError("resources.arsc kaynak tablosu değil")
        konum = baslik_boyu
        while konum + 8 <= len(veri):
            tur, baslik_boyu, boyut = struct.unpack_from("<HHI", veri, konum)
            if boyut < 8:
                break
            if tur == dizgi_havuzu.TUR:
                self.dizgiler = dizgi_havuzu.oku(veri, konum, baslik_boyu)
            elif tur == PAKET:
                self._paket(konum, baslik_boyu, boyut)
            konum += boyut

    def _paket(self, konum, baslik_boyu, boyut):
        (paket_no,) = struct.unpack_from("<I", self.veri, konum + 8)
        son = konum + boyut
        konum += baslik_boyu
        while konum + 8 <= son:
            tur, _, parca_boyu = struct.unpack_from("<HHI", self.veri, konum)
            if parca_boyu < 8:
                break
            if tur == TUR:
                self.turler.setdefault((paket_no, self.veri[konum + 8]), []).append(konum)
            konum += parca_boyu

    def _girdi(self, parca, girdi_no):
        """Bir tur parcasindaki girdiyi Aday olarak dondurur; yoksa None."""
        v = self.veri
        _, baslik_boyu, _ = struct.unpack_from("<HHI", v, parca)
        bayraklar = v[parca + 9]
        sayi, girdi_basi, yapilandirma_boyu = struct.unpack_from("<III", v, parca + 12)
        # ResTable_config (parca + 20): language 8. baytta, density 14. baytta
        dil = _dil(v[parca + 28 : parca + 30])
        yogunluk = struct.unpack_from("<H", v, parca + 34)[0] if yapilandirma_boyu >= 16 else 0
        dizin = parca + baslik_boyu
        if bayraklar & SEYREK:
            for i in range(sayi):
                no, ofset = struct.unpack_from("<HH", v, dizin + 4 * i)
                if no == girdi_no:
                    ofset *= 4
                    break
            else:
                return None
        elif girdi_no >= sayi:
            return None
        elif bayraklar & OFSET16:
            (ofset,) = struct.unpack_from("<H", v, dizin + 2 * girdi_no)
            if ofset == GIRDI_YOK16:
                return None
            ofset *= 4
        else:
            (ofset,) = struct.unpack_from("<I", v, dizin + 4 * girdi_no)
            if ofset == GIRDI_YOK:
                return None

        girdi = parca + girdi_basi + ofset
        girdi_boyu, girdi_bayraklari = struct.unpack_from("<HH", v, girdi)
        if girdi_bayraklari & KOMPAKT:
            (deger,) = struct.unpack_from("<I", v, girdi + 4)
            return Aday(dil, yogunluk, girdi_bayraklari >> 8, deger)
        if girdi_bayraklari & KARMASIK:
            return None
        _, _, veri_turu, deger = struct.unpack_from("<HBBI", v, girdi + girdi_boyu)
        return Aday(dil, yogunluk, veri_turu, deger)

    def adaylar(self, kimlik):
        """Kaynagin tum yapilandirmalardaki degerleri."""
        paket_no, tur_no, girdi_no = kimlik >> 24, (kimlik >> 16) & 0xFF, kimlik & 0xFFFF
        return [g for p in self.turler.get((paket_no, tur_no), []) if (g := self._girdi(p, girdi_no))]

    def dosyalar(self, kimlik, _derinlik=0):
        """Kaynagin APK icindeki dosya yollari: [(yogunluk, "res/mipmap-xxhdpi/ic_launcher.png"), ...]."""
        sonuc = []
        for aday in self.adaylar(kimlik):
            if aday.veri_turu == TUR_STRING and aday.deger < len(self.dizgiler):
                sonuc.append((aday.yogunluk, self.dizgiler[aday.deger]))
            elif aday.veri_turu == TUR_REFERANS and _derinlik < EN_UZUN_ZINCIR:
                sonuc.extend(self.dosyalar(aday.deger, _derinlik + 1))
        return sonuc

    def dizgi(self, kimlik, diller=(), _derinlik=0):
        """Kaynak kimliginin dizgi degeri. diller: tercih sirasina gore dil kodlari ("tr", "en")."""
        adaylar = self.adaylar(kimlik)
        if not adaylar:
            return None

        def oncelik(aday):
            dil = aday[0]
            if dil in diller:
                return diller.index(dil)
            return len(diller) if dil == "" else len(diller) + 1  # dilsiz varsayilan, sonra herhangi biri

        _, _, veri_turu, deger = min(adaylar, key=oncelik)
        if veri_turu == TUR_STRING and deger < len(self.dizgiler):
            return self.dizgiler[deger]
        if veri_turu == TUR_REFERANS and _derinlik < EN_UZUN_ZINCIR:
            return self.dizgi(deger, diller, _derinlik + 1)
        return None


def _dil(iki_bayt):
    if iki_bayt == b"\0\0":
        return ""
    if iki_bayt[0] & 0x80:
        return iki_bayt.hex()  # 3 harfli paketlenmis dil kodu; tercih listesinde olmaz
    return iki_bayt.decode("ascii", "replace")
