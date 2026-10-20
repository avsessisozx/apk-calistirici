"""Kucuk durum penceresi: isler arka planda calisir, pencere ilerlemeyi gosterir."""

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from . import ayarlar

YOKLAMA_MS = 100


class _Kutu:
    """Is parcacigindan ana parcacikta acilan pencerenin cevabini beklemek icin."""

    def __init__(self):
        self.olay = threading.Event()
        self.deger = None

    def koy(self, deger):
        self.deger = deger
        self.olay.set()

    def bekle(self):
        self.olay.wait()
        return self.deger


class DurumPenceresi:
    def __init__(self):
        self.kok = tk.Tk()
        self.kok.title(ayarlar.UYGULAMA_ADI)
        self.kok.resizable(False, False)
        self.kok.protocol("WM_DELETE_WINDOW", self._kapat)
        cerceve = ttk.Frame(self.kok, padding=16)
        cerceve.pack(fill="both", expand=True)
        self._etiket = ttk.Label(cerceve, text="Hazırlanıyor...", width=60)
        self._etiket.pack(anchor="w")
        self._cubuk = ttk.Progressbar(cerceve, length=440, mode="indeterminate")
        self._cubuk.pack(fill="x", pady=(10, 4))
        self._cubuk.start(15)
        self._ayrinti = ttk.Label(cerceve, text="", foreground="gray")
        self._ayrinti.pack(anchor="w")
        self._kuyruk = queue.Queue()
        self.hata = None

    # Asagidakiler is parcacigindan cagrilabilir.

    def mesaj(self, metin):
        self._kuyruk.put(("mesaj", metin))

    def ilerleme(self, alinan, toplam):
        self._kuyruk.put(("ilerleme", alinan, toplam))

    def lisans_sor(self, metin):
        kutu = _Kutu()
        self._kuyruk.put(("lisans", metin, kutu))
        return kutu.bekle()

    def bilgi(self, metin):
        kutu = _Kutu()
        self._kuyruk.put(("bilgi", metin, kutu))
        kutu.bekle()

    # Ana parcacik

    def calistir(self, is_fonk):
        """is_fonk(self) arka planda calisir; hata olursa gosterilir. Basariliysa True."""

        def is_parcacigi():
            try:
                is_fonk(self)
            except Exception as e:  # noqa: BLE001 - kullaniciya gosterilecek
                self.hata = e
            self._kuyruk.put(("bitti",))

        threading.Thread(target=is_parcacigi, daemon=True).start()
        self.kok.after(YOKLAMA_MS, self._isle)
        self.kok.mainloop()
        return self.hata is None

    def _isle(self):
        ilerleme = None
        while True:
            try:
                is_ = self._kuyruk.get_nowait()
            except queue.Empty:
                break
            tur = is_[0]
            if tur == "ilerleme":
                ilerleme = is_[1:]  # yalnizca sonuncusu onemli
            elif tur == "mesaj":
                self._etiket.config(text=is_[1])
                self._ayrinti.config(text="")
            elif tur == "lisans":
                is_[2].koy(self._lisans_penceresi(is_[1]))
            elif tur == "bilgi":
                messagebox.showinfo(ayarlar.UYGULAMA_ADI, is_[1], parent=self.kok)
                is_[2].koy(None)
            elif tur == "bitti":
                if self.hata:
                    messagebox.showerror(ayarlar.UYGULAMA_ADI, str(self.hata), parent=self.kok)
                self.kok.destroy()
                return
        if ilerleme:
            self._ilerleme_goster(*ilerleme)
        self.kok.after(YOKLAMA_MS, self._isle)

    def _ilerleme_goster(self, alinan, toplam):
        if not toplam:
            if self._cubuk["mode"] != "indeterminate":
                self._cubuk.config(mode="indeterminate")
                self._cubuk.start(15)
            return
        if self._cubuk["mode"] != "determinate":
            self._cubuk.stop()
            self._cubuk.config(mode="determinate", maximum=100)
        self._cubuk["value"] = alinan * 100 / toplam
        self._ayrinti.config(text=f"{alinan / 2**20:.0f} / {toplam / 2**20:.0f} MB")

    def _lisans_penceresi(self, metin):
        pencere = tk.Toplevel(self.kok)
        pencere.title("Android SDK Lisansı")
        pencere.transient(self.kok)
        ttk.Label(
            pencere,
            text="Android emülatörü ve sistem imajı Google'ın lisansıyla indirilecek:",
            padding=(12, 12, 12, 4),
        ).pack(anchor="w")
        alan = scrolledtext.ScrolledText(pencere, width=90, height=24, wrap="word")
        alan.insert("1.0", metin)
        alan.config(state="disabled")
        alan.pack(fill="both", expand=True, padx=12)
        sonuc = {"kabul": False}

        def sec(kabul):
            sonuc["kabul"] = kabul
            pencere.destroy()

        dugmeler = ttk.Frame(pencere, padding=12)
        dugmeler.pack(fill="x")
        ttk.Button(dugmeler, text="Reddet", command=lambda: sec(False)).pack(side="right")
        ttk.Button(dugmeler, text="Kabul ediyorum", command=lambda: sec(True)).pack(side="right", padx=8)
        pencere.protocol("WM_DELETE_WINDOW", lambda: sec(False))
        pencere.grab_set()
        self.kok.wait_window(pencere)
        return sonuc["kabul"]

    def _kapat(self):
        if messagebox.askyesno(ayarlar.UYGULAMA_ADI, "İşlem iptal edilsin mi?", parent=self.kok):
            # Yarim indirmeler bir sonraki acilista kaldigi yerden devam eder.
            os._exit(1)
