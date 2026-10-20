"""Giris noktasi.

  apk-calistirici                  ilk kurulum + .apk iliskilendirme
  apk-calistirici dosya.apk        APK'yi kur ve kendi penceresinde ac
  apk-calistirici --durdur         emulatoru kapat (anlik goruntu kaydedilir)
  apk-calistirici --iliskiyi-kaldir
  apk-calistirici --konum E:\\klasor  bilesenlerin klasorunu degistir
"""

import argparse
import logging
from pathlib import Path

from . import apk, arayuz, ayarlar, iliskilendirme, kurulum, sanal_makine, simge

log = logging.getLogger("apk_calistirici")

VARSAYILAN_UYGULAMA_NOTU = (
    "\n\nWindows .apk dosyaları için başka bir uygulamayı varsayılan tutuyor. "
    "Bir APK'ya sağ tıklayıp 'Birlikte aç > Başka bir uygulama seç' ile "
    f"{ayarlar.UYGULAMA_ADI}'yı seçin ve 'Her zaman' kutusunu işaretleyin."
)


def _gunluk_ayarla():
    ayarlar.KOK.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=ayarlar.GUNLUK,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def ilk_kurulum(pencere):
    kurulum.kur(pencere)
    pencere.mesaj("Android ilk kez başlatılıyor...")
    sanal_makine.hazirla()
    iliskilendirme.iliskilendir()
    metin = "Hazır. Artık .apk dosyalarına çift tıklayarak açabilirsiniz."
    if not iliskilendirme.iliskili_mi():
        metin += VARSAYILAN_UYGULAMA_NOTU
    pencere.bilgi(metin)


def apk_ac(yol):
    def is_(pencere):
        pencere.mesaj(f"{yol.name} okunuyor...")
        bilgi = apk.oku(yol)
        log.info("APK: %s", bilgi)
        if not bilgi.x86_destekli():
            log.warning("%s yalnızca %s içeriyor, ARM çevirisi gerekecek", bilgi.paket, bilgi.abiler)
        if not kurulum.hazir_mi():
            kurulum.kur(pencere)
        pencere.mesaj("Android başlatılıyor...")
        sanal_makine.hazirla()
        pencere.mesaj(f"{bilgi.ad} kuruluyor...")
        sanal_makine.kur(yol, bilgi)
        pencere.mesaj(f"{bilgi.ad} açılıyor...")
        sanal_makine.ac(bilgi, simge.hazirla(yol, bilgi))

    return is_


def main(argv=None):
    ayr = argparse.ArgumentParser(prog="apk-calistirici", description=ayarlar.UYGULAMA_ADI)
    ayr.add_argument("apk", nargs="?", type=Path, help="açılacak .apk dosyası")
    ayr.add_argument("--durdur", action="store_true", help="Android'i kapat")
    ayr.add_argument("--iliskiyi-kaldir", action="store_true", help=".apk ilişkilendirmesini kaldır")
    ayr.add_argument("--konum", type=Path, help="bileşenlerin kurulacağı klasörü kalıcı olarak ayarla")
    argumanlar = ayr.parse_args(argv)
    if argumanlar.konum:
        # Mevcut dosyalar tasinmaz; yeni klasor bossa ilk acilista bilesenler oraya indirilir.
        ayarlar.konum_kaydet(argumanlar.konum.resolve())
        return 0
    _gunluk_ayarla()

    if argumanlar.iliskiyi_kaldir:
        iliskilendirme.kaldir()
        return 0
    if argumanlar.durdur:
        sanal_makine.durdur()
        return 0

    is_ = apk_ac(argumanlar.apk.resolve()) if argumanlar.apk else ilk_kurulum
    pencere = arayuz.DurumPenceresi()
    if pencere.calistir(is_):
        return 0
    log.error("Başarısız", exc_info=pencere.hata)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
