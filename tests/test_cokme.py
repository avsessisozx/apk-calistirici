import unittest

from apk_calistirici import cokme

# Eden'in emulatorde gercekten coktugu andaki logcat satirlari (2026-10-20)
EDEN = [
    "10-20 20:31:57.129   550   586 I ActivityManager: Start proc 16059:dev.legacy.eden_emulator/u0a194 for top-activity {dev.legacy.eden_emulator/org.yuzu.yuzu_emu.ui.main.MainActivity}",
    "10-20 20:31:57.492 16059 16059 E ndk_translation: Undefined instruction 0xd53be000 at 0x00007489268dd91c",
    "10-20 20:31:57.492 16059 16059 F libc    : Fatal signal 4 (SIGILL), code -6 (SI_TKILL) in tid 16059 (y.eden_emulator), pid 16059 (y.eden_emulator)",
]

JAVA = [
    "10-20 21:00:00.100   550   586 I ActivityManager: Start proc 4242:com.ornek/u0a200 for top-activity {com.ornek/.Ana}",
    "10-20 21:00:01.000  4242  4242 E AndroidRuntime: FATAL EXCEPTION: main",
    "10-20 21:00:01.000  4242  4242 E AndroidRuntime: Process: com.ornek, PID: 4242",
    "10-20 21:00:01.000  4242  4242 E AndroidRuntime: java.lang.IllegalStateException: olmadi",
    "10-20 21:00:01.000  4242  4242 E AndroidRuntime: \tat com.ornek.Ana.onCreate(Ana.java:10)",
]


class CokmeTesti(unittest.TestCase):
    def test_arm_cevirisi(self):
        bulunan = cokme.coz(EDEN, "dev.legacy.eden_emulator")
        self.assertEqual(bulunan.tur, cokme.ARM)
        self.assertIn("0xd53be000", bulunan.ayrinti)
        self.assertIn("ARM", bulunan.mesaj("dev.legacy.eden_emulator"))

    def test_baska_paketin_cokmesi_sayilmaz(self):
        self.assertIsNone(cokme.coz(EDEN, "com.baska.uygulama"))

    def test_onceden_calisan_surec(self):
        # "Start proc" satiri yoksa pidof ile bilinen numara kullanilir.
        self.assertEqual(cokme.coz(EDEN[1:], "dev.legacy.eden_emulator", {16059}).tur, cokme.ARM)
        self.assertIsNone(cokme.coz(EDEN[1:], "dev.legacy.eden_emulator"))

    def test_yerel_cokme(self):
        bulunan = cokme.coz([EDEN[0], EDEN[2]], "dev.legacy.eden_emulator")
        self.assertEqual(bulunan.tur, cokme.YEREL)
        self.assertIn("SIGILL", bulunan.ayrinti)

    def test_java_cokmesi(self):
        bulunan = cokme.coz(JAVA, "com.ornek")
        self.assertEqual(bulunan.tur, cokme.JAVA)
        self.assertEqual(bulunan.ayrinti, "java.lang.IllegalStateException: olmadi")

    def test_cokme_yok(self):
        self.assertIsNone(cokme.coz(JAVA[:1], "com.ornek"))


if __name__ == "__main__":
    unittest.main()
