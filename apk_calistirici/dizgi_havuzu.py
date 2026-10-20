"""Android ikili dosyalarindaki (AndroidManifest.xml, resources.arsc) dizgi havuzu okuyucusu."""

import struct

TUR = 0x0001
UTF8_BAYRAGI = 0x100


def oku(veri, konum, baslik_boyu):
    sayi, _, bayraklar, dizgi_basi, _ = struct.unpack_from("<IIIII", veri, konum + 8)
    konumlar = struct.unpack_from(f"<{sayi}I", veri, konum + baslik_boyu)
    taban = konum + dizgi_basi
    utf8 = bayraklar & UTF8_BAYRAGI
    return [_utf8_dizgi(veri, taban + k) if utf8 else _utf16_dizgi(veri, taban + k) for k in konumlar]


def _utf8_dizgi(veri, k):
    def uzunluk(k):
        n = veri[k]
        if n & 0x80:
            return ((n & 0x7F) << 8) | veri[k + 1], k + 2
        return n, k + 1

    _, k = uzunluk(k)  # karakter sayisi
    bayt, k = uzunluk(k)
    return veri[k : k + bayt].decode("utf-8", "replace")


def _utf16_dizgi(veri, k):
    (n,) = struct.unpack_from("<H", veri, k)
    k += 2
    if n & 0x8000:
        (alt,) = struct.unpack_from("<H", veri, k)
        n = ((n & 0x7FFF) << 16) | alt
        k += 2
    return veri[k : k + n * 2].decode("utf-16-le", "replace")
