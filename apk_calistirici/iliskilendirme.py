""".apk dosyalarini bu uygulamayla iliskilendirir (HKCU, yonetici gerekmez)."""

import ctypes
import logging
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

from . import ayarlar

log = logging.getLogger(__name__)

PROGID = "ApkCalistirici.apk"
EXE_ADI = "ApkCalistirici.exe"
ONCEKI_DEGER = "OncekiApkUygulamasi"
SINIFLAR = r"Software\Classes"
KULLANICI_SECIMI = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.apk\UserChoice"
SHCNE_ASSOCCHANGED = 0x08000000


def kurulu_exe():
    return ayarlar.KOK / EXE_ADI


def kendini_kopyala():
    """Exe'yi bilesen klasorune kopyalar; indirilen exe silinse de iliskilendirme calisir."""
    hedef = kurulu_exe()
    kaynak = Path(sys.executable).resolve()
    if kaynak == hedef.resolve():
        return hedef
    try:
        shutil.copy2(kaynak, hedef)
    except OSError:
        # Kopya baska bir pencerede calisiyorsa eskisi kalir.
        log.warning("%s güncellenemedi", hedef, exc_info=True)
    return hedef


def _komut():
    if getattr(sys, "frozen", False):
        exe = kendini_kopyala()
        return f'"{exe}" "%1"', str(exe)
    # Gelistirme: konsolsuz python ile depo kokundeki baslaticiyi calistir.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    yorumlayici = pythonw if pythonw.exists() else Path(sys.executable)
    baslatici = Path(__file__).resolve().parent.parent / "calistir.pyw"
    return f'"{yorumlayici}" "{baslatici}" "%1"', str(yorumlayici)


def _oku(yol, ad=""):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, yol) as k:
            return winreg.QueryValueEx(k, ad)[0]
    except OSError:
        return None


def _varsayilan():
    return _oku(rf"{SINIFLAR}\.apk")


def _yaz(yol, deger, ad=""):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, yol) as k:
        winreg.SetValueEx(k, ad, 0, winreg.REG_SZ, deger)


def iliskilendir():
    komut, simge = _komut()
    _yaz(rf"{SINIFLAR}\{PROGID}", "Android uygulaması")
    _yaz(rf"{SINIFLAR}\{PROGID}\DefaultIcon", f'"{simge}",0')
    _yaz(rf"{SINIFLAR}\{PROGID}\shell\open", "Android'de aç")
    _yaz(rf"{SINIFLAR}\{PROGID}\shell\open\command", komut)
    onceki = _varsayilan()
    if onceki and onceki != PROGID:
        # Kaldirilinca eski uygulama (orn. LDPlayer) geri gelsin.
        _yaz(ayarlar.KAYIT_ANAHTARI, onceki, ONCEKI_DEGER)
    _yaz(rf"{SINIFLAR}\.apk", PROGID)
    _yaz(rf"{SINIFLAR}\.apk\OpenWithProgids", "", PROGID)
    # 'Birlikte ac' listesinde dogru adla gorunsun
    uygulama = rf"{SINIFLAR}\Applications\{EXE_ADI}"
    _yaz(uygulama, ayarlar.UYGULAMA_ADI, "FriendlyAppName")
    _yaz(rf"{uygulama}\SupportedTypes", "", ".apk")
    _yaz(rf"{uygulama}\shell\open\command", komut)
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)


def kullanici_secimi():
    """Kullanici daha once .apk icin baska bir uygulama secmisse onun ProgId'si.

    Bu secim Windows tarafindan korunur ve programla degistirilemez; kullanicinin
    'Birlikte ac > Her zaman' ile secmesi gerekir.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KULLANICI_SECIMI) as k:
            return winreg.QueryValueEx(k, "ProgId")[0]
    except OSError:
        return None


def iliskili_mi():
    secim = kullanici_secimi()
    if secim and secim != PROGID:
        return False
    return _varsayilan() == PROGID


def birlikte_ac_penceresi(apk_yolu):
    """Windows'un 'Birlikte ac' penceresini acar."""
    subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(apk_yolu)])


def _agaci_sil(yol):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, yol) as k:
            altlar = []
            while True:
                try:
                    altlar.append(winreg.EnumKey(k, len(altlar)))
                except OSError:
                    break
        for alt in altlar:
            _agaci_sil(rf"{yol}\{alt}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, yol)
    except OSError:
        pass


def kaldir():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, rf"{SINIFLAR}\.apk\OpenWithProgids", 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, PROGID)
    except OSError:
        pass
    if _varsayilan() == PROGID:
        _yaz(rf"{SINIFLAR}\.apk", _oku(ayarlar.KAYIT_ANAHTARI, ONCEKI_DEGER) or "")
    _agaci_sil(rf"{SINIFLAR}\{PROGID}")
    _agaci_sil(rf"{SINIFLAR}\Applications\{EXE_ADI}")
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)
