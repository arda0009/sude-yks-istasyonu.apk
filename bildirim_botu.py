"""YKS Asistanım - bildirim botu.

GitHub Actions bunu 15 dakikada bir çalıştırır. Firebase'deki öğrenci verilerine bakar,
uygun bir hatırlatma varsa ntfy üzerinden öğrencinin telefonuna GERÇEK bildirim yollar
(uygulama kapalıyken de gelir). Aynı bildirim aynı gün ikinci kez gönderilmez.
"""
import os
import sys
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

FIREBASE_URL = (os.environ.get("FIREBASE_URL") or "https://yks-istasyonu-default-rtdb.firebaseio.com").rstrip("/")
NTFY_SUNUCU = (os.environ.get("NTFY_SUNUCU") or "https://ntfy.sh").rstrip("/")
KURU_CALISTIR = os.environ.get("KURU_CALISTIR") == "1"      # 1 ise bildirim göndermez, sadece yazdırır
TZ = ZoneInfo("Europe/Istanbul")
PENCERE = 60            # dakika: cron geciksede planlanan saati yakalasın

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
VARSAYILAN = {"aktif": True, "baslama": 11, "su": True, "ders": True, "gunsonu": True, "sabah": True}

# ---- mesaj havuzları: her seferinde rastgele biri seçilir ----
SABAH = [
    "Günaydın {ad}! ☀️ Bugünün ilk görevi: {gorev}",
    "Yeni gün, yeni fırsat {ad}! 🌅 Sırada: {gorev}",
    "Kahveni al, hazırlan! ☕ Bugün seni bekleyen ilk iş: {gorev}",
]
SABAH_GOREVSIZ = ["Günaydın {ad}! ☀️ Bugün için planın boş, kendi hedefini belirle 💪"]
SU = [
    ("💧 Su içmeyi unutma!", "Bugün sadece {n} bardak içtin. Hadi bir bardak daha! 🚰"),
    ("🥤 Bir bardak su vakti", "Beynin su ister {ad}! Şimdiye kadar {n} bardak içtin 💧"),
    ("💦 Susadın mı?", "{n} bardakta kaldın. Ders çalışırken su içmek odağı artırır 🧠"),
]
DERS = [   # derse başlama hatırlatmaları, sırayla sertleşir sonra yumuşar
    [("⏰ Saat {h}'i geçti!", "Hâlâ derse başlamadın. Ne zaman başlamayı düşünüyorsun? 😠"),
     ("⏰ {h}:00 oldu bile", "Kronometre hâlâ kapalı {ad}… 🤨 Başlıyoruz!")],
    [("😡 Hâlâ ses yok!", "Bir 25 dakikalık pomodoro bile yeter, başla artık!"),
     ("😤 Neredesin {ad}?", "Çalışma masası seni bekliyor. Sadece 25 dakika, söz!")],
    [("😤 Gün yarılandı!", "Bugün çalışma süren hâlâ sıfır. Şimdi başla, akşam kendine teşekkür edeceksin."),
     ("🙄 Bu kadar mı?", "Kendine verdiğin sözü hatırla. Bir oturum başlat!")],
    [("🥺 Endişelenmeye başladım", "Bugün kısa da olsa bir oturum yapalım mı {ad}? Yarın için de güzel olur ❤️")],
]
GUNSONU = [
    ("🌙 Gün sonunu doldurmayı unutma!", "Bugün kaç saat çalıştığın ve nasıl hissettiğin kayda geçsin 📝"),
    ("😴 Uyumadan önce son iş", "Gün sonu kaydın eksik {ad}. 1 dakikanı alır! 🌙"),
]
OVGU = {
    "yuksek": [("🏆 Efsane bir gün!", "Bugün {s} çalıştın {ad}, seninle gurur duyuyorum! 🎉")],
    "orta": [("👏 Güzel çalışma", "Bugün {s} çalıştın. İstikrar böyle kazanılır 💪")],
    "dusuk": [("💙 Yarın daha iyi olacak", "Bugün {s} çalıştın. Dinlen, yarın yeniden başlarız!")],
}


def listeye(x):
    if isinstance(x, dict):
        try:
            x = [x[k] for k in sorted(x, key=lambda i: int(i))]
        except (ValueError, TypeError):
            x = list(x.values())
    return [i for i in x if i is not None] if isinstance(x, list) else []


def sayi(v, varsayilan=0.0):
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return varsayilan


def sn_metni(sn):
    sn = int(sn)
    return f"{sn // 3600} sa {(sn % 3600) // 60} dk" if sn >= 3600 else f"{sn // 60} dk"


def degerlendir(ad, veri, simdi, rastgele=random):
    """Bu an gönderilmesi gereken bildirimleri döndürür: [(id, baslik, mesaj, oncelik), ...]"""
    ayar = dict(VARSAYILAN)
    ayar.update(veri.get("bildirim") or {})
    if not ayar.get("aktif") or not ayar.get("konu"):
        return []
    dk = simdi.hour * 60 + simdi.minute
    if dk < 8 * 60 + 30 or dk > 23 * 60 + 30:
        return []
    bugun = simdi.strftime("%d.%m.%Y")
    gun_adi = GUNLER[simdi.weekday()]
    gun_bilgi = veri.get("gun") or {}
    derse_basladi = gun_bilgi.get("tarih") == bugun
    gunluk_bugun = [g for g in listeye(veri.get("gunluk")) if isinstance(g, dict) and g.get("tarih") == bugun]
    sonuc = []

    def yakala(baslangic, pencere=PENCERE):
        return baslangic <= dk < baslangic + pencere

    # sabah planı
    if ayar.get("sabah") and yakala(8 * 60 + 30, 90):
        plan = (veri.get("plan") or {}).get(gun_adi)
        bekleyen = [t for t in listeye(plan) if isinstance(t, dict) and not t.get("bitti")]
        if bekleyen:
            sonuc.append(("sabah", "☀️ Günaydın!", rastgele.choice(SABAH).format(ad=ad, gorev=bekleyen[0].get("gorev", "")), 3))
        else:
            sonuc.append(("sabah", "☀️ Günaydın!", rastgele.choice(SABAH_GOREVSIZ).format(ad=ad), 3))

    # su hatırlatma: (saat, o saate kadar içilmesi gereken bardak)
    if ayar.get("su"):
        su = veri.get("su") or {}
        bardak = int(sayi(su.get("bardak"))) if su.get("tarih") == bugun else 0
        for i, (saat_dk, beklenen) in enumerate([(10 * 60, 1), (12 * 60 + 30, 3), (15 * 60, 5), (17 * 60 + 30, 6), (20 * 60, 8)]):
            if yakala(saat_dk) and bardak < beklenen:
                b, m = rastgele.choice(SU)
                sonuc.append((f"su{i}", b.format(n=bardak, ad=ad), m.format(n=bardak, ad=ad), 3))

    # derse başlamadı
    if ayar.get("ders") and not derse_basladi:
        h = int(sayi(ayar.get("baslama"), 11))
        for i, ek in enumerate([0, 90, 180, 300]):
            if yakala(h * 60 + ek):
                b, m = rastgele.choice(DERS[i])
                sonuc.append((f"ders{i}", b.format(h=h, ad=ad), m.format(h=h, ad=ad), 4 if i < 3 else 3))

    # gün sonu
    if ayar.get("gunsonu") and not gunluk_bugun:
        for i, saat_dk in enumerate([22 * 60, 23 * 60 + 15]):
            if yakala(saat_dk, 45):
                b, m = rastgele.choice(GUNSONU)
                sonuc.append((f"gs{i}", b.format(ad=ad), m.format(ad=ad), 3))

    # övgü: gün sonu kaydedildikten sonra bir kez
    if gunluk_bugun:
        sn = int(sayi(gunluk_bugun[-1].get("sn"), sayi(gunluk_bugun[-1].get("saat")) * 3600))
        seviye = "yuksek" if sn >= 6 * 3600 else "orta" if sn >= 3 * 3600 else "dusuk"
        b, m = rastgele.choice(OVGU[seviye])
        sonuc.append(("ovgu", b, m.format(s=sn_metni(sn), ad=ad), 3))
    return sonuc


def ntfy_gonder(konu, baslik, mesaj, oncelik=3):
    r = requests.post(NTFY_SUNUCU, json={"topic": konu, "title": baslik, "message": mesaj, "priority": oncelik}, timeout=15)
    r.raise_for_status()


def main():
    simdi = datetime.now(TZ)
    bugun = simdi.strftime("%d.%m.%Y")
    r = requests.get(f"{FIREBASE_URL}/users.json", timeout=20)
    r.raise_for_status()
    kullanicilar = r.json() or {}
    toplam = 0
    for ad, veri in kullanicilar.items():
        if not isinstance(veri, dict):
            continue
        log = veri.get("bildirim_log") or {}
        gonderilen = listeye(log.get("gonderilen")) if log.get("tarih") == bugun else []
        yeni = []
        for bid, baslik, mesaj, oncelik in degerlendir(ad, veri, simdi):
            if bid in gonderilen:
                continue
            konu = veri["bildirim"]["konu"]
            print(f"[{ad}] {bid}: {baslik} | {mesaj}")
            if KURU_CALISTIR:
                continue
            try:
                ntfy_gonder(konu, baslik, mesaj, oncelik)
                yeni.append(bid)
                toplam += 1
            except Exception as ex:
                print(f"[{ad}] gönderilemedi: {ex}")
        if yeni:
            requests.patch(f"{FIREBASE_URL}/users/{ad}.json",
                           json={"bildirim_log": {"tarih": bugun, "gonderilen": gonderilen + yeni}}, timeout=15).raise_for_status()
    print(f"{simdi:%d.%m.%Y %H:%M} - {toplam} bildirim gönderildi.")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("HATA:", ex)
        sys.exit(1)
