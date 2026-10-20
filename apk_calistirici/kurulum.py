"""Ilk acilista gereken bilesenleri (emulator, sistem imaji, adb, scrcpy) indirip kurar."""

import logging
import shutil

from . import ayarlar, indirme, sanal_makine

log = logging.getLogger(__name__)

# Acilan zip'ler gecici olarak yer kapladigi icin indirme boyutunun katlari kadar bos alan gerekir.
ALAN_CARPANI = 3
# Kullanici verisi icin ayrilan sanal disk (disk.dataPartition.size)
VERI_ALANI = 8 << 30


def _hedefler():
    s = ayarlar.SDK
    return {
        "platform-tools": (s / "platform-tools", ayarlar.adb_exe()),
        "emulator": (s / "emulator", ayarlar.emulator_exe()),
        ayarlar.SISTEM_IMAJI: (
            s / "system-images" / ayarlar.API / ayarlar.ETIKET / ayarlar.ABI,
            s / "system-images" / ayarlar.API / ayarlar.ETIKET / ayarlar.ABI / "system.img",
        ),
        "scrcpy": (ayarlar.SCRCPY_KLASORU, ayarlar.scrcpy_exe()),
    }


def eksikler():
    durum = ayarlar.durum_oku().get("bilesenler", {})
    return [ad for ad, (_, dosya) in _hedefler().items() if ad not in durum or not dosya.exists()]


def hazir_mi():
    avd = ayarlar.AVD_KLASORU / f"{ayarlar.AVD_ADI}.avd" / "config.ini"
    return not eksikler() and avd.exists()


def kur(arayuz):
    """Eksik bilesenleri kurar. arayuz: mesaj(), ilerleme(), lisans_sor() saglar."""
    eksik = eksikler()
    if eksik:
        arayuz.mesaj("Bileşen listesi alınıyor...")
        paketler = indirme.sdk_paketleri()
        paketler["scrcpy"] = indirme.scrcpy_paketi()
        paketler = {ad: p for ad, p in paketler.items() if ad in eksik}

        durum = ayarlar.durum_oku()
        lisanslar = {p.lisans for p in paketler.values() if p.lisans}
        if lisanslar and not durum.get("lisans_kabul"):
            if not arayuz.lisans_sor("\n\n".join(sorted(lisanslar))):
                raise RuntimeError("Lisans kabul edilmedi, kurulum iptal edildi.")
            durum["lisans_kabul"] = True
            ayarlar.durum_yaz(durum)

        _alan_denetle(sum(p.boyut for p in paketler.values()))
        hedefler = _hedefler()
        for sira, (ad, paket) in enumerate(paketler.items(), 1):
            etiket = f"({sira}/{len(paketler)}) {ad} {paket.surum}"
            arayuz.mesaj(f"İndiriliyor {etiket}")
            zip_yolu = indirme.indir(paket, arayuz.ilerleme)
            arayuz.mesaj(f"Açılıyor {etiket}")
            arayuz.ilerleme(0, 0)
            indirme.zip_ac(zip_yolu, hedefler[ad][0])
            zip_yolu.unlink()
            durum = ayarlar.durum_oku()
            durum.setdefault("bilesenler", {})[ad] = paket.surum
            ayarlar.durum_yaz(durum)
            log.info("Kuruldu: %s %s", ad, paket.surum)
        shutil.rmtree(ayarlar.INDIRMELER, ignore_errors=True)

    avd = ayarlar.AVD_KLASORU / f"{ayarlar.AVD_ADI}.avd" / "config.ini"
    if not avd.exists():
        arayuz.mesaj("Sanal telefon oluşturuluyor...")
        sanal_makine.avd_olustur()


def _alan_denetle(indirilecek):
    ayarlar.KOK.mkdir(parents=True, exist_ok=True)
    gerekli = indirilecek * ALAN_CARPANI + VERI_ALANI // 4
    bos = shutil.disk_usage(ayarlar.KOK).free
    if bos < gerekli:
        raise RuntimeError(
            f"Diskte yeterli boş alan yok: {gerekli / 2**30:.1f} GB gerekli, {bos / 2**30:.1f} GB var."
        )
