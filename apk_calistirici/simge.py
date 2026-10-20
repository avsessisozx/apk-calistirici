"""APK'nin simgesini scrcpy'nin pencere simgesi olarak hazirlar (SCRCPY_ICON_DIR)."""

import io
import logging
import shutil
import zipfile

from . import ayarlar

log = logging.getLogger(__name__)

BOYUT = 256
PNG_IMZASI = b"\x89PNG"
# scrcpy klasorde bu iki dosyayi arar; ikincisi baglanti kopunca gosterilir.
SIMGE_DOSYASI = "scrcpy.png"
BAGLANTI_YOK_DOSYASI = "disconnected.png"


def png_yap(veri):
    """Bitmap'i (PNG/WebP) 256x256 RGBA PNG'ye cevirir.

    scrcpy'nin ffmpeg'i WebP cozemez; paletli PNG'leri de desteklemeyebilir. Pillow yoksa
    ya da goruntu bozuksa PNG oldugu gibi kullanilir, digerleri icin None.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(veri)) as resim:
            resim = resim.convert("RGBA")
            resim.thumbnail((BOYUT, BOYUT), Image.Resampling.LANCZOS)
            tuval = Image.new("RGBA", (BOYUT, BOYUT))
            tuval.paste(resim, ((BOYUT - resim.width) // 2, (BOYUT - resim.height) // 2))
            cikti = io.BytesIO()
            tuval.save(cikti, "PNG")
            return cikti.getvalue()
    except Exception:  # noqa: BLE001 - simge olmadan da pencere acilir
        log.warning("Simge dönüştürülemedi", exc_info=True)
        return veri if veri.startswith(PNG_IMZASI) else None


def hazirla(apk_yolu, bilgi):
    """Uygulamanin simge klasorunu olusturur; simge yoksa None (scrcpy kendi simgesini kullanir)."""
    if not bilgi.simge:
        return None
    try:
        with zipfile.ZipFile(apk_yolu) as z:
            png = png_yap(z.read(bilgi.simge))
    except (zipfile.BadZipFile, KeyError, OSError):
        log.warning("Simge okunamadı: %s", bilgi.simge, exc_info=True)
        return None
    if png is None:
        return None
    klasor = ayarlar.KOK / "simgeler" / bilgi.paket
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / SIMGE_DOSYASI).write_bytes(png)
    shutil.copyfile(ayarlar.SCRCPY_KLASORU / BAGLANTI_YOK_DOSYASI, klasor / BAGLANTI_YOK_DOSYASI)
    return klasor
