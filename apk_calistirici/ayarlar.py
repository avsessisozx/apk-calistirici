"""Sabitler, klasorler ve alt sureclerin ortam degiskenleri."""

import json
import os
import subprocess
import winreg
from pathlib import Path

UYGULAMA_ADI = "APK Çalıştırıcı"

KAYIT_ANAHTARI = r"Software\ApkCalistirici"


def kayitli_konum():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KAYIT_ANAHTARI) as k:
            return winreg.QueryValueEx(k, "Kok")[0]
    except OSError:
        return None


def konum_kaydet(yol):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KAYIT_ANAHTARI) as k:
        winreg.SetValueEx(k, "Kok", 0, winreg.REG_SZ, str(yol))


# Bilesenlerin ve sanal telefonun durdugu klasor (birkac GB). Oncelik:
# APK_CALISTIRICI_KOK ortam degiskeni, kayit defterindeki konum, %LOCALAPPDATA%.
KOK = Path(
    os.environ.get("APK_CALISTIRICI_KOK")
    or kayitli_konum()
    or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ApkCalistirici"
)
SDK = KOK / "sdk"
AVD_KLASORU = KOK / "avd"
SCRCPY_KLASORU = KOK / "scrcpy"
INDIRMELER = KOK / "indirmeler"
DURUM_DOSYASI = KOK / "durum.json"
GUNLUK = KOK / "gunluk.txt"
EMULATOR_GUNLUGU = KOK / "emulator.txt"
KILIT = KOK / "kilit"

AVD_ADI = "apkc"
# adb emulatorleri 5555-5585 araliginda tarar; 5584 son cift port.
PORT = 5584
SERI = f"emulator-{PORT}"
# Bilgisayardaki baska adb sunuculariyla (LDPlayer vb.) cakismamak icin ayri port.
ADB_SUNUCU_PORTU = "15037"

API, ETIKET, ABI = "android-34", "google_apis", "x86_64"
SISTEM_IMAJI = f"system-images;{API};{ETIKET};{ABI}"

# Google'in SDK paket listeleri; indirme adresleri bunlardan okunur.
SDK_DEPOSU = "https://dl.google.com/android/repository/"
SDK_LISTESI = SDK_DEPOSU + "repository2-3.xml"
SISTEM_IMAJI_DEPOSU = f"{SDK_DEPOSU}sys-img/{ETIKET}/"
SISTEM_IMAJI_LISTESI = SISTEM_IMAJI_DEPOSU + "sys-img2-3.xml"
SCRCPY_SON_SURUM = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"

PENCERESIZ = subprocess.CREATE_NO_WINDOW


def adb_exe():
    return SDK / "platform-tools" / "adb.exe"


def emulator_exe():
    return SDK / "emulator" / "emulator.exe"


def scrcpy_exe():
    return SCRCPY_KLASORU / "scrcpy.exe"


def ortam():
    env = dict(os.environ)
    env.update(
        ANDROID_SDK_ROOT=str(SDK),
        ANDROID_HOME=str(SDK),
        ANDROID_AVD_HOME=str(AVD_KLASORU),
        ANDROID_ADB_SERVER_PORT=ADB_SUNUCU_PORTU,
        # scrcpy kendi adb'si yerine SDK'ninkini kullansin (surum uyumsuzlugu olmasin).
        ADB=str(adb_exe()),
    )
    return env


def durum_oku():
    try:
        return json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def durum_yaz(durum):
    KOK.mkdir(parents=True, exist_ok=True)
    gecici = DURUM_DOSYASI.with_suffix(".tmp")
    gecici.write_text(json.dumps(durum, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(gecici, DURUM_DOSYASI)
