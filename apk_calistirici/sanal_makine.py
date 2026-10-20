"""Android emulatorunu baslatma/durdurma, APK kurma ve uygulamayi scrcpy penceresinde acma."""

import contextlib
import ctypes
import ctypes.wintypes
import hashlib
import logging
import msvcrt
import os
import re
import shutil
import subprocess
import time

from . import ayarlar

log = logging.getLogger(__name__)

ACILIS_SURESI = 300
KURULUM_SURESI = 600
SCRCPY_DENETIM_SURESI = 4
VERI_DISKI_EN_AZ_GB = 2
VERI_DISKI_EN_COK_GB = 8
# Once ekran karti; acilamazsa emulatorun kendi secimi (gerekirse yazilimsal cizim).
GPU_KIPLERI = ("host", "auto")

# Sik gorulen kurulum hatalarinin kullaniciya gosterilecek aciklamalari
KURULUM_HATALARI = {
    "INSTALL_FAILED_NO_MATCHING_ABIS": "Bu uygulama bilgisayarın işlemci mimarisini desteklemiyor (yalnızca ARM).",
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "Aynı uygulamanın farklı imzalı bir sürümü zaten kurulu. Önce onu kaldırın.",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "Daha yeni bir sürümü zaten kurulu.",
    "INSTALL_FAILED_OLDER_SDK": "Bu uygulama daha yeni bir Android sürümü istiyor.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "Sanal telefonda yer kalmadı.",
    "INSTALL_PARSE_FAILED": "APK dosyası bozuk ya da eksik (bölünmüş APK olabilir).",
}


class SanalMakineHatasi(Exception):
    pass


class DiskDoluHatasi(SanalMakineHatasi):
    pass


def _calistir(*args, zaman_asimi=60):
    sonuc = subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ayarlar.ortam(),
        timeout=zaman_asimi,
        creationflags=ayarlar.PENCERESIZ,
    )
    return sonuc.returncode, (sonuc.stdout + sonuc.stderr).strip()


def adb(*args, zaman_asimi=60):
    return _calistir(ayarlar.adb_exe(), "-s", ayarlar.SERI, *args, zaman_asimi=zaman_asimi)


@contextlib.contextmanager
def kilit():
    """Ayni anda acilan birden fazla APK'nin emulatoru iki kez baslatmasini onler."""
    ayarlar.KOK.mkdir(parents=True, exist_ok=True)
    with open(ayarlar.KILIT, "a+b") as f:
        while True:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.5)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _bellek_mb():
    class Durum(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (ad, ctypes.c_ulonglong)
            for ad in ("toplam", "bos", "sayfa", "bos_sayfa", "sanal", "bos_sanal", "ek")
        ]

    d = Durum()
    d.dwLength = ctypes.sizeof(d)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(d))
    return d.toplam // (1 << 20)


def avd_olustur():
    """avdmanager (Java) kullanmadan AVD dosyalarini yazar."""
    avd = ayarlar.AVD_KLASORU / f"{ayarlar.AVD_ADI}.avd"
    avd.mkdir(parents=True, exist_ok=True)
    ram = max(2048, min(4096, _bellek_mb() // 4))
    # Emulator veri diski icin boyutun 1.2 katı bos alan ister.
    bos_gb = shutil.disk_usage(avd).free / 2**30
    veri_gb = int(max(VERI_DISKI_EN_AZ_GB, min(VERI_DISKI_EN_COK_GB, bos_gb / 1.2 - 2)))
    cekirdek = max(2, min(4, (os.cpu_count() or 4) // 2))
    yapilandirma = {
        "avd.ini.encoding": "UTF-8",
        "AvdId": ayarlar.AVD_ADI,
        "abi.type": ayarlar.ABI,
        "hw.cpu.arch": ayarlar.ABI,
        "hw.cpu.ncore": cekirdek,
        "hw.ramSize": ram,
        "vm.heapSize": 256,
        "hw.gpu.enabled": "yes",
        "hw.gpu.mode": "auto",
        "hw.keyboard": "yes",
        "hw.lcd.width": 1080,
        "hw.lcd.height": 1920,
        "hw.lcd.density": 420,
        "disk.dataPartition.size": f"{veri_gb}G",
        "image.sysdir.1": f"system-images\\{ayarlar.API}\\{ayarlar.ETIKET}\\{ayarlar.ABI}\\",
        "tag.id": ayarlar.ETIKET,
        "PlayStore.enabled": "false",
        "showDeviceFrame": "no",
    }
    (avd / "config.ini").write_text(
        "".join(f"{k}={v}\n" for k, v in yapilandirma.items()), encoding="utf-8"
    )
    (ayarlar.AVD_KLASORU / f"{ayarlar.AVD_ADI}.ini").write_text(
        f"avd.ini.encoding=UTF-8\npath={avd}\ntarget={ayarlar.API}\n", encoding="utf-8"
    )


def calisiyor_mu():
    _, cikti = _calistir(ayarlar.adb_exe(), "devices")
    return re.search(rf"^{re.escape(ayarlar.SERI)}\s+device$", cikti, re.M) is not None


def _baslat(gpu):
    log.info("Emülatör başlatılıyor (gpu=%s)", gpu)
    gunluk = open(ayarlar.EMULATOR_GUNLUGU, "w", encoding="utf-8", errors="replace")
    komut = [
        str(ayarlar.emulator_exe()),
        "-avd", ayarlar.AVD_ADI,
        "-port", str(ayarlar.PORT),
        "-no-window",
        "-no-audio",  # ses scrcpy ile uygulama penceresinden gelir
        "-no-boot-anim",
        "-gpu", gpu,
    ]
    bayraklar = ayarlar.PENCERESIZ | subprocess.CREATE_NEW_PROCESS_GROUP
    with gunluk:
        try:
            # Bu surec kapaninca emulator acik kalsin.
            return subprocess.Popen(
                komut, stdout=gunluk, stderr=subprocess.STDOUT, env=ayarlar.ortam(),
                creationflags=bayraklar | subprocess.CREATE_BREAKAWAY_FROM_JOB,
            )
        except OSError:
            return subprocess.Popen(
                komut, stdout=gunluk, stderr=subprocess.STDOUT, env=ayarlar.ortam(),
                creationflags=bayraklar,
            )


def _acilisi_bekle(surec):
    bitis = time.monotonic() + ACILIS_SURESI
    while time.monotonic() < bitis:
        if surec.poll() is not None:
            gunluk = _gunluk_sonu(ayarlar.EMULATOR_GUNLUGU)
            if "Not enough space" in gunluk:
                raise DiskDoluHatasi(
                    "Sanal telefonun verileri için diskte yeterli boş alan yok. "
                    "Biraz yer açıp tekrar deneyin.\n\n" + gunluk
                )
            raise SanalMakineHatasi("Android başlatılamadı.\n\n" + gunluk)
        if calisiyor_mu():
            _, deger = adb("shell", "getprop", "sys.boot_completed", zaman_asimi=10)
            if deger.strip() == "1":
                return
        time.sleep(0.5)
    surec.kill()
    raise SanalMakineHatasi("Android açılışı çok uzun sürdü.")


def _gunluk_sonu(yol, satir=15):
    try:
        return "\n".join(yol.read_text(encoding="utf-8", errors="replace").splitlines()[-satir:])
    except OSError:
        return ""


def hazirla():
    """Emulator calismiyorsa baslatir ve acilmasini bekler."""
    with kilit():
        if calisiyor_mu():
            return
        # Emulator acilista kendini adb sunucusuna bildirir; sunucu once ayakta olmali.
        _calistir(ayarlar.adb_exe(), "start-server")
        for gpu in GPU_KIPLERI:
            baslangic = time.monotonic()
            try:
                _acilisi_bekle(_baslat(gpu))
            except DiskDoluHatasi:
                raise
            except SanalMakineHatasi:
                if gpu == GPU_KIPLERI[-1]:
                    raise
                log.warning("gpu=%s ile açılmadı, sonraki deneniyor", gpu, exc_info=True)
                continue
            log.info("Android %.1f sn'de açıldı", time.monotonic() - baslangic)
            return


def durdur():
    """Emulatoru kapatir; kapanirken anlik goruntu kaydedilir, sonraki acilis hizli olur."""
    if calisiyor_mu():
        adb("emu", "kill")


def _dosya_ozeti(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        while blok := f.read(1 << 20):
            h.update(blok)
    return h.hexdigest()


def kur(apk_yolu, bilgi):
    """APK kurulu degilse ya da dosya degistiyse kurar."""
    ozet = _dosya_ozeti(apk_yolu)
    durum = ayarlar.durum_oku()
    kurulular = durum.setdefault("kurulu_apkler", {})
    if kurulular.get(bilgi.paket) == ozet:
        kod, cikti = adb("shell", "pm", "path", bilgi.paket)
        if kod == 0 and cikti.startswith("package:"):
            log.info("%s zaten kurulu", bilgi.paket)
            return
    log.info("%s kuruluyor", bilgi.paket)
    _, cikti = adb("install", "-r", "-t", "-g", apk_yolu, zaman_asimi=KURULUM_SURESI)
    if "Success" not in cikti:
        hata = re.search(r"(INSTALL_[A-Z_]+)", cikti)
        kod = hata.group(1) if hata else ""
        aciklama = next((v for k, v in KURULUM_HATALARI.items() if kod.startswith(k)), "")
        raise SanalMakineHatasi(f"Uygulama kurulamadı. {aciklama}\n\n{cikti[-500:]}")
    durum = ayarlar.durum_oku()
    durum.setdefault("kurulu_apkler", {})[bilgi.paket] = ozet
    ayarlar.durum_yaz(durum)


def _ekran_boyutu():
    """Calisma alanina sigan, 9:16 oranli sanal ekran boyutu (piksel, dpi)."""
    ctypes.windll.user32.SetProcessDPIAware()
    alan = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(alan), 0)  # SPI_GETWORKAREA
    yukseklik = (alan.bottom - alan.top) * 9 // 10 // 16 * 16
    yukseklik = max(960, min(yukseklik, 1920))
    genislik = yukseklik * 9 // 16 // 8 * 8
    # 1080 piksel genislikte 420 dpi ile ayni gorunum
    return genislik, yukseklik, genislik * 420 // 1080


def ac(bilgi, baslik):
    """Uygulamayi kendi sanal ekraninda, ayri bir scrcpy penceresinde acar."""
    genislik, yukseklik, dpi = _ekran_boyutu()
    komut = [
        str(ayarlar.scrcpy_exe()),
        "-s", ayarlar.SERI,
        f"--new-display={genislik}x{yukseklik}/{dpi}",
        f"--start-app={bilgi.paket}",
        # Sanal ekranda baslatici olmasin: hem pencerede yalnizca uygulama gorunur hem de
        # baslaticinin sonradan acilip uygulamanin ustune cikmasi (yaris durumu) onlenir.
        "--no-vd-system-decorations",
        # Pencere kapaninca uygulama yok edilmesin, ana ekrana tasinsin.
        "--no-vd-destroy-content",
        f"--window-title={baslik}",
    ]
    log.info("Açılıyor: %s", " ".join(komut))
    gunluk_yolu = ayarlar.KOK / f"scrcpy-{bilgi.paket}.txt"
    with open(gunluk_yolu, "w", encoding="utf-8", errors="replace") as gunluk:
        surec = subprocess.Popen(
            komut, stdout=gunluk, stderr=subprocess.STDOUT, env=ayarlar.ortam(),
            creationflags=ayarlar.PENCERESIZ | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    # Hemen kapanirsa (uygulama baslatilamadi vb.) kullaniciya nedenini goster.
    try:
        kod = surec.wait(SCRCPY_DENETIM_SURESI)
    except subprocess.TimeoutExpired:
        return surec
    if kod != 0:
        raise SanalMakineHatasi("Uygulama penceresi açılamadı.\n\n" + _gunluk_sonu(gunluk_yolu))
    return surec
