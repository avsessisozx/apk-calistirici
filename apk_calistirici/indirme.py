"""Bilesen listelerini okuma, indirme (devam ettirilebilir) ve zip acma."""

import hashlib
import json
import logging
import shutil
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import ayarlar

log = logging.getLogger(__name__)

BLOK = 1 << 20
ZAMAN_ASIMI = 60
KULLANICI_ARACI = "apk-calistirici"


@dataclass
class Paket:
    ad: str
    surum: str
    url: str
    ozet_turu: str  # "sha1" / "sha256"
    ozet: str
    boyut: int
    lisans: str = ""


def _istek(url, **basliklar):
    return urllib.request.Request(url, headers={"User-Agent": KULLANICI_ARACI, **basliklar})


def _getir(url):
    with urllib.request.urlopen(_istek(url), timeout=ZAMAN_ASIMI) as yanit:
        return yanit.read()


def _yerel_ad(etiket):
    return etiket.rsplit("}", 1)[-1]


def _kararli_paketler(kok, taban_url):
    """Bir SDK deposu XML'indeki kararli kanal Windows paketlerini dondurur."""
    kanallar = {e.get("id"): e.text for e in kok if _yerel_ad(e.tag) == "channel"}
    lisanslar = {e.get("id"): e.text or "" for e in kok if _yerel_ad(e.tag) == "license"}
    for paket in kok:
        if _yerel_ad(paket.tag) != "remotePackage":
            continue
        kanal = paket.find("channelRef")
        if kanal is not None and kanallar.get(kanal.get("ref")) != "stable":
            continue
        surum = ".".join(e.text for e in paket.find("revision") if e.text)
        lisans = paket.find("uses-license")
        for arsiv in paket.iter("archive"):
            if arsiv.findtext("host-os") not in (None, "windows"):
                continue
            if arsiv.findtext("host-arch") not in (None, "x64"):
                continue
            tam = arsiv.find("complete")
            ozet = tam.find("checksum")
            yield Paket(
                ad=paket.get("path"),
                surum=surum,
                url=taban_url + tam.findtext("url"),
                ozet_turu=ozet.get("type", "sha1"),
                ozet=ozet.text.strip(),
                boyut=int(tam.findtext("size")),
                lisans=lisanslar.get(lisans.get("ref"), "") if lisans is not None else "",
            )
            break


def sdk_paketleri():
    """emulator, platform-tools ve sistem imaji icin guncel paketleri bulur."""
    istenen = {"emulator", "platform-tools", ayarlar.SISTEM_IMAJI}
    bulunan = {}
    for liste, taban in (
        (ayarlar.SDK_LISTESI, ayarlar.SDK_DEPOSU),
        (ayarlar.SISTEM_IMAJI_LISTESI, ayarlar.SISTEM_IMAJI_DEPOSU),
    ):
        kok = ET.fromstring(_getir(liste))
        for paket in _kararli_paketler(kok, taban):
            if paket.ad in istenen and paket.ad not in bulunan:
                bulunan[paket.ad] = paket
    eksik = istenen - bulunan.keys()
    if eksik:
        raise RuntimeError(f"Google paket listesinde bulunamadı: {', '.join(sorted(eksik))}")
    return bulunan


def scrcpy_paketi():
    surum = json.loads(_getir(ayarlar.SCRCPY_SON_SURUM))
    for varlik in surum.get("assets", []):
        ad = varlik["name"]
        if ad.startswith("scrcpy-win64-") and ad.endswith(".zip"):
            ozet_turu, _, ozet = (varlik.get("digest") or "").partition(":")
            return Paket(
                ad="scrcpy",
                surum=surum["tag_name"],
                url=varlik["browser_download_url"],
                ozet_turu=ozet_turu,
                ozet=ozet,
                boyut=varlik["size"],
            )
    raise RuntimeError("scrcpy'nin Windows sürümü bulunamadı.")


def indir(paket, ilerleme=None):
    """Paketi INDIRMELER altina indirir; yarim kalan indirmeye devam eder, ozeti dogrular."""
    ayarlar.INDIRMELER.mkdir(parents=True, exist_ok=True)
    hedef = ayarlar.INDIRMELER / Path(paket.url).name
    if hedef.exists() and _ozet_tutuyor(hedef, paket):
        return hedef
    yarim = hedef.with_name(hedef.name + ".part")
    alinan = yarim.stat().st_size if yarim.exists() else 0
    if alinan >= paket.boyut:
        yarim.unlink()
        alinan = 0

    basliklar = {"Range": f"bytes={alinan}-"} if alinan else {}
    with urllib.request.urlopen(_istek(paket.url, **basliklar), timeout=ZAMAN_ASIMI) as yanit:
        if alinan and yanit.status != 206:
            alinan = 0  # Sunucu devam etmeyi desteklemiyor, bastan.
        with open(yarim, "ab" if alinan else "wb") as dosya:
            while blok := yanit.read(BLOK):
                dosya.write(blok)
                alinan += len(blok)
                if ilerleme:
                    ilerleme(alinan, paket.boyut)

    if not _ozet_tutuyor(yarim, paket):
        yarim.unlink()
        raise RuntimeError(f"{paket.ad} indirmesi bozuk geldi, tekrar deneyin.")
    yarim.replace(hedef)
    return hedef


def _ozet_tutuyor(dosya, paket):
    if not paket.ozet_turu:
        log.warning("%s için doğrulama özeti yok", paket.ad)
        return dosya.stat().st_size == paket.boyut
    h = hashlib.new(paket.ozet_turu)
    with open(dosya, "rb") as f:
        while blok := f.read(BLOK):
            h.update(blok)
    return h.hexdigest().lower() == paket.ozet.lower()


def zip_ac(zip_yolu, hedef):
    """Tek ust klasorlu zip'i acar, ust klasorun icerigini hedef klasor yapar."""
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=hedef.parent) as gecici:
        gecici = Path(gecici)
        with zipfile.ZipFile(zip_yolu) as z:
            for uye in z.namelist():
                if not (gecici / uye).resolve().is_relative_to(gecici.resolve()):
                    raise RuntimeError(f"Zip içinde geçersiz yol: {uye}")
            z.extractall(gecici)
        ust = list(gecici.iterdir())
        if hedef.exists():
            shutil.rmtree(hedef)
        if len(ust) == 1 and ust[0].is_dir():
            shutil.move(str(ust[0]), str(hedef))
        else:
            hedef.mkdir()
            for oge in ust:
                shutil.move(str(oge), str(hedef / oge.name))
