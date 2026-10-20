# DURUM (apk-calistirici)

Amac: Windows'ta .apk'ya cift tikla, Android uygulamasi kendi penceresinde acilsin. Tek exe, kurulum yok, reklam yok.

## Mimari karari
- Motor: Google Android Emulator (WHPX ile hizlandirilmis). Ham QEMU degil, GPU hizlandirma ve snapshot icin.
- Pencere: scrcpy (--new-display ile uygulama basina pencere denenecek).
- Exe: Python + PyInstaller, GitHub Actions (windows-latest) ile derlenecek.
- Ilk acilista bilesenler indirilir (SDK arac, sistem imaji, scrcpy). Adresler sabit yazilmayacak, Google'in guncel listesinden okunacak (sdkmanager).
- .apk dosya baglama (HKCU, yonetici gerektirmez) + paylasilan klasor/video acma sonra.

## Kullanicinin PC'si (dogrulandi)
- Windows 10 Pro (19045), Ryzen 5 5600, 16 GB RAM, GTX 1050 Ti
- BIOS'ta SVM acik, WHPX etkin, emulator -accel-check: "WHPX is installed and usable"
- C:\apk-test\sdk altinda: cmdline-tools, platform-tools, emulator, system-images;android-34;google_apis;x86_64, AVD "test" olusturuldu
- Java var (sdkmanager calisiyor); PATH'te 'java' yok olabilir, JAVA_HOME ile bulunuyor
- adb "more than one device/emulator" veriyor: bilgisayarda baska Android cihaz/emulator (muhtemelen LDPlayer) goruluyor. Emulator -port 5584 ile baslatip adb -s emulator-5584 kullan.

## Yapildi
- Repo acildi, README
- Altyapi dogrulandi (yukaridaki liste)
- AVD "test" duzeltildi: hw.ramSize 96M -> 4096, hw.gpu.enabled=yes, hw.gpu.mode=host, hw.cpu.ncore=4, hw.keyboard=yes (yedek: config.ini.bak). Uygulama kendi AVD'sini olustururken bu degerleri yazmali.
- Olcum (2026-10-20): soguk acilis 20 sn (-no-snapshot-load), snapshot'tan acilis 5 sn (-no-window). Snapshot kaydi kapanista ~1 sn.
- GPU: GTX 1050 Ti ile host GLES calisiyor (OpenGL ES 3.1), WHPX aktif.
- scrcpy v5.0.1 (C:pk-test\scrcpy-win64-v5.0.1). ADB ortam degiskeni SDK adb'sine ayarlanmali (surum uyumsuzlugu olmasin).
- Calisan komut: scrcpy -s emulator-5584 --new-display=1080x1920/420 --start-app=<paket> --no-audio --window-title=<ad>
  -> uygulama ayri sanal ekranda, ana ekranda launcher kaliyor. Iki uygulama ayni anda iki pencerede dogrulandi (display 2 ve 3).
  -> Emulator -no-window iken de calisiyor; scrcpy D3D11VA donanim cozumleme kullaniyor.
- APK kurulum: adb install -r. KeyAttestation (1.3 MB) 0.5 sn, Nekogram x86_64 (48 MB) 6 sn.

## Siradaki
1. Python uygulamasi: ilk kurulum, VM yonetimi, .apk baglama
2. GitHub Actions: exe derleme + test
3. Snapshot akisi: emulator arka planda -no-window acik kalsin, kapanista snapshot; paket adini APK'dan oku (aapt2/androguard)
4. Ana ekran (display 0) 320x640 kucuk; -no-window'da onemsiz ama skin/cozunurluk ayari dusunulmeli
5. Sadece arm64 APK'lar: x86_64 imajda ARM ceviri (ndk_translation) var mi test edilmeli

## Bilinen sorunlar
- Bulut ortamindan dl.google.com ve GitHub API erisilemiyor; indirme/test sadece kullanicinin PC'sinde
- scrcpy kapaninca sanal ekran ve icindeki uygulama penceresi yok oluyor (FLAG_DESTROY_CONTENT_ON_REMOVAL); uygulama durumu korunmuyor olabilir, test et
- Computer use ile Windows terminaline yazilamiyor; testler yerel (Code sekmesi) oturumdan yapilmali
