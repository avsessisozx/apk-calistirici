""".apk dosyalarini bu uygulamayla iliskilendirir (HKCU, yonetici gerekmez)."""

import ctypes
import subprocess
import sys
import winreg
from pathlib import Path

PROGID = "ApkCalistirici.apk"
SINIFLAR = r"Software\Classes"
KULLANICI_SECIMI = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.apk\UserChoice"
SHCNE_ASSOCCHANGED = 0x08000000


def _komut():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"', sys.executable
    # Gelistirme: konsolsuz python ile depo kokundeki baslaticiyi calistir.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    yorumlayici = pythonw if pythonw.exists() else Path(sys.executable)
    baslatici = Path(__file__).resolve().parent.parent / "calistir.pyw"
    return f'"{yorumlayici}" "{baslatici}" "%1"', str(yorumlayici)


def _yaz(yol, deger, ad=""):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, yol) as k:
        winreg.SetValueEx(k, ad, 0, winreg.REG_SZ, deger)


def iliskilendir():
    komut, simge = _komut()
    _yaz(rf"{SINIFLAR}\{PROGID}", "Android uygulaması")
    _yaz(rf"{SINIFLAR}\{PROGID}\DefaultIcon", f'"{simge}",0')
    _yaz(rf"{SINIFLAR}\{PROGID}\shell\open", "Android'de aç")
    _yaz(rf"{SINIFLAR}\{PROGID}\shell\open\command", komut)
    _yaz(rf"{SINIFLAR}\.apk", PROGID)
    _yaz(rf"{SINIFLAR}\.apk\OpenWithProgids", "", PROGID)
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
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{SINIFLAR}\.apk") as k:
            return winreg.QueryValueEx(k, "")[0] == PROGID
    except OSError:
        return False


def birlikte_ac_penceresi(apk_yolu):
    """Windows'un 'Birlikte ac' penceresini acar."""
    subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(apk_yolu)])


def kaldir():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, rf"{SINIFLAR}\.apk\OpenWithProgids", 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, PROGID)
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{SINIFLAR}\.apk") as k:
            bizim = winreg.QueryValueEx(k, "")[0] == PROGID
    except OSError:
        bizim = False
    if bizim:
        _yaz(rf"{SINIFLAR}\.apk", "")
    for alt in (r"shell\open\command", r"shell\open", "shell", "DefaultIcon", ""):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{SINIFLAR}\{PROGID}\{alt}".rstrip("\\"))
        except OSError:
            pass
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)
