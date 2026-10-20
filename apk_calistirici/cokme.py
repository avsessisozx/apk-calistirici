"""Uygulamanin acilista cokup cokmedigini logcat satirlarindan anlar ve nedenini aciklar."""

import re
from dataclasses import dataclass

# logcat -v threadtime: "10-20 20:31:57.492 16059 16059 E ndk_translation: Undefined instruction ..."
SATIR = re.compile(r"^\d\d-\d\d \S+\s+(\d+)\s+\d+\s+[VDIWEF]\s+(.*?)\s*: (.*)$")
SUREC_BASLADI = re.compile(r"Start proc (\d+):([^/\s]+)")

# Okunan etiketler; logcat'e "-s" ile verilir.
ETIKETLER = ("ndk_translation:E", "AndroidRuntime:E", "libc:F", "ActivityManager:I")

ARM = "arm"
JAVA = "java"
YEREL = "yerel"


@dataclass
class Cokme:
    tur: str
    ayrinti: str

    def mesaj(self, paket):
        if self.tur == ARM:
            return (
                f"{paket} açılırken kapandı.\n\n"
                "Bu uygulama ARM işlemciler (telefonlar) için derlenmiş. Bilgisayarınız onu "
                "çeviri yoluyla çalıştırıyor, ancak uygulamanın kullandığı bir işlemci komutu "
                "çevrilemiyor. Uygulamanın x86_64 (Intel/AMD) sürümü varsa onu deneyin.\n\n"
                f"Ayrıntı: {self.ayrinti}"
            )
        if self.tur == JAVA:
            return f"{paket} açılırken çöktü.\n\nAyrıntı: {self.ayrinti}"
        return f"{paket} açılırken çöktü (yerel kod hatası).\n\nAyrıntı: {self.ayrinti}"


def coz(satirlar, paket, pidler=()):
    """Paketin sureclerine ait cokme satirlarini bulur; yoksa None.

    pidler: zaten bilinen surec numaralari (uygulama onceden calisiyorsa "Start proc" satiri olmaz).
    """
    pidler = set(pidler)
    arm = java = yerel = None
    java_bekleyen = None
    for satir in satirlar:
        eslesme = SATIR.match(satir.rstrip())
        if not eslesme:
            continue
        pid, etiket, ileti = int(eslesme[1]), eslesme[2], eslesme[3]
        if etiket == "ActivityManager":
            basladi = SUREC_BASLADI.search(ileti)
            # Surec adi "paket" ya da "paket:hizmet" olabilir.
            if basladi and basladi[2].split(":")[0] == paket:
                pidler.add(int(basladi[1]))
            continue
        if etiket == "AndroidRuntime":
            if ileti.startswith(f"Process: {paket},") or ileti.startswith(f"Process: {paket}:"):
                java_bekleyen = pid
            elif java_bekleyen == pid and java is None:
                java = ileti.strip()
            continue
        if pid not in pidler:
            continue
        if etiket == "ndk_translation" and "Undefined instruction" in ileti:
            arm = arm or ileti.strip()
        elif etiket == "libc" and "Fatal signal" in ileti:
            yerel = yerel or ileti.strip()

    if arm:
        return Cokme(ARM, arm)
    if java:
        return Cokme(JAVA, java)
    if yerel:
        return Cokme(YEREL, yerel)
    return None
