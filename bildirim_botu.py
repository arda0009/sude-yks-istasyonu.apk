import os
import random
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    requests = None

FIREBASE_URL = os.environ.get("FIREBASE_URL", "https://yks-istasyonu-default-rtdb.firebaseio.com").rstrip("/")
NTFY_SUNUCU = os.environ.get("NTFY_SUNUCU", "https://ntfy.sh").rstrip("/")
ISTANBUL_TZ = timezone(timedelta(hours=3))


def istanbul_simdi(ts=None):
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=ISTANBUL_TZ)
        return ts.astimezone(ISTANBUL_TZ)
    if ts is None:
        return datetime.now(ISTANBUL_TZ)
    return datetime.fromtimestamp(float(ts), tz=ISTANBUL_TZ)


def istanbul_bugun(ts=None):
    return istanbul_simdi(ts).strftime("%Y-%m-%d")


def onceki_gun_str(gun_str):
    try:
        d = datetime.strptime(gun_str, "%Y-%m-%d").date()
        return (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def cift_id(u1, u2):
    a, b = sorted([str(u1).strip().lower(), str(u2).strip().lower()])
    return f"{a}__{b}"


def cift_kullanicilar(pair_id):
    parcalar = str(pair_id).split("__")
    if len(parcalar) == 2:
        return parcalar[0], parcalar[1]
    return "", ""


def seri_gorunum_durumu(kayit, bugun):
    kayit = kayit if isinstance(kayit, dict) else {}
    ham_sayi = int(kayit.get("sayi") or 0)
    son_gun = str(kayit.get("sonSayilanGun") or "")
    a_gun = str(kayit.get("a_gun") or "")
    b_gun = str(kayit.get("b_gun") or "")
    dun = onceki_gun_str(bugun)
    onceki_iki = onceki_gun_str(dun)

    a_yazdi = (a_gun == bugun)
    b_yazdi = (b_gun == bugun)
    bugun_tamam = (son_gun == bugun) or (a_yazdi and b_yazdi)

    if son_gun == bugun:
        etkin_sayi = ham_sayi
        riskli = False
        kayboldu_bugun = False
    elif son_gun == dun:
        etkin_sayi = ham_sayi
        riskli = (etkin_sayi >= 2) and not (a_yazdi and b_yazdi)
        kayboldu_bugun = False
    else:
        etkin_sayi = 0
        riskli = False
        kayboldu_bugun = (ham_sayi >= 2 and son_gun == onceki_iki)

    return {
        "sayi": etkin_sayi,
        "gorunur": etkin_sayi >= 2,
        "riskli": riskli,
        "kayboldu_bugun": kayboldu_bugun,
        "eski_sayi": ham_sayi if kayboldu_bugun else 0,
        "bugun_tamam": bugun_tamam,
        "a_yazdi": a_yazdi,
        "b_yazdi": b_yazdi,
    }


def sessiz_saat_mi(dt, son_sans_izin=False):
    dakika = dt.hour * 60 + dt.minute
    if son_sans_izin and 23 * 60 <= dakika < 23 * 60 + 30:
        return False
    return dakika >= (23 * 60 + 30) or dakika < (8 * 60 + 30)


SERI_RISK_20 = [
    "🔥 {arkadas} ile {sayi} günlük serin bugün henüz tamamlanmadı! Bir selam yaz, ateş sönmesin 💬",
    "⏳ {arkadas} ile {sayi} günlük seriniz seni bekliyor! Günün bitmesine saatler kala bir mesaj at ✨",
    "👋 Hey! {arkadas} ile {sayi} günlük seriyi korumak için bugün bir mesaj yazmayı unutma 🔥",
]

SERI_RISK_22 = [
    "⚠️ {arkadas} ile {sayi} günlük serin tehlikede! Saat 22:00 oldu, hemen bir mesaj yaz 🔥",
    "🚨 Ateş sönmek üzere! {arkadas} ile {sayi} günlük serini kurtarmak için son 2 saat ⏳",
    "🔥 {sayi} günlük emek boşa gitmesin! {arkadas} ile sohbete hemen bir mesaj bırak 💬",
]

SERI_RISK_2315 = [
    "🆘 SON ŞANS! {arkadas} ile {sayi} günlük serin gece yarısında sıfırlanacak! Hemen yaz 🔥⏳",
    "⏰ Gece yarısına 45 dakika kaldı! {arkadas} ile {sayi} günlük serini kurtarmak için son çağrı 🚨",
    "🔥⏳ {arkadas} ile {sayi} günlük serin kaybolmak üzere! Şimdi 1 mesaj at, seriyi kurtar!",
]

SERI_KAYBOLDU_HAVUZU = [
    "💔 {arkadas} ile {eski} günlük seriniz dün tamamlanmadığı için sıfırlandı. Bugün yeni bir seri başlat! 🔥",
    "🕯️ {arkadas} ile {eski} günlük ateş söndü... Ama üzülme, bugün yazışarak yeni bir rekor kırabilirsiniz! 💪",
    "😢 {arkadas} ile {eski} günlük seriniz sona erdi. Hemen bir mesaj atıp yeniden 1. günden başlayın! ✨",
]

BEKLEYEN_ARKADAS_HAVUZU = [
    "💬 {arkadas} bugün sana yazdı ve cevabını bekliyor! Hem sohbet et hem seriyi ilerlet 🔥",
    "👀 {arkadas} özel sohbette senden mesaj bekliyor! Cevap ver, bugünün serisi tamamlansın ✨",
]

HAFTALIK_OZET_HAVUZU = [
    "🏆 Haftalık Seri Özeti: {aktif} aktif serin var, en uzun serin {rekor} gün 🔥 Harika gidiyorsun!",
    "🔥 Bu haftayı {aktif} aktif sohbet serisi ve {rekor} günlük rekorla kapatıyorsun! Alevler hiç sönmesin 🚀",
]


def degerlendir(veri, simdi_dt, rng=None):
    rng = rng or random
    dt = istanbul_simdi(simdi_dt)
    bugun_iso = dt.strftime("%Y-%m-%d")
    bugun_tr = dt.strftime("%d.%m.%Y")
    saat = dt.hour
    dakika = dt.minute
    toplam_dk = saat * 60 + dakika

    veri = veri if isinstance(veri, dict) else {}
    users = veri.get("users") if isinstance(veri.get("users"), dict) else {}
    seriler = veri.get("seri") if isinstance(veri.get("seri"), dict) else {}

    bildirimler = []

    def ekle(kul, konu, baslik, mesaj, oncelik, log_key, kategori, son_sans=False):
        if not konu:
            return
        if sessiz_saat_mi(dt, son_sans_izin=son_sans):
            return
        u_obj = users.get(kul) or {}
        b_ayar = u_obj.get("bildirim") if isinstance(u_obj.get("bildirim"), dict) else {}
        if not b_ayar.get("aktif", True):
            return
        if not b_ayar.get(kategori, True):
            return
        loglar = u_obj.get("bildirim_log") if isinstance(u_obj.get("bildirim_log"), dict) else {}
        if loglar.get(log_key):
            return
        bildirimler.append({
            "kullanici": kul,
            "konu": konu,
            "baslik": baslik,
            "mesaj": mesaj,
            "oncelik": oncelik,
            "log_anahtari": log_key,
            "kategori": kategori,
        })

    for kul, u in sorted(users.items()):
        if not isinstance(u, dict):
            continue
        b_ayar = u.get("bildirim") if isinstance(u.get("bildirim"), dict) else {}
        konu = b_ayar.get("konu", "")
        if not konu or not b_ayar.get("aktif", True):
            continue

        if 8 * 60 + 45 <= toplam_dk <= 10 * 60:
            ekle(kul, konu, "☀️ Günaydın Şampiyon!",
                 "Bugünün planına göz atıp ilk görevinle güne harika bir başlangıç yap! 🚀",
                 3, f"sabah_{bugun_iso}", "sabah")

        hedef_saat = int(b_ayar.get("baslama", 11) or 11)
        gun = u.get("gun") if isinstance(u.get("gun"), dict) else {}
        basladi_mi = (gun.get("tarih") == bugun_tr and bool(gun.get("baslama")))
        if saat >= hedef_saat and not basladi_mi and toplam_dk < 22 * 60:
            ekle(kul, konu, "⏰ Derse Başlama Zamanı!",
                 f"Hedef saatin ({hedef_saat:02d}:00) geçti ama kronometre henüz açılmadı. Hadi masaya! 📚",
                 4, f"ders_{bugun_iso}", "ders")

        su = u.get("su") if isinstance(u.get("su"), dict) else {}
        bardak = int(su.get("bardak", 0) or 0) if su.get("tarih") == bugun_tr else 0
        if 14 <= saat < 16 and bardak < 4:
            ekle(kul, konu, "💧 Su İçmeyi Unutma!",
                 f"Bugün şu ana kadar {bardak}/8 bardak su içtin. Bir bardak suyla zihnini tazele! 🚰",
                 3, f"su14_{bugun_iso}", "su")
        elif 18 <= saat < 20 and bardak < 6:
            ekle(kul, konu, "💧 Su Hedefine Az Kaldı!",
                 f"Bugün {bardak}/8 bardaktasın. Akşam çalışması öncesi suyunu içmeyi unutma! 💧",
                 3, f"su18_{bugun_iso}", "su")

        gunlukler = u.get("gunluk") or []
        if isinstance(gunlukler, dict):
            gunlukler = list(gunlukler.values())
        bugun_kayitli = any(isinstance(g, dict) and g.get("tarih") == bugun_tr for g in gunlukler)
        if 21 * 60 + 30 <= toplam_dk <= 23 * 60 and not bugun_kayitli:
            ekle(kul, konu, "🌙 Gün Sonunu Kaydet",
                 "Bugünkü çalışmanı ve performansını kaydedip günü huzurla kapatmayı unutma 💖",
                 3, f"gunsonu_{bugun_iso}", "gunsonu")

    risk_seviye = None
    if 20 * 60 <= toplam_dk < 22 * 60:
        risk_seviye = ("20", SERI_RISK_20, 3, False)
    elif 22 * 60 <= toplam_dk < 23 * 60 + 10:
        risk_seviye = ("22", SERI_RISK_22, 4, False)
    elif 23 * 60 + 10 <= toplam_dk < 23 * 60 + 30:
        risk_seviye = ("2315", SERI_RISK_2315, 5, True)

    kullanici_aktif_seriler = {}

    for pid, kayit in sorted(seriler.items()):
        if not isinstance(kayit, dict):
            continue
        u_a, u_b = cift_kullanicilar(pid)
        if not u_a or not u_b:
            continue
        durum = seri_gorunum_durumu(kayit, bugun_iso)
        sayi = durum["sayi"]

        if sayi >= 2:
            kullanici_aktif_seriler.setdefault(u_a, []).append(sayi)
            kullanici_aktif_seriler.setdefault(u_b, []).append(sayi)

        if durum["riskli"] and risk_seviye is not None:
            kod, havuz, oncelik, son_sans = risk_seviye
            for hedef, diger, yazdi in ((u_a, u_b, durum["a_yazdi"]), (u_b, u_a, durum["b_yazdi"])):
                if not yazdi and hedef in users:
                    konu = ((users[hedef].get("bildirim") or {}).get("konu") or "")
                    sablon = rng.choice(havuz)
                    mesaj = sablon.format(arkadas=diger, sayi=sayi)
                    baslik = "🆘 Serin Kaybolmak Üzere!" if kod == "2315" else "🔥 Serin Tehlikede!"
                    ekle(hedef, konu, baslik, mesaj, oncelik,
                         f"seri_risk_{kod}_{pid}_{bugun_iso}", "sosyal_seri", son_sans=son_sans)

        if durum["kayboldu_bugun"] and 9 * 60 <= toplam_dk <= 12 * 60:
            eski = durum["eski_sayi"]
            for hedef, diger in ((u_a, u_b), (u_b, u_a)):
                if hedef in users:
                    konu = ((users[hedef].get("bildirim") or {}).get("konu") or "")
                    mesaj = rng.choice(SERI_KAYBOLDU_HAVUZU).format(arkadas=diger, eski=eski)
                    ekle(hedef, konu, "💔 Seri Kayboldu", mesaj, 3,
                         f"seri_kayip_{pid}_{bugun_iso}", "sosyal_seri")

        if 15 * 60 <= toplam_dk < 20 * 60 and (durum["a_yazdi"] ^ durum["b_yazdi"]):
            bekleyen = u_b if durum["a_yazdi"] else u_a
            yazan = u_a if durum["a_yazdi"] else u_b
            if bekleyen in users:
                konu = ((users[bekleyen].get("bildirim") or {}).get("konu") or "")
                mesaj = rng.choice(BEKLEYEN_ARKADAS_HAVUZU).format(arkadas=yazan)
                ekle(bekleyen, konu, f"💬 {yazan} Senden Cevap Bekliyor", mesaj, 3,
                     f"seri_bekliyor_{pid}_{bugun_iso}", "sosyal_seri")

    if dt.weekday() == 6 and 19 * 60 <= toplam_dk <= 20 * 60 + 30:
        for kul, s_list in sorted(kullanici_aktif_seriler.items()):
            if s_list and kul in users:
                konu = ((users[kul].get("bildirim") or {}).get("konu") or "")
                mesaj = rng.choice(HAFTALIK_OZET_HAVUZU).format(aktif=len(s_list), rekor=max(s_list))
                ekle(kul, konu, "🏆 Haftalık Seri Özeti", mesaj, 3,
                     f"seri_haftalik_{bugun_iso}", "sosyal_seri")

    return bildirimler


def calistir():
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    users = requests.get(f"{FIREBASE_URL}/users.json", timeout=10).json() or {}
    seriler = requests.get(f"{FIREBASE_URL}/seri.json", timeout=10).json() or {}
    simdi = istanbul_simdi()
    gonderilecekler = degerlendir({"users": users, "seri": seriler}, simdi)
    for b in gonderilecekler:
        try:
            r = requests.post(
                NTFY_SUNUCU,
                json={"topic": b["konu"], "title": b["baslik"], "message": b["mesaj"], "priority": b["oncelik"]},
                timeout=10,
            )
            r.raise_for_status()
            requests.patch(
                f"{FIREBASE_URL}/users/{b['kullanici']}/bildirim_log.json",
                json={b["log_anahtari"]: int(simdi.timestamp() * 1000)},
                timeout=10,
            )
        except Exception as ex:
            print(f"Bildirim gönderilemedi ({b['kullanici']}): {ex}")


if __name__ == "__main__":
    calistir()
