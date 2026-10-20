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

## Siradaki
1. Emulatoru -port 5584 ile ac, acilis suresi ve akicilik olc (SONUC HENUZ YOK)
2. scrcpy indir, APK kur, uygulamayi ayri pencerede ac (-new-display / --start-app)
3. Python uygulamasi: ilk kurulum, VM yonetimi, .apk baglama
4. GitHub Actions: exe derleme + test
5. Snapshot ile hizli acilis

## Bilinen sorunlar
- Bulut ortamindan dl.google.com ve GitHub API erisilemiyor; indirme/test sadece kullanicinin PC'sinde
- Computer use ile Windows terminaline yazilamiyor; testler yerel (Code sekmesi) oturumdan yapilmali
