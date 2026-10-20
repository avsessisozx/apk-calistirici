# DURUM (apk-calistirici)

Amac: Windows'ta .apk'ya cift tikla, Android uygulamasi kendi penceresinde acilsin. Tek exe, kurulum yok, reklam yok.

## Calistirma (gelistirme)
- `python calistir.pyw` -> ilk kurulum (lisans onayi, indirme, AVD, .apk iliskilendirme)
- `python calistir.pyw dosya.apk` -> kur ve kendi penceresinde ac
- `python calistir.pyw --durdur` -> Android'i kapat (snapshot kaydedilir)
- `python calistir.pyw --konum E:\klasor` -> bilesen klasorunu kalici ayarla (HKCU\Software\ApkCalistirici\Kok)
- Testler: `python -m unittest`

## Mimari karari
- Motor: Google Android Emulator (WHPX ile hizlandirilmis). Ham QEMU degil, GPU hizlandirma ve snapshot icin.
- Pencere: scrcpy (--new-display ile uygulama basina pencere denenecek).
- Exe: Python + PyInstaller, GitHub Actions (windows-latest) ile derlenecek.
- Ilk acilista bilesenler indirilir (emulator, platform-tools, sistem imaji, scrcpy). Adresler Google'in repository2-3.xml / sys-img2-3.xml listelerinden (kararli kanal) ve GitHub API'den okunur, sha1/sha256 dogrulanir, yarim indirme devam eder.
- sdkmanager/avdmanager KULLANILMIYOR (Java gerektirir); XML dogrudan okunur, AVD config.ini elle yazilir.
- Ayri adb sunucu portu 15037 (LDPlayer vb. adb'leriyle cakismasin).
- .apk dosya baglama (HKCU, yonetici gerektirmez) + paylasilan klasor/video acma sonra.

## Kullanicinin PC'si (dogrulandi)
- Bilesen klasoru: E:\cloude\ApkCalistirici (C: dolu oldugu icin tasindi, kayit defterinde kayitli). C:pk-test\sdk eski deneme kurulumu, artik kullanilmiyor.
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

- Python uygulamasi (apk_calistirici/): ayarlar, indirme, kurulum, sanal_makine, apk (ikili manifest okuyucu, aapt gerekmez), arayuz (tkinter durum penceresi + lisans onayi), iliskilendirme (HKCU).
- Uctan uca dogrulandi (2026-10-20): ilk kurulum indirmesi ~2 dk (1.9 GB, diskte 5.3 GB); ilk AVD acilisi 46 sn (host GPU, NVIDIA); Android kapaliyken APK'ya cift tik -> pencere 9 sn (snapshot'tan 3.4 sn acilis); kurulu APK'yi tekrar acma 4-5 sn.
- scrcpy bayraklari: --no-vd-system-decorations (yoksa sanal ekranin baslaticisi uygulamanin ustune cikabiliyor - yaris durumu, Nekogram'da goruldu), --no-vd-destroy-content (pencere kapaninca uygulama ana ekrana tasinir, durum korunur; dogrulandi).
- Veri diski bos alana gore 2-8 GB (emulator 1.2 kati bos alan ister). GPU once host, acilmazsa auto.
- Manifest okuyucu Downloads'taki 12 APK'nin hepsinde dogru calisti.

## Siradaki
1. GitHub Actions: PyInstaller ile tek exe (calistir.pyw giris noktasi, --noconsole) + unittest
2. .apk iliskilendirmesi gercek kayit defterinde HENUZ TEST EDILMEDI (gelistirme modunda pythonw+repo yolunu yazar; exe ile test edilmeli). Kullanicinin onceden sectigi UserChoice varsa Windows'un 'Birlikte ac' ile secilmesi gerekiyor.
3. Pencere basligi su an paket adi; uygulama etiketi (resources.arsc) okunabilir ya da scrcpy ciktisindaki 'Starting app "X"' kullanilabilir
4. Sadece arm64 APK'lar: x86_64 imajda ARM ceviri var mi test edilmeli (orn. Eden, mlc-chat, ReVanced)
5. Hic pencere kalmayinca emulatoru otomatik kapatma (snapshot) / bolunmus APK (.apks/.xapk) destegi

## Bilinen sorunlar
- Bulut ortamindan dl.google.com ve GitHub API erisilemiyor; indirme/test sadece kullanicinin PC'sinde
- Computer use ile Windows terminaline yazilamiyor; testler yerel (Code sekmesi) oturumdan yapilmali
