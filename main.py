import flet as ft
import random
import math
import time
import threading
import copy
import json
import os
import hashlib
import re
import asyncio
import io
import base64
from datetime import datetime, date, timedelta, timezone

# Firebase Realtime Database adresin (Console > Realtime Database sayfasının en üstünde yazar).
# Avrupa bölgesi seçtiysen şuna benzer olur: https://PROJE-default-rtdb.europe-west1.firebasedatabase.app
FIREBASE_URL = "https://yks-istasyonu-default-rtdb.firebaseio.com"
try:
    import requests
except ImportError:  # requests yoksa uygulama yine açılır, sadece Asistan çalışmaz
    requests = None

ISTANBUL_TZ = timezone(timedelta(hours=3))


# ==========================================
# SÜRÜM UYUMLULUK KATMANI
# (Flet'in eski ve yeni sürümlerinde aynı kod çalışsın diye)
# ==========================================
IKON_ALT = {
    "NIGHTLIGHT_ROUND": ("NIGHTLIGHT", "BEDTIME", "DARK_MODE"),
    "BEDTIME": ("NIGHTLIGHT", "DARK_MODE"),
    "ROCKET_LAUNCH_ROUNDED": ("ROCKET_LAUNCH", "ROCKET"),
    "SHOW_CHART_OUTLINED": ("SHOW_CHART", "INSERT_CHART_OUTLINED", "INSERT_CHART"),
    "GRID_VIEW_OUTLINED": ("GRID_VIEW", "APPS"),
    "TIMER_OUTLINED": ("TIMER", "ACCESS_TIME"),
    "HOME_OUTLINED": ("HOME",),
    "CALENDAR_MONTH_OUTLINED": ("CALENDAR_MONTH", "CALENDAR_TODAY", "EVENT"),
    "CALENDAR_MONTH": ("CALENDAR_TODAY", "EVENT"),
    "EMOJI_EMOTIONS": ("SENTIMENT_SATISFIED", "MOOD"),
    "SMART_TOY": ("ANDROID", "CHAT"),
    "SPORTS_ESPORTS": ("GAMEPAD", "VIDEOGAME_ASSET"),
    "ADMIN_PANEL_SETTINGS": ("SETTINGS", "SECURITY"),
    "CLEANING_SERVICES": ("DELETE_SWEEP", "DELETE"),
    "TRACK_CHANGES": ("GPS_FIXED", "TARGET"),
    "HOURGLASS_BOTTOM": ("HOURGLASS_EMPTY", "TIMER"),
    "REMOVE_CIRCLE_OUTLINE": ("REMOVE_CIRCLE", "REMOVE"),
    "ADD_CIRCLE": ("ADD", "ADD_CIRCLE_OUTLINE"),
    "STOP_CIRCLE": ("STOP",),
    "CIRCLE_OUTLINED": ("RADIO_BUTTON_UNCHECKED", "CIRCLE"),
    "LOCK_OUTLINE": ("LOCK",),
    "EVENT_AVAILABLE": ("EVENT", "CALENDAR_TODAY"),
    "EVENT_NOTE": ("EVENT", "NOTE"),
    "EDIT_NOTE": ("EDIT", "NOTE_ADD"),
    "WB_SUNNY": ("SUNNY", "LIGHT_MODE"),
    "GRID_3X3": ("GRID_ON", "GRID_VIEW"),
    "ARROW_BACK_IOS_NEW": ("ARROW_BACK_IOS", "ARROW_BACK"),
    "CARD_GIFTCARD": ("REDEEM", "CARD_GIFTCARD_OUTLINED"),
    "NOTIFICATIONS_ACTIVE": ("NOTIFICATIONS",),
    "WATER_DROP": ("WATER", "OPACITY"),
    "FORUM_OUTLINED": ("FORUM", "CHAT_BUBBLE_OUTLINE", "CHAT"),
    "FORUM": ("CHAT_BUBBLE", "CHAT"),
    "ADD_PHOTO_ALTERNATE": ("ADD_A_PHOTO", "ADD_PHOTO_ALTERNATE_OUTLINED", "IMAGE", "PHOTO"),
    "FAVORITE_BORDER": ("FAVORITE_OUTLINE", "FAVORITE"),
    "CHAT_BUBBLE_OUTLINE": ("CHAT_BUBBLE", "COMMENT", "CHAT"),
    "CHAT_BUBBLE": ("FORUM", "COMMENT", "CHAT"),
    "SEND": ("SEND_ROUNDED", "ARROW_FORWARD"),
    "PEOPLE": ("GROUP", "PERSON"),
    "LOCAL_FIRE_DEPARTMENT": ("WHATSHOT", "FIREPLACE", "BOLT", "STAR"),
    "EMOJI_EVENTS": ("WORKSPACE_PREMIUM", "MILITARY_TECH", "STAR"),
    "MARK_CHAT_UNREAD": ("CHAT_BUBBLE", "FORUM", "MAIL"),
    "PERSON_ADD": ("ADD_CIRCLE", "PERSON", "ADD"),
    "SEARCH": ("FIND_IN_PAGE", "FILTER_LIST"),
    "VOLUME_OFF": ("NOTIFICATIONS_OFF", "MUTE"),
    "VOLUME_UP": ("NOTIFICATIONS_ACTIVE", "NOTIFICATIONS"),
    "FLAG": ("OUTLINED_FLAG", "STOP_CIRCLE", "CLOSE"),
}


def ik(ad):
    """Ikon adini hangi Flet surumu olursa olsun bulur, bulamazsa benzerini/yedegini verir."""
    adaylar = (ad,) + IKON_ALT.get(ad, ()) + ("CIRCLE", "STAR")
    for kaynak_adi in ("Icons", "icons"):
        kaynak = getattr(ft, kaynak_adi, None)
        if kaynak is None:
            continue
        for a in adaylar:
            try:
                d = getattr(kaynak, a)
                if d is not None:
                    return d
            except Exception:
                pass
    return None


def opak(oran, renk_hex):
    """#AARRGGBB uretir (Flet surum farkindan bagimsiz)."""
    h = renk_hex.lstrip("#")
    if len(h) == 8:
        h = h[2:]
    return "#{:02X}{}".format(int(max(0.0, min(1.0, oran)) * 255), h)


KIRMIZI = "#EF5350"
YESIL = "#2ECC71"
TURUNCU = "#FF9800"
SEFFAF = "#00000000"
ORTA = ft.Alignment(0, 0)
UST_SOL = ft.Alignment(-1, -1)
ALT_SAG = ft.Alignment(1, 1)


def kenar(genislik, renk_):
    k = ft.BorderSide(genislik, renk_)
    return ft.Border(top=k, right=k, bottom=k, left=k)


def pad_only(left=0, top=0, right=0, bottom=0):
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def pad_sim(horizontal=0, vertical=0):
    return ft.Padding(left=horizontal, top=vertical, right=horizontal, bottom=vertical)


DUGME = getattr(ft, "ElevatedButton", None) or getattr(ft, "Button")


def dugme_olustur(metin, **kw):
    try:
        return DUGME(text=metin, **kw)
    except TypeError:
        return DUGME(content=metin, **kw)


def metin_dugmesi(metin, **kw):
    try:
        return ft.TextButton(text=metin, **kw)
    except TypeError:
        return ft.TextButton(content=metin, **kw)


def dd_secenek(metin):
    s_ = getattr(ft, "DropdownOption", None)
    return s_(metin) if s_ else ft.dropdown.Option(metin)


def dd_olustur(secenekler, deger, degisti, **kw):
    try:
        return ft.Dropdown(options=[dd_secenek(x) for x in secenekler], value=deger, on_select=degisti, **kw)
    except TypeError:
        return ft.Dropdown(options=[dd_secenek(x) for x in secenekler], value=deger, on_change=degisti, **kw)


FIT = getattr(ft, "BoxFit", None) or getattr(ft, "ImageFit", None)


def resim_olustur(b64, **kw):
    """Base64 resmi gösterir (Flet sürümüne göre src_base64 / src)."""
    if FIT is not None:
        kw.setdefault("fit", FIT.COVER)
    for ad in ("src_base64", "src"):
        try:
            return ft.Image(**{ad: b64}, **kw)
        except TypeError:
            continue
    return ft.Container(**{k: v for k, v in kw.items() if k in ("width", "height")})


def foto_hazirla(veri, maks=720, kalite=72):
    """Telefondan gelen fotoğrafı küçültüp base64'e çevirir. (b64, hata) döndürür."""
    try:
        from PIL import Image, ImageOps
    except Exception:
        Image = None
    if Image is not None:
        try:
            im = Image.open(io.BytesIO(veri))
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((maks, maks))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=kalite, optimize=True)
            return base64.b64encode(buf.getvalue()).decode("ascii"), ""
        except Exception as ex:
            return None, f"Fotoğraf işlenemedi: {ex}"
    if len(veri) <= 700_000:
        return base64.b64encode(veri).decode("ascii"), ""
    return None, "Fotoğraf çok büyük (Pillow paketi kurulu değil, küçültemedim)."


def yeni_id():
    return f"{int(time.time() * 1000):013d}{os.urandom(2).hex()}"


def zaman_oncesi(ms):
    fark = max(0, time.time() - sayi(ms) / 1000.0)
    if fark < 60:
        return "şimdi"
    if fark < 3600:
        return f"{int(fark // 60)} dk"
    if fark < 86400:
        return f"{int(fark // 3600)} sa"
    return f"{int(fark // 86400)} g"


def tarih_ms(gg_aa_yyyy):
    try:
        return datetime.strptime(gg_aa_yyyy.replace("-", "."), "%d.%m.%Y").timestamp() * 1000
    except Exception:
        return None


# ==========================================
# 0. AYARLAR (BURAYI KENDİNE GÖRE DÜZENLE)
# ==========================================
HEDEF_UNIVERSITE = "Güneş Üniversitesi Tıp Fakültesi"
HEDEF_TYT = 105.0
HEDEF_AYT = 64.0
YKS_TARIHI = datetime(2027, 6, 19, 10, 15)
PANEL_SIFRESI = "1905"
SPOTIFY_URL = "https://open.spotify.com/playlist/0zHr4z4SfUeKZOXv3rxVIV"

GROQ_API_KEY = ""
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-3.8-flash"

# ==========================================
# 1. TEMA VE VERİTABANI
# ==========================================
TEMA_RENKLERI = {
    "Gündüz Bahçesi 🌻": {"bg": "#FFF5F5", "card_bg": "#FFFFFF", "border": "#FFD1DC", "hdr": "#D6336C", "accent": "#FF8FAB", "muted": "#868E96", "gul_renk": "#FFB3C6", "gul_op": 0.5, "txt": "#495057", "mode": ft.ThemeMode.LIGHT},
    "Gece Moru 🌙": {"bg": "#1E1E24", "card_bg": "#2B2B36", "border": "#503080", "hdr": "#C084FC", "accent": "#E9D5FF", "muted": "#94A3B8", "gul_renk": "#3B2859", "gul_op": 0.4, "txt": "#E2E8F0", "mode": ft.ThemeMode.DARK},
    "Doğa Yeşili 🌿": {"bg": "#F4F9F4", "card_bg": "#FFFFFF", "border": "#B7E4C7", "hdr": "#2D6A4F", "accent": "#52B788", "muted": "#718096", "gul_renk": "#B7E4C7", "gul_op": 0.5, "txt": "#2B3E34", "mode": ft.ThemeMode.LIGHT},
    "Coffee Latte ☕": {"bg": "#FDF6EC", "card_bg": "#FFFFFF", "border": "#DDBEA9", "hdr": "#7F5539", "accent": "#B08968", "muted": "#A0AEC0", "gul_renk": "#DDBEA9", "gul_op": 0.5, "txt": "#4A3525", "mode": ft.ThemeMode.LIGHT},
    "Kozmik Galaksi 🌌": {"bg": "#0D0914", "card_bg": "#1A1429", "border": "#2A2240", "hdr": "#8B5CF6", "accent": "#00E5FF", "muted": "#8A849C", "gul_renk": "#1E3A8A", "gul_op": 0.3, "txt": "#F8F9FA", "mode": ft.ThemeMode.DARK},
    "Sakura Pembe 🌸": {"bg": "#FFF0F3", "card_bg": "#FFFFFF", "border": "#FFB3C1", "hdr": "#FF4D6D", "accent": "#FF758F", "muted": "#A0AEB0", "gul_renk": "#FFB3C1", "gul_op": 0.6, "txt": "#590D22", "mode": ft.ThemeMode.LIGHT}
}
VARSAYILAN_TEMA = "Kozmik Galaksi 🌌"

HAFTALIK_PLAN = {
    "Pazartesi": [{"gorev": "Matematik (Türev) - 2 Saat", "bitti": False}, {"gorev": "Paragraf - 30 Soru", "bitti": False}],
    "Salı": [{"gorev": "Fizik (Elektrik) - 1.5 Saat", "bitti": False}, {"gorev": "Geometri - 40 Soru", "bitti": False}],
    "Çarşamba": [{"gorev": "Türkçe (Dil Bilgisi) - 1 Saat", "bitti": False}, {"gorev": "Biyoloji (Hücre) - 1 Saat", "bitti": False}],
    "Perşembe": [{"gorev": "Kimya (Organik) - 2 Saat", "bitti": False}, {"gorev": "Problem - 20 Soru", "bitti": False}],
    "Cuma": [{"gorev": "TYT Genel Denemesi", "bitti": False}, {"gorev": "Deneme Analizi", "bitti": False}],
    "Cumartesi": [{"gorev": "AYT Matematik", "bitti": False}, {"gorev": "Dinlenme", "bitti": False}],
    "Pazar": [{"gorev": "Haftalık Tekrar", "bitti": False}, {"gorev": "Kelime Ezberi", "bitti": False}]
}
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

KONULAR = {
    "Türkçe": [
        "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam", "Anlatım Biçimleri", "Ses Bilgisi",
        "Yazım Kuralları", "Noktalama İşaretleri", "Sözcükte Yapı", "Sözcük Türleri",
        "Edat-Bağlaç-Ünlem", "Fiil-Ek Fiil", "Fiilimsi", "Fiilde Çatı", "Deyim ve Atasözü",
        "Cümlenin Öğeleri", "Cümle Türleri", "Anlatım Bozuklukları",
    ],
    "Matematik": [
        "Temel Kavramlar", "Sayı Basamakları", "Bölme ve Bölünebilme", "EBOB-EKOK",
        "Rasyonel Sayılar-Ondalık Sayılar", "Basit Eşitsizlikler", "Mutlak Değer", "Üslü Sayılar",
        "Köklü Sayılar", "Çarpanlara Ayırma", "Oran Orantı", "Denklem Çözme", "Problemler",
        "Kümeler-Kartezyen Çarpımı", "Fonksiyonlar", "Permütasyon", "Kombinasyon", "Binom",
        "Olasılık", "İstatistik", "2. Dereceden Denklemler", "Karmaşık Sayılar", "Polinomlar",
        "Mantık", "Veri Analizi",
    ],
    "Geometri": [
        "Doğruda ve Üçgende Açılar", "Üçgende Açı-Kenar Bağıntıları", "Üçgende Benzerlik",
        "Üçgende Açıortay-Kenarortay", "Dik Üçgen", "İkizkenar Üçgen", "Eşkenar Üçgen",
        "Üçgende Alan", "Çokgenler", "Dörtgenler", "Yamuk-Paralelkenar", "Eşkenar Dörtgen",
        "Dikdörtgen", "Kare", "Deltoid", "Çemberde Açı", "Çemberde Uzunluk",
        "Dairenin Çevresi ve Alanı", "Doğrunun Analitik İncelenmesi",
        "Çemberin Analitik İncelenmesi", "Katı Cisimler",
    ],
    "Tarih": [
        "Tarih Bilimine Giriş", "Uygarlığın Doğuşu ve İlk Uygarlıklar", "İlk Türk Devletleri",
        "İslam Tarihi ve Uygarlığı", "Türk-İslam Devletleri", "Türkler'in İslamiyeti Kabulü",
        "Türkiye Tarihi", "Beylikten Devlete (1300-1453)", "Dünya Gücü: Osmanlı Devleti",
        "Osmanlı Duraklama Dönemi", "Gerileme Devri (1699 – 1792)", "Arayış Yılları (17. Yüzyıl)",
        "Avrupa ve Osmanlı Devleti (18. Yüzyıl)", "En Uzun Yüzyıl (1800-1922)",
        "20. Yüzyıl Başlarında Osmanlı Devleti", "XIX. YY Osmanlı Devleti", "1. Dünya Savaşı",
        "Kurtuluş Savaşında Cepheler", "Türk İnkılabı", "Atatürkçülük ve Atatürk İlkeleri",
        "Türk Dış Politikası",
    ],
    "Coğrafya": [
        "İnsan ve Doğa", "Dünya'nın Şekli ve Hareketleri", "Coğrafi Konum", "Harita Bilgisi",
        "Atmosfer ve Sıcaklık", "İklimler", "Basınç ve Rüzgarlar", "Nem, Yağış ve Buharlaşma",
        "İç Kuvvetler / Dış Kuvvetler", "Su – Toprak ve Bitkiler", "Nüfus-Göç-Yerleşme",
        "Türkiye'nin Yer Şekilleri", "Ekonomik Faaliyetler", "Bölgeler ve Ülkeler",
        "Uluslararası Ulaşım Hatları", "Çevre ve Toplum", "Doğal Afetler",
    ],
    "Fizik": [
        "Fizik Bilimine Giriş", "Madde ve Özellikleri", "Kuvvet ve Hareket", "İş, Güç ve Enerji",
        "Isı, Sıcaklık ve Genleşme", "Basınç", "Kaldırma Kuvveti", "Elektrik ve Manyetizma",
        "Dalgalar", "Optik",
    ],
    "Kimya": [
        "Kimya Bilimi", "Atom ve Periyodik Sistem", "Kimyasal Türler Arası Etkileşimler",
        "Maddenin Halleri", "Doğa ve Kimya", "Kimyanın Temel Kanunları", "Karışımlar",
        "Asitler-Bazlar ve Tuzlar", "Kimya Her Yerde",
    ],
    "Biyoloji": [
        "Yaşam Bilimi Biyoloji", "Hücre", "Canlılar Dünyası", "Hücre Bölünmeleri ve Üreme",
        "Kalıtımın Genel İlkeleri", "Ekosistem Ekolojisi",
    ],
    "Felsefe": [
        "Felsefe'nin Alanı", "Bilgi Felsefesi", "Bilim Felsefesi", "Varlık Felsefesi",
        "Ahlak Felsefesi", "Siyaset Felsefesi", "Sanat Felsefesi", "Din Felsefesi",
    ],
    "Din Kültürü": [
        "İnsan ve Din (İnanç)", "İbadet", "Hz. Muhammed'in Hayatı", "Vahiy ve Akıl",
        "İslam Düşüncesi ve Yorumu", "İslamda Değerler, Sanat ve Laiklik", "Yaşayan Dinler",
    ],
}

SURPRIZ_NOTLARI = [
    "Bütün emeklerinin karşılığını fazlasıyla alacaksın!",
    "Şu an yorulduğunu biliyorum ama hayallerine çok yakınsın. ❤️",
    "Seninle ne kadar gurur duyduğumu kelimelerle anlatamam!",
    "Kahveni yudumla, derin bir nefes al. Üstesinden geleceksin!",
    "Arda arkanda! Ne zaman yorulsan buradayım.",
]

PERFORMANS = [
    ("😞", "Çok kötü"), ("😕", "İdare eder"), ("😐", "Normal"), ("🙂", "İyi"), ("🤩", "Harika"),
]
GUN_KISA = [g[:3] for g in GUNLER]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

VARSAYILAN_BILDIRIM = {
    "aktif": True,
    "konu": "",
    "baslama": 11,
    "su": True,
    "ders": True,
    "gunsonu": True,
    "sabah": True,
    "sosyal_foto": True,
    "sosyal_genel": True,
    "genel_sessiz": False,
    "genel_ilk_sonrasi_sessiz": True,
    "sosyal_dm": True,
    "sosyal_oyun": True,
    "sosyal_etkilesim": True,
    "sosyal_seri": True,
}

VARSAYILAN_VERI = {
    "tema": VARSAYILAN_TEMA,
    "hesap": None,         # {"kullanici", "tuz", "ozet"}
    "oturum": False,       # giriş yapılmış mı (uygulama kapanınca hatırlanır)
    "plan": HAFTALIK_PLAN,
    "todo": [],            # {"gorev", "bitti"}
    "su": {"tarih": "", "bardak": 0},
    "netler": [],          # {"ad", "sinav", "tr", "mat", "sos", "fen", "toplam"}
    "konu_bitti": [],      # "Ders|Konu"
    "kumbara": [],         # {"eksik", "bitti"}
    "gunluk": [],          # {"tarih", "baslama", "bitis", "saat", "sn", "performans", "gunluk"}
    "ozel_gorevler": [],   # {"gorev", "odul", "durum"}
    "calisma_sn": {},      # {"gg.aa.yyyy": saniye}  (kronometreden)
    "calisma_log": {},     # eski sürümden kalan {"gg.aa.yyyy": dakika}
    "gun": {"tarih": "", "baslama": ""},   # günün ilk kronometre başlangıcı
    "sinyal": {"aktif": False, "mesaj": ""},
    "bildirim": VARSAYILAN_BILDIRIM,
    "son_aktif": 0,        # son uygulama açılışı (ms), pasif hesapları bulmak için
    "acilan_oduller": [],  # ilk kez açıldığında kutlama yapılan başarım kimlikleri
    "aktif_ekran": "",     # "genel", "dm:pairId", "oyun:gameId" vb. (açık ekranda bildirim susturmak için)
}


# ==========================================
# 2. YARDIMCI FONKSİYONLAR
# ==========================================
def bugun_str():
    return date.today().strftime("%d.%m.%Y")


def sayi(deger, varsayilan=0.0):
    try:
        return float(str(deger).replace(",", ".").strip())
    except (ValueError, TypeError):
        return varsayilan


def okunur_renk(hex_renk):
    h = hex_renk.lstrip("#")
    r_, g_, b_ = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#1A1A1A" if (0.299 * r_ + 0.587 * g_ + 0.114 * b_) > 150 else "#FFFFFF"


def karistir(h1, h2, t):
    """h1 rengine h2'yi t oranında (0-1) karıştırır."""
    a, b = h1.lstrip("#"), h2.lstrip("#")
    c = [int(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4)]
    return "#{:02X}{:02X}{:02X}".format(*c)


def sn_metni(sn):
    sn = int(sn)
    s, d = sn // 3600, (sn % 3600) // 60
    return f"{s} sa {d} dk" if s else f"{d} dk"


def sn_kisa(sn):
    sn = int(sn)
    s, d = sn // 3600, (sn % 3600) // 60
    return f"{s}s {d}dk" if s else f"{d} dk"


def sifre_ozeti(sifre, tuz):
    return hashlib.sha256((tuz + sifre).encode("utf-8")).hexdigest()


def depo_dosyasi():
    """Yazilabilen ilk klasoru secer (mobilde uygulama klasoru salt-okunur olabilir)."""
    import tempfile
    adaylar = [os.environ.get("FLET_APP_STORAGE_DATA"), os.environ.get("FLET_APP_STORAGE_TEMP"),
               os.path.expanduser("~"), os.path.dirname(os.path.abspath(__file__)), tempfile.gettempdir()]
    for klasor in adaylar:
        if not klasor:
            continue
        try:
            os.makedirs(klasor, exist_ok=True)
            sinama = os.path.join(klasor, ".yazma_testi")
            with open(sinama, "w") as f:
                f.write("1")
            os.remove(sinama)
            return os.path.join(klasor, "yks_asistan_veri.json")
        except Exception:
            continue
    return "yks_asistan_veri.json"


# ==========================================
# FIREBASE YARDIMCILARI
# ==========================================
BULUT_ANAHTARLARI = [k for k in VARSAYILAN_VERI if k != "oturum"]
TARIHLI_ANAHTARLAR = ("calisma_sn", "calisma_log")   # içindeki anahtarlar "07.11.2026" gibi tarih
LISTE_ANAHTARLARI = ("todo", "netler", "konu_bitti", "kumbara", "gunluk", "ozel_gorevler", "acilan_oduller")


def bulut_hazirla(anahtar, deger):
    """Firebase anahtarlarında '.' olamaz. Tarihleri 07.11.2026 -> 07-11-2026 yapar."""
    if anahtar in TARIHLI_ANAHTARLAR and isinstance(deger, dict):
        return {k.replace(".", "-"): v for k, v in deger.items()}
    return deger


def bulut_coz(anahtar, deger):
    if anahtar in TARIHLI_ANAHTARLAR and isinstance(deger, dict):
        return {k.replace("-", "."): v for k, v in deger.items()}
    return deger


def listeye(x):
    """Firebase bazen listeyi {"0":..,"2":..} sözlüğüne çevirir, boş listeyi hiç göndermez."""
    if isinstance(x, dict):
        try:
            x = [x[k] for k in sorted(x, key=lambda i: int(i))]
        except (ValueError, TypeError):
            x = list(x.values())
    if not isinstance(x, list):
        return []
    return [i for i in x if i is not None]


def db_hazirla(ham):
    """Firebase'den (veya dosyadan) gelen ham veriyi eksiksiz bir DB sözlüğüne çevirir.
    Firebase boş liste/sözlükleri sakladığı için bu adım olmadan KeyError alırdık."""
    ham = ham if isinstance(ham, dict) else {}
    db = {}
    for k, varsayilan in VARSAYILAN_VERI.items():
        d = bulut_coz(k, ham.get(k))
        db[k] = d if d is not None else copy.deepcopy(varsayilan)
    for k in LISTE_ANAHTARLARI:
        db[k] = listeye(db[k])
    if not isinstance(db["plan"], dict):
        db["plan"] = copy.deepcopy(HAFTALIK_PLAN)
    for g in GUNLER:
        db["plan"][g] = listeye(db["plan"].get(g))
    for k in ("su", "gun", "sinyal", "bildirim", "calisma_sn", "calisma_log"):
        if not isinstance(db[k], dict):
            db[k] = copy.deepcopy(VARSAYILAN_VERI[k])
    b_ = copy.deepcopy(VARSAYILAN_BILDIRIM)
    b_.update(db["bildirim"])
    db["bildirim"] = b_
    if db["tema"] not in TEMA_RENKLERI:
        db["tema"] = VARSAYILAN_TEMA
    return db


def bulut_oku(kullanici=None):
    """Bir kullanıcının verisini (yoksa None), kullanici=None ise tüm kullanıcıları okur."""
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    yol = f"{FIREBASE_URL}/users/{kullanici}.json" if kullanici else f"{FIREBASE_URL}/users.json"
    r = requests.get(yol, timeout=10)
    r.raise_for_status()
    return r.json()


NTFY_SUNUCU = "https://ntfy.sh"   # bildirimleri telefona ulaştıran ücretsiz servis (ntfy uygulaması)


def bulut_get(yol, params=None):
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    r = requests.get(f"{FIREBASE_URL}/{yol}.json", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def bulut_sil(yol):
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    r = requests.delete(f"{FIREBASE_URL}/{yol}.json", timeout=10)
    r.raise_for_status()


def bulut_patch(yol, veri):
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    r = requests.patch(f"{FIREBASE_URL}/{yol}.json", json=veri, timeout=10)
    r.raise_for_status()


def ntfy_gonder(konu, baslik, mesaj, oncelik=3):
    """Telefona gerçek (uygulama kapalıyken de gelen) bildirim yollar. (başarılı_mı, hata) döndürür."""
    if requests is None:
        return False, "'requests' paketi yüklü değil"
    if not konu:
        return False, "bildirim konusu yok"
    try:
        r = requests.post(NTFY_SUNUCU, json={"topic": konu, "title": baslik, "message": mesaj, "priority": oncelik},
                          timeout=10)
        r.raise_for_status()
        return True, ""
    except Exception as ex:
        return False, str(ex)


def bulut_guncelle(kullanici, veri):
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    r = requests.patch(f"{FIREBASE_URL}/users/{kullanici}.json", json=veri, timeout=10)
    r.raise_for_status()


def ai_sor(soru):
    """Önce Groq, olmazsa Gemini. (cevap, servis, hatalar) döndürür."""
    prompt = (
        "Sen YKS sınavına hazırlanan Sude adında bir öğrenciye destek olan ve ismi Arda olan "
        f"profesyonel bir rehberlik asistanısın. Sude sana şunu sordu: '{soru}'. "
        "Sude'ye motive edici, çok tatlı, samimi, pratik ve eğitici bir cevap ver (maksimum 3-4 cümle)."
    )
    hatalar = []
    if GROQ_API_KEY:
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300},
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                timeout=30,
            )
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"], "Groq", hatalar
            hatalar.append(f"🔴 Groq Hatası: {res.text}")
        except Exception as ex:
            hatalar.append(f"🔴 Groq Sistem Hatası: {ex}")
    if GEMINI_API_KEY:
        try:
            res = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"], "Google Gemini", hatalar
            hatalar.append(f"🔵 Gemini Hatası: {res.text}")
        except Exception as ex:
            hatalar.append(f"🔵 Gemini Sistem Hatası: {ex}")
    return None, "", hatalar


# ==========================================
# 2b. SAF (PURE) ÖZEL SOHBET, SERİ (STREAK) VE BİLDİRİM MANTIĞI
# (Flet nesnesi kullanmaz, doğrudan birim testlerinde çağrılabilir)
# ==========================================
def istanbul_simdi(ts=None):
    """Europe/Istanbul (UTC+3) saat diliminde datetime döndürür."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=ISTANBUL_TZ)
        return ts.astimezone(ISTANBUL_TZ)
    if ts is None:
        return datetime.now(ISTANBUL_TZ)
    return datetime.fromtimestamp(float(ts), tz=ISTANBUL_TZ)


def istanbul_bugun(ts=None):
    """Europe/Istanbul takvim gününü 'YYYY-MM-DD' biçiminde döndürür (noktasız, sıralanabilir)."""
    return istanbul_simdi(ts).strftime("%Y-%m-%d")


def onceki_gun_str(gun_str):
    try:
        d = datetime.strptime(str(gun_str), "%Y-%m-%d").date()
        return (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def cift_id(u1, u2):
    """İki kullanıcı adını alfabetik sıralayıp '__' ile birleştirir."""
    a, b = sorted([str(u1).strip().lower(), str(u2).strip().lower()])
    return f"{a}__{b}"


def cift_kullanicilar(pair_id):
    parcalar = str(pair_id).split("__")
    if len(parcalar) == 2:
        return parcalar[0], parcalar[1]
    return "", ""


def seri_gorunum_durumu(kayit, bugun):
    """Seri kaydının bugünkü etkin durumunu döndürür.
    Bir gün atlanmışsa (sonSayilanGun < dün) etkin seri 0 olur.
    Seri 2. ardışık günden itibaren görünür (gorunur = etkin_sayi >= 2).
    """
    kayit = kayit if isinstance(kayit, dict) else {}
    ham_sayi = int(kayit.get("sayi") or 0)
    son_gun = str(kayit.get("sonSayilanGun") or "")
    a_gun = str(kayit.get("a_gun") or "")
    b_gun = str(kayit.get("b_gun") or "")
    dun = onceki_gun_str(bugun)

    a_yazdi = (a_gun == bugun)
    b_yazdi = (b_gun == bugun)

    if son_gun == bugun:
        etkin_sayi = ham_sayi
        riskli = False
    elif son_gun == dun:
        etkin_sayi = ham_sayi
        riskli = (etkin_sayi >= 2) and not (a_yazdi and b_yazdi)
    else:
        etkin_sayi = 0
        riskli = False

    return {
        "sayi": etkin_sayi,
        "gorunur": etkin_sayi >= 2,
        "riskli": riskli,
        "bugun_tamam": (son_gun == bugun) or (a_yazdi and b_yazdi),
        "a_yazdi": a_yazdi,
        "b_yazdi": b_yazdi,
    }


def seri_guncelle_pure(mevcut, gonderen, u1, u2, bugun):
    """Özel sohbette mesaj atıldığında seriyi güncelleyen saf ve idempotent fonksiyon.
    Döndürür: (yeni_kayit_dict, olay_str)
    olay_str: "" | "basladi" (2. gün) | "milestone_7" | "milestone_30" | "milestone_100" | "artti"
    Yarış (race condition) güvenliği:
    - a ve b kullanıcıları alfabetik sırayla belirlenir.
    - Her kullanıcı kendi alanını (a_gun veya b_gun) bugünün tarihiyle günceller.
    - Her iki taraf da bugün mesaj attıysa (a_gun == bugun ve b_gun == bugun):
      * sonSayilanGun zaten bugun ise sayi tekrar artırılmaz (idempotent).
      * sonSayilanGun == dün ise sayi 1 artırılır ve sonSayilanGun = bugun yapılır.
      * Aksi halde (ilk gün veya seri kopmuşsa) sayi = 1 ve sonSayilanGun = bugun yapılır.
    """
    mevcut = mevcut if isinstance(mevcut, dict) else {}
    a, b = sorted([str(u1).strip().lower(), str(u2).strip().lower()])
    gonderen = str(gonderen).strip().lower()
    dun = onceki_gun_str(bugun)

    eski_sayi = int(mevcut.get("sayi") or 0)
    son_gun = str(mevcut.get("sonSayilanGun") or "")
    a_gun = str(mevcut.get("a_gun") or "")
    b_gun = str(mevcut.get("b_gun") or "")

    # Eğer sonSayilanGun dünden daha eskiyse seri zaten kopmuştur
    if son_gun not in (bugun, dun):
        eski_sayi = 0

    if gonderen == a:
        a_gun = bugun
    elif gonderen == b:
        b_gun = bugun

    yeni_sayi = eski_sayi
    yeni_son_gun = son_gun
    olay = ""

    if a_gun == bugun and b_gun == bugun:
        if son_gun == bugun:
            # Bugün zaten sayılmış, tekrar artırma (idempotent)
            yeni_sayi = max(1, eski_sayi)
        elif son_gun == dun and eski_sayi >= 1:
            yeni_sayi = eski_sayi + 1
            yeni_son_gun = bugun
            if yeni_sayi == 2:
                olay = "basladi"
            elif yeni_sayi in (7, 30, 100):
                olay = f"milestone_{yeni_sayi}"
            else:
                olay = "artti"
        else:
            yeni_sayi = 1
            yeni_son_gun = bugun

    return {
        "sayi": yeni_sayi,
        "sonSayilanGun": yeni_son_gun,
        "a_gun": a_gun,
        "b_gun": b_gun,
    }, olay


def alev_rozeti(kayit, bugun):
    """Seri uzunluğuna göre büyüyen alev rozetini döndürür.
    2-6 gün: 🔥, 7-29 gün: 🔥🔥, 30-99 gün: 🔥🔥🔥, 100+ gün: 🔥🔥🔥🔥
    Risk altındaysa başına ⏳ ekler.
    Döndürür: (metin, gorunur, riskli, sayi)
    """
    d = seri_gorunum_durumu(kayit, bugun)
    sayi_ = d["sayi"]
    if sayi_ < 2:
        return "", False, False, sayi_
    if sayi_ >= 100:
        alev = "🔥🔥🔥🔥"
    elif sayi_ >= 30:
        alev = "🔥🔥🔥"
    elif sayi_ >= 7:
        alev = "🔥🔥"
    else:
        alev = "🔥"
    metin = f"⏳ {alev} {sayi_}" if d["riskli"] else f"{alev} {sayi_}"
    return metin, True, d["riskli"], sayi_


def sessiz_saat_mi(dt=None, son_sans_izin=False):
    """23:30 ile 08:30 arası sessiz saatlerdir."""
    dt = istanbul_simdi(dt)
    dk = dt.hour * 60 + dt.minute
    if son_sans_izin and 23 * 60 <= dk < 23 * 60 + 30:
        return False
    return dk >= (23 * 60 + 30) or dk < (8 * 60 + 30)


def sosyal_bildirim_karar(hedef_kullanici, gonderen, kategori, hedef_db, simdi_ms,
                          oran_durumu=None, beklenen_ekran=None, son_sans=False):
    """Sosyal bildirim gönderilip gönderilmeyeceğine karar veren saf fonksiyon.
    Döndürür: (gonderilsin_mi: bool, neden: str)
    """
    if not hedef_kullanici or hedef_kullanici == gonderen:
        return False, "kendi_islemi"
    hedef_db = hedef_db if isinstance(hedef_db, dict) else {}
    b_ayar = hedef_db.get("bildirim") if isinstance(hedef_db.get("bildirim"), dict) else {}
    if not b_ayar.get("aktif", True):
        return False, "bildirimler_kapali"
    konu = b_ayar.get("konu", "")
    if not konu:
        return False, "konu_yok"
    if not b_ayar.get(kategori, True):
        return False, f"kategori_kapali:{kategori}"

    dt = istanbul_simdi(simdi_ms / 1000.0)
    if sessiz_saat_mi(dt, son_sans_izin=son_sans):
        return False, "sessiz_saat"

    # Alıcı şu an ilgili sohbeti/oyunu açık tutuyorsa bildirim gönderme (son 45 sn içinde aktifse)
    aktif_ekran = str(hedef_db.get("aktif_ekran") or "")
    son_aktif = sayi(hedef_db.get("son_aktif"), 0)
    if beklenen_ekran and aktif_ekran == beklenen_ekran and (simdi_ms - son_aktif) < 120_000:
        return False, "ekran_acik"

    oran_durumu = oran_durumu if isinstance(oran_durumu, dict) else {}
    if kategori == "sosyal_genel":
        if b_ayar.get("genel_sessiz", False):
            return False, "genel_sessiz"
        # İlk bildirimden sonra kullanıcı genel sohbeti açana kadar sessize alma
        if b_ayar.get("genel_ilk_sonrasi_sessiz", True) and oran_durumu.get(f"genel_bekliyor:{hedef_kullanici}"):
            return False, "genel_ilk_sonrasi_sessiz"
        son_gonderim = sayi(oran_durumu.get(f"genel_oran:{gonderen}:{hedef_kullanici}"), 0)
        if son_gonderim and (simdi_ms - son_gonderim) < 300_000:  # 5 dakika
            return False, "genel_hiz_siniri"
        oran_durumu[f"genel_oran:{gonderen}:{hedef_kullanici}"] = simdi_ms
        oran_durumu[f"genel_bekliyor:{hedef_kullanici}"] = True

    if kategori == "sosyal_foto":
        son_foto = sayi(oran_durumu.get(f"foto_oran:{hedef_kullanici}"), 0)
        if son_foto and (simdi_ms - son_foto) < 180_000:  # 3 dakika içindeki fotoğrafları tek bildirimde birleştir
            return False, "foto_birlestirildi"
        oran_durumu[f"foto_oran:{hedef_kullanici}"] = simdi_ms

    return True, "ok"


# ==========================================
# 2c. SAF (PURE) 2 KİŞİLİK ONLINE OYUN MOTORU
# (XOX, Dört Bağlama, YKS Bilgi Düellosu, Taş-Kâğıt-Makas, Adam Asmaca)
# ==========================================
OYUN_TURLERI = {
    "xox": {"ad": "XOX Online", "emoji": "❌⭕", "aciklama": "3x3 klasik strateji kapışması"},
    "c4": {"ad": "Dört Bağlama", "emoji": "🔴🟡", "aciklama": "7x6 yerçekimli 4'lü dizme oyunu"},
    "yks_quiz": {"ad": "YKS Bilgi Düellosu", "emoji": "🧠⚡", "aciklama": "10 soruluk TYT bilgi ve hız yarışması"},
    "tkm": {"ad": "Taş-Kâğıt-Makas", "emoji": "✊✋✌️", "aciklama": "3 tur üzerinden eşzamanlı düello"},
    "adam": {"ad": "Adam Asmaca", "emoji": "🔤🎯", "aciklama": "Gizli Türkçe kelimeyi 6 hakta bul"},
}

# 64 Özgün YKS (TYT) Sorusu (Türkçe, Matematik, Sosyal, Fen)
TYT_SORU_BANKASI = [
    # TÜRKÇE (16 soru)
    {"ders": "Türkçe", "s": "Aşağıdaki cümlelerin hangisinde 'de/da' bağlacının yazımıyla ilgili bir yanlışlık yapılmıştır?", "sec": ["Kitabımı evde unutmuşum.", "Sen de mi bizimle geleceksin?", "Sokakta kimsecikler yoktu.", "Bize geldi de derdini anlatmadı."], "d": 0},
    {"ders": "Türkçe", "s": "'Gözden düşmek' deyiminin anlamı aşağıdakilerden hangisidir?", "sec": ["Görme yetisini yitirmek", "Değerini ve kendisine duyulan güveni kaybetmek", "Çok uzakta kalmak", "Beklenmedik bir anda ortaya çıkmak"], "d": 1},
    {"ders": "Türkçe", "s": "Aşağıdaki sözcüklerden hangisi ünlü düşmesine uğramıştır?", "sec": ["Kitapçık", "Gönlüm", "Yolculuk", "Gözlükçü"], "d": 1},
    {"ders": "Türkçe", "s": "'Sabahleyin sahilde yürürken serin rüzgâr yüzümüze çarpıyordu.' cümlesinde kaç tane fiilimsi (eylemsi) vardır?", "sec": ["1", "2", "3", "4"], "d": 0},
    {"ders": "Türkçe", "s": "Aşağıdaki cümlelerin hangisinde ünsüz yumuşamasına aykırılık gösteren bir sözcük vardır?", "sec": ["Ağacın dalları meyveyle doldu.", "Hukukun üstünlüğü herkes için şarttır.", "Kitabın kapağı çok güzelmiş.", "Yemeğin tuzu biraz az olmuş."], "d": 1},
    {"ders": "Türkçe", "s": "Hangisinde 'ki' eki bitişik yazılmalıdır?", "sec": ["Duydum ki unutmuşsun.", "Akşamki maç çok heyecanlıydı.", "Bilmem ki ne yapsak?", "Öyle güzel ki anlatamam."], "d": 1},
    {"ders": "Türkçe", "s": "'Soğuk bir kış günüydü.' cümlesinin yüklemi hangi sözcük grubundan oluşmuştur?", "sec": ["İsim tamlaması", "Sıfat tamlaması", "Birleşik fiil", "Edat grubu"], "d": 1},
    {"ders": "Türkçe", "s": "Aşağıdaki sözcüklerin hangisinde hem yapım hem çekim eki vardır?", "sec": ["Evlerden", "Gözlükçüler", "Masada", "Koşuyor"], "d": 1},
    {"ders": "Türkçe", "s": "Hangi cümlede neden-sonuç ilişkisi vardır?", "sec": ["Sınavı kazanmak için çok çalıştı.", "Yağmur yağdığından maç ertelendi.", "Seni görmeye geldim.", "Başarılı olmak üzere yola çıktı."], "d": 1},
    {"ders": "Türkçe", "s": "Aşağıdaki kelimelerden hangisinin yazımı doğrudur?", "sec": ["Herşey", "Birçok", "Hiç bir", "Herkez"], "d": 1},
    {"ders": "Türkçe", "s": "'Keskin' sözcüğü hangi cümlede mecaz anlamda kullanılmıştır?", "sec": ["Keskin bıçakla ekmeği dilimledi.", "Keskin bir zekâya sahipti.", "Camın keskin kenarı elini kesti.", "Balta oldukça keskindi."], "d": 1},
    {"ders": "Türkçe", "s": "İki nokta (:) aşağıdaki yerlerden hangisinde kullanılmaz?", "sec": ["Örnek verilecek cümlenin sonunda", "Açıklama yapılacak cümlenin sonunda", "Tamamlanmış cümlelerin en sonunda", "Karşılıklı konuşmalarda konuşan kişiden sonra"], "d": 2},
    {"ders": "Türkçe", "s": "'Güneş doğudan doğar, batıdan batar.' cümlesi anlatım açısından nasıl bir cümledir?", "sec": ["Öznel", "Nesnel", "Koşullu", "Varsayım"], "d": 1},
    {"ders": "Türkçe", "s": "Aşağıdaki cümlelerin hangisinde anlatım bozukluğu vardır?", "sec": ["Bahçedeki çiçekleri suladım.", "Yaklaşık üç yıl kadar burada çalıştı.", "Kitap okumayı çok seviyorum.", "Arkadaşımla sinemaya gittik."], "d": 1},
    {"ders": "Türkçe", "s": "'Kuşlar sıcak ülkelere göç etti.' cümlesinde özne aşağıdakilerden hangisidir?", "sec": ["Kuşlar", "Sıcak ülkelere", "Göç etti", "Ülkelere"], "d": 0},
    {"ders": "Türkçe", "s": "Aşağıdakilerden hangisi somut anlamlı bir sözcüktür?", "sec": ["Sevgi", "Rüzgâr", "Hayal", "Endişe"], "d": 1},
    # MATEMATİK & GEOMETRİ (16 soru)
    {"ders": "Matematik", "s": "3x - 7 = 14 denkleminde x kaçtır?", "sec": ["5", "6", "7", "8"], "d": 2},
    {"ders": "Matematik", "s": "Ardışık üç doğal sayının toplamı 48 ise en büyük sayı kaçtır?", "sec": ["15", "16", "17", "18"], "d": 2},
    {"ders": "Matematik", "s": "2^5 + 3^2 işleminin sonucu kaçtır?", "sec": ["39", "41", "43", "45"], "d": 1},
    {"ders": "Matematik", "s": "Bir aracın 60 km/sa hızla 4 saatte aldığı yolu 80 km/sa hızla kaç saatte alır?", "sec": ["2", "2,5", "3", "3,5"], "d": 2},
    {"ders": "Matematik", "s": "EBOB(24, 36) değeri kaçtır?", "sec": ["6", "8", "12", "18"], "d": 2},
    {"ders": "Matematik", "s": "Bir dik üçgenin dik kenarları 6 cm ve 8 cm ise hipotenüsü kaç cm'dir?", "sec": ["9", "10", "12", "14"], "d": 1},
    {"ders": "Matematik", "s": "%20'si 15 olan sayının tamamı kaçtır?", "sec": ["60", "70", "75", "80"], "d": 2},
    {"ders": "Matematik", "s": "f(x) = 2x + 5 olduğuna göre f(4) kaçtır?", "sec": ["11", "12", "13", "14"], "d": 2},
    {"ders": "Matematik", "s": "4 elemanlı bir kümenin alt küme sayısı kaçtır?", "sec": ["8", "12", "16", "32"], "d": 2},
    {"ders": "Matematik", "s": "Bir düzgün altıgenin bir iç açısı kaç derecedir?", "sec": ["108", "120", "135", "140"], "d": 1},
    {"ders": "Matematik", "s": "|x - 3| = 5 denklemini sağlayan x değerlerinin toplamı kaçtır?", "sec": ["0", "3", "6", "8"], "d": 2},
    {"ders": "Matematik", "s": "Hilesiz bir zar atıldığında üst yüze asal sayı gelme olasılığı nedir?", "sec": ["1/6", "1/3", "1/2", "2/3"], "d": 2},
    {"ders": "Matematik", "s": "kök(49) + kök(16) işleminin sonucu kaçtır?", "sec": ["9", "10", "11", "13"], "d": 2},
    {"ders": "Matematik", "s": "5! (5 faktöriyel) sayısı kaçtır?", "sec": ["60", "100", "120", "240"], "d": 2},
    {"ders": "Matematik", "s": "Yarıçapı 4 cm olan çemberin çevresi kaç pi cm'dir?", "sec": ["4", "6", "8", "16"], "d": 2},
    {"ders": "Matematik", "s": "x^2 - 9 = 0 denkleminin pozitif kökü kaçtır?", "sec": ["1", "3", "6", "9"], "d": 1},
    # SOSYAL BİLİMLER (16 soru)
    {"ders": "Tarih", "s": "Malazgirt Meydan Muharebesi hangi yılda gerçekleşmiştir?", "sec": ["1040", "1071", "1176", "1243"], "d": 1},
    {"ders": "Tarih", "s": "Türkiye Büyük Millet Meclisi hangi tarihte açılmıştır?", "sec": ["19 Mayıs 1919", "23 Nisan 1920", "29 Ekim 1923", "30 Ağustos 1922"], "d": 1},
    {"ders": "Tarih", "s": "İlk Türk devletlerinde devlet işlerinin görüşüldüğü meclise ne ad verilirdi?", "sec": ["Divan", "Kurultay (Toy)", "Pankuş", "Senato"], "d": 1},
    {"ders": "Tarih", "s": "Lozan Barış Antlaşması hangi yılda imzalanmıştır?", "sec": ["1920", "1921", "1922", "1923"], "d": 3},
    {"ders": "Coğrafya", "s": "Türkiye'de en fazla yağış alan kıyı bölgemiz hangisidir?", "sec": ["Akdeniz", "Ege", "Karadeniz", "Marmara"], "d": 2},
    {"ders": "Coğrafya", "s": "Dünya'nın kendi ekseni etrafındaki dönüşü kaç saatte tamamlanır?", "sec": ["12 saat", "24 saat", "30 gün", "365 gün"], "d": 1},
    {"ders": "Coğrafya", "s": "Aşağıdakilerden hangisi yenilenebilir enerji kaynaklarından biridir?", "sec": ["Taş kömürü", "Linyit", "Rüzgâr enerjisi", "Doğal gaz"], "d": 2},
    {"ders": "Coğrafya", "s": "Haritalarda eş yükselti eğrilerine ne ad verilir?", "sec": ["İzobar", "İzohips", "İzoterm", "İzobath"], "d": 1},
    {"ders": "Felsefe", "s": "'Düşünüyorum, öyleyse varım.' sözü hangi filozofa aittir?", "sec": ["Platon", "Descartes", "Kant", "Sokrates"], "d": 1},
    {"ders": "Felsefe", "s": "Felsefede varlığın ne olduğunu araştıran alt dal hangisidir?", "sec": ["Epistemoloji", "Ontoloji", "Etik", "Estetik"], "d": 1},
    {"ders": "Felsefe", "s": "Ahlak felsefesinin temel kavramlarından biri aşağıdakilerden hangisidir?", "sec": ["Güzellik", "İyi ve Kötü", "Doğruluk değeri", "Atom"], "d": 1},
    {"ders": "Felsefe", "s": "Bilginin kaynağının yalnızca akıl olduğunu savunan akım hangisidir?", "sec": ["Empirizm", "Rasyonalizm", "Pozitivizm", "Pragmatizm"], "d": 1},
    {"ders": "Din Kültürü", "s": "İslam'da zenginlerin yılda bir kez mallarının belirli bir kısmını ihtiyaç sahiplerine vermesine ne denir?", "sec": ["Sadaka-i cariye", "Zekât", "Fitre", "İnfak"], "d": 1},
    {"ders": "Din Kültürü", "s": "Allah'ın her şeyi bilmesi sıfatına ne ad verilir?", "sec": ["İlim", "Kudret", "İrade", "Tekvin"], "d": 0},
    {"ders": "Tarih", "s": "İstanbul'un Fethi hangi yılda gerçekleşmiştir?", "sec": ["1402", "1453", "1517", "1526"], "d": 1},
    {"ders": "Coğrafya", "s": "Ekvator'dan kutuplara doğru gidildikçe sıcaklık genel olarak nasıl değişir?", "sec": ["Artar", "Azalır", "Değişmez", "Önce artar sonra azalır"], "d": 1},
    # FEN BİLİMLERİ (16 soru)
    {"ders": "Fizik", "s": "Uluslararası birim sisteminde (SI) kuvvetin birimi nedir?", "sec": ["Joule", "Watt", "Newton", "Pascal"], "d": 2},
    {"ders": "Fizik", "s": "Sabit hızla hareket eden bir cismin ivmesi kaçtır?", "sec": ["0", "1", "9,8", "Hızına eşittir"], "d": 0},
    {"ders": "Fizik", "s": "Bir elektrik devresinde V = I . R bağıntısı hangi yasa olarak bilinir?", "sec": ["Faraday Yasası", "Ohm Yasası", "Coulomb Yasası", "Kirchhoff Yasası"], "d": 1},
    {"ders": "Fizik", "s": "Ses dalgaları aşağıdakilerden hangi ortamda yayılamaz?", "sec": ["Hava", "Su", "Boşluk (Vakum)", "Demir"], "d": 2},
    {"ders": "Kimya", "s": "Suyun (H2O) normal basınçta kaynama noktası kaç °C'dir?", "sec": ["0", "50", "100", "212"], "d": 2},
    {"ders": "Kimya", "s": "Atom numarası 6 ve kütle numarası 12 olan karbon atomunun nötron sayısı kaçtır?", "sec": ["4", "6", "12", "18"], "d": 1},
    {"ders": "Kimya", "s": "Oda sıcaklığında pH değeri 7'den küçük olan çözeltiler nasıl özellik gösterir?", "sec": ["Bazik", "Nötr", "Asidik", "Amfoter"], "d": 2},
    {"ders": "Kimya", "s": "Periyodik tabloda yatay sıralara ne ad verilir?", "sec": ["Grup", "Periyot", "Soygaz", "Katman"], "d": 1},
    {"ders": "Biyoloji", "s": "Ökaryot hücrede ATP üretiminin (oksijenli solunumun) gerçekleştiği organel hangisidir?", "sec": ["Ribozom", "Mitokondri", "Golgi", "Lizozom"], "d": 1},
    {"ders": "Biyoloji", "s": "Bitki hücrelerinde fotosentezin gerçekleştiği organel aşağıdakilerden hangisidir?", "sec": ["Kloroplast", "Sentrozom", "Koful", "Endoplazmik retikulum"], "d": 0},
    {"ders": "Biyoloji", "s": "DNA'da Adenin (A) bazının karşısına hangi baz gelir?", "sec": ["Guanin", "Sitozin", "Timin", "Urasil"], "d": 2},
    {"ders": "Biyoloji", "s": "Hücrede protein sentezinden sorumlu zarsız organel hangisidir?", "sec": ["Ribozom", "Lizozom", "Peroksizom", "Golgi"], "d": 0},
    {"ders": "Fizik", "s": "Bir cismin birim hacminin kütlesine ne ad verilir?", "sec": ["Ağırlık", "Özkütle (Yoğunluk)", "Basınç", "İvme"], "d": 1},
    {"ders": "Kimya", "s": "NaCl bileşiğinin yaygın adı aşağıdakilerden hangisidir?", "sec": ["Çamaşır sodası", "Yemek tuzu", "Kireç taşı", "Tuz ruhu"], "d": 1},
    {"ders": "Biyoloji", "s": "İnsanda vücut hücrelerinde kaç kromozom bulunur?", "sec": ["23", "44", "46", "48"], "d": 2},
    {"ders": "Fizik", "s": "Isı birimi olarak aşağıdakilerden hangisi kullanılır?", "sec": ["Kelvin", "Derece Celsius", "Kalori / Joule", "Amper"], "d": 2},
]

ADAM_KELIME_HAVUZU = [
    "PARAGRAF", "TÜREV", "İNTEGRAL", "MİTOKONDRİ", "FOTOSENTEZ",
    "CUMHURİYET", "İZOHİPS", "POLİNOM", "OLASILIK", "LOGARİTMA",
]

TR_HARFLER = list("ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")


def tr_buyuk(metin):
    """Türkçe karakter duyarlı büyük harfe çevirme (i->İ, ı->I)."""
    harita = str.maketrans({
        "i": "İ", "ı": "I", "ç": "Ç", "ğ": "Ğ", "ö": "Ö", "ş": "Ş", "ü": "Ü",
    })
    return str(metin or "").translate(harita).upper()


def oyun_baslangic_tahtasi(tur, oyuncular, tohum=None):
    """Seçilen oyun türü için başlangıç tahtası (JSON-safe, noktasız anahtarlar) oluşturur."""
    rng = random.Random(tohum) if tohum is not None else random
    if tur == "xox":
        return {"hucreler": [""] * 9, "kazananHat": []}
    if tur == "c4":
        return {"izgara": [["" for _ in range(7)] for _ in range(6)], "kazananDortlu": []}
    if tur == "yks_quiz":
        indisler = rng.sample(range(len(TYT_SORU_BANKASI)), 10)
        return {
            "sorular": indisler,
            "cevaplar": {"a": [], "b": []},
            "sureler": {"a": [], "b": []},
            "puanlar": {"a": 0, "b": 0},
            "dogrular": {"a": 0, "b": 0},
        }
    if tur == "tkm":
        return {
            "turNo": 1,
            "skor": {"a": 0, "b": 0},
            "secim": {"a": "", "b": ""},
            "gecmis": [],
        }
    if tur == "adam":
        return {
            "kelime": "",
            "maske": "",
            "tahminler": [],
            "yanlis": 0,
            "maksYanlis": 6,
            "asama": "kelime_bekliyor",
        }
    raise ValueError(f"Bilinmeyen oyun türü: {tur}")


def xox_hamle_yap(tahta, oyuncular, oyuncu, hucre):
    """XOX hamlesi uygular (saf fonksiyon).
    Döndürür: (gecerli_mi, hata_mesaji, yeni_tahta, sonraki_sira, bitti_mi, kazanan)
    """
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    sembol = "X" if oyuncu == a else "O"
    rakip = b if oyuncu == a else a
    hucreler = list(tahta.get("hucreler") or [""] * 9)
    if len(hucreler) < 9:
        hucreler += [""] * (9 - len(hucreler))
    if not isinstance(hucre, int) or not (0 <= hucre < 9):
        return False, "Geçersiz hücre seçimi!", tahta, oyuncu, False, ""
    if hucreler[hucre] != "":
        return False, "Bu kare zaten dolu!", tahta, oyuncu, False, ""

    hucreler[hucre] = sembol
    hatlar = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ]
    for x, y, z in hatlar:
        if hucreler[x] == hucreler[y] == hucreler[z] == sembol:
            return True, "", {"hucreler": hucreler, "kazananHat": [x, y, z]}, "", True, oyuncu
    if "" not in hucreler:
        return True, "", {"hucreler": hucreler, "kazananHat": []}, "", True, "berabere"
    return True, "", {"hucreler": hucreler, "kazananHat": []}, rakip, False, ""


def c4_hamle_yap(tahta, oyuncular, oyuncu, sutun):
    """Dört Bağlama (Connect 4 - 7x6) yerçekimli hamle ve 4 yönlü kazanan tespiti."""
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    sembol = "A" if oyuncu == a else "B"
    rakip = b if oyuncu == a else a
    ham_izgara = tahta.get("izgara") or []
    izgara = []
    for r_i in range(6):
        satir = list(ham_izgara[r_i]) if r_i < len(ham_izgara) and isinstance(ham_izgara[r_i], list) else []
        if len(satir) < 7:
            satir += [""] * (7 - len(satir))
        izgara.append(satir[:7])

    if not isinstance(sutun, int) or not (0 <= sutun < 7):
        return False, "Geçersiz sütun!", tahta, oyuncu, False, ""

    hedef_satir = -1
    for r_i in range(5, -1, -1):
        if izgara[r_i][sutun] == "":
            hedef_satir = r_i
            break
    if hedef_satir == -1:
        return False, "Bu sütun tamamen dolu!", tahta, oyuncu, False, ""

    izgara[hedef_satir][sutun] = sembol

    # 4 yönlü kontrol: yatay, dikey, sağ-alt çapraz, sağ-üst çapraz
    yonler = [(0, 1), (1, 0), (1, 1), (-1, 1)]
    for dr, dc in yonler:
        for r_i in range(6):
            for c_i in range(7):
                dortlu = []
                for adim in range(4):
                    nr, nc = r_i + dr * adim, c_i + dc * adim
                    if 0 <= nr < 6 and 0 <= nc < 7 and izgara[nr][nc] == sembol:
                        dortlu.append([nr, nc])
                    else:
                        break
                if len(dortlu) == 4:
                    return True, "", {"izgara": izgara, "kazananDortlu": dortlu}, "", True, oyuncu

    dolu_mu = all(izgara[0][c_i] != "" for c_i in range(7))
    if dolu_mu:
        return True, "", {"izgara": izgara, "kazananDortlu": []}, "", True, "berabere"
    return True, "", {"izgara": izgara, "kazananDortlu": []}, rakip, False, ""


def tkm_hamle_yap(tahta, oyuncular, oyuncu, secim):
    """Taş-Kâğıt-Makas (Best of 3 - 2 olan kazanır). Seçimler her iki taraf seçince açılır."""
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    rol = "a" if oyuncu == a else ("b" if oyuncu == b else "")
    if not rol:
        return False, "Bu oyunda oyuncu değilsin!", tahta, "", False, ""
    secim = str(secim or "").lower().strip()
    if secim not in ("tas", "kagit", "makas"):
        return False, "Geçersiz seçim! (tas, kagit, makas olmalı)", tahta, "", False, ""

    yeni = copy.deepcopy(tahta)
    yeni.setdefault("skor", {"a": 0, "b": 0})
    yeni.setdefault("secim", {"a": "", "b": ""})
    yeni["gecmis"] = listeye(yeni.get("gecmis"))
    yeni["turNo"] = int(yeni.get("turNo") or 1)

    if yeni["secim"].get(rol):
        return False, "Bu tur için seçimini zaten yaptın!", tahta, "", False, ""

    yeni["secim"][rol] = secim
    sa, sb = yeni["secim"].get("a", ""), yeni["secim"].get("b", "")
    if sa and sb:
        ustun = {"tas": "makas", "makas": "kagit", "kagit": "tas"}
        if sa == sb:
            tur_kazanan = "berabere"
        elif ustun[sa] == sb:
            tur_kazanan = "a"
            yeni["skor"]["a"] = int(yeni["skor"].get("a", 0)) + 1
        else:
            tur_kazanan = "b"
            yeni["skor"]["b"] = int(yeni["skor"].get("b", 0)) + 1

        yeni["gecmis"].append({"tur": yeni["turNo"], "a": sa, "b": sb, "sonuc": tur_kazanan})
        yeni["secim"] = {"a": "", "b": ""}
        yeni["turNo"] += 1

        if yeni["skor"]["a"] >= 2:
            return True, "", yeni, "", True, a
        if yeni["skor"]["b"] >= 2:
            return True, "", yeni, "", True, b
        return True, "", yeni, a, False, ""

    diger = b if rol == "a" else a
    return True, "", yeni, diger, False, ""


def adam_hamle_yap(tahta, oyuncular, oyuncu, girdi_metni):
    """Adam Asmaca: A gizli Türkçe kelimeyi girer, B harf tahmin eder (6 yanlış hakkı)."""
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    yeni = copy.deepcopy(tahta)
    asama = yeni.get("asama", "kelime_bekliyor")
    tahminler = [tr_buyuk(x) for x in listeye(yeni.get("tahminler"))]
    maks_yanlis = int(yeni.get("maksYanlis") or 6)

    if asama == "kelime_bekliyor":
        if oyuncu != a:
            return False, "Önce kelimeyi belirleyen oyuncunun kelime girmesi gerekiyor!", tahta, a, False, ""
        kelime = tr_buyuk(girdi_metni).strip()
        if len(kelime) < 3 or len(kelime) > 15 or not all(ch in TR_HARFLER for ch in kelime):
            return False, "Kelime 3-15 harf arası olmalı ve sadece Türkçe harfler içermeli!", tahta, a, False, ""
        yeni["kelime"] = kelime
        yeni["maske"] = " ".join("_" for _ in kelime)
        yeni["tahminler"] = []
        yeni["yanlis"] = 0
        yeni["asama"] = "tahmin"
        return True, "", yeni, b, False, ""

    if oyuncu != b:
        return False, "Harf tahmin etme sırası diğer oyuncuda!", tahta, b, False, ""

    harf = tr_buyuk(girdi_metni).strip()
    if len(harf) != 1 or harf not in TR_HARFLER:
        return False, "Lütfen geçerli tek bir Türkçe harf seç!", tahta, b, False, ""
    if harf in tahminler:
        return False, "Bu harfi zaten denedin!", tahta, b, False, ""

    tahminler.append(harf)
    yeni["tahminler"] = tahminler
    kelime = tr_buyuk(yeni.get("kelime", ""))
    if harf not in kelime:
        yeni["yanlis"] = int(yeni.get("yanlis") or 0) + 1

    acilan = [ch if ch in tahminler else "_" for ch in kelime]
    yeni["maske"] = " ".join(acilan)

    if "_" not in acilan:
        yeni["asama"] = "bitti"
        return True, "", yeni, "", True, b
    if yeni["yanlis"] >= maks_yanlis:
        yeni["asama"] = "bitti"
        return True, "", yeni, "", True, a
    return True, "", yeni, b, False, ""


def quiz_hamle_yap(tahta, oyuncular, oyuncu, secenek_idx, sure_ms=5000):
    """Bilgi Düellosu: Her iki oyuncu 10 soruyu eşzamansız çözebilir.
    Skor = doğru * 100 + hız bonusu (doğru cevap başına 0..20 puan).
    """
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    rol = "a" if oyuncu == a else ("b" if oyuncu == b else "")
    if not rol:
        return False, "Bu oyunda oyuncu değilsin!", tahta, "", False, ""
    if not isinstance(secenek_idx, int) or not (0 <= secenek_idx < 4):
        return False, "Geçersiz şık seçimi!", tahta, "", False, ""

    yeni = copy.deepcopy(tahta)
    sorular = [int(x) for x in listeye(yeni.get("sorular"))]
    cevaplar = yeni.setdefault("cevaplar", {"a": [], "b": []})
    sureler = yeni.setdefault("sureler", {"a": [], "b": []})
    puanlar = yeni.setdefault("puanlar", {"a": 0, "b": 0})
    dogrular = yeni.setdefault("dogrular", {"a": 0, "b": 0})

    cevap_list = list(listeye(cevaplar.get(rol)))
    sure_list = list(listeye(sureler.get(rol)))
    soru_no = len(cevap_list)
    if soru_no >= len(sorular):
        return False, "Tüm soruları zaten tamamladın!", tahta, "", False, ""

    soru_obj = TYT_SORU_BANKASI[sorular[soru_no] % len(TYT_SORU_BANKASI)]
    dogru_mu = (secenek_idx == soru_obj["d"])
    cevap_list.append(secenek_idx)
    sure_sn = max(0.5, min(20.0, float(sure_ms or 5000) / 1000.0))
    sure_list.append(round(sure_sn, 1))
    cevaplar[rol] = cevap_list
    sureler[rol] = sure_list

    if dogru_mu:
        hiz_bonusu = int(max(0, round(20 - sure_sn)))
        puanlar[rol] = int(puanlar.get(rol, 0)) + 100 + hiz_bonusu
        dogrular[rol] = int(dogrular.get(rol, 0)) + 1

    a_bitti = len(listeye(cevaplar.get("a"))) >= len(sorular)
    b_bitti = len(listeye(cevaplar.get("b"))) >= len(sorular)
    if a_bitti and b_bitti:
        pa, pb = int(puanlar.get("a", 0)), int(puanlar.get("b", 0))
        if pa > pb:
            kazanan = a
        elif pb > pa:
            kazanan = b
        else:
            kazanan = "berabere"
        return True, "", yeni, "", True, kazanan

    sonraki = b if (rol == "a" and len(cevap_list) >= len(sorular)) else (a if (rol == "b" and len(cevap_list) >= len(sorular)) else oyuncu)
    return True, "", yeni, sonraki, False, ""


def oyun_hamle_uygula(oyun_verisi, oyuncu, hamle, simdi_ms=None):
    """Genel oyun hamlesi uygulayıcı (saf fonksiyon).
    Sıra kontrolü, hamleNo artışı, kazanan belirleme işlemlerini yapar.
    Döndürür: (gecerli_mi, hata_mesaji, guncel_oyun_sozlugu)
    """
    simdi_ms = int(simdi_ms if simdi_ms is not None else time.time() * 1000)
    g = copy.deepcopy(oyun_verisi) if isinstance(oyun_verisi, dict) else {}
    if g.get("durum") != "oynuyor":
        return False, "Bu oyun şu an aktif değil!", g

    tur = g.get("tur", "xox")
    oyuncular = g.get("oyuncular") or {}
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    if oyuncu not in (a, b):
        return False, "Bu oyunun oyuncusu değilsin!", g

    # XOX, Connect 4 ve Adam Asmaca'da yalnızca sırası gelen oyuncu hamle yazabilir (tek yazıcı kuralı)
    if tur in ("xox", "c4", "adam") and g.get("sira") != oyuncu:
        return False, "Şu an sıra rakipte!", g

    tahta = g.get("tahta") or {}
    if tur == "xox":
        ok, hata, yeni_tahta, sonraki, bitti, kazanan = xox_hamle_yap(tahta, oyuncular, oyuncu, hamle)
    elif tur == "c4":
        ok, hata, yeni_tahta, sonraki, bitti, kazanan = c4_hamle_yap(tahta, oyuncular, oyuncu, hamle)
    elif tur == "tkm":
        ok, hata, yeni_tahta, sonraki, bitti, kazanan = tkm_hamle_yap(tahta, oyuncular, oyuncu, hamle)
    elif tur == "adam":
        ok, hata, yeni_tahta, sonraki, bitti, kazanan = adam_hamle_yap(tahta, oyuncular, oyuncu, hamle)
    elif tur == "yks_quiz":
        secim = hamle.get("secenek") if isinstance(hamle, dict) else hamle
        sure_ms = hamle.get("sure_ms", 5000) if isinstance(hamle, dict) else 5000
        ok, hata, yeni_tahta, sonraki, bitti, kazanan = quiz_hamle_yap(tahta, oyuncular, oyuncu, secim, sure_ms)
    else:
        return False, "Bilinmeyen oyun türü!", g

    if not ok:
        return False, hata, g

    g["tahta"] = yeni_tahta
    g["hamleNo"] = int(g.get("hamleNo") or 0) + 1
    g["sonHamle"] = simdi_ms
    g["sonHamleYapan"] = oyuncu
    if bitti:
        g["durum"] = "bitti"
        g["kazanan"] = kazanan
        g["sira"] = ""
    else:
        g["sira"] = sonraki
    return True, "", g


def skor_hesapla_pure(mevcut_skor, sonuc):
    """Galibiyet: 3 puan, Beraberlik: 1 puan, Mağlubiyet: 0 puan."""
    s = copy.deepcopy(mevcut_skor) if isinstance(mevcut_skor, dict) else {}
    gal = int(s.get("galibiyet") or 0)
    mag = int(s.get("maglubiyet") or 0)
    ber = int(s.get("beraberlik") or 0)
    if sonuc == "galibiyet":
        gal += 1
    elif sonuc == "maglubiyet":
        mag += 1
    elif sonuc == "beraberlik":
        ber += 1
    return {
        "galibiyet": gal,
        "maglubiyet": mag,
        "beraberlik": ber,
        "puan": gal * 3 + ber * 1,
    }


def oyun_zaman_asimi_durumu(oyun_verisi, simdi_ms=None):
    """Oyunun zaman aşımı durumunu hesaplar:
    - 24 saat (86_400_000 ms) hareketsizlik -> iptal_24s = True
    - 2 dakika (120_000 ms) hareketsizlik -> hukmen_2dk = True
    """
    simdi_ms = int(simdi_ms if simdi_ms is not None else time.time() * 1000)
    g = oyun_verisi if isinstance(oyun_verisi, dict) else {}
    son = int(g.get("sonHamle") or g.get("olusturma") or simdi_ms)
    gecen = max(0, simdi_ms - son)
    aktif = g.get("durum") in ("bekliyor", "oynuyor")
    return {
        "gecen_ms": gecen,
        "iptal_24s": aktif and gecen >= 86_400_000,
        "hukmen_2dk": (g.get("durum") == "oynuyor") and gecen >= 120_000,
    }


def main(page: ft.Page):
    page.title = "YKS Asistanım 🚀"
    page.padding = 0
    page.spacing = 0
    try:
        page.window.width = 400
        page.window.height = 820
    except Exception:
        pass

    # ==========================================
    # 3. KALICI VERİ
    #    Önce telefondaki dosyaya, ayrıca client_storage'a yazılır. Açılışta dosya okunur.
    # ==========================================
    DOSYA = depo_dosyasi()
    kilit = threading.RLock()
    oturum = {"kullanici": "", "kirli": {}, "surum": 0}
    bulut_olay = threading.Event()
    DB = {}   # DİKKAT: hiçbir yerde yeniden atanmaz, DB.clear()/DB.update() ile yerinde değişir

    def arka_plan(fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def yerel_yaz():
        """Telefondaki yedeği yazar (internet yokken de veri kaybolmasın)."""
        with kilit:
            try:
                gecici = DOSYA + ".tmp"
                with open(gecici, "w", encoding="utf-8") as f:
                    json.dump({"kullanici": oturum["kullanici"], "kirli": oturum["kirli"], "db": DB},
                              f, ensure_ascii=False)
                os.replace(gecici, DOSYA)
            except Exception as ex:
                print("Yerel kayıt hatası:", ex)

    def yerelden_yukle():
        try:
            with open(DOSYA, "r", encoding="utf-8") as f:
                veri = json.load(f)
        except Exception:
            return "", {}, {}
        if not isinstance(veri, dict):
            return "", {}, {}
        if "db" not in veri:                      # eski sürümün düz dosya biçimi
            return "", {}, veri
        if isinstance(veri.get("kirli"), dict):
            kirli = {str(k): int(v) for k, v in veri["kirli"].items()}
        elif veri.get("senkron") is False:        # bir önceki sürümün biçimi
            kirli = {k: 1 for k in BULUT_ANAHTARLARI}
        else:
            kirli = {}
        return str(veri.get("kullanici") or ""), kirli, veri.get("db") or {}

    _k, _kirli, _ham = yerelden_yukle()
    DB.update(db_hazirla(_ham))
    oturum["kullanici"], oturum["kirli"] = _k, _kirli
    oturum["surum"] = max(_kirli.values(), default=0)

    def bulut_gonder():
        """Buluta gitmemiş değişiklikleri Firebase'e yollar. Başarılıysa True döner."""
        with kilit:
            kul = oturum["kullanici"]
            foto = dict(oturum["kirli"])
            veri = {a: bulut_hazirla(a, copy.deepcopy(DB.get(a))) for a in foto}
        if not kul or not foto:
            return True
        try:
            bulut_guncelle(kul, veri)
        except Exception as ex:
            print("Bulut kayıt hatası:", ex)
            return False
        with kilit:
            for a, v in foto.items():
                if oturum["kirli"].get(a) == v:     # gönderirken yeniden değişmediyse temizle
                    del oturum["kirli"][a]
            yerel_yaz()
        return True

    def bulut_isci():
        """Tek bir arka plan işçisi: yazmalar sırayla gider, internet yoksa 5 sn'de bir tekrar dener."""
        while True:
            bulut_olay.wait()
            bulut_olay.clear()
            while not bulut_gonder():
                time.sleep(5)

    arka_plan(bulut_isci)

    def kaydet(anahtar=None):
        """Önce telefona, sonra arka planda Firebase'e kaydeder."""
        with kilit:
            if oturum["kullanici"]:
                oturum["surum"] += 1
                for a in ([anahtar] if anahtar else BULUT_ANAHTARLARI):
                    oturum["kirli"][a] = oturum["surum"]
            yerel_yaz()
        if oturum["kullanici"]:
            bulut_olay.set()

    def not_cek():
        """Panelden eklenen sürpriz notları (herkese ya da bu kullanıcıya özel) buluttan alır."""
        try:
            ham = bulut_get("ayarlar/notlar") or {}
            return [v["m"] for v in ham.values()
                    if isinstance(v, dict) and v.get("m") and v.get("k", "") in ("", oturum["kullanici"])]
        except Exception as ex:
            print("Notlar alınamadı:", ex)
            return []

    def aktif_isaretle(ekran=None):
        if oturum["kullanici"]:
            DB["son_aktif"] = int(time.time() * 1000)
            if ekran is not None:
                DB["aktif_ekran"] = ekran
            kaydet("son_aktif")
            if ekran is not None:
                kaydet("aktif_ekran")

    def oturumu_kapat():
        """Yerel oturumu temizler (çıkış yapınca ya da hesap silinince)."""
        with kilit:
            oturum["kullanici"] = ""
            oturum["kirli"] = {}
            tema = DB["tema"]
            DB.clear()
            DB.update(db_hazirla({"tema": tema}))
            zm.update({"durum": "bos", "birikmis": 0.0, "t0": None})
            yerel_yaz()

    def bildirim_konu_hazirla():
        """Her öğrenciye tahmin edilemez, kendine özel bir bildirim konusu verir."""
        if not oturum["kullanici"]:
            return
        b = DB["bildirim"]
        if not b.get("konu"):
            ad = re.sub(r"[^a-z0-9]", "", oturum["kullanici"].translate(str.maketrans("çğıöşü", "cgiosu"))) or "ogrenci"
            b["konu"] = f"yks-{ad}-{os.urandom(4).hex()}"
            kaydet("bildirim")

    def yonetici_haber(baslik, mesaj):
        """Öğrenci gün sonu/deneme ekleyince yöneticinin (Arda) telefonuna anında bildirim yollar."""
        def is_():
            try:
                y = bulut_get("yonetici") or {}
                if y.get("konu") and y.get("kullanici") != oturum["kullanici"]:
                    ntfy_gonder(y["konu"], baslik, mesaj, 4)
            except Exception as ex:
                print("Yöneticiye haber verilemedi:", ex)
        arka_plan(is_)

    ui = {
        "sekme": 0, "alt": None, "net_tab": 0, "net_sinav": "TYT", "ders": None,
        "surpriz": "", "panel_giris": False, "panel_tab": 0, "eglence_tab": 0, "panel_hata": "",
        "plan_gun": datetime.now().weekday(), "giris_mod": "giris" if oturum["kullanici"] else "kayit", "hata": "",
        "gs_tarih": "", "gs_puan": 0, "gs_not": "", "panel_ogrenci": None, "taslak": "",
        "sosyal_tab": 0, "sosyal_alt": None,      # None (Akış), "sohbet", "oyun"
        "sohbet_tab": 0,                          # 0: Genel Sohbet, 1: Özel Sohbetler
        "aktif_dm": None,                         # pairId (açık özel sohbet)
        "dm_yeni_acik": False, "dm_arama": "",    # yeni özel sohbet arama kutusu
        "aktif_oyun": None,                       # gameId (açık oyun ekranı)
        "oyun_davet_acik": False, "oyun_secilen_tur": "xox", "oyun_arama": "",
        "oyun_skor_tur": "genel", "quiz_soru_t0": 0.0,
        "panel_esik": 1, "silinecek": None, "not_hedef": 0,
        "genel_temizle_onay": False, "_anahtar": None,
    }
    oyun = {"xox": [""] * 9, "xox_kazanan": None}
    zm = {"mod": "krono", "durum": "bos", "birikmis": 0.0, "t0": None,
          "label": None, "ring": None, "thread": None, "bildirildi": False}
    gk = {"metinler": None}   # ana sayfadaki canlı geri sayım yazıları

    # Sosyal, DM, Seri ve Oyun önbelleği
    sosyal = {
        "posts": {}, "resim": {}, "sohbet": {}, "admin": "",
        "akis_kap": None, "sohbet_kap": None,
        "dm_index": {}, "dm_mesajlar": {}, "seri": {},
        "dm_liste_kap": None, "dm_mesaj_kap": None, "dm_baslik_seri": None,
        "oyunlar": {}, "oyun_skor": {},
        "oyun_lobi_kap": None, "oyun_tahta_kap": None, "oyun_durum_txt": None,
        "kullanicilar_cache": [], "kullanici_bildirim_cache": {}, "oran_durumu": {},
        "genel_okundu_zaman": 0,
        "yeni_foto": None, "yeni_aciklama": "", "yorum_acik": set(),
        "imza": {}, "son_cek": {0: 0.0, 1: 0.0, "dm": 0.0, "oyun": 0.0},
        "foto_mesaj": "",
    }

    # --- çalışma süresi yardımcıları ---
    def gun_sn(tarih):
        return int(DB["calisma_sn"].get(tarih, 0)) + int(DB["calisma_log"].get(tarih, 0)) * 60

    def toplam_sn():
        return sum(int(v) for v in DB["calisma_sn"].values()) + sum(int(v) for v in DB["calisma_log"].values()) * 60

    def kullanici_adi():
        return (DB["hesap"] or {}).get("kullanici", "") or oturum["kullanici"]

    # ==========================================
    # 5. ORTAK BİLEŞENLER
    # ==========================================
    def renk():
        return TEMA_RENKLERI[DB["tema"]]

    def duzelt(c):
        """Column içindeki 'expand' düğmeleri sınırsız yükseklik hatası verip kartı gizler.
        Onları genişlik doldurmaya (STRETCH) çevirir. Row içindekilere dokunmaz."""
        if isinstance(c, ft.Column):
            for k in c.controls:
                if isinstance(k, DUGME) and k.expand:
                    k.expand = False
                    c.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        for k in (getattr(c, "controls", None) or []):
            duzelt(k)
        icerik = getattr(c, "content", None)
        if icerik is not None and not isinstance(icerik, str):
            duzelt(icerik)
        return c

    def yenile():
        icerik_guncelle(renk())
        page.update()

    def snack(mesaj):
        try:
            bar = ft.SnackBar(ft.Text(mesaj))
            if hasattr(page, "show_dialog"):
                page.show_dialog(bar)
            else:
                page.open(bar)
        except Exception as ex:
            print("Snack gosterilemedi:", ex)

    def url_ac(url):
        """Baglantiyi tarayicida/uygulamada acar (Flet surumunden bagimsiz)."""
        try:
            sonuc = page.launch_url(url)
            if asyncio.iscoroutine(sonuc):
                async def _bekle():
                    await sonuc
                page.run_task(_bekle)
            return
        except Exception:
            pass
        try:
            async def _ac():
                await ft.UrlLauncher().launch_url(url)
            page.run_task(_ac)
        except Exception as ex:
            print("URL acilamadi:", ex)

    def kutlama():
        def isle():
            try:
                w = int(page.width or 400)
                h = int(page.height or 800)
                kat = ft.Stack(expand=True)
                for _ in range(14):
                    kat.controls.append(ft.Container(
                        content=ft.Text(random.choice(["🎈", "🎉", "💖", "✨", "🌹", "🔥"]), size=random.randint(24, 38)),
                        left=random.randint(0, max(10, w - 40)), top=h,
                        animate_position=ft.Animation(random.randint(1800, 3000), ft.AnimationCurve.EASE_OUT),
                    ))
                page.overlay.append(kat)
                page.update()
                time.sleep(0.15)
                for c in kat.controls:
                    c.top = -90
                page.update()
                time.sleep(3.3)
                page.overlay.remove(kat)
                page.update()
            except Exception:
                pass
        threading.Thread(target=isle, daemon=True).start()

    def kart(r, icerik, padding=18, border=None, **kw):
        return ft.Container(
            bgcolor=r["card_bg"], border_radius=22, padding=padding,
            border=border or kenar(1, r["border"]),
            shadow=ft.BoxShadow(blur_radius=14, color=opak(0.06, "#000000"), offset=ft.Offset(0, 4)),
            content=icerik, **kw
        )

    def buton(r, metin, on_click, ikon=None, genis=False, ikincil=False, data=None, yukseklik=48):
        return dugme_olustur(
            metin, icon=ikon, on_click=on_click, data=data, expand=genis, height=yukseklik,
            bgcolor=r["card_bg"] if ikincil else r["hdr"],
            color=r["hdr"] if ikincil else okunur_renk(r["hdr"]),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=14),
                side=ft.BorderSide(1, r["border"]) if ikincil else None,
                elevation=0,
            ),
        )

    def girdi(r, ipucu="", **kw):
        return ft.TextField(
            hint_text=ipucu, bgcolor=r["bg"], border_color=r["border"], focused_border_color=r["hdr"],
            color=r["txt"], cursor_color=r["hdr"], content_padding=15, border_radius=14,
            hint_style=ft.TextStyle(color=r["muted"]), label_style=ft.TextStyle(color=r["muted"]), **kw
        )

    def bolum_basligi(r, ikon, metin, sag=None):
        satir = [
            ft.Container(
                width=34, height=34, border_radius=12, alignment=ORTA,
                bgcolor=opak(0.14, r["hdr"]),
                content=ft.Icon(ikon, color=r["hdr"], size=19),
            ),
            ft.Text(metin, size=16, color=r["txt"], weight=ft.FontWeight.W_700, expand=True),
        ]
        if sag is not None:
            satir.append(sag)
        return ft.Row(satir, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def sayfa_basligi(r, baslik, alt=None, geri=None, sag=None):
        baslik_kolon = ft.Column([
            ft.Text(baslik, size=26, weight=ft.FontWeight.W_800, color=r["txt"]),
            *([ft.Text(alt, size=13, color=r["muted"])] if alt else []),
        ], spacing=2, expand=True)
        satir = []
        if geri:
            satir.append(ft.IconButton(icon=ik("ARROW_BACK_IOS_NEW"), icon_color=r["hdr"], icon_size=20, on_click=geri))
        satir.append(baslik_kolon)
        if sag is not None:
            satir.append(sag)
        return ft.Row(satir, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def gorev_satiri(r, metin, bitti, data, on_change):
        bg_renk = opak(0.10, r["accent"]) if bitti else r["bg"]
        txt_renk = r["muted"] if bitti else r["txt"]
        decor = ft.TextDecoration.LINE_THROUGH if bitti else ft.TextDecoration.NONE
        return ft.Container(
            padding=pad_only(left=4, right=12, top=2, bottom=2),
            border_radius=16, bgcolor=bg_renk,
            border=kenar(1, opak(0.5, r["border"])),
            content=ft.Row([
                ft.Checkbox(value=bitti, data=data, on_change=on_change, fill_color=r["accent"], check_color=r["card_bg"]),
                ft.Text(metin, color=txt_renk, weight=ft.FontWeight.W_600, size=14,
                        style=ft.TextStyle(decoration=decor), expand=True),
            ])
        )

    def ilerleme_cubugu(r, oran, renk_=None):
        return ft.Container(
            border_radius=10, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.ProgressBar(value=max(0.0, min(oran, 1.0)), color=renk_ or r["hdr"],
                                   bgcolor=opak(0.2, r["muted"]), bar_height=12),
        )

    def segment(r, etiketler, secili, degisti):
        """Üstte yan yana seçim butonları (Tabs yerine, boş kutu hatası çıkarmaz)."""
        def tik(i):
            def f(e):
                degisti(i)
            return f
        ogeler = []
        for i, etiket in enumerate(etiketler):
            aktif = i == secili
            ogeler.append(ft.Container(
                expand=True, padding=pad_sim(vertical=10), border_radius=12,
                alignment=ORTA, ink=True, on_click=tik(i),
                bgcolor=r["hdr"] if aktif else SEFFAF,
                content=ft.Text(etiket, size=12, weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER,
                                color=okunur_renk(r["hdr"]) if aktif else r["muted"]),
            ))
        return ft.Container(
            bgcolor=r["card_bg"], border_radius=16, padding=4, border=kenar(1, r["border"]),
            content=ft.Row(ogeler, spacing=4),
        )

    def stat_kutusu(r, ikon, deger, etiket):
        return ft.Container(
            expand=True, padding=pad_only(left=14, right=10, top=14, bottom=14), border_radius=20,
            bgcolor=r["card_bg"], border=kenar(1, r["border"]),
            content=ft.Column([
                ft.Icon(ikon, color=r["accent"], size=22),
                ft.Text(deger, size=16, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text(etiket, size=11, color=r["muted"]),
            ], spacing=4),
        )

    # ==========================================
    # 6. ÖDÜL SİSTEMİ (ana sayfada gösterilir + seri başarımları)
    # ==========================================
    def kullanici_seri_istatistikleri():
        """Giriş yapmış kullanıcının en uzun aktif serisini ve aktif seri (2+ gün) sayısını döndürür."""
        ben = kullanici_adi()
        if not ben:
            return 0, 0
        bugun_iso = istanbul_bugun()
        en_uzun = 0
        aktif_arkadas_sayisi = 0
        for pid, kayit in (sosyal.get("seri") or {}).items():
            u1, u2 = cift_kullanicilar(pid)
            if ben not in (u1, u2):
                continue
            d = seri_gorunum_durumu(kayit, bugun_iso)
            s_ = d["sayi"]
            if s_ > en_uzun:
                en_uzun = s_
            if s_ >= 2:
                aktif_arkadas_sayisi += 1
        return en_uzun, aktif_arkadas_sayisi

    def basarim_kutlama_kontrol(kod, baslik, acik_mi):
        """Bir başarım ilk kez açıldığında konfeti patlatır ve bildirim gösterir."""
        if not acik_mi or not oturum["kullanici"]:
            return
        acilanlar = DB.setdefault("acilan_oduller", [])
        if kod not in acilanlar:
            acilanlar.append(kod)
            kaydet("acilan_oduller")
            kutlama()
            snack(f"🏆 Yeni Başarım Açıldı: {baslik}!")

    def oduller_listesi(r):
        tyt = [n["toplam"] for n in DB["netler"] if n["sinav"] == "TYT"]
        max_tyt = max(tyt) if tyt else 0.0
        max_saat = max([sayi(g.get("saat")) for g in DB["gunluk"]] + [gun_sn(bugun_str()) / 3600.0])
        kayitli_gun = len({g["tarih"] for g in DB["gunluk"]})
        en_uzun_seri, aktif_seri_sayisi = kullanici_seri_istatistikleri()

        def basari(kod, ad, aciklama, acik, odul, ikon_metin=None):
            basarim_kutlama_kontrol(kod, ad, acik)
            sol_ikon = (ikon_metin if acik and ikon_metin else ("🔓" if acik else "🔒"))
            return ft.Container(
                padding=12, border_radius=16,
                bgcolor=opak(0.12, r["accent"]) if acik else r["bg"],
                border=kenar(2 if acik else 1, r["accent"] if acik else r["border"]),
                content=ft.Row([
                    ft.Text(sol_ikon, size=26),
                    ft.Column([
                        ft.Text(ad, size=14, weight=ft.FontWeight.W_700, color=r["hdr"] if acik else r["txt"]),
                        ft.Text(odul if acik else aciklama, size=12, color=r["accent"] if acik else r["muted"]),
                    ], spacing=2, expand=True),
                ], spacing=12),
            )

        ogeler = [
            basari("demir_irade", "Demir İrade (8 Saat!)", f"Bir günde en az 8 saat çalış. (Rekorun: {max_saat:.1f} sa)",
                   max_saat >= 8.0, "Ödül: İlk fırsatta favori yemeğin benden!"),
            basari("istikrar_5", "İstikrar Zinciri (5 Gün!)", f"Gün sonunu 5 gün kaydet. (Mevcut: {kayitli_gun} gün)",
                   kayitli_gun >= 5, "Ödül: Ufak bir sürpriz hediye seni bekliyor!"),
            basari("zirve_tyt", f"Zirve Yürüyüşü ({HEDEF_TYT:g} Net!)", f"TYT'de {HEDEF_TYT:g} neti aş! (Rekorun: {max_tyt:g} net)",
                   max_tyt >= HEDEF_TYT, "Ödül: Birlikte geziyor ve tatlı yiyoruz! 🎉"),
            basari("seri_2", "İlk Kıvılcım (2 Gün Seri! 🔥)",
                   f"Bir arkadaşınla özel sohbette 2 günlük seri yakala. (En uzun: {en_uzun_seri} gün)",
                   en_uzun_seri >= 2, "Başarım Açıldı: Sohbet ateşi yandı! 🔥", "🔥"),
            basari("seri_7", "Alev Ustası (7 Gün Seri! 🔥🔥)",
                   f"Bir arkadaşınla 7 günlük sohbet serisine ulaş. (En uzun: {en_uzun_seri} gün)",
                   en_uzun_seri >= 7, "Başarım Açıldı: Tam 1 haftalık kesintisiz seri! 🔥🔥", "🔥🔥"),
            basari("seri_30", "Sönmeyen Ateş (30 Gün Seri! 🔥🔥🔥)",
                   f"Bir arkadaşınla 30 günlük sohbet serisine ulaş. (En uzun: {en_uzun_seri} gün)",
                   en_uzun_seri >= 30, "Başarım Açıldı: 1 aylık efsanevi dostluk serisi! 🔥🔥🔥", "🔥🔥🔥"),
            basari("seri_100", "Yüzyıllık Efsane (100 Gün Seri! 🔥🔥🔥🔥)",
                   f"Bir arkadaşınla 100 günlük sohbet serisine ulaş. (En uzun: {en_uzun_seri} gün)",
                   en_uzun_seri >= 100, "Başarım Açıldı: 100 günlük kırılmaz rekor! 👑🔥", "👑"),
            basari("seri_5_arkadas", "Sosyal Kelebek (5 Arkadaşla Seri!)",
                   f"Aynı anda 5 farklı arkadaşınla aktif seri (2+ gün) yap. (Aktif: {aktif_seri_sayisi}/5)",
                   aktif_seri_sayisi >= 5, "Başarım Açıldı: Sosyal çevren alev alıyor! 🦋🔥", "🦋"),
        ]

        def tamamla(e):
            DB["ozel_gorevler"][e.control.data]["durum"] = "Tamamlandı"
            kaydet("ozel_gorevler")
            kutlama()
            yenile()

        ozel = []
        for i, g in enumerate(DB["ozel_gorevler"]):
            if g["durum"] != "Tamamlandı":
                ozel.append(ft.Container(
                    padding=12, border_radius=16, bgcolor=r["bg"], border=kenar(1, r["hdr"]),
                    content=ft.Column([
                        ft.Text(f"🎯 Arda'dan görev: {g['gorev']}", size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                        ft.Text(f"🎁 Ödül: {g['odul']}", size=12, color=r["accent"]),
                        buton(r, "Görevi Tamamladım ✔️", tamamla, data=i, genis=True, yukseklik=40),
                    ], spacing=8),
                ))
        return [*ogeler, *ozel]

    # ==========================================
    # 7. ANA SAYFA
    # ==========================================
    def su_guncel():
        if DB["su"].get("tarih") != bugun_str():
            DB["su"] = {"tarih": bugun_str(), "bardak": 0}
            kaydet("su")
        return DB["su"]

    def ana_sayfa_olustur(r):
        bugun_ad = GUNLER[datetime.now().weekday()]
        simdi = datetime.now()

        # --- Başlık ---
        isim = kullanici_adi() or "Şampiyon"
        avatar_kutu = ft.Container(
            width=46, height=46, border_radius=23, alignment=ORTA, bgcolor=r["hdr"],
            content=ft.Text(isim[:1].upper(), size=20, weight=ft.FontWeight.BOLD, color=okunur_renk(r["hdr"])),
        )
        header = ft.Row([
            ft.Column([
                ft.Text(f"{bugun_ad}, {simdi.day} {AYLAR[simdi.month - 1]}", size=12, color=r["muted"]),
                ft.Text(f"Merhaba {isim}! 👋", size=24, weight=ft.FontWeight.W_800, color=r["txt"]),
            ], spacing=2, expand=True),
            avatar_kutu,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # --- Arda'dan canlı sinyal ---
        sinyal_banner = []
        if DB["sinyal"].get("aktif") and DB["sinyal"].get("mesaj"):
            sinyal_banner.append(ft.Container(
                padding=14, border_radius=18, bgcolor=opak(0.15, r["hdr"]),
                border=kenar(1, r["hdr"]),
                content=ft.Row([
                    ft.Icon(ik("NOTIFICATIONS_ACTIVE"), color=r["hdr"]),
                    ft.Column([
                        ft.Text("Arda'dan Sinyal 🚨", size=12, color=r["hdr"], weight=ft.FontWeight.BOLD),
                        ft.Text(DB["sinyal"]["mesaj"], color=r["txt"], weight=ft.FontWeight.W_600),
                    ], spacing=2, expand=True),
                ]),
            ))

        # --- YKS geri sayım (hero kart) ---
        fark = YKS_TARIHI - simdi
        beyaz = "#FFFFFF"
        beyaz_sonuk = opak(0.78, beyaz)

        metinler = []

        def zaman_kutu(deger, etiket):
            t = ft.Text(str(deger), size=22, weight=ft.FontWeight.W_800, color=beyaz)
            metinler.append(t)
            return ft.Container(
                expand=True, padding=pad_sim(vertical=10), border_radius=16,
                bgcolor=opak(0.18, beyaz), alignment=ORTA,
                content=ft.Column([t, ft.Text(etiket, size=11, color=beyaz_sonuk)],
                                  spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        kalan_sn = int(fark.total_seconds())
        if kalan_sn > 0:
            kutular = ft.Row([
                zaman_kutu(kalan_sn // 86400, "Gün"), zaman_kutu((kalan_sn % 86400) // 3600, "Saat"),
                zaman_kutu((kalan_sn % 3600) // 60, "Dakika"), zaman_kutu(kalan_sn % 60, "Saniye"),
            ], spacing=6)
            gk["metinler"] = metinler
        else:
            gk["metinler"] = None
            kutular = ft.Text("Sınav Başladı! 🚀", size=24, weight=ft.FontWeight.BOLD, color=beyaz)
        hero = ft.Container(
            padding=20, border_radius=26,
            gradient=ft.LinearGradient(
                begin=UST_SOL, end=ALT_SAG,
                colors=[karistir(r["hdr"], "#000000", 0.12), karistir(r["hdr"], "#000000", 0.5)],
            ),
            shadow=ft.BoxShadow(blur_radius=20, color=opak(0.25, r["hdr"]), offset=ft.Offset(0, 8)),
            content=ft.Column([
                ft.Row([ft.Icon(ik("ROCKET_LAUNCH_ROUNDED"), color=beyaz, size=20),
                        ft.Text(f"YKS {YKS_TARIHI.year}'ye kalan süre", size=14, color=beyaz_sonuk, weight=ft.FontWeight.W_600)]),
                kutular,
                ft.Text(f"🎓 {HEDEF_UNIVERSITE}", size=13, color=beyaz, weight=ft.FontWeight.W_600),
            ], spacing=14),
        )

        # --- İstatistik kutuları ---
        su = su_guncel()
        mevcut_su = int(su["bardak"])
        istatistikler = ft.Row([
            stat_kutusu(r, ik("TODAY"), sn_kisa(gun_sn(bugun_str())), "Bugün"),
            stat_kutusu(r, ik("HOURGLASS_BOTTOM"), sn_kisa(toplam_sn()), "Toplam"),
            stat_kutusu(r, ik("WATER_DROP"), f"{mevcut_su}/8", "Su"),
        ], spacing=10)

        # --- Bugünün programı ---
        bugunku_gorevler = DB["plan"].get(bugun_ad, [])
        bitenler = sum(1 for t in bugunku_gorevler if t["bitti"])
        gorev_listesi = ft.Column(spacing=8)

        def gorev_tiklandi(e):
            DB["plan"][bugun_ad][e.control.data]["bitti"] = e.control.value
            kaydet("plan")
            yenile()

        if not bugunku_gorevler:
            gorev_listesi.controls.append(ft.Text("Bugün için planlanmış görev yok 🎉  (Plan sekmesinden ekleyebilirsin)",
                                                  color=r["muted"], italic=True, size=13))
        else:
            for i, task in enumerate(bugunku_gorevler):
                gorev_listesi.controls.append(gorev_satiri(r, task["gorev"], task["bitti"], i, gorev_tiklandi))
        program_karti = kart(r, ft.Column([
            bolum_basligi(r, ik("EVENT_AVAILABLE"), f"{bugun_ad} Programı",
                          ft.Text(f"{bitenler}/{len(bugunku_gorevler)}", size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
            ilerleme_cubugu(r, bitenler / len(bugunku_gorevler) if bugunku_gorevler else 0, r["accent"]),
            gorev_listesi,
        ], spacing=12))

        # --- Yapılacaklar listesi ---
        todo_input = girdi(r, "Yeni görev ekle...", expand=True)

        def todo_ekle(e):
            v = (todo_input.value or "").strip()
            if v:
                DB["todo"].append({"gorev": v, "bitti": False})
                kaydet("todo")
                yenile()

        todo_input.on_submit = todo_ekle

        def todo_tikla(e):
            DB["todo"][e.control.data]["bitti"] = e.control.value
            kaydet("todo")
            if e.control.value:
                kutlama()
            yenile()

        def todo_temizle(e):
            DB["todo"] = [t for t in DB["todo"] if not t["bitti"]]
            kaydet("todo")
            yenile()

        todo_kontrolleri = [
            bolum_basligi(r, ik("CHECKLIST"), "Yapılacaklar"),
            ft.Row([todo_input, ft.IconButton(icon=ik("ADD_CIRCLE"), icon_color=r["hdr"], icon_size=38, on_click=todo_ekle)]),
        ]
        if DB["todo"]:
            for i, t in enumerate(DB["todo"]):
                todo_kontrolleri.append(gorev_satiri(r, t["gorev"], t["bitti"], i, todo_tikla))
            if any(t["bitti"] for t in DB["todo"]):
                todo_kontrolleri.append(buton(r, "Bitenleri Temizle", todo_temizle, ikon=ik("CLEANING_SERVICES"),
                                              ikincil=True, genis=True, yukseklik=42))
        else:
            todo_kontrolleri.append(ft.Text("Listen şu an boş.", color=r["muted"], italic=True, size=13))
        todo_karti = kart(r, ft.Column(todo_kontrolleri, spacing=10))

        # --- Su takibi ---
        def su_ictim(e):
            DB["su"]["bardak"] = int(DB["su"]["bardak"]) + 1
            kaydet("su")
            if DB["su"]["bardak"] == 8:
                snack("Günlük su hedefi tamam! 💧")
                kutlama()
            yenile()

        def su_geri(e):
            DB["su"]["bardak"] = max(int(DB["su"]["bardak"]) - 1, 0)
            kaydet("su")
            yenile()

        bardak_ikonlari = ft.Row([
            ft.Icon(ik("WATER_DROP"), size=28,
                    color=r["accent"] if i < mevcut_su else opak(0.25, r["muted"]))
            for i in range(8)
        ], spacing=4, alignment=ft.MainAxisAlignment.CENTER)
        su_karti = kart(r, ft.Column([
            bolum_basligi(r, ik("WATER_DROP"), "Su Takibi",
                          ft.Text(f"{mevcut_su} bardak" + (f"  (+{mevcut_su - 8})" if mevcut_su > 8 else ""),
                                  size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
            bardak_ikonlari,
            ft.Row([
                buton(r, "Bir Bardak İçtim 🚰", su_ictim, genis=True),
                ft.IconButton(icon=ik("REMOVE_CIRCLE_OUTLINE"), icon_color=r["muted"], on_click=su_geri, tooltip="Geri al"),
            ]),
        ], spacing=12))

        # --- Ödül sistemi ---
        odul_karti = kart(r, ft.Column([
            bolum_basligi(r, ik("CARD_GIFTCARD"), "Ödül Sistemi"),
            ft.Text("Kilitli başarıları ve 🔥 sohbet serisi ödüllerini aç 👀", size=12, color=r["muted"]),
            *oduller_listesi(r),
        ], spacing=10))

        # --- Günün sürpriz notu ---
        def not_oku(e):
            def is_():
                bulutta = not_cek()
                havuz = bulutta if bulutta and random.random() < 0.6 else SURPRIZ_NOTLARI
                ui["surpriz"] = random.choice(havuz)
                kutlama()
                yenile()
            arka_plan(is_)

        surpriz_icerik = [
            ft.Text("Günün Notu ❤", size=16, weight=ft.FontWeight.W_700, color=r["hdr"]),
            ft.Text("Bu zorlu maratonda her anında yanındayım. Derin bir nefes al ve asla pes etme.", color=r["txt"], size=13),
            buton(r, "Sürpriz Notu Oku", not_oku, ikon=ik("MAIL"), genis=True, ikincil=True, yukseklik=42),
        ]
        if ui["surpriz"]:
            surpriz_icerik.append(ft.Container(
                padding=16, border_radius=14, bgcolor=r["bg"],
                border=ft.Border(left=ft.BorderSide(5, r["accent"])),
                content=ft.Column([
                    ft.Text(f"\"{ui['surpriz']}\"", italic=True, color=r["txt"], text_align=ft.TextAlign.CENTER),
                    ft.Text("— Arda", weight=ft.FontWeight.BOLD, color=r["hdr"], text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            ))
        surpriz_karti = kart(r, ft.Column(surpriz_icerik, spacing=12))

        return ft.Column([
            header, *sinyal_banner, hero, istatistikler,
            program_karti, todo_karti, su_karti, odul_karti, surpriz_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 8. KRONOMETRE (başlat / duraklat / bitir)
    # ==========================================
    def gecen_sn():
        g = zm["birikmis"]
        if zm["durum"] == "calisiyor" and zm["t0"] is not None:
            g += time.time() - zm["t0"]
        return int(g)

    def zaman_metni():
        g = gecen_sn()
        if zm["mod"] == "pomo":
            kalan = max(25 * 60 - g, 0)
            return f"{kalan // 60:02d}:{kalan % 60:02d}"
        return f"{g // 3600:02d}:{(g % 3600) // 60:02d}:{g % 60:02d}"

    def halka_degeri():
        g = gecen_sn()
        if zm["mod"] == "pomo":
            return min(g / (25 * 60), 1.0)
        return (g % 3600) / 3600.0

    def tik_dongusu():
        while zm["durum"] == "calisiyor":
            if zm["mod"] == "pomo" and gecen_sn() >= 25 * 60 and not zm["bildirildi"]:
                zm["bildirildi"] = True
                snack("🍅 Pomodoro bitti! Bitir'e basıp süreni kaydedebilirsin.")
            try:
                if zm["label"] is not None:
                    zm["label"].value = zaman_metni()
                    zm["label"].update()
                if zm["ring"] is not None:
                    zm["ring"].value = halka_degeri()
                    zm["ring"].update()
            except Exception:
                pass
            time.sleep(0.5)

    def tik_baslat():
        if not (zm["thread"] and zm["thread"].is_alive()):
            zm["thread"] = threading.Thread(target=tik_dongusu, daemon=True)
            zm["thread"].start()

    def gun_baslangicini_kaydet():
        """Günün ilk kronometre başlatışı 'derse başlama saati' olur."""
        if DB["gun"].get("tarih") != bugun_str():
            DB["gun"] = {"tarih": bugun_str(), "baslama": datetime.now().strftime("%H:%M")}
            kaydet("gun")

    def krono_bitir_kaydet():
        """Çalışan/duraklatılmış oturumu bugüne ekler, kronometreyi sıfırlar. Eklenen saniyeyi döndürür."""
        toplam = gecen_sn()
        zm.update({"durum": "bos", "birikmis": 0.0, "t0": None, "bildirildi": False})
        if toplam > 0:
            t = bugun_str()
            DB["calisma_sn"][t] = int(DB["calisma_sn"].get(t, 0)) + toplam
            kaydet("calisma_sn")
        return toplam

    def calisma_sayfasi_olustur(r):
        durum = zm["durum"]

        def mod_sec(mod):
            def f(e):
                if zm["durum"] == "bos":
                    zm["mod"] = mod
                    yenile()
            return f

        def baslat(e):
            gun_baslangicini_kaydet()
            zm.update({"durum": "calisiyor", "birikmis": 0.0, "t0": time.time(), "bildirildi": False})
            tik_baslat()
            yenile()

        def duraklat(e):
            zm["birikmis"] += time.time() - zm["t0"]
            zm.update({"durum": "durakladi", "t0": None})
            yenile()

        def devam(e):
            zm.update({"durum": "calisiyor", "t0": time.time()})
            tik_baslat()
            yenile()

        def bitir(e):
            eklenen = krono_bitir_kaydet()
            snack(f"🎉 {sn_metni(eklenen)} çalışma bugüne eklendi!" if eklenen else "Süre 0 olduğu için kayıt eklenmedi.")
            yenile()

        def sifirla(e):
            zm.update({"durum": "bos", "birikmis": 0.0, "t0": None, "bildirildi": False})
            snack("Kronometre kaydedilmeden sıfırlandı.")
            yenile()

        zm["label"] = ft.Text(zaman_metni(), size=44, weight=ft.FontWeight.W_800, color=r["txt"])
        zm["ring"] = ft.ProgressRing(
            value=halka_degeri(), width=250, height=250, stroke_width=12, color=r["hdr"],
            bgcolor=opak(0.15, r["muted"]),
        )
        durum_yazi = {"bos": "Hazır", "calisiyor": "Çalışıyorsun 🔥", "durakladi": "Duraklatıldı ⏸"}[durum]
        daire = ft.Stack([
            ft.Container(content=zm["ring"], width=250, height=250, alignment=ORTA),
            ft.Container(
                width=250, height=250, alignment=ORTA,
                content=ft.Column([
                    zm["label"],
                    ft.Text(durum_yazi, size=13, color=r["muted"], weight=ft.FontWeight.W_600),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            ),
        ], width=250, height=250)

        if durum == "bos":
            butonlar = ft.Column([
                buton(r, "Başlat" if zm["mod"] == "krono" else "25 Dk Pomodoro Başlat", baslat,
                      ikon=ik("PLAY_ARROW"), genis=True, yukseklik=56),
            ])
        else:
            ana_btn = (buton(r, "Duraklat", duraklat, ikon=ik("PAUSE"), genis=True, ikincil=True, yukseklik=56)
                       if durum == "calisiyor" else
                       buton(r, "Devam Et", devam, ikon=ik("PLAY_ARROW"), genis=True, ikincil=True, yukseklik=56))
            butonlar = ft.Column([
                ft.Row([ana_btn, buton(r, "Bitir", bitir, ikon=ik("STOP_CIRCLE"), genis=True, yukseklik=56)], spacing=12),
                metin_dugmesi("Kaydetmeden sıfırla", on_click=sifirla, style=ft.ButtonStyle(color=r["muted"])),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

        secici = segment(r, ["⏱ Kronometre", "🍅 Pomodoro"], 0 if zm["mod"] == "krono" else 1,
                         lambda i: mod_sec("krono" if i == 0 else "pomo")(None))

        baslama = DB["gun"]["baslama"] if DB["gun"].get("tarih") == bugun_str() else "—"
        bugun_karti = kart(r, ft.Row([
            ft.Column([ft.Text("Bugün", size=12, color=r["muted"]),
                       ft.Text(sn_metni(gun_sn(bugun_str())), size=18, weight=ft.FontWeight.W_800, color=r["hdr"])],
                      spacing=2, expand=True),
            ft.Column([ft.Text("Başlama saati", size=12, color=r["muted"]),
                       ft.Text(baslama, size=18, weight=ft.FontWeight.W_800, color=r["txt"])],
                      spacing=2, expand=True),
            ft.Column([ft.Text("Toplam", size=12, color=r["muted"]),
                       ft.Text(sn_metni(toplam_sn()), size=18, weight=ft.FontWeight.W_800, color=r["txt"])],
                      spacing=2, expand=True),
        ]), padding=16)

        return ft.Column([
            sayfa_basligi(r, "Çalışma Masası", "Bitir'e bastığında süre bugüne ve toplama eklenir"),
            secici,
            ft.Container(content=daire, alignment=ORTA, padding=pad_sim(vertical=10)),
            butonlar,
            bugun_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 9. NETLER, MÜFREDAT, EKSİKLER
    # ==========================================
    def net_grafigi(r, kayitlar):
        try:
            return _net_grafigi_ciz(r, kayitlar)
        except Exception as ex:
            print("Grafik cizilemedi:", ex)
            return ft.Column([ft.Text(f"{i + 1}) {k['ad']} — {k['toplam']:.2f} net", size=12, color=r["muted"])
                              for i, k in enumerate(kayitlar)], spacing=6)

    def _net_grafigi_ciz(r, kayitlar):
        n = len(kayitlar)
        if n == 0:
            return ft.Text("Henüz deneme eklenmemiş.", color=r["muted"], italic=True)
        max_y = max(max(k["toplam"] for k in kayitlar) * 1.15, 10)
        aralik = max(5, int(-(-max_y / 4 // 5) * 5))
        seri = ft.LineChartData(
            data_points=[ft.LineChartDataPoint(i, k["toplam"], tooltip=f"{k['ad']}: {k['toplam']:.2f}") for i, k in enumerate(kayitlar)],
            stroke_width=3, color=r["hdr"], curved=True, stroke_cap_round=True,
            below_line_bgcolor=opak(0.12, r["hdr"]),
        )
        etiketler = [
            ft.ChartAxisLabel(value=i, label=ft.Container(ft.Text(str(i + 1), size=11, color=r["muted"]), padding=pad_only(top=6)))
            for i in range(n)
        ]
        grafik = ft.LineChart(
            data_series=[seri], min_y=0, max_y=max_y, min_x=-0.3, max_x=(n - 1) + 0.3, height=220,
            horizontal_grid_lines=ft.ChartGridLines(color=opak(0.15, r["muted"]), width=1),
            left_axis=ft.ChartAxis(labels_size=38, labels_interval=aralik),
            bottom_axis=ft.ChartAxis(labels=etiketler, labels_size=28),
            border=kenar(1, opak(0.2, r["muted"])),
        )
        liste = [ft.Text(f"{i + 1}) {k['ad']} — {k['toplam']:.2f} net", size=12, color=r["muted"]) for i, k in enumerate(kayitlar)]
        return ft.Column([grafik, *liste], spacing=6)

    def net_sekmesi(r):
        netler = DB["netler"]
        tyt = [n["toplam"] for n in netler if n["sinav"] == "TYT"]
        ayt = [n["toplam"] for n in netler if n["sinav"] == "AYT"]
        rekor_tyt = max(tyt) if tyt else 0.0
        rekor_ayt = max(ayt) if ayt else 0.0
        yuzde_tyt = min(int(rekor_tyt / HEDEF_TYT * 100), 100)
        yuzde_ayt = min(int(rekor_ayt / HEDEF_AYT * 100), 100)

        hedef_karti = kart(r, ft.Column([
            ft.Text(f"🎓 {HEDEF_UNIVERSITE}", size=15, weight=ft.FontWeight.W_800, color=r["hdr"]),
            ft.Row([ft.Text("TYT", weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    ft.Text(f"Rekor {rekor_tyt:g} / Hedef {HEDEF_TYT:g}", size=12, color=r["muted"])]),
            ilerleme_cubugu(r, yuzde_tyt / 100, r["accent"]),
            ft.Row([ft.Text("AYT", weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    ft.Text(f"Rekor {rekor_ayt:g} / Hedef {HEDEF_AYT:g}", size=12, color=r["muted"])]),
            ilerleme_cubugu(r, yuzde_ayt / 100, r["hdr"]),
        ], spacing=8))

        ad_input = girdi(r, label="Deneme Adı")
        sinav_radyo = ft.RadioGroup(
            value="TYT",
            content=ft.Row([
                ft.Radio(value="TYT", label="TYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
                ft.Radio(value="AYT", label="AYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
            ]),
        )
        tr_in = girdi(r, label="Tr/Edb", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        mat_in = girdi(r, label="Mat", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        sos_in = girdi(r, label="Sos", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        fen_in = girdi(r, label="Fen", keyboard_type=ft.KeyboardType.NUMBER, expand=True)

        def net_kaydet(e):
            ad = (ad_input.value or "").strip()
            if not ad:
                snack("Önce deneme adını yaz 📝")
                return
            tr_, mat_, sos_, fen_ = sayi(tr_in.value), sayi(mat_in.value), sayi(sos_in.value), sayi(fen_in.value)
            DB["netler"].append({
                "ad": ad, "sinav": sinav_radyo.value, "tr": tr_, "mat": mat_, "sos": sos_, "fen": fen_,
                "toplam": tr_ + mat_ + sos_ + fen_,
            })
            kaydet("netler")
            yonetici_haber(f"📈 {kullanici_adi()} yeni deneme ekledi",
                           f"{ad} ({sinav_radyo.value}) • {tr_ + mat_ + sos_ + fen_:.2f} net")
            snack("Eklendi! ✅")
            yenile()

        form = kart(r, ft.Column([
            bolum_basligi(r, ik("EDIT_NOTE"), "Yeni Deneme Ekle"),
            ad_input, sinav_radyo,
            ft.Row([tr_in, mat_in], spacing=10),
            ft.Row([sos_in, fen_in], spacing=10),
            buton(r, "Netleri Kaydet 💾", net_kaydet, genis=True),
        ], spacing=12))

        def sinav_sec(sinav):
            def f(e):
                ui["net_sinav"] = sinav
                yenile()
            return f

        secili = ui["net_sinav"]
        kayitlar = [n for n in netler if n["sinav"] == secili]
        analiz = [
            bolum_basligi(r, ik("INSIGHTS"), "Analiz"),
            ft.Row([
                buton(r, "TYT", sinav_sec("TYT"), genis=True, ikincil=secili != "TYT", yukseklik=42),
                buton(r, "AYT", sinav_sec("AYT"), genis=True, ikincil=secili != "AYT", yukseklik=42),
            ], spacing=10),
        ]
        if kayitlar:
            ilk, son = kayitlar[0], kayitlar[-1]
            ders_adlari = [("tr", "Türkçe" if secili == "TYT" else "Edb"), ("mat", "Mat"), ("sos", "Sos"), ("fen", "Fen"), ("toplam", "TOPLAM")]
            metrikler = []
            for anahtar, etiket in ders_adlari:
                fark = son[anahtar] - ilk[anahtar]
                metrikler.append(ft.Container(
                    width=96, padding=10, border_radius=14, bgcolor=r["bg"], border=kenar(1, r["border"]),
                    content=ft.Column([
                        ft.Text(etiket, size=11, color=r["muted"]),
                        ft.Text(f"{son[anahtar]:g}", size=20, weight=ft.FontWeight.BOLD, color=r["txt"]),
                        ft.Text(f"{fark:+.2f}", size=12, weight=ft.FontWeight.BOLD, color=r["accent"] if fark >= 0 else KIRMIZI),
                    ], spacing=2),
                ))
            analiz.append(ft.Row(metrikler, wrap=True, spacing=8, run_spacing=8))
            analiz.append(net_grafigi(r, kayitlar))
        else:
            analiz.append(ft.Text(f"Henüz {secili} denemesi eklenmemiş.", color=r["muted"], italic=True))
        return [hedef_karti, form, kart(r, ft.Column(analiz, spacing=12))]

    def konu_sekmesi(r):
        bitenler = set(DB["konu_bitti"])
        toplam = sum(len(v) for v in KONULAR.values())
        if ui["ders"] not in KONULAR:
            ui["ders"] = list(KONULAR.keys())[0]

        yuzde_text = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=r["hdr"])
        yuzde_bar = ilerleme_cubugu(r, 0, r["accent"])

        def oran_guncelle():
            biten = len(set(DB["konu_bitti"]))
            yuzde = int(biten / toplam * 100) if toplam else 0
            yuzde_text.value = f"Genel Müfredat: %{yuzde}  ({biten}/{toplam})"
            yuzde_bar.content.value = yuzde / 100

        oran_guncelle()

        def ders_degisti(e):
            ui["ders"] = e.control.value
            yenile()

        def konu_tikla(e):
            anahtar = e.control.data
            if e.control.value and anahtar not in DB["konu_bitti"]:
                DB["konu_bitti"].append(anahtar)
            elif not e.control.value and anahtar in DB["konu_bitti"]:
                DB["konu_bitti"].remove(anahtar)
            kaydet("konu_bitti")
            oran_guncelle()
            page.update()

        ders_dropdown = dd_olustur(
            list(KONULAR), ui["ders"], ders_degisti,
            label="Ders", border_color=r["border"],
            focused_border_color=r["hdr"], color=r["txt"], border_radius=14,
            label_style=ft.TextStyle(color=r["muted"]),
        )
        satirlar = [
            ft.Checkbox(
                label=konu, value=f"{ui['ders']}|{konu}" in bitenler, data=f"{ui['ders']}|{konu}",
                on_change=konu_tikla, fill_color=r["accent"], check_color=r["card_bg"],
                label_style=ft.TextStyle(color=r["txt"], size=14),
            )
            for konu in KONULAR[ui["ders"]]
        ]
        return [
            kart(r, ft.Column([yuzde_text, yuzde_bar], spacing=8)),
            kart(r, ft.Column([ders_dropdown, *satirlar], spacing=4)),
        ]

    def kumbara_sekmesi(r):
        yeni = girdi(r, "Örn: Ses Bilgisi", expand=True)

        def at(e):
            v = (yeni.value or "").strip()
            if v:
                DB["kumbara"].append({"eksik": v, "bitti": False})
                kaydet("kumbara")
                yenile()

        yeni.on_submit = at

        def tikla(e):
            DB["kumbara"][e.control.data]["bitti"] = e.control.value
            kaydet("kumbara")
            if e.control.value:
                kutlama()
            yenile()

        def temizle(e):
            DB["kumbara"] = [k for k in DB["kumbara"] if not k["bitti"]]
            kaydet("kumbara")
            yenile()

        icerik = [
            bolum_basligi(r, ik("TRACK_CHANGES"), "Eksik Avcısı"),
            ft.Row([yeni, ft.IconButton(icon=ik("ADD_CIRCLE"), icon_color=r["hdr"], icon_size=38, on_click=at)]),
        ]
        for i, k in enumerate(DB["kumbara"]):
            icerik.append(gorev_satiri(r, k["eksik"], k["bitti"], i, tikla))
        if not DB["kumbara"]:
            icerik.append(ft.Text("Eksik listesi şu an boş. Yanlış yaptığın konuları buraya at 🎯", color=r["muted"], italic=True, size=13))
        elif any(k["bitti"] for k in DB["kumbara"]):
            icerik.append(buton(r, "Halledilenleri Temizle", temizle, ikon=ik("CLEANING_SERVICES"), ikincil=True, genis=True, yukseklik=42))
        return [kart(r, ft.Column(icerik, spacing=10))]

    def net_sayfasi_olustur(r):
        def degisti(i):
            ui["net_tab"] = i
            yenile()
        sekmeler = [net_sekmesi, konu_sekmesi, kumbara_sekmesi]
        return ft.Column([
            sayfa_basligi(r, "Netler & Eksikler"),
            segment(r, ["📈 Netler", "📚 Müfredat", "🎯 Eksikler"], ui["net_tab"], degisti),
            *sekmeler[ui["net_tab"]](r),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 10. HAFTALIK PLAN
    # ==========================================
    def plan_sayfasi_olustur(r):
        gi = ui["plan_gun"]
        g_ad = GUNLER[gi]
        gorevler = DB["plan"][g_ad]

        def gun_sec(i):
            def f(e):
                ui["plan_gun"] = i
                yenile()
            return f

        bugun_i = datetime.now().weekday()
        cipler = []
        for i, g in enumerate(GUNLER):
            aktif = i == gi
            biten = sum(1 for t in DB["plan"][g] if t["bitti"])
            toplam = len(DB["plan"][g])
            cipler.append(ft.Container(
                width=58, padding=pad_sim(vertical=10), border_radius=16, ink=True, on_click=gun_sec(i),
                bgcolor=r["hdr"] if aktif else r["card_bg"],
                border=kenar(2 if i == bugun_i else 1, r["accent"] if i == bugun_i and not aktif else r["border"]),
                content=ft.Column([
                    ft.Text(GUN_KISA[i], size=13, weight=ft.FontWeight.W_700,
                            color=okunur_renk(r["hdr"]) if aktif else r["txt"]),
                    ft.Text(f"{biten}/{toplam}", size=11,
                            color=opak(0.8, okunur_renk(r["hdr"])) if aktif else r["muted"]),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ))

        yeni_in = girdi(r, f"{g_ad} gününe görev ekle...", expand=True)

        def ekle(e):
            v = (yeni_in.value or "").strip()
            if v:
                DB["plan"][g_ad].append({"gorev": v, "bitti": False})
                kaydet("plan")
                yenile()

        yeni_in.on_submit = ekle

        def tikla(e):
            DB["plan"][g_ad][e.control.data]["bitti"] = e.control.value
            kaydet("plan")
            yenile()

        def sil(e):
            del DB["plan"][g_ad][e.control.data]
            kaydet("plan")
            yenile()

        def haftayi_sifirla(e):
            for g in GUNLER:
                for t in DB["plan"][g]:
                    t["bitti"] = False
            kaydet("plan")
            snack("Haftanın tüm tikleri kaldırıldı 🔄")
            yenile()

        satirlar = []
        for i, t in enumerate(gorevler):
            satirlar.append(ft.Container(
                padding=pad_only(left=4, right=4), border_radius=16,
                bgcolor=opak(0.10, r["accent"]) if t["bitti"] else r["bg"],
                border=kenar(1, opak(0.5, r["border"])),
                content=ft.Row([
                    ft.Checkbox(value=t["bitti"], data=i, on_change=tikla, fill_color=r["accent"], check_color=r["card_bg"]),
                    ft.Text(t["gorev"], expand=True, size=14, weight=ft.FontWeight.W_600,
                            color=r["muted"] if t["bitti"] else r["txt"],
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if t["bitti"] else ft.TextDecoration.NONE)),
                    ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, data=i, on_click=sil),
                ], spacing=0),
            ))
        if not satirlar:
            satirlar.append(ft.Text("Bu gün için görev yok. Yukarıdan ekleyebilirsin.", color=r["muted"], italic=True, size=13))

        biten = sum(1 for t in gorevler if t["bitti"])
        return ft.Column([
            sayfa_basligi(r, "Haftalık Plan", "Eklediklerin ana sayfana yansır"),
            ft.Row(cipler, scroll=ft.ScrollMode.AUTO, spacing=8),
            kart(r, ft.Column([
                bolum_basligi(r, ik("EVENT_NOTE"), g_ad,
                              ft.Text(f"{biten}/{len(gorevler)}", size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
                ft.Row([yeni_in, ft.IconButton(icon=ik("ADD_CIRCLE"), icon_color=r["hdr"], icon_size=38, on_click=ekle)]),
                *satirlar,
            ], spacing=10)),
            buton(r, "Haftanın Tiklerini Sıfırla", haftayi_sifirla, ikon=ik("REFRESH"), ikincil=True, genis=True, yukseklik=44),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 11. GÜN SONU
    # ==========================================
    def haftalik_bar(r):
        gunler = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        saatler = [gun_sn(d.strftime("%d.%m.%Y")) / 3600.0 for d in gunler]
        mx = max(max(saatler), 1.0)
        sutunlar = []
        for d, h in zip(gunler, saatler):
            bugun_mu = d == date.today()
            sutunlar.append(ft.Column([
                ft.Text(f"{h:.1f}", size=10, color=r["muted"]),
                ft.Container(width=24, height=max(4.0, 80 * h / mx), border_radius=8,
                             bgcolor=r["hdr"] if bugun_mu else r["accent"]),
                ft.Text(GUN_KISA[d.weekday()], size=11, color=r["hdr"] if bugun_mu else r["muted"]),
            ], height=118, expand=True, alignment=ft.MainAxisAlignment.END,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4))
        return ft.Row(sutunlar, vertical_alignment=ft.CrossAxisAlignment.END)

    def gun_sonu_sayfasi_olustur(r):
        bugun = bugun_str()
        if ui["gs_tarih"] != bugun:
            mevcut_kayit = next((g for g in DB["gunluk"] if g["tarih"] == bugun), None)
            ui["gs_tarih"] = bugun
            ui["gs_puan"] = int(mevcut_kayit.get("performans", 0)) if mevcut_kayit else 0
            ui["gs_not"] = mevcut_kayit.get("gunluk", "") if mevcut_kayit else ""

        canli = gecen_sn() if zm["durum"] != "bos" else 0
        bugun_toplam = gun_sn(bugun) + canli
        baslama = DB["gun"]["baslama"] if DB["gun"].get("tarih") == bugun else ""

        def bilgi(ikon, etiket, deger):
            return ft.Row([
                ft.Icon(ikon, color=r["accent"], size=20),
                ft.Text(etiket, size=13, color=r["muted"], expand=True),
                ft.Text(deger, size=15, weight=ft.FontWeight.W_800, color=r["txt"]),
            ], spacing=10)

        ozet = kart(r, ft.Column([
            bolum_basligi(r, ik("NIGHTLIGHT_ROUND"), "Bugünün Özeti"),
            bilgi(ik("WB_SUNNY"), "Derse başlama", baslama or "Kronometre başlatılmadı"),
            bilgi(ik("TIMER"), "Çalışma süresi", sn_metni(bugun_toplam)),
            bilgi(ik("BEDTIME"), "Bitiş saati", f"Kaydedince ({datetime.now().strftime('%H:%M')})"),
            *([ft.Text("⏱ Kronometre açık, kaydedince süresi otomatik eklenecek.", size=12, color=r["hdr"])] if canli else []),
        ], spacing=12))

        def puan_sec(i):
            def f(e):
                ui["gs_puan"] = i
                yenile()
            return f

        puan_butonlari = []
        for i, (emoji, _) in enumerate(PERFORMANS, start=1):
            secili = ui["gs_puan"] == i
            puan_butonlari.append(ft.Container(
                expand=True, padding=pad_sim(vertical=12), border_radius=14, ink=True,
                alignment=ORTA, on_click=puan_sec(i),
                bgcolor=opak(0.18, r["hdr"]) if secili else r["bg"],
                border=kenar(2 if secili else 1, r["hdr"] if secili else r["border"]),
                content=ft.Text(emoji, size=28 if secili else 24),
            ))
        puan_yazi = PERFORMANS[ui["gs_puan"] - 1][1] if ui["gs_puan"] else "Bir yüz seç"

        def not_degisti(e):
            ui["gs_not"] = e.control.value

        not_in = girdi(r, "Bugün nasıl geçti, neler hissettin?", multiline=True, min_lines=3, max_lines=6,
                       value=ui["gs_not"], on_change=not_degisti)

        def gunu_kaydet(e):
            if not ui["gs_puan"]:
                snack("Önce bugünkü performansını seç 🙂")
                return
            if zm["durum"] != "bos":
                krono_bitir_kaydet()
            sn = gun_sn(bugun)
            ilk = DB["gun"]["baslama"] if DB["gun"].get("tarih") == bugun else "-"
            kayit = {
                "tarih": bugun, "baslama": ilk or "-", "bitis": datetime.now().strftime("%H:%M"),
                "sn": sn, "saat": round(sn / 3600.0, 2), "performans": ui["gs_puan"],
                "gunluk": (ui["gs_not"] or "").strip(),
            }
            DB["gunluk"] = [g for g in DB["gunluk"] if g["tarih"] != bugun] + [kayit]
            kaydet("gunluk")
            p_ = PERFORMANS[ui["gs_puan"] - 1]
            yonetici_haber(f"🌙 {kullanici_adi()} gününü kaydetti",
                           f"{sn_metni(sn)} çalıştı • {p_[0]} {p_[1]}" + (f" • {kayit['gunluk'][:80]}" if kayit["gunluk"] else ""))
            snack("Gün kaydedildi. İyi uykular! 💖")
            kutlama()
            yenile()

        performans_karti = kart(r, ft.Column([
            bolum_basligi(r, ik("EMOJI_EMOTIONS"), "Bugünkü performansın nasıldı?"),
            ft.Row(puan_butonlari, spacing=8),
            ft.Text(puan_yazi, size=13, color=r["hdr"], weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER),
            not_in,
            buton(r, "Günü Kaydet 💤", gunu_kaydet, genis=True, yukseklik=52),
        ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

        gecmis = []
        for k in reversed(DB["gunluk"][-30:]):
            p = int(k.get("performans", 0) or 0)
            emoji = PERFORMANS[p - 1][0] if 1 <= p <= 5 else "📝"
            saat_txt = sn_metni(k["sn"]) if "sn" in k else f"{sayi(k.get('saat')):g} sa"
            govde = [
                ft.Row([
                    ft.Text(k["tarih"], size=13, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                    ft.Text(emoji, size=22),
                ]),
                ft.Text(f"⏰ {k.get('baslama', '-')} → {k.get('bitis', '-')}    ⏱ {saat_txt}", size=12, color=r["muted"]),
            ]
            if k.get("gunluk"):
                govde.append(ft.Text(k["gunluk"], size=13, color=r["txt"]))
            gecmis.append(ft.Container(
                padding=12, border_radius=16, bgcolor=r["bg"], border=kenar(1, r["border"]),
                content=ft.Column(govde, spacing=4)))
        if not gecmis:
            gecmis.append(ft.Text("Henüz kayıtlı gün yok. İlk günü kaydetmeye ne dersin?", color=r["muted"], italic=True, size=13))

        return ft.Column([
            ozet, performans_karti,
            kart(r, ft.Column([bolum_basligi(r, ik("BAR_CHART"), "Son 7 Gün (saat)"), haftalik_bar(r)], spacing=12)),
            kart(r, ft.Column([bolum_basligi(r, ik("HISTORY"), "Gün Gün Kayıtlar"), *gecmis], spacing=10)),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 12. ASİSTAN, EĞLENCE, MÜZİK
    # ==========================================
    def asistan_sayfasi_olustur(r):
        soru = girdi(r, "Örn: Paragraf netlerimi nasıl artırabilirim?", label="Bugün hangi konuda yardıma ihtiyacın var?",
                     multiline=True, min_lines=2, max_lines=5)
        sonuc = ft.Column(spacing=10)
        bekle = ft.ProgressRing(visible=False, width=22, height=22, color=r["hdr"])

        def sor(e):
            q = (soru.value or "").strip()
            if not q:
                return
            if not GROQ_API_KEY and not GEMINI_API_KEY:
                snack("⚠️ API anahtarı yok! main.py'nin başındaki GROQ_API_KEY / GEMINI_API_KEY alanını doldur.")
                return
            if requests is None:
                snack("⚠️ 'requests' paketi yüklü değil.")
                return
            sonuc.controls.clear()
            bekle.visible = True
            page.update()

            def isle():
                cevap, servis, hatalar = ai_sor(q)
                if cevap:
                    sonuc.controls.append(kart(r, ft.Column([
                        ft.Text("💡 Arda'nın Cevabı:", weight=ft.FontWeight.BOLD, color=r["hdr"]),
                        ft.Text(cevap, color=r["txt"]),
                        ft.Text(f"⚡ Yanıtlayan servis: {servis}", size=11, color=r["muted"]),
                    ], spacing=8)))
                else:
                    sonuc.controls.append(ft.Text("⚠️ Sistem şu an yanıt veremedi. Detaylar:", color=KIRMIZI, weight=ft.FontWeight.BOLD))
                    for h in hatalar:
                        sonuc.controls.append(ft.Text(h, size=12, color=r["muted"]))
                bekle.visible = False
                page.update()

            threading.Thread(target=isle, daemon=True).start()

        return ft.Column([
            kart(r, ft.Column([
                ft.Text("Sınav süreciyle ilgili takıldığın soruları sorabilir, taktikler alabilirsin.", color=r["muted"], size=13),
                soru,
                ft.Row([buton(r, "Asistana Sor ✨", sor, genis=True), bekle]),
            ], spacing=12)),
            sonuc,
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    def xox_olustur(r):
        sonuc = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=r["hdr"], text_align=ft.TextAlign.CENTER)
        hucreler = []
        kazanma = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]

        def kazanan_bul(t):
            for a, b, c in kazanma:
                if t[a] == t[b] == t[c] and t[a] != "":
                    return t[a]
            return "Berabere" if "" not in t else None

        def ai_hamle(t):
            bos = [i for i, x in enumerate(t) if x == ""]
            if not bos:
                return None
            for isaret in ("⭕", "❌"):  # önce kazan, sonra engelle
                for a, b, c in kazanma:
                    satir = [t[a], t[b], t[c]]
                    if satir.count(isaret) == 2 and satir.count("") == 1:
                        return (a, b, c)[satir.index("")]
            if t[4] == "":
                return 4
            return random.choice(bos)

        def sonuc_yazisi():
            k = oyun["xox_kazanan"]
            if k == "Berabere":
                return "Kıyasıya bir mücadele! Berabere 🤝"
            if k == "❌":
                return "Tebrikler! Arda-Bot'u yendin! 🎉"
            if k == "⭕":
                return "Arda-Bot kazandı! Bir dahakine 🤖"
            return ""

        def guncelle_hucreler():
            for i, h in enumerate(hucreler):
                h.content.value = oyun["xox"][i] or "⬜"
            sonuc.value = sonuc_yazisi()
            page.update()

        def tikla(e):
            i = e.control.data
            t = oyun["xox"]
            if t[i] == "" and oyun["xox_kazanan"] is None:
                t[i] = "❌"
                k = kazanan_bul(t)
                if k is None:
                    a = ai_hamle(t)
                    if a is not None:
                        t[a] = "⭕"
                        k = kazanan_bul(t)
                oyun["xox_kazanan"] = k
                if k == "❌":
                    kutlama()
                guncelle_hucreler()

        def sifirla(e):
            oyun["xox"] = [""] * 9
            oyun["xox_kazanan"] = None
            guncelle_hucreler()

        for i in range(9):
            hucreler.append(ft.Container(
                width=78, height=78, border_radius=16, bgcolor=r["bg"], border=kenar(2, r["border"]),
                alignment=ORTA, data=i, on_click=tikla, ink=True,
                content=ft.Text(oyun["xox"][i] or "⬜", size=32),
            ))
        sonuc.value = sonuc_yazisi()
        grid = ft.Column([
            ft.Row(hucreler[0:3], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(hucreler[3:6], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(hucreler[6:9], alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=8)
        return [kart(r, ft.Column([
            bolum_basligi(r, ik("GRID_3X3"), "Arda-Bot'a Karşı XOX"),
            grid, sonuc,
            buton(r, "Oyunu Sıfırla 🔄", sifirla, genis=True, ikincil=True),
        ], spacing=14))]

    def youtube_olustur(r):
        def ac(url):
            return lambda e: url_ac(url)

        def kanal(emoji, ad, url, yazi):
            return kart(r, ft.Row([
                ft.Text(f"{emoji} {ad}", size=15, weight=ft.FontWeight.BOLD, color=r["txt"], expand=True),
                buton(r, yazi, ac(url), ikincil=True, yukseklik=40),
            ]), padding=12)

        return [
            ft.Text("Mola verdiğinde hızlıca göz atabileceğin kanallar:", size=12, color=r["muted"]),
            kanal("🔴", "RRaene", "https://www.youtube.com/@RRaenee", "Aç"),
            kanal("🟢", "Bakır Kertenkele", "https://www.youtube.com/results?search_query=bakir+kertenkele", "Ara"),
            kanal("🔵", "Deniz Yıldızı", "https://www.youtube.com/results?search_query=deniz+yildizi", "Ara"),
            kanal("⚪", "YouTube Ana Sayfa", "https://www.youtube.com", "Git"),
        ]

    def eglence_sayfasi_olustur(r):
        def degisti(i):
            ui["eglence_tab"] = i
            yenile()
        sekmeler = [xox_olustur, youtube_olustur]
        return ft.Column([
            segment(r, ["❌⭕ XOX", "📺 YouTube"], ui["eglence_tab"], degisti),
            *sekmeler[ui["eglence_tab"]](r),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    def muzik_sayfasi_olustur(r):
        def ac(url):
            return lambda e: url_ac(url)

        def liste_karti(emoji, ad, aciklama, url):
            return kart(r, ft.Row([
                ft.Text(emoji, size=30),
                ft.Column([ft.Text(ad, weight=ft.FontWeight.W_700, color=r["txt"]),
                           ft.Text(aciklama, size=12, color=r["muted"])], spacing=2, expand=True),
                ft.IconButton(icon=ik("OPEN_IN_NEW"), icon_color=r["hdr"], on_click=ac(url)),
            ], spacing=12), padding=14)

        return ft.Column([
            kart(r, ft.Column([
                ft.Icon(ik("HEADPHONES"), size=56, color=r["hdr"]),
                ft.Text("Ders Çalışma Listesi", size=19, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text("Odak listen Spotify'da seni bekliyor. Kulaklığını tak ve başla 🎶", color=r["muted"],
                        text_align=ft.TextAlign.CENTER, size=13),
                buton(r, "Spotify'da Aç", ac(SPOTIFY_URL), ikon=ik("OPEN_IN_NEW"), genis=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)),
            ft.Text("Diğer odak sesleri", size=13, color=r["muted"], weight=ft.FontWeight.W_600),
            liste_karti("🎹", "Lofi / Çalışma Müziği", "YouTube'da ara", "https://www.youtube.com/results?search_query=lofi+study+music"),
            liste_karti("🌧️", "Yağmur Sesi", "YouTube'da ara", "https://www.youtube.com/results?search_query=rain+sounds+for+studying"),
            liste_karti("🌊", "Beyaz Gürültü", "YouTube'da ara", "https://www.youtube.com/results?search_query=white+noise+focus"),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)


    # ==========================================
    # 12c. SOSYAL (Fotoğraf Akışı + Genel/Özel Sohbet + 🔥 Seri + 🎮 2 Kişilik Online Oyunlar)
    # ==========================================
    def silebilir(sahip):
        return oturum["kullanici"] in (sahip, sosyal["admin"]) and bool(oturum["kullanici"])

    def avatar(r, ad, boyut=36):
        return ft.Container(
            width=boyut, height=boyut, border_radius=boyut / 2, alignment=ORTA, bgcolor=r["hdr"],
            content=ft.Text((ad or "?")[:1].upper(), size=boyut * 0.45, weight=ft.FontWeight.BOLD, color=okunur_renk(r["hdr"])))

    def rozetli_ikon_buton(r, ikon_adi, sayi_degeri, tikla, ipucu=""):
        """Sosyal başlığının sağ üstündeki bildirim rozetli ikon düğmesi (360px ekranlara tam uyumlu)."""
        btn = ft.IconButton(icon=ik(ikon_adi), icon_color=r["hdr"], icon_size=22, on_click=tikla, tooltip=ipucu)
        if not sayi_degeri or int(sayi_degeri) <= 0:
            return ft.Container(width=42, height=42, alignment=ORTA, content=btn)
        etiket = "9+" if int(sayi_degeri) > 9 else str(int(sayi_degeri))
        rozet = ft.Container(
            right=2, top=2, width=18, height=18, border_radius=9,
            bgcolor=KIRMIZI, alignment=ORTA,
            content=ft.Text(etiket, size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        )
        return ft.Stack([ft.Container(width=42, height=42, alignment=ORTA, content=btn), rozet], width=42, height=42)

    def kullanici_listesi_cek(zorla=False):
        """Kayıtlı kullanıcı adlarını önbellekli olarak buluttan getirir."""
        simdi = time.time()
        if not zorla and sosyal["kullanicilar_cache"] and (simdi - sosyal.get("kullanicilar_ts", 0)) < 20:
            return sosyal["kullanicilar_cache"]
        try:
            ham = bulut_oku() or {}
            isimler = sorted(k for k, v in ham.items() if isinstance(v, dict))
            with kilit:
                sosyal["kullanicilar_cache"] = isimler
                sosyal["kullanicilar_ts"] = simdi
                for k, v in ham.items():
                    if isinstance(v, dict):
                        sosyal["kullanici_bildirim_cache"][k] = {
                            "bildirim": v.get("bildirim") or {},
                            "aktif_ekran": v.get("aktif_ekran") or "",
                            "son_aktif": v.get("son_aktif") or 0,
                            "ts": simdi,
                        }
            return isimler
        except Exception as ex:
            print("Kullanıcı listesi alınamadı:", ex)
            return sosyal["kullanicilar_cache"]

    def hedef_kullanici_durumu_getir(hedef):
        """Alıcının bildirim ayarlarını ve açık ekran bilgisini getirir (önbellekli)."""
        simdi = time.time()
        cached = sosyal["kullanici_bildirim_cache"].get(hedef)
        if cached and (simdi - cached.get("ts", 0)) < 15:
            return cached
        try:
            b_ = bulut_get(f"users/{hedef}/bildirim") or {}
            ekran_ = bulut_get(f"users/{hedef}/aktif_ekran") or ""
            son_ = bulut_get(f"users/{hedef}/son_aktif") or 0
            veri = {"bildirim": b_, "aktif_ekran": ekran_, "son_aktif": son_, "ts": simdi}
            sosyal["kullanici_bildirim_cache"][hedef] = veri
            return veri
        except Exception:
            return cached or {}

    def sosyal_bildirim_yolla(hedef, kategori, baslik, mesaj, oncelik=3, beklenen_ekran=None, senkron=False, simdi_ms=None):
        """Alıcının tercihlerine, sessiz saatlere ve açık ekranına saygı duyarak ntfy bildirimi gönderir."""
        ben = oturum["kullanici"]
        if not hedef or hedef == ben:
            return False

        def is_():
            try:
                hedef_db = hedef_kullanici_durumu_getir(hedef)
                z_ms = int(simdi_ms if simdi_ms is not None else time.time() * 1000)
                izn, _ = sosyal_bildirim_karar(
                    hedef, ben, kategori, hedef_db, z_ms,
                    oran_durumu=sosyal["oran_durumu"], beklenen_ekran=beklenen_ekran,
                )
                if not izn:
                    return False
                konu = (hedef_db.get("bildirim") or {}).get("konu", "")
                if konu:
                    ok, _ = ntfy_gonder(konu, baslik, mesaj, oncelik)
                    return ok
            except Exception as ex:
                print("Sosyal bildirim hatası:", ex)
            return False

        if senkron:
            return is_()
        arka_plan(is_)
        return True

    def toplu_sosyal_bildirim_yolla(kategori, baslik, mesaj, oncelik=3, beklenen_ekran=None, senkron=False):
        """Gönderen dışındaki tüm kullanıcılara (tercihlerine göre) bildirim yollar."""
        ben = oturum["kullanici"]

        def is_():
            isimler = kullanici_listesi_cek()
            for u_ in isimler:
                if u_ != ben:
                    sosyal_bildirim_yolla(u_, kategori, baslik, mesaj, oncelik=oncelik,
                                          beklenen_ekran=beklenen_ekran, senkron=True)

        if senkron:
            is_()
        else:
            arka_plan(is_)

    def okunmamis_sohbet_sayisi():
        """Özel sohbetlerdeki okunmamış mesaj toplamını döndürür."""
        toplam = 0
        for pid, d in (sosyal.get("dm_index") or {}).items():
            if isinstance(d, dict):
                toplam += int(d.get("okunmamis") or 0)
        return toplam

    def aktif_oyun_bildirim_sayisi():
        """Bekleyen oyun davetleri + sırası bende olan aktif oyunların sayısını döndürür."""
        ben = oturum["kullanici"]
        if not ben:
            return 0
        adet = 0
        for gid, g in (sosyal.get("oyunlar") or {}).items():
            if not isinstance(g, dict):
                continue
            oyuncular = g.get("oyuncular") or {}
            durum = g.get("durum")
            if durum == "bekliyor" and oyuncular.get("b") == ben:
                adet += 1
            elif durum == "oynuyor":
                tur = g.get("tur")
                if tur == "yks_quiz":
                    rol = "a" if oyuncular.get("a") == ben else "b"
                    cevaplar = listeye(((g.get("tahta") or {}).get("cevaplar") or {}).get(rol))
                    sorular = listeye((g.get("tahta") or {}).get("sorular"))
                    if len(cevaplar) < len(sorular):
                        adet += 1
                elif tur == "tkm":
                    rol = "a" if oyuncular.get("a") == ben else "b"
                    secim = (((g.get("tahta") or {}).get("secim") or {}).get(rol))
                    if not secim:
                        adet += 1
                elif g.get("sira") == ben:
                    adet += 1
        return adet

    # ---------- VERİ ÇEKME VE CANLI GÜNCELLEME ----------
    def sosyal_cek(hangisi="akis"):
        """Buluttan akış, genel sohbet, özel sohbet (dm) veya oyun verisini alır. Değiştiyse True döner."""
        sosyal["son_cek"][hangisi] = time.time()
        ben = oturum["kullanici"]
        if not ben:
            return False
        try:
            sosyal["admin"] = (bulut_get("yonetici") or {}).get("kullanici", "")
            if hangisi in (0, "akis"):
                ham = bulut_get("sosyal/posts", {"orderBy": '"$key"', "limitToLast": 30}) or {}
                posts = {k: v for k, v in ham.items() if isinstance(v, dict)}
                for pid in sorted(posts, reverse=True):
                    if pid not in sosyal["resim"]:
                        d = bulut_get(f"sosyal/resim/{pid}/d")
                        if isinstance(d, str) and d:
                            sosyal["resim"][pid] = d
                while len(sosyal["resim"]) > 60:
                    sosyal["resim"].pop(min(sosyal["resim"]))
                # Rozetlerin güncel kalması için dm_index ve oyun özetini de hafifçe kontrol et
                dm_ham = bulut_get(f"dm_index/{ben}") or {}
                sosyal["dm_index"] = {k: v for k, v in dm_ham.items() if isinstance(v, dict)}
                imza = (
                    sorted((k, len(v.get("begeni") or {}), len(v.get("yorumlar") or {})) for k, v in posts.items()),
                    len(sosyal["resim"]),
                    okunmamis_sohbet_sayisi(),
                    aktif_oyun_bildirim_sayisi(),
                )
                degisti = imza != sosyal["imza"].get("akis")
                sosyal["posts"] = posts
                sosyal["imza"]["akis"] = imza
                return degisti

            if hangisi in (1, "genel"):
                ham = bulut_get("sosyal/sohbet", {"orderBy": '"$key"', "limitToLast": 60}) or {}
                mesajlar = {k: v for k, v in ham.items() if isinstance(v, dict)}
                imza = sorted((k, len(v.get("b") or {})) for k, v in mesajlar.items())
                degisti = imza != sosyal["imza"].get("sohbet")
                sosyal["sohbet"] = mesajlar
                sosyal["imza"]["sohbet"] = imza
                sosyal["oran_durumu"].pop(f"genel_bekliyor:{ben}", None)
                return degisti

            if hangisi == "dm_liste":
                dm_ham = bulut_get(f"dm_index/{ben}") or {}
                dm_idx = {k: v for k, v in dm_ham.items() if isinstance(v, dict)}
                seri_ham = bulut_get("seri") or {}
                seri_map = {k: v for k, v in seri_ham.items() if isinstance(v, dict)}
                imza = (
                    sorted((k, v.get("sonZaman", 0), v.get("okunmamis", 0), v.get("son", "")) for k, v in dm_idx.items()),
                    sorted((k, v.get("sayi", 0), v.get("sonSayilanGun", ""), v.get("a_gun", ""), v.get("b_gun", ""))
                           for k, v in seri_map.items()),
                )
                degisti = imza != sosyal["imza"].get("dm_liste")
                sosyal["dm_index"] = dm_idx
                sosyal["seri"] = seri_map
                sosyal["imza"]["dm_liste"] = imza
                return degisti

            if hangisi == "dm_aktif":
                pid = ui.get("aktif_dm")
                if not pid:
                    return False
                ham = bulut_get(f"dm/{pid}/mesajlar", {"orderBy": '"$key"', "limitToLast": 60}) or {}
                mesajlar = {k: v for k, v in ham.items() if isinstance(v, dict)}
                s_kayit = bulut_get(f"seri/{pid}") or {}
                if isinstance(s_kayit, dict):
                    sosyal["seri"][pid] = s_kayit
                # Konuşma açıkken okunmamış sayacını sıfırla
                mevcut_idx = (sosyal["dm_index"].get(pid) or {})
                if int(mevcut_idx.get("okunmamis") or 0) > 0:
                    mevcut_idx["okunmamis"] = 0
                    mevcut_idx["sonGorulme"] = int(time.time() * 1000)
                    bulut_patch(f"dm_index/{ben}/{pid}", {"okunmamis": 0, "sonGorulme": mevcut_idx["sonGorulme"]})
                imza = (
                    sorted((k, len(v.get("b") or {})) for k, v in mesajlar.items()),
                    s_kayit.get("sayi", 0) if isinstance(s_kayit, dict) else 0,
                    s_kayit.get("a_gun", "") if isinstance(s_kayit, dict) else "",
                    s_kayit.get("b_gun", "") if isinstance(s_kayit, dict) else "",
                )
                degisti = imza != sosyal["imza"].get(f"dm:{pid}")
                sosyal["dm_mesajlar"][pid] = mesajlar
                sosyal["imza"][f"dm:{pid}"] = imza
                return degisti

            if hangisi == "oyun_lobi":
                indeks = bulut_get(f"oyuncu_oyunlari/{ben}") or {}
                oyunlar_map = {}
                simdi_ms = int(time.time() * 1000)
                if isinstance(indeks, dict):
                    for gid in sorted(indeks, reverse=True)[:40]:
                        g = bulut_get(f"oyunlar/{gid}")
                        if isinstance(g, dict):
                            # 24 saat hareketsiz kalan oyunları otomatik iptal et
                            za = oyun_zaman_asimi_durumu(g, simdi_ms)
                            if za["iptal_24s"]:
                                g["durum"] = "iptal"
                                bulut_patch(f"oyunlar/{gid}", {"durum": "iptal"})
                            oyunlar_map[gid] = g
                skor_ham = bulut_get("oyunlar_skor") or {}
                skor_map = {k: v for k, v in skor_ham.items() if isinstance(v, dict)}
                imza = (
                    sorted((k, v.get("durum", ""), v.get("hamleNo", 0), v.get("sira", ""), v.get("kazanan", ""))
                           for k, v in oyunlar_map.items()),
                    sorted((u, str(s)) for u, s in skor_map.items()),
                )
                degisti = imza != sosyal["imza"].get("oyun_lobi")
                sosyal["oyunlar"] = oyunlar_map
                sosyal["oyun_skor"] = skor_map
                sosyal["imza"]["oyun_lobi"] = imza
                return degisti

            if hangisi == "oyun_aktif":
                gid = ui.get("aktif_oyun")
                if not gid:
                    return False
                g = bulut_get(f"oyunlar/{gid}")
                if not isinstance(g, dict):
                    return False
                simdi_ms = int(time.time() * 1000)
                # Oyuncunun oyunu açık tuttuğunu kaydet (60 sn sıra bildirimi kontrolü için)
                bulut_patch(f"oyunlar/{gid}/sonGorulme", {ben: simdi_ms})
                g.setdefault("sonGorulme", {})[ben] = simdi_ms
                za = oyun_zaman_asimi_durumu(g, simdi_ms)
                if za["iptal_24s"] and g.get("durum") in ("bekliyor", "oynuyor"):
                    g["durum"] = "iptal"
                    bulut_patch(f"oyunlar/{gid}", {"durum": "iptal"})

                # Rakip > 60 sn oyuna bakmadıysa ve sıra rakipteyse 1 kez "sıra sende" bildirimi gönder
                if g.get("durum") == "oynuyor":
                    oyuncular = g.get("oyuncular") or {}
                    rakip = oyuncular.get("b") if oyuncular.get("a") == ben else oyuncular.get("a")
                    sira_kimde = g.get("sira", "")
                    hamle_no = int(g.get("hamleNo") or 0)
                    son_hamle_ms = int(g.get("sonHamle") or 0)
                    rakip_gorulme = int((g.get("sonGorulme") or {}).get(rakip) or 0)
                    bildirim_hamle = int(g.get("bildirimHamleNo") or -1)
                    if (rakip and sira_kimde == rakip and hamle_no > 0 and bildirim_hamle != hamle_no
                            and (simdi_ms - son_hamle_ms) >= 60_000 and (simdi_ms - rakip_gorulme) >= 60_000):
                        g["bildirimHamleNo"] = hamle_no
                        bulut_patch(f"oyunlar/{gid}", {"bildirimHamleNo": hamle_no})
                        tur_ad = (OYUN_TURLERI.get(g.get("tur"), {})).get("ad", "Oyun")
                        sosyal_bildirim_yolla(
                            rakip, "sosyal_oyun", f"🎮 {tur_ad}: Sıra Sende!",
                            f"{ben} hamlesini yaptı, {tur_ad} oyununda sıra sende!",
                            oncelik=3, beklenen_ekran=f"oyun:{gid}",
                        )

                eski = sosyal["oyunlar"].get(gid) or {}
                # Eski durumdan düşük hamleNo geldiyse (bayat veri) yoksay
                if int(g.get("hamleNo") or 0) < int(eski.get("hamleNo") or 0) and g.get("durum") == eski.get("durum"):
                    return False

                imza = (g.get("durum"), g.get("hamleNo"), g.get("sira"), g.get("kazanan"),
                        str(g.get("tahta")), za["hukmen_2dk"])
                degisti = imza != sosyal["imza"].get(f"oyun:{gid}")
                sosyal["oyunlar"][gid] = g
                sosyal["imza"][f"oyun:{gid}"] = imza
                return degisti
        except Exception as ex:
            print("Sosyal veri alınamadı:", ex)
            return False

    def sosyal_ui_guncelle():
        """Sadece ilgili alt konteyneri yerinde yeniler (yazılan metin silinmez, sayfa en üste sıçramaz)."""
        try:
            r = renk()
            alt = ui.get("sosyal_alt")
            if alt is None and sosyal["akis_kap"] is not None:
                sosyal["akis_kap"].controls = [duzelt(c) for c in akis_kartlari(r)]
                sosyal["akis_kap"].update()
            elif alt == "sohbet":
                if ui.get("aktif_dm"):
                    pid = ui["aktif_dm"]
                    if sosyal["dm_mesaj_kap"] is not None:
                        sosyal["dm_mesaj_kap"].controls = dm_mesaj_balonlari(r, pid)
                        sosyal["dm_mesaj_kap"].update()
                    if sosyal["dm_baslik_seri"] is not None:
                        rozet_txt, gorunur, riskli, _ = alev_rozeti(sosyal["seri"].get(pid), istanbul_bugun())
                        sosyal["dm_baslik_seri"].value = rozet_txt if gorunur else ""
                        sosyal["dm_baslik_seri"].color = r["muted"] if riskli else TURUNCU
                        sosyal["dm_baslik_seri"].update()
                elif ui.get("sohbet_tab") == 0 and sosyal["sohbet_kap"] is not None:
                    sosyal["sohbet_kap"].controls = mesaj_balonlari(r)
                    sosyal["sohbet_kap"].update()
                elif ui.get("sohbet_tab") == 1 and sosyal["dm_liste_kap"] is not None:
                    sosyal["dm_liste_kap"].controls = [duzelt(c) for c in dm_konusma_kartlari(r)]
                    sosyal["dm_liste_kap"].update()
            elif alt == "oyun":
                if ui.get("aktif_oyun") and sosyal["oyun_tahta_kap"] is not None:
                    gid = ui["aktif_oyun"]
                    g = sosyal["oyunlar"].get(gid) or {}
                    sosyal["oyun_tahta_kap"].controls = [duzelt(c) for c in oyun_ekrani_icerigi(r, gid, g)]
                    sosyal["oyun_tahta_kap"].update()
                elif not ui.get("aktif_oyun") and sosyal["oyun_lobi_kap"] is not None:
                    sosyal["oyun_lobi_kap"].controls = [duzelt(c) for c in oyun_lobi_kartlari(r)]
                    sosyal["oyun_lobi_kap"].update()
        except Exception as ex:
            print("Sosyal ekran yenilenemedi:", ex)

    def sosyal_getir(hangisi="akis"):
        if sosyal_cek(hangisi):
            sosyal_ui_guncelle()

    # ---------- 1) FOTOĞRAF AKIŞI ----------
    def foto_sec(sonra):
        """Telefondan fotoğraf seçtirir. sonra(bayt_veya_None, hata_metni) çağrılır."""
        def dosyalar_islensin(dosyalar):
            if not dosyalar:
                return sonra(None, "")
            f = dosyalar[0]
            veri = getattr(f, "bytes", None)
            if not veri and getattr(f, "path", None):
                try:
                    with open(f.path, "rb") as fh:
                        veri = fh.read()
                except Exception as ex:
                    return sonra(None, f"Dosya okunamadı: {ex}")
            sonra(veri, "" if veri else "Dosya okunamadı")

        try:
            secici = ft.FilePicker(on_result=lambda e: dosyalar_islensin(e.files))
            page.overlay.append(secici)
            page.update()
            secici.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
            return
        except TypeError:
            pass
        except Exception as ex:
            print("Eski FilePicker çalışmadı:", ex)

        async def _sec():
            try:
                dosyalar = await ft.FilePicker().pick_files(
                    allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE, with_data=True)
                dosyalar_islensin(dosyalar)
            except Exception as ex:
                sonra(None, f"Fotoğraf seçici açılamadı: {ex}")
        try:
            page.run_task(_sec)
        except Exception as ex:
            sonra(None, f"Fotoğraf seçici açılamadı: {ex}")

    def gonderi_karti(r, pid, p):
        ben = oturum["kullanici"]
        sahip = p.get("kullanici", "")
        begeniler = p.get("begeni") or {}
        yorumlar = p.get("yorumlar") or {}
        beniyor = ben in begeniler
        genislik = max(240, int((page.width or 400) - 32 - 28))
        b64 = sosyal["resim"].get(pid)

        def begen(e):
            b_ = p.setdefault("begeni", {})
            if ben in b_:
                del b_[ben]
                deger = None
            else:
                b_[ben] = True
                deger = True
                if sahip and sahip != ben:
                    sosyal_bildirim_yolla(
                        sahip, "sosyal_etkilesim", "❤️ Fotoğrafın Beğenildi",
                        f"{ben} paylaştığın fotoğrafı beğendi!", oncelik=3,
                    )
            arka_plan(lambda: bulut_patch(f"sosyal/posts/{pid}/begeni", {ben: deger}))
            yenile()

        def yorumlari_ac(e):
            if pid in sosyal["yorum_acik"]:
                sosyal["yorum_acik"].discard(pid)
            else:
                sosyal["yorum_acik"].add(pid)
            yenile()

        def sil(e):
            sosyal["posts"].pop(pid, None)
            sosyal["resim"].pop(pid, None)

            def is_():
                try:
                    bulut_sil(f"sosyal/posts/{pid}")
                    bulut_sil(f"sosyal/resim/{pid}")
                except Exception as ex:
                    snack(f"⚠️ Silinemedi: {ex}")
            arka_plan(is_)
            yenile()

        ust = ft.Row([
            avatar(r, sahip),
            ft.Column([ft.Text(sahip or "?", size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                       ft.Text(zaman_oncesi(p.get("zaman")), size=11, color=r["muted"])], spacing=0, expand=True),
            *([ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=r["muted"], on_click=sil)] if silebilir(sahip) else []),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        if b64:
            gorsel = ft.Container(width=genislik, height=genislik, border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                  content=resim_olustur(b64, width=genislik, height=genislik))
        else:
            gorsel = ft.Container(width=genislik, height=genislik, border_radius=14, bgcolor=r["bg"], alignment=ORTA,
                                  content=ft.ProgressRing(width=28, height=28, color=r["hdr"]))

        eylemler = ft.Row([
            ft.IconButton(icon=ik("FAVORITE") if beniyor else ik("FAVORITE_BORDER"),
                          icon_color="#E53935" if beniyor else r["txt"], on_click=begen),
            ft.Text(str(len(begeniler)), size=13, color=r["txt"], weight=ft.FontWeight.W_700),
            ft.Container(width=8),
            ft.IconButton(icon=ik("CHAT_BUBBLE_OUTLINE"), icon_color=r["txt"], on_click=yorumlari_ac),
            ft.Text(str(len(yorumlar)), size=13, color=r["txt"], weight=ft.FontWeight.W_700),
        ], spacing=0)

        govde = [ust, gorsel, eylemler]
        if p.get("aciklama"):
            govde.append(ft.Row([ft.Text(sahip, size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                                 ft.Text(p["aciklama"], size=13, color=r["txt"])], wrap=True, spacing=6))
        sirali = [yorumlar[k] for k in sorted(yorumlar) if isinstance(yorumlar[k], dict)]
        acik = pid in sosyal["yorum_acik"]
        gosterilecek = sirali if acik else sirali[-2:]
        if sirali and not acik and len(sirali) > 2:
            govde.append(ft.Text(f"{len(sirali)} yorumun tümünü gör", size=12, color=r["muted"]))
        for y in gosterilecek:
            govde.append(ft.Row([ft.Text(y.get("k", ""), size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                                 ft.Text(y.get("m", ""), size=13, color=r["txt"])], wrap=True, spacing=6))
        if acik:
            yorum_in = girdi(r, "Yorum ekle...", expand=True, text_size=13)

            def yorum_yolla(e):
                m = (yorum_in.value or "").strip()
                if not m:
                    return
                cid = yeni_id()
                kayit = {"k": ben, "m": m[:300], "z": int(time.time() * 1000)}
                p.setdefault("yorumlar", {})[cid] = kayit
                arka_plan(lambda: bulut_patch(f"sosyal/posts/{pid}/yorumlar", {cid: kayit}))
                if sahip and sahip != ben:
                    sosyal_bildirim_yolla(
                        sahip, "sosyal_etkilesim", f"💬 {ben} fotoğrafına yorum yaptı",
                        m[:120], oncelik=3,
                    )
                yenile()

            yorum_in.on_submit = yorum_yolla
            govde.append(ft.Row([yorum_in, ft.IconButton(icon=ik("SEND"), icon_color=r["hdr"], on_click=yorum_yolla)]))
        return kart(r, ft.Column(govde, spacing=8), padding=14)

    def akis_kartlari(r):
        if not sosyal["posts"]:
            durum = "Henüz paylaşım yok. İlk fotoğrafı sen paylaş 📸" if sosyal["imza"].get("akis") is not None \
                else "Yükleniyor…"
            return [ft.Text(durum, color=r["muted"], italic=True)]
        return [gonderi_karti(r, pid, sosyal["posts"][pid]) for pid in sorted(sosyal["posts"], reverse=True)]

    def paylas_karti(r):
        def secildi(veri, hata):
            if hata:
                sosyal["foto_mesaj"] = hata
            elif veri:
                b64, h = foto_hazirla(veri)
                sosyal["yeni_foto"] = b64
                sosyal["foto_mesaj"] = h
            yenile()

        def sec(e):
            sosyal["foto_mesaj"] = ""
            foto_sec(secildi)

        def aciklama_degisti(e):
            sosyal["yeni_aciklama"] = e.control.value

        def paylas(e):
            if not sosyal["yeni_foto"]:
                snack("Önce bir fotoğraf seç 📷")
                return
            pid, ben = yeni_id(), oturum["kullanici"]
            b64, aciklama = sosyal["yeni_foto"], (sosyal["yeni_aciklama"] or "").strip()[:500]
            zaman = int(time.time() * 1000)
            sosyal["posts"][pid] = {"kullanici": ben, "aciklama": aciklama, "zaman": zaman}
            sosyal["resim"][pid] = b64
            sosyal["yeni_foto"], sosyal["yeni_aciklama"], sosyal["foto_mesaj"] = None, "", ""

            def is_():
                try:
                    bulut_patch(f"sosyal/resim/{pid}", {"d": b64})
                    bulut_patch(f"sosyal/posts/{pid}", {"kullanici": ben, "aciklama": aciklama, "zaman": zaman})
                    toplu_sosyal_bildirim_yolla(
                        "sosyal_foto", f"📸 {ben} yeni bir fotoğraf paylaştı",
                        aciklama[:100] if aciklama else "Sosyal akışta yeni bir fotoğraf var! Göz at 👀",
                        oncelik=3, beklenen_ekran="akis", senkron=True,
                    )
                    snack("📸 Paylaşıldı!")
                except Exception as ex:
                    snack(f"⚠️ Paylaşılamadı: {ex}")
            arka_plan(is_)
            yenile()

        icerik = [bolum_basligi(r, ik("ADD_PHOTO_ALTERNATE"), "Yeni paylaşım")]
        if sosyal["yeni_foto"]:
            gn = max(160, int((page.width or 400) - 32 - 36))
            icerik.append(ft.Container(width=gn, height=gn, border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                       content=resim_olustur(sosyal["yeni_foto"], width=gn, height=gn)))
        if sosyal["foto_mesaj"]:
            icerik.append(ft.Text(sosyal["foto_mesaj"], size=12, color=KIRMIZI))
        icerik.append(buton(r, "Fotoğrafı değiştir" if sosyal["yeni_foto"] else "Fotoğraf seç", sec,
                            ikon=ik("ADD_PHOTO_ALTERNATE"), genis=True, ikincil=True, yukseklik=44))
        icerik.append(girdi(r, "Bir açıklama yaz...", value=sosyal["yeni_aciklama"], on_change=aciklama_degisti,
                            multiline=True, min_lines=1, max_lines=3))
        icerik.append(buton(r, "Paylaş", paylas, genis=True, yukseklik=46))
        return kart(r, ft.Column(icerik, spacing=10), padding=14)

    # ---------- 2) SOHBET SİSTEMİ (GENEL SOHBET + ÖZEL SOHBETLER + 🔥 SERİ) ----------
    def ortak_balon_listesi(r, mesajlar_dict, begen_yol_fn, sil_yol_fn):
        """Hem genel sohbet hem özel sohbet için genişlik sınırlamalı mesaj balonlarını üretir."""
        ben = oturum["kullanici"]
        if not mesajlar_dict:
            return [ft.Text("Henüz mesaj yok, ilk mesajı sen yaz 💬", color=r["muted"], italic=True)]
        maks = int((page.width or 400) * 0.66)
        cikti = []
        for mid in sorted(mesajlar_dict):
            m = mesajlar_dict[mid]
            if not isinstance(m, dict):
                continue
            benim = m.get("k") == ben
            begeniler = m.get("b") or {}
            beniyor = ben in begeniler
            metin = str(m.get("m", ""))

            def begen(e, mid=mid, m=m):
                b_ = m.setdefault("b", {})
                if ben in b_:
                    del b_[ben]
                    deger = None
                else:
                    b_[ben] = True
                    deger = True
                arka_plan(lambda: bulut_patch(begen_yol_fn(mid), {ben: deger}))
                sosyal_ui_guncelle()

            def sil(e, mid=mid):
                mesajlar_dict.pop(mid, None)
                arka_plan(lambda: bulut_sil(sil_yol_fn(mid)))
                sosyal_ui_guncelle()

            genislik = int(min(max(len(metin) * 8.5 + 30, 80), maks))
            balon = ft.Container(
                width=genislik, padding=pad_sim(horizontal=12, vertical=9), border_radius=18,
                bgcolor=r["hdr"] if benim else r["card_bg"], border=kenar(1, r["hdr"] if benim else r["border"]),
                content=ft.Text(metin, size=14, color=okunur_renk(r["hdr"]) if benim else r["txt"]))
            alt = ft.Row([
                ft.Container(on_click=begen, padding=pad_sim(horizontal=4, vertical=2),
                             content=ft.Text(("❤️ " + str(len(begeniler))) if beniyor else
                                             ("🤍 " + str(len(begeniler)) if begeniler else "🤍"), size=12)),
                ft.Text(zaman_oncesi(m.get("z")), size=10, color=r["muted"]),
                *([ft.Container(on_click=sil, padding=pad_sim(horizontal=4), content=ft.Icon(ik("DELETE_OUTLINE"), size=14, color=r["muted"]))]
                  if silebilir(m.get("k")) else []),
            ], spacing=4, alignment=ft.MainAxisAlignment.END if benim else ft.MainAxisAlignment.START)
            if benim:
                cikti.append(ft.Column([ft.Row([balon], alignment=ft.MainAxisAlignment.END), alt], spacing=0,
                                       horizontal_alignment=ft.CrossAxisAlignment.END))
            else:
                cikti.append(ft.Row([
                    avatar(r, m.get("k"), 30),
                    ft.Column([ft.Text(m.get("k", "?"), size=11, color=r["muted"], weight=ft.FontWeight.W_700), balon, alt], spacing=2),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
        return cikti

    def mesaj_balonlari(r):
        return ortak_balon_listesi(
            r, sosyal["sohbet"],
            lambda mid: f"sosyal/sohbet/{mid}/b",
            lambda mid: f"sosyal/sohbet/{mid}",
        )

    def dm_mesaj_balonlari(r, pid):
        mesajlar = sosyal["dm_mesajlar"].get(pid) or {}
        return ortak_balon_listesi(
            r, mesajlar,
            lambda mid: f"dm/{pid}/mesajlar/{mid}/b",
            lambda mid: f"dm/{pid}/mesajlar/{mid}",
        )

    def dm_mesaj_gonder_islem(hedef_kullanici, metin, senkron=False, simdi_ms=None, bugun_override=None):
        """Özel mesaj gönderir, dm_index'leri ve seri (streak) kaydını günceller, bildirimleri tetikler."""
        ben = oturum["kullanici"]
        hedef = str(hedef_kullanici or "").strip().lower()
        m = str(metin or "").strip()[:500]
        if not ben or not hedef or ben == hedef or not m:
            return None
        pid = cift_id(ben, hedef)
        zaman = int(simdi_ms if simdi_ms is not None else time.time() * 1000)
        bugun_iso = bugun_override or istanbul_bugun(zaman / 1000.0)
        mid = f"{zaman:013d}{os.urandom(2).hex()}"
        kayit = {"k": ben, "m": m, "z": zaman}

        sosyal["dm_mesajlar"].setdefault(pid, {})[mid] = kayit
        sosyal["dm_index"][pid] = {
            "diger": hedef, "son": m[:80], "sonZaman": zaman,
            "okunmamis": 0, "sonGorulme": zaman,
        }

        def is_():
            try:
                bulut_patch(f"dm/{pid}/mesajlar/{mid}", kayit)
                bulut_patch(f"dm_index/{ben}/{pid}", {
                    "diger": hedef, "son": m[:80], "sonZaman": zaman,
                    "okunmamis": 0, "sonGorulme": zaman,
                })
                karsi_idx = bulut_get(f"dm_index/{hedef}/{pid}") or {}
                karsi_okunmamis = int((karsi_idx.get("okunmamis") if isinstance(karsi_idx, dict) else 0) or 0) + 1
                bulut_patch(f"dm_index/{hedef}/{pid}", {
                    "diger": ben, "son": m[:80], "sonZaman": zaman,
                    "okunmamis": karsi_okunmamis,
                })

                # Seri (streak) güncelleme (idempotent ve yarış-güvenli)
                u_a, u_b = cift_kullanicilar(pid)
                alan = "a_gun" if ben == u_a else "b_gun"
                bulut_patch(f"seri/{pid}", {alan: bugun_iso})
                mevcut_seri = bulut_get(f"seri/{pid}") or {}
                yeni_seri, olay = seri_guncelle_pure(mevcut_seri, ben, u_a, u_b, bugun_iso)
                bulut_patch(f"seri/{pid}", yeni_seri)
                sosyal["seri"][pid] = yeni_seri

                # Anlık özel mesaj bildirimi
                sosyal_bildirim_yolla(
                    hedef, "sosyal_dm", f"✉️ {ben}", m[:120],
                    oncelik=4, beklenen_ekran=f"dm:{pid}", senkron=senkron, simdi_ms=zaman,
                )

                # Seri başlangıç / milestone bildirimleri ve başarım kontrolü
                if olay == "basladi":
                    snack(f"🔥 {hedef} ile 2 günlük sohbet seriniz başladı!")
                    kutlama()
                    sosyal_bildirim_yolla(
                        hedef, "sosyal_seri", "🔥 Seri Başladı!",
                        f"{ben} ile 2 günlük sohbet seriniz başladı! Ateşi koruyun 🔥",
                        oncelik=4, senkron=senkron, simdi_ms=zaman,
                    )
                elif olay.startswith("milestone_"):
                    gun_s = yeni_seri["sayi"]
                    snack(f"🏆 Muhteşem! {hedef} ile {gun_s} günlük seriye ulaştınız! 🔥")
                    kutlama()
                    sosyal_bildirim_yolla(
                        hedef, "sosyal_seri", f"🏆 {gun_s} Günlük Seri!",
                        f"Harika! {ben} ile {gun_s} günlük kesintisiz sohbet serisine ulaştınız! 🔥🔥",
                        oncelik=4, senkron=senkron, simdi_ms=zaman,
                    )
            except Exception as ex:
                print("Özel mesaj gönderim hatası:", ex)

        if senkron:
            is_()
        else:
            arka_plan(is_)
        return pid

    def dm_konusma_kartlari(r):
        ben = oturum["kullanici"]
        bugun_iso = istanbul_bugun()
        indeks = sosyal.get("dm_index") or {}
        sirali = sorted(
            [(pid, v) for pid, v in indeks.items() if isinstance(v, dict)],
            key=lambda x: sayi(x[1].get("sonZaman"), 0),
            reverse=True,
        )
        if not sirali:
            return [ft.Text("Henüz özel sohbetin yok. '＋ Yeni sohbet' düğmesinden bir arkadaşını seç 💬🔥",
                            color=r["muted"], italic=True, size=13)]

        kartlar = []
        for pid, d in sirali:
            diger = d.get("diger") or ""
            if not diger:
                u1, u2 = cift_kullanicilar(pid)
                diger = u2 if u1 == ben else u1
            okunmamis = int(d.get("okunmamis") or 0)
            son_m = str(d.get("son") or "")
            z_txt = zaman_oncesi(d.get("sonZaman")) if d.get("sonZaman") else ""
            rozet_txt, gorunur, riskli, _ = alev_rozeti(sosyal["seri"].get(pid), bugun_iso)

            def ac(e, pid=pid):
                ui["aktif_dm"] = pid
                ui["dm_yeni_acik"] = False
                aktif_isaretle(f"dm:{pid}")
                arka_plan(sosyal_getir, "dm_aktif")
                yenile()

            isim_satiri = [
                ft.Text(diger, size=15, weight=ft.FontWeight.W_800, color=r["txt"]),
            ]
            if gorunur:
                isim_satiri.append(ft.Container(
                    padding=pad_sim(horizontal=8, vertical=2), border_radius=10,
                    bgcolor=opak(0.15, r["muted"] if riskli else TURUNCU),
                    content=ft.Text(rozet_txt, size=12, weight=ft.FontWeight.BOLD,
                                    color=r["muted"] if riskli else TURUNCU),
                ))

            sag_kolon = [ft.Text(z_txt, size=11, color=r["muted"])]
            if okunmamis > 0:
                sag_kolon.append(ft.Container(
                    padding=pad_sim(horizontal=7, vertical=2), border_radius=10, bgcolor=KIRMIZI,
                    content=ft.Text(str(okunmamis), size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                ))

            kartlar.append(kart(r, ft.Container(
                ink=True, on_click=ac,
                content=ft.Row([
                    avatar(r, diger, 42),
                    ft.Column([
                        ft.Row(isim_satiri, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(son_m or "Sohbeti görüntüle", size=12,
                                color=r["txt"] if okunmamis else r["muted"],
                                weight=ft.FontWeight.W_700 if okunmamis else ft.FontWeight.NORMAL),
                    ], spacing=3, expand=True),
                    ft.Column(sag_kolon, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ), padding=12))
        return kartlar

    def ozel_sohbet_acik_gorunum(r, pid):
        ben = oturum["kullanici"]
        u1, u2 = cift_kullanicilar(pid)
        diger = u2 if u1 == ben else u1
        rozet_txt, gorunur, riskli, _ = alev_rozeti(sosyal["seri"].get(pid), istanbul_bugun())

        def geri(e):
            ui["aktif_dm"] = None
            aktif_isaretle("sohbet_dm_liste")
            arka_plan(sosyal_getir, "dm_liste")
            yenile()

        seri_etiket = ft.Text(
            rozet_txt if gorunur else "",
            size=14, weight=ft.FontWeight.BOLD,
            color=r["muted"] if riskli else TURUNCU,
        )
        sosyal["dm_baslik_seri"] = seri_etiket

        ust_bar = ft.Row([
            ft.IconButton(icon=ik("ARROW_BACK_IOS_NEW"), icon_color=r["hdr"], icon_size=20, on_click=geri),
            avatar(r, diger, 36),
            ft.Column([
                ft.Row([
                    ft.Text(diger, size=17, weight=ft.FontWeight.W_800, color=r["txt"]),
                    seri_etiket,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("Her gün karşılıklı mesajlaşarak 🔥 seriyi büyütün!", size=11, color=r["muted"]),
            ], spacing=1, expand=True),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        liste = ft.Column(scroll=ft.ScrollMode.AUTO, auto_scroll=True, expand=True, spacing=10)
        liste.controls = dm_mesaj_balonlari(r, pid)
        sosyal["dm_mesaj_kap"] = liste

        giris = girdi(r, f"{diger} kişisine mesaj yaz...", expand=True)

        def gonder(e):
            m = (giris.value or "").strip()
            if not m:
                return
            giris.value = ""
            dm_mesaj_gonder_islem(diger, m)
            sosyal_ui_guncelle()
            try:
                giris.update()
                giris.focus()
            except Exception:
                pass

        giris.on_submit = gonder
        alt_satir = ft.Row([giris, ft.IconButton(icon=ik("SEND"), icon_color=r["hdr"], icon_size=28, on_click=gonder)])
        return ft.Column([ust_bar, ft.Container(expand=True, content=liste), alt_satir], expand=True, spacing=10)

    def sohbet_ana_gorunumu(r):
        ben = oturum["kullanici"]
        if ui.get("aktif_dm"):
            pid = ui["aktif_dm"]
            aktif_isaretle(f"dm:{pid}")
            if time.time() - sosyal["son_cek"].get("dm", 0) > 1.5:
                arka_plan(sosyal_getir, "dm_aktif")
            return ozel_sohbet_acik_gorunum(r, pid)

        def geri_akisa(e):
            ui["sosyal_alt"] = None
            aktif_isaretle("akis")
            yenile()

        def sekme_degis(i):
            ui["sohbet_tab"] = i
            if i == 0:
                aktif_isaretle("genel")
                arka_plan(sosyal_getir, "genel")
            else:
                aktif_isaretle("sohbet_dm_liste")
                arka_plan(sosyal_getir, "dm_liste")
            yenile()

        sessiz_mi = bool(DB["bildirim"].get("genel_sessiz", False))

        def genel_sessiz_degis(e):
            DB["bildirim"]["genel_sessiz"] = not sessiz_mi
            kaydet("bildirim")
            snack("🔕 Genel sohbet bildirimleri sessize alındı" if DB["bildirim"]["genel_sessiz"]
                  else "🔔 Genel sohbet bildirimleri açıldı")
            yenile()

        sag_buton = ft.IconButton(
            icon=ik("VOLUME_OFF") if sessiz_mi else ik("VOLUME_UP"),
            icon_color=r["muted"] if sessiz_mi else r["hdr"],
            tooltip="Genel sohbet bildirimlerini sessize al / aç",
            on_click=genel_sessiz_degis,
        )

        okunmamis_dm = okunmamis_sohbet_sayisi()
        dm_sekme_adi = f"👤 Özel Sohbetler ({okunmamis_dm})" if okunmamis_dm > 0 else "👤 Özel Sohbetler"
        ust = [
            sayfa_basligi(r, "Sohbet", "Genel sohbet ve 🔥 serili özel mesajlar", geri=geri_akisa, sag=sag_buton),
            segment(r, ["🌍 Genel Sohbet", dm_sekme_adi], ui["sohbet_tab"], sekme_degis),
        ]

        # Sekme 0: Genel Sohbet
        if ui["sohbet_tab"] == 0:
            aktif_isaretle("genel")
            sosyal["oran_durumu"].pop(f"genel_bekliyor:{ben}", None)
            if time.time() - sosyal["son_cek"].get(1, 0) > 2.5:
                arka_plan(sosyal_getir, "genel")
            liste = ft.Column(scroll=ft.ScrollMode.AUTO, auto_scroll=True, expand=True, spacing=10)
            liste.controls = mesaj_balonlari(r)
            sosyal["sohbet_kap"] = liste
            giris = girdi(r, "Genel sohbete mesaj yaz...", expand=True)

            def genel_gonder(e):
                m = (giris.value or "").strip()
                if not m:
                    return
                mid = yeni_id()
                kayit = {"k": ben, "m": m[:500], "z": int(time.time() * 1000)}
                sosyal["sohbet"][mid] = kayit
                arka_plan(lambda: bulut_patch(f"sosyal/sohbet/{mid}", kayit))
                toplu_sosyal_bildirim_yolla(
                    "sosyal_genel", f"💬 Genel Sohbet • {ben}", m[:120],
                    oncelik=3, beklenen_ekran="genel",
                )
                giris.value = ""
                sosyal_ui_guncelle()
                try:
                    giris.update()
                    giris.focus()
                except Exception:
                    pass

            giris.on_submit = genel_gonder
            satir = ft.Row([giris, ft.IconButton(icon=ik("SEND"), icon_color=r["hdr"], icon_size=28, on_click=genel_gonder)])
            return ft.Column([*ust, ft.Container(expand=True, content=liste), satir], expand=True, spacing=10)

        # Sekme 1: Özel Sohbetler
        aktif_isaretle("sohbet_dm_liste")
        if time.time() - sosyal["son_cek"].get("dm", 0) > 3.0:
            arka_plan(sosyal_getir, "dm_liste")

        def yeni_sohbet_ac_kapat(e):
            ui["dm_yeni_acik"] = not ui["dm_yeni_acik"]
            if ui["dm_yeni_acik"]:
                arka_plan(lambda: (kullanici_listesi_cek(zorla=True), yenile()))
            yenile()

        yeni_bolum = [buton(r, "Vazgeç" if ui["dm_yeni_acik"] else "＋ Yeni Sohbet Başlat",
                            yeni_sohbet_ac_kapat, ikon=ik("PERSON_ADD"), genis=True,
                            ikincil=ui["dm_yeni_acik"], yukseklik=44)]

        if ui["dm_yeni_acik"]:
            def arama_degisti(e):
                ui["dm_arama"] = e.control.value or ""
                yenile()

            arama_in = girdi(r, "Kullanıcı adı ara...", value=ui["dm_arama"], on_change=arama_degisti, prefix_icon=ik("SEARCH"))
            adaylar = [u for u in kullanici_listesi_cek() if u != ben and ui["dm_arama"].lower().strip() in u.lower()]

            def kisi_sec(u_hedef):
                def f(e):
                    pid = cift_id(ben, u_hedef)
                    ui["dm_yeni_acik"] = False
                    ui["aktif_dm"] = pid
                    aktif_isaretle(f"dm:{pid}")
                    arka_plan(sosyal_getir, "dm_aktif")
                    yenile()
                return f

            kisi_satirlari = [
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=8), border_radius=14, bgcolor=r["bg"],
                    border=kenar(1, r["border"]), ink=True, on_click=kisi_sec(u_),
                    content=ft.Row([
                        avatar(r, u_, 32),
                        ft.Text(u_, size=14, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                        ft.Icon(ik("CHEVRON_RIGHT"), color=r["hdr"], size=18),
                    ], spacing=10),
                )
                for u_ in adaylar[:20]
            ]
            if not kisi_satirlari:
                kisi_satirlari = [ft.Text("Eşleşen kullanıcı bulunamadı.", size=12, color=r["muted"], italic=True)]
            yeni_bolum.append(kart(r, ft.Column([arama_in, *kisi_satirlari], spacing=8), padding=12))

        dm_kap = ft.Column(dm_konusma_kartlari(r), spacing=10)
        sosyal["dm_liste_kap"] = dm_kap
        return ft.Column([*ust, *yeni_bolum, dm_kap, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)


    # ---------- 3) 2 KİŞİLİK ONLINE OYUNLAR (LOBİ, SKOR TABLOSU VE 5 OYUN EKRANI) ----------
    def oyun_skor_kaydet_bulut(tur, a_kul, b_kul, kazanan):
        """Oyun bittiğinde her iki oyuncunun ilgili oyun türünde skorunu günceller."""
        if not a_kul or not b_kul or not kazanan:
            return
        for kul in (a_kul, b_kul):
            try:
                mevcut = bulut_get(f"oyunlar_skor/{kul}/{tur}") or {}
                if kazanan == "berabere":
                    sonuc = "beraberlik"
                elif kazanan == kul:
                    sonuc = "galibiyet"
                else:
                    sonuc = "maglubiyet"
                yeni_skor = skor_hesapla_pure(mevcut, sonuc)
                bulut_patch(f"oyunlar_skor/{kul}/{tur}", yeni_skor)
                sosyal.setdefault("oyun_skor", {}).setdefault(kul, {})[tur] = yeni_skor
            except Exception as ex:
                print(f"Oyun skoru yazılamadı ({kul}):", ex)

    def oyun_davet_olustur(rakip, tur="xox", senkron=False, baslangic_kelime=None):
        """Yeni bir 2 kişilik oyun oluşturur, oyuncu indekslerine yazar ve rakibe bildirim gönderir."""
        ben = oturum["kullanici"]
        rakip = str(rakip or "").strip().lower()
        if not ben or not rakip or ben == rakip or tur not in OYUN_TURLERI:
            return None
        gid = yeni_id()
        simdi_ms = int(time.time() * 1000)
        oyuncular = {"a": ben, "b": rakip}
        tahta = oyun_baslangic_tahtasi(tur, oyuncular)
        if tur == "adam" and baslangic_kelime:
            ok, _, yeni_t, _, _, _ = adam_hamle_yap(tahta, oyuncular, ben, baslangic_kelime)
            if ok:
                tahta = yeni_t

        veri = {
            "tur": tur,
            "oyuncular": oyuncular,
            "durum": "bekliyor",
            "sira": ben if (tur != "adam" or tahta.get("asama") == "kelime_bekliyor") else rakip,
            "hamleNo": 0,
            "tahta": tahta,
            "kazanan": "",
            "olusturma": simdi_ms,
            "sonHamle": simdi_ms,
            "sonGorulme": {ben: simdi_ms},
            "bildirimHamleNo": -1,
        }
        sosyal["oyunlar"][gid] = veri

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", veri)
                bulut_patch(f"oyuncu_oyunlari/{ben}", {gid: True})
                bulut_patch(f"oyuncu_oyunlari/{rakip}", {gid: True})
                tur_ad = OYUN_TURLERI[tur]["ad"]
                sosyal_bildirim_yolla(
                    rakip, "sosyal_oyun", "🎮 Oyun Daveti!",
                    f"{ben} seni {tur_ad}'a davet etti!",
                    oncelik=4, senkron=senkron,
                )
            except Exception as ex:
                snack(f"⚠️ Oyun oluşturulamadı: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)
        return gid

    def oyun_kabul_islem(gid, senkron=False):
        g = sosyal["oyunlar"].get(gid)
        if not g:
            try:
                g = bulut_get(f"oyunlar/{gid}") or {}
            except Exception:
                g = {}
        if not g:
            return
        simdi_ms = int(time.time() * 1000)
        g["durum"] = "oynuyor"
        g["sonHamle"] = simdi_ms
        sosyal["oyunlar"][gid] = g

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", {"durum": "oynuyor", "sonHamle": simdi_ms})
            except Exception as ex:
                snack(f"⚠️ Oyun başlatılamadı: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)

    def oyun_iptal_islem(gid, senkron=False):
        g = sosyal["oyunlar"].get(gid)
        if not g:
            try:
                g = bulut_get(f"oyunlar/{gid}") or {}
            except Exception:
                g = {}
        if not g:
            return
        g["durum"] = "iptal"
        sosyal["oyunlar"][gid] = g

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", {"durum": "iptal"})
            except Exception as ex:
                snack(f"⚠️ İptal edilemedi: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)

    def oyun_teslim_ol_islem(gid, senkron=False):
        ben = oturum["kullanici"]
        g = sosyal["oyunlar"].get(gid)
        if not g:
            try:
                g = bulut_get(f"oyunlar/{gid}") or {}
            except Exception:
                g = {}
        if not g or g.get("durum") != "oynuyor":
            return
        oyuncular = g.get("oyuncular") or {}
        a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
        kazanan = b if ben == a else a
        simdi_ms = int(time.time() * 1000)
        g["durum"] = "bitti"
        g["kazanan"] = kazanan
        g["sira"] = ""
        g["hamleNo"] = int(g.get("hamleNo") or 0) + 1
        g["sonHamle"] = simdi_ms
        sosyal["oyunlar"][gid] = g

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", {
                    "durum": "bitti", "kazanan": kazanan, "sira": "",
                    "hamleNo": g["hamleNo"], "sonHamle": simdi_ms,
                })
                oyun_skor_kaydet_bulut(g.get("tur", "xox"), a, b, kazanan)
            except Exception as ex:
                snack(f"⚠️ İşlem hatası: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)

    def oyun_hukmen_kazan_islem(gid, senkron=False):
        ben = oturum["kullanici"]
        g = sosyal["oyunlar"].get(gid) or {}
        if not g or g.get("durum") != "oynuyor":
            return False
        za = oyun_zaman_asimi_durumu(g)
        if not za["hukmen_2dk"]:
            snack("Rakibin hamle süresi henüz 2 dakikayı doldurmadı.")
            return False
        oyuncular = g.get("oyuncular") or {}
        a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
        simdi_ms = int(time.time() * 1000)
        g["durum"] = "bitti"
        g["kazanan"] = ben
        g["sira"] = ""
        g["hamleNo"] = int(g.get("hamleNo") or 0) + 1
        g["sonHamle"] = simdi_ms

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", {
                    "durum": "bitti", "kazanan": ben, "sira": "",
                    "hamleNo": g["hamleNo"], "sonHamle": simdi_ms,
                })
                oyun_skor_kaydet_bulut(g.get("tur", "xox"), a, b, ben)
            except Exception as ex:
                snack(f"⚠️ Hükmen galibiyet kaydedilemedi: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)
        kutlama()
        return True

    def oyun_hamle_gonder_islem(gid, hamle, senkron=False, simdi_ms=None):
        """Oyuncunun hamlesini doğrular, tahtayı günceller ve buluta yazar."""
        ben = oturum["kullanici"]
        mevcut = sosyal["oyunlar"].get(gid)
        if not mevcut:
            try:
                mevcut = bulut_get(f"oyunlar/{gid}") or {}
            except Exception:
                mevcut = {}
        ok, hata, yeni_g = oyun_hamle_uygula(mevcut, ben, hamle, simdi_ms=simdi_ms)
        if not ok:
            snack(f"⚠️ {hata}")
            return False, hata

        sosyal["oyunlar"][gid] = yeni_g
        if yeni_g.get("durum") == "bitti" and yeni_g.get("kazanan") == ben:
            kutlama()

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", {
                    "tahta": yeni_g["tahta"],
                    "hamleNo": yeni_g["hamleNo"],
                    "sira": yeni_g["sira"],
                    "durum": yeni_g["durum"],
                    "kazanan": yeni_g["kazanan"],
                    "sonHamle": yeni_g["sonHamle"],
                    "sonHamleYapan": yeni_g.get("sonHamleYapan", ben),
                })
                if yeni_g.get("durum") == "bitti":
                    oyuncular = yeni_g.get("oyuncular") or {}
                    oyun_skor_kaydet_bulut(
                        yeni_g.get("tur", "xox"),
                        oyuncular.get("a", ""), oyuncular.get("b", ""),
                        yeni_g.get("kazanan", ""),
                    )
            except Exception as ex:
                snack(f"⚠️ Hamle kaydedilemedi: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)
        sosyal_ui_guncelle()
        return True, ""

    def oyun_tekrar_oyna_islem(eski_g, senkron=False):
        """Biten oyunun ardından rövanş oyunu başlatır (Adam Asmaca'da roller yer değiştirir)."""
        ben = oturum["kullanici"]
        oyuncular = eski_g.get("oyuncular") or {}
        a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
        rakip = b if ben == a else a
        tur = eski_g.get("tur", "xox")
        gid = yeni_id()
        simdi_ms = int(time.time() * 1000)
        # Adam asmaca ve diğer oyunlarda rövanşta rolleri (a <-> b) değiştir
        yeni_oyuncular = {"a": b, "b": a} if tur == "adam" else {"a": ben, "b": rakip}
        tahta = oyun_baslangic_tahtasi(tur, yeni_oyuncular)
        veri = {
            "tur": tur,
            "oyuncular": yeni_oyuncular,
            "durum": "oynuyor",
            "sira": yeni_oyuncular["a"],
            "hamleNo": 0,
            "tahta": tahta,
            "kazanan": "",
            "olusturma": simdi_ms,
            "sonHamle": simdi_ms,
            "sonGorulme": {ben: simdi_ms},
            "bildirimHamleNo": -1,
        }
        sosyal["oyunlar"][gid] = veri
        ui["aktif_oyun"] = gid

        def is_():
            try:
                bulut_patch(f"oyunlar/{gid}", veri)
                bulut_patch(f"oyuncu_oyunlari/{a}", {gid: True})
                bulut_patch(f"oyuncu_oyunlari/{b}", {gid: True})
            except Exception as ex:
                snack(f"⚠️ Rövanş başlatılamadı: {ex}")

        if senkron:
            is_()
        else:
            arka_plan(is_)
        return gid

    def oyun_ekrani_icerigi(r, gid, g):
        """Açık olan oyunun (XOX, Dört Bağlama, Bilgi Düellosu, TKM, Adam Asmaca) tahtasını ve durumunu çizer."""
        ben = oturum["kullanici"]
        if not g:
            return [ft.Text("Oyun yükleniyor...", color=r["muted"], italic=True)]
        tur = g.get("tur", "xox")
        tur_bilgi = OYUN_TURLERI.get(tur, OYUN_TURLERI["xox"])
        oyuncular = g.get("oyuncular") or {}
        a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
        rakip = b if ben == a else a
        durum = g.get("durum", "bekliyor")
        sira = g.get("sira", "")
        kazanan = g.get("kazanan", "")
        tahta = g.get("tahta") or {}
        ekran_genislik = max(320, int(page.width or 380) - 48)

        # Üst durum kartı
        if durum == "bekliyor":
            durum_yazi = "⏳ Rakibin daveti kabul etmesi bekleniyor..." if ben == a else "📩 Rakip seni oyuna davet etti!"
            durum_renk = TURUNCU
        elif durum == "iptal":
            durum_yazi = "🚫 Bu oyun iptal edildi veya süresi doldu."
            durum_renk = KIRMIZI
        elif durum == "bitti":
            if kazanan == "berabere":
                durum_yazi = "🤝 Oyun Berabere Bitti! (+1 Puan)"
                durum_renk = r["accent"]
            elif kazanan == ben:
                durum_yazi = "🎉 Tebrikler, Oyunu Kazandın! (+3 Puan)"
                durum_renk = YESIL
            else:
                durum_yazi = f"🏁 {kazanan} Kazandı! Bir dahaki sefere 💪"
                durum_renk = KIRMIZI
        else:
            if tur in ("yks_quiz", "tkm"):
                durum_yazi = "⚡ Eşzamanlı Düello Devam Ediyor!"
                durum_renk = r["hdr"]
            elif sira == ben:
                durum_yazi = "🟢 Sıra Sende! Hamleni yap"
                durum_renk = YESIL
            else:
                durum_yazi = f"⏳ Sıra {rakip} oyuncusunda..."
                durum_renk = r["muted"]

        ust_kart = kart(r, ft.Column([
            ft.Row([
                avatar(r, ben, 34),
                ft.Text(ben, size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text("⚡ VS ⚡", size=12, weight=ft.FontWeight.BOLD, color=r["hdr"], expand=True,
                        text_align=ft.TextAlign.CENTER),
                ft.Text(rakip, size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                avatar(r, rakip, 34),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                padding=pad_sim(horizontal=12, vertical=8), border_radius=12,
                bgcolor=opak(0.14, durum_renk), alignment=ORTA,
                content=ft.Text(durum_yazi, size=13, weight=ft.FontWeight.BOLD, color=durum_renk,
                                text_align=ft.TextAlign.CENTER),
            ),
        ], spacing=10), padding=14)

        kontroller = [ust_kart]

        if durum == "bekliyor" and ben == b:
            kontroller.append(kart(r, ft.Row([
                buton(r, "Kabul Et ve Başla 🎮", lambda e: (oyun_kabul_islem(gid), yenile()), genis=True),
                buton(r, "Reddet", lambda e: (oyun_iptal_islem(gid), yenile()), ikincil=True, genis=True),
            ], spacing=10), padding=14))
            return kontroller

        # --- OYUN 1: XOX (3x3) ---
        if tur == "xox":
            hucreler = list(tahta.get("hucreler") or [""] * 9)
            if len(hucreler) < 9:
                hucreler += [""] * (9 - len(hucreler))
            kazanan_hat = set(listeye(tahta.get("kazananHat")))
            boyut = max(72, min(92, (ekran_genislik - 36) // 3))

            def xox_tik(idx):
                def f(e):
                    oyun_hamle_gonder_islem(gid, idx)
                return f

            satirlar = []
            for r_i in range(3):
                row_items = []
                for c_i in range(3):
                    idx = r_i * 3 + c_i
                    val = hucreler[idx]
                    vurgulu = idx in kazanan_hat
                    sembol = "❌" if val == "X" else ("⭕" if val == "O" else "")
                    row_items.append(ft.Container(
                        width=boyut, height=boyut, border_radius=16, alignment=ORTA, ink=True,
                        bgcolor=opak(0.25, YESIL) if vurgulu else r["bg"],
                        border=kenar(3 if vurgulu else 2, YESIL if vurgulu else r["border"]),
                        on_click=xox_tik(idx) if durum == "oynuyor" else None,
                        content=ft.Text(sembol, size=32),
                    ))
                satirlar.append(ft.Row(row_items, alignment=ft.MainAxisAlignment.CENTER, spacing=8))
            kontroller.append(kart(r, ft.Column(satirlar, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=16))

        # --- OYUN 2: DÖRT BAĞLAMA / CONNECT 4 (7x6) ---
        elif tur == "c4":
            ham_izgara = tahta.get("izgara") or []
            dortlu = {tuple(x) for x in listeye(tahta.get("kazananDortlu")) if isinstance(x, list) and len(x) == 2}
            hucre_w = max(36, min(44, (ekran_genislik - 36) // 7))

            def c4_tik(sutun_i):
                def f(e):
                    oyun_hamle_gonder_islem(gid, sutun_i)
                return f

            sutun_oklari = ft.Row([
                ft.Container(
                    width=hucre_w, height=28, border_radius=8, alignment=ORTA, ink=True,
                    bgcolor=opak(0.15, r["hdr"]), on_click=c4_tik(c_i) if durum == "oynuyor" else None,
                    content=ft.Text("⬇️", size=14),
                )
                for c_i in range(7)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4)

            izgara_satirlari = [sutun_oklari]
            for r_i in range(6):
                satir_veri = list(ham_izgara[r_i]) if r_i < len(ham_izgara) and isinstance(ham_izgara[r_i], list) else [""] * 7
                while len(satir_veri) < 7:
                    satir_veri.append("")
                hucre_list = []
                for c_i in range(7):
                    v = satir_veri[c_i]
                    vurgulu = (r_i, c_i) in dortlu
                    top_emoji = "🔴" if v == "A" else ("🟡" if v == "B" else "⚪")
                    hucre_list.append(ft.Container(
                        width=hucre_w, height=hucre_w, border_radius=hucre_w / 2, alignment=ORTA, ink=True,
                        bgcolor=opak(0.28, YESIL) if vurgulu else r["bg"],
                        border=kenar(2 if vurgulu else 1, YESIL if vurgulu else r["border"]),
                        on_click=c4_tik(c_i) if durum == "oynuyor" else None,
                        content=ft.Text(top_emoji, size=max(18, hucre_w - 16)),
                    ))
                izgara_satirlari.append(ft.Row(hucre_list, alignment=ft.MainAxisAlignment.CENTER, spacing=4))

            kontroller.append(kart(r, ft.Column([
                ft.Text(f"🔴 {a}   •   🟡 {b}", size=12, color=r["muted"], text_align=ft.TextAlign.CENTER),
                *izgara_satirlari,
            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=12))

        # --- OYUN 3: YKS BİLGİ DÜELLOSU (10 TYT SORUSU) ---
        elif tur == "yks_quiz":
            sorular = [int(x) for x in listeye(tahta.get("sorular"))]
            cevaplar = tahta.get("cevaplar") or {"a": [], "b": []}
            puanlar = tahta.get("puanlar") or {"a": 0, "b": 0}
            dogrular = tahta.get("dogrular") or {"a": 0, "b": 0}
            rol = "a" if ben == a else "b"
            rakip_rol = "b" if rol == "a" else "a"
            benim_cevaplar = listeye(cevaplar.get(rol))
            rakip_cevaplar = listeye(cevaplar.get(rakip_rol))

            skor_ozet = kart(r, ft.Row([
                ft.Column([
                    ft.Text(f"{a} {'(Sen)' if ben == a else ''}", size=13, weight=ft.FontWeight.BOLD, color=r["txt"]),
                    ft.Text(f"{puanlar.get('a', 0)} Puan ({dogrular.get('a', 0)}/10 Doğru)", size=12, color=r["hdr"]),
                ], expand=True),
                ft.Column([
                    ft.Text(f"{b} {'(Sen)' if ben == b else ''}", size=13, weight=ft.FontWeight.BOLD, color=r["txt"]),
                    ft.Text(f"{puanlar.get('b', 0)} Puan ({dogrular.get('b', 0)}/10 Doğru)", size=12, color=r["accent"]),
                ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.END),
            ]), padding=12)
            kontroller.append(skor_ozet)

            soru_idx = len(benim_cevaplar)
            if durum == "oynuyor" and soru_idx < len(sorular):
                if ui["quiz_soru_t0"] <= 0:
                    ui["quiz_soru_t0"] = time.time()
                q_obj = TYT_SORU_BANKASI[sorular[soru_idx] % len(TYT_SORU_BANKASI)]

                def sik_sec(sec_i):
                    def f(e):
                        gecen_ms = int(max(500, (time.time() - (ui["quiz_soru_t0"] or time.time())) * 1000))
                        ui["quiz_soru_t0"] = time.time()
                        oyun_hamle_gonder_islem(gid, {"secenek": sec_i, "sure_ms": gecen_ms})
                    return f

                sik_butonlari = [
                    buton(r, f"{['A', 'B', 'C', 'D'][i]}) {sec_metin}", sik_sec(i),
                          ikincil=True, genis=True, yukseklik=44)
                    for i, sec_metin in enumerate(q_obj["sec"])
                ]
                kontroller.append(kart(r, ft.Column([
                    ft.Row([
                        ft.Text(f"Soru {soru_idx + 1} / {len(sorular)}", size=13, weight=ft.FontWeight.BOLD, color=r["hdr"], expand=True),
                        ft.Text(f"📚 {q_obj['ders']}", size=12, color=r["accent"], weight=ft.FontWeight.W_600),
                    ]),
                     ilerleme_cubugu(r, (soru_idx + 1) / max(1, len(sorular)), r["hdr"]),
                    ft.Text(q_obj["s"], size=14, weight=ft.FontWeight.W_600, color=r["txt"]),
                    *sik_butonlari,
                ], spacing=10), padding=14))
            else:
                # Karşılaştırma ekranı
                karsilastirma = [
                    ft.Text("📊 Soru Karşılaştırma Tablosu", size=14, weight=ft.FontWeight.BOLD, color=r["hdr"]),
                    ft.Text(f"Rakibin durumu: {len(rakip_cevaplar)}/{len(sorular)} soru tamamlandı", size=12, color=r["muted"]),
                ]
                for i_q, s_id in enumerate(sorular):
                    q_obj = TYT_SORU_BANKASI[s_id % len(TYT_SORU_BANKASI)]
                    d_idx = q_obj["d"]
                    c_ben = benim_cevaplar[i_q] if i_q < len(benim_cevaplar) else None
                    c_rakip = rakip_cevaplar[i_q] if i_q < len(rakip_cevaplar) else None
                    ben_ikon = "✅" if c_ben == d_idx else ("❌" if c_ben is not None else "⏳")
                    rakip_ikon = ("✅" if c_rakip == d_idx else ("❌" if c_rakip is not None else "⏳")) if durum == "bitti" else ("✔️" if c_rakip is not None else "⏳")
                    karsilastirma.append(ft.Container(
                        padding=8, border_radius=10, bgcolor=r["bg"],
                        content=ft.Column([
                            ft.Text(f"{i_q + 1}. ({q_obj['ders']}) {q_obj['s'][:75]}...", size=11, color=r["txt"], weight=ft.FontWeight.W_600),
                            ft.Text(f"Doğru: {q_obj['sec'][d_idx]}   |   Sen: {ben_ikon}   |   {rakip}: {rakip_ikon}", size=11, color=r["muted"]),
                        ], spacing=2),
                    ))
                kontroller.append(kart(r, ft.Column(karsilastirma, spacing=6), padding=12))

        # --- OYUN 4: TAŞ - KÂĞIT - MAKAS (BEST OF 3) ---
        elif tur == "tkm":
            skor = tahta.get("skor") or {"a": 0, "b": 0}
            secim = tahta.get("secim") or {"a": "", "b": ""}
            gecmis = listeye(tahta.get("gecmis"))
            rol = "a" if ben == a else "b"
            rakip_rol = "b" if rol == "a" else "a"
            ben_sectim = bool(secim.get(rol))
            rakip_secti = bool(secim.get(rakip_rol))

            emoji_harita = {"tas": "✊ Taş", "kagit": "✋ Kâğıt", "makas": "✌️ Makas"}

            def tkm_sec(hamle_ad):
                def f(e):
                    oyun_hamle_gonder_islem(gid, hamle_ad)
                return f

            tkm_govde = [
                ft.Text(f"Skor: {a} {skor.get('a', 0)}  -  {skor.get('b', 0)} {b}  (2 olan kazanır)",
                        size=15, weight=ft.FontWeight.W_800, color=r["hdr"], text_align=ft.TextAlign.CENTER),
                ft.Text(
                    f"Sen: {'Seçildi 🔒' if ben_sectim else 'Bekleniyor...'}   |   {rakip}: {'Seçildi 🔒' if rakip_secti else 'Düşünüyor...'}",
                    size=12, color=r["muted"], text_align=ft.TextAlign.CENTER,
                ),
            ]
            if durum == "oynuyor" and not ben_sectim:
                tkm_govde.append(ft.Row([
                    buton(r, "✊ Taş", tkm_sec("tas"), genis=True),
                    buton(r, "✋ Kâğıt", tkm_sec("kagit"), genis=True),
                    buton(r, "✌️ Makas", tkm_sec("makas"), genis=True),
                ], spacing=8))
            for tur_kayit in reversed(gecmis):
                if isinstance(tur_kayit, dict):
                    tkm_govde.append(ft.Text(
                        f"{tur_kayit.get('tur')}. Tur: {a} ({emoji_harita.get(tur_kayit.get('a'), '')}) vs "
                        f"{b} ({emoji_harita.get(tur_kayit.get('b'), '')})",
                        size=12, color=r["txt"],
                    ))
            kontroller.append(kart(r, ft.Column(tkm_govde, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), padding=14))

        # --- OYUN 5: ADAM ASMACA (TÜRKÇE HARFLER) ---
        elif tur == "adam":
            asama = tahta.get("asama", "kelime_bekliyor")
            yanlis = int(tahta.get("yanlis") or 0)
            maks_yanlis = int(tahta.get("maksYanlis") or 6)
            tahminler = set(listeye(tahta.get("tahminler")))
            maske = tahta.get("maske") or ""

            if asama == "kelime_bekliyor":
                if ben == a:
                    kelime_in = girdi(r, "Gizli Türkçe kelimeyi yaz (3-15 harf)...", expand=True)

                    def kelime_kaydet(e):
                        oyun_hamle_gonder_islem(gid, kelime_in.value or "")

                    kelime_in.on_submit = kelime_kaydet
                    kontroller.append(kart(r, ft.Column([
                        ft.Text("🔤 Rakibin tahmin etmesi için gizli bir Türkçe kelime belirle:", size=13, color=r["txt"]),
                        kelime_in,
                        buton(r, "Kelimeyi Kilitle ve Başlat 🔒", kelime_kaydet, genis=True),
                    ], spacing=10), padding=14))
                else:
                    kontroller.append(kart(r, ft.Text(f"⏳ {a} şu an gizli kelimeyi belirliyor...",
                                                      size=13, color=r["muted"]), padding=14))
            else:
                gosterilen_kelime = tahta.get("kelime", "") if (durum == "bitti" or ben == a) else maske
                harf_dugmeleri = []
                if durum == "oynuyor" and ben == b:
                    def harf_tik(h_ch):
                        def f(e):
                            oyun_hamle_gonder_islem(gid, h_ch)
                        return f

                    for h_ch in TR_HARFLER:
                        denendi = h_ch in tahminler
                        harf_dugmeleri.append(ft.Container(
                            width=34, height=34, border_radius=8, alignment=ORTA,
                            ink=not denendi, on_click=None if denendi else harf_tik(h_ch),
                            bgcolor=opak(0.15, r["muted"]) if denendi else r["hdr"],
                            content=ft.Text(h_ch, size=13, weight=ft.FontWeight.BOLD,
                                            color=r["muted"] if denendi else okunur_renk(r["hdr"])),
                        ))
                kontroller.append(kart(r, ft.Column([
                    ft.Text(f"Yanlış Hak: {yanlis} / {maks_yanlis}   {'❤️' * max(0, maks_yanlis - yanlis)}{'🖤' * yanlis}",
                            size=13, weight=ft.FontWeight.BOLD, color=KIRMIZI if yanlis >= 4 else r["txt"],
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        padding=14, border_radius=14, bgcolor=r["bg"], alignment=ORTA,
                        content=ft.Text(maske if (durum == "oynuyor" and ben == b) else f"{maske}  ({gosterilen_kelime})",
                                        size=22, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    ),
                    *([ft.Row(harf_dugmeleri, wrap=True, spacing=5, run_spacing=5,
                              alignment=ft.MainAxisAlignment.CENTER)] if harf_dugmeleri else []),
                ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=14))

        # Alt kontrol düğmeleri (Teslim Ol, 2 dk Hükmen Kazan, Tekrar Oyna)
        za = oyun_zaman_asimi_durumu(g)
        alt_dugmeler = []
        if durum == "oynuyor":
            if za["hukmen_2dk"]:
                alt_dugmeler.append(buton(
                    r, "🏆 Rakip Ayrıldı, Hükmen Kazan (2+ dk)",
                    lambda e: (oyun_hukmen_kazan_islem(gid), yenile()),
                    genis=True, yukseklik=44,
                ))
            alt_dugmeler.append(buton(
                r, "🏳️ Teslim Ol",
                lambda e: (oyun_teslim_ol_islem(gid), yenile()),
                ikincil=True, genis=True, yukseklik=42,
            ))
        elif durum in ("bitti", "iptal"):
            alt_dugmeler.append(buton(
                r, "🔄 Tekrar Oyna (Rövanş)",
                lambda e: (oyun_tekrar_oyna_islem(g), yenile()),
                genis=True, yukseklik=46,
            ))
        if alt_dugmeler:
            kontroller.append(ft.Column(alt_dugmeler, spacing=8))
        return kontroller

    def oyun_lobi_kartlari(r):
        ben = oturum["kullanici"]
        oyunlar_map = sosyal.get("oyunlar") or {}
        gelen_davetler = []
        aktif_oyunlar = []
        biten_oyunlar = []

        for gid in sorted(oyunlar_map, reverse=True):
            g = oyunlar_map[gid]
            if not isinstance(g, dict):
                continue
            durum = g.get("durum", "")
            oyuncular = g.get("oyuncular") or {}
            if durum == "bekliyor" and oyuncular.get("b") == ben:
                gelen_davetler.append((gid, g))
            elif durum in ("bekliyor", "oynuyor"):
                aktif_oyunlar.append((gid, g))
            else:
                biten_oyunlar.append((gid, g))

        cikti = []

        # 1) Gelen Davetler
        if gelen_davetler:
            davet_satirlari = [bolum_basligi(r, ik("NOTIFICATIONS_ACTIVE"), f"Gelen Oyun Davetleri ({len(gelen_davetler)})")]
            for gid, g in gelen_davetler:
                tur_bilgi = OYUN_TURLERI.get(g.get("tur"), OYUN_TURLERI["xox"])
                davet_eden = (g.get("oyuncular") or {}).get("a", "?")

                def kabul(e, gid=gid):
                    oyun_kabul_islem(gid)
                    ui["aktif_oyun"] = gid
                    aktif_isaretle(f"oyun:{gid}")
                    yenile()

                def red(e, gid=gid):
                    oyun_iptal_islem(gid)
                    yenile()

                davet_satirlari.append(ft.Container(
                    padding=10, border_radius=14, bgcolor=r["bg"], border=kenar(1, r["hdr"]),
                    content=ft.Column([
                        ft.Text(f"{tur_bilgi['emoji']} {davet_eden} seni {tur_bilgi['ad']} oyununa davet etti!",
                                size=13, weight=ft.FontWeight.W_700, color=r["txt"]),
                        ft.Row([
                            buton(r, "Kabul Et ✔️", kabul, genis=True, yukseklik=38),
                            buton(r, "Reddet ✖️", red, ikincil=True, genis=True, yukseklik=38),
                        ], spacing=8),
                    ], spacing=8),
                ))
            cikti.append(kart(r, ft.Column(davet_satirlari, spacing=8), padding=14))

        # 2) Devam Eden Oyunlar
        aktif_satirlar = [bolum_basligi(r, ik("SPORTS_ESPORTS"), f"Devam Eden Oyunlar ({len(aktif_oyunlar)})")]
        if not aktif_oyunlar:
            aktif_satirlar.append(ft.Text("Şu an aktif oyunun yok. Yukarıdan yeni bir düello başlat! 🎮",
                                          size=12, color=r["muted"], italic=True))
        for gid, g in aktif_oyunlar:
            tur_bilgi = OYUN_TURLERI.get(g.get("tur"), OYUN_TURLERI["xox"])
            oyuncular = g.get("oyuncular") or {}
            rakip = oyuncular.get("b") if oyuncular.get("a") == ben else oyuncular.get("a")
            durum_ = g.get("durum")
            if durum_ == "bekliyor":
                alt_txt = "⏳ Davet gönderildi, onay bekleniyor"
                renk_ = r["muted"]
            elif g.get("sira") == ben or g.get("tur") in ("yks_quiz", "tkm"):
                alt_txt = "🟢 Sıra sende! Dokun ve oyna"
                renk_ = YESIL
            else:
                alt_txt = f"⏳ Sıra {rakip} oyuncusunda"
                renk_ = r["muted"]

            def oyuna_gir(e, gid=gid):
                ui["aktif_oyun"] = gid
                aktif_isaretle(f"oyun:{gid}")
                arka_plan(sosyal_getir, "oyun_aktif")
                yenile()

            aktif_satirlar.append(ft.Container(
                padding=12, border_radius=14, bgcolor=r["bg"], border=kenar(1, r["border"]),
                ink=True, on_click=oyuna_gir,
                content=ft.Row([
                    ft.Text(tur_bilgi["emoji"], size=24),
                    ft.Column([
                        ft.Text(f"{tur_bilgi['ad']} • vs {rakip}", size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                        ft.Text(alt_txt, size=12, color=renk_, weight=ft.FontWeight.W_600),
                    ], spacing=2, expand=True),
                    ft.Icon(ik("CHEVRON_RIGHT"), color=r["hdr"]),
                ], spacing=10),
            ))
        cikti.append(kart(r, ft.Column(aktif_satirlar, spacing=8), padding=14))

        # 3) Skor Tablosu (Genel ve Oyun Bazlı)
        skor_filtreler = [("genel", "🏆 Genel"), ("xox", "❌ XOX"), ("c4", "🔴 C4"),
                          ("yks_quiz", "🧠 Quiz"), ("tkm", "✊ TKM"), ("adam", "🔤 Adam")]
        secili_tur = ui.get("oyun_skor_tur", "genel")

        def filtre_sec(t_kod):
            def f(e):
                ui["oyun_skor_tur"] = t_kod
                yenile()
            return f

        filtre_satiri = ft.Row([
            ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=12, ink=True, on_click=filtre_sec(kod),
                bgcolor=r["hdr"] if kod == secili_tur else r["bg"], border=kenar(1, r["border"]),
                content=ft.Text(etiket, size=11, weight=ft.FontWeight.BOLD,
                                color=okunur_renk(r["hdr"]) if kod == secili_tur else r["txt"]),
            )
            for kod, etiket in skor_filtreler
        ], scroll=ft.ScrollMode.AUTO, spacing=6)

        skor_map = sosyal.get("oyun_skor") or {}
        tablo = []
        for u_ad, turler_dict in skor_map.items():
            if not isinstance(turler_dict, dict):
                continue
            if secili_tur == "genel":
                top_g = sum(int((v or {}).get("galibiyet", 0)) for v in turler_dict.values() if isinstance(v, dict))
                top_b = sum(int((v or {}).get("beraberlik", 0)) for v in turler_dict.values() if isinstance(v, dict))
                top_m = sum(int((v or {}).get("maglubiyet", 0)) for v in turler_dict.values() if isinstance(v, dict))
                top_p = sum(int((v or {}).get("puan", 0)) for v in turler_dict.values() if isinstance(v, dict))
            else:
                v = turler_dict.get(secili_tur) or {}
                top_g = int(v.get("galibiyet", 0))
                top_b = int(v.get("beraberlik", 0))
                top_m = int(v.get("maglubiyet", 0))
                top_p = int(v.get("puan", 0))
            if top_g or top_b or top_m or top_p:
                tablo.append((top_p, top_g, u_ad, top_b, top_m))
        tablo.sort(reverse=True)

        skor_satirlari = [
            bolum_basligi(r, ik("EMOJI_EVENTS"), "Puan Tablosu (Galibiyet 3, Beraberlik 1)"),
            filtre_satiri,
        ]
        if not tablo:
            skor_satirlari.append(ft.Text("Henüz tamamlanan maç skoru yok.", size=12, color=r["muted"], italic=True))
        for sira_no, (puan_, gal_, u_ad, ber_, mag_) in enumerate(tablo[:15], start=1):
            madalya = "🥇" if sira_no == 1 else ("🥈" if sira_no == 2 else ("🥉" if sira_no == 3 else f"#{sira_no}"))
            skor_satirlari.append(ft.Container(
                padding=pad_sim(horizontal=10, vertical=8), border_radius=12, bgcolor=r["bg"],
                content=ft.Row([
                    ft.Text(madalya, size=14, weight=ft.FontWeight.BOLD, width=30),
                    avatar(r, u_ad, 30),
                    ft.Column([
                        ft.Text(u_ad, size=13, weight=ft.FontWeight.W_700, color=r["txt"]),
                        ft.Text(f"{gal_}G • {ber_}B • {mag_}M", size=11, color=r["muted"]),
                    ], spacing=1, expand=True),
                    ft.Text(f"{puan_} Puan", size=14, weight=ft.FontWeight.W_800, color=r["hdr"]),
                ], spacing=8),
            ))
        cikti.append(kart(r, ft.Column(skor_satirlari, spacing=8), padding=14))
        return cikti

    def oyun_ana_gorunumu(r):
        ben = oturum["kullanici"]
        if ui.get("aktif_oyun"):
            gid = ui["aktif_oyun"]
            aktif_isaretle(f"oyun:{gid}")
            if time.time() - sosyal["son_cek"].get("oyun", 0) > 1.2:
                arka_plan(sosyal_getir, "oyun_aktif")

            def geri_lobi(e):
                ui["aktif_oyun"] = None
                aktif_isaretle("oyun_lobi")
                arka_plan(sosyal_getir, "oyun_lobi")
                yenile()

            g = sosyal["oyunlar"].get(gid) or {}
            tur_bilgi = OYUN_TURLERI.get(g.get("tur", "xox"), OYUN_TURLERI["xox"])
            tahta_kap = ft.Column(oyun_ekrani_icerigi(r, gid, g), spacing=12)
            sosyal["oyun_tahta_kap"] = tahta_kap
            return ft.Column([
                sayfa_basligi(r, f"{tur_bilgi['emoji']} {tur_bilgi['ad']}", tur_bilgi["aciklama"], geri=geri_lobi),
                tahta_kap,
                ft.Container(height=24),
            ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

        aktif_isaretle("oyun_lobi")
        if time.time() - sosyal["son_cek"].get("oyun", 0) > 2.5:
            arka_plan(sosyal_getir, "oyun_lobi")

        def geri_akisa(e):
            ui["sosyal_alt"] = None
            aktif_isaretle("akis")
            yenile()

        def davet_panel_ac_kapat(e):
            ui["oyun_davet_acik"] = not ui["oyun_davet_acik"]
            if ui["oyun_davet_acik"]:
                arka_plan(lambda: (kullanici_listesi_cek(zorla=True), yenile()))
            yenile()

        ust = [
            sayfa_basligi(r, "🎮 Online Oyunlar", "Arkadaşlarınla gerçek zamanlı mola düelloları", geri=geri_akisa),
            buton(r, "Vazgeç" if ui["oyun_davet_acik"] else "＋ Yeni Oyun Başlat",
                  davet_panel_ac_kapat, ikon=ik("SPORTS_ESPORTS"), genis=True,
                  ikincil=ui["oyun_davet_acik"], yukseklik=46),
        ]

        if ui["oyun_davet_acik"]:
            sec_tur = ui.get("oyun_secilen_tur", "xox")

            def tur_sec(t_kod):
                def f(e):
                    ui["oyun_secilen_tur"] = t_kod
                    yenile()
                return f

            tur_kartlari = [
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=8), border_radius=12, ink=True, on_click=tur_sec(kod),
                    bgcolor=r["hdr"] if kod == sec_tur else r["bg"],
                    border=kenar(2 if kod == sec_tur else 1, r["hdr"] if kod == sec_tur else r["border"]),
                    content=ft.Row([
                        ft.Text(bilgi["emoji"], size=20),
                        ft.Column([
                            ft.Text(bilgi["ad"], size=13, weight=ft.FontWeight.BOLD,
                                    color=okunur_renk(r["hdr"]) if kod == sec_tur else r["txt"]),
                            ft.Text(bilgi["aciklama"], size=11,
                                    color=opak(0.85, okunur_renk(r["hdr"])) if kod == sec_tur else r["muted"]),
                        ], spacing=1, expand=True),
                    ], spacing=10),
                )
                for kod, bilgi in OYUN_TURLERI.items()
            ]

            adaylar = [u for u in kullanici_listesi_cek() if u != ben]

            def davet_et(rakip_ad):
                def f(e):
                    gid = oyun_davet_olustur(rakip_ad, sec_tur)
                    ui["oyun_davet_acik"] = False
                    if gid:
                        ui["aktif_oyun"] = gid
                        snack(f"🎮 {rakip_ad} oyuncusuna {OYUN_TURLERI[sec_tur]['ad']} daveti gönderildi!")
                    yenile()
                return f

            rakip_satirlari = [
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=8), border_radius=12, bgcolor=r["bg"],
                    border=kenar(1, r["border"]),
                    content=ft.Row([
                        avatar(r, u_, 30),
                        ft.Text(u_, size=13, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                        buton(r, "Davet Et", davet_et(u_), yukseklik=34),
                    ], spacing=8),
                )
                for u_ in adaylar[:20]
            ]
            if not rakip_satirlari:
                rakip_satirlari = [ft.Text("Davet edilecek başka kayıtlı kullanıcı bulunamadı.", size=12, color=r["muted"])]

            ust.append(kart(r, ft.Column([
                ft.Text("1) Oyun Türünü Seç:", size=13, weight=ft.FontWeight.BOLD, color=r["txt"]),
                *tur_kartlari,
                ft.Text("2) Rakibini Seç ve Davet Gönder:", size=13, weight=ft.FontWeight.BOLD, color=r["txt"]),
                *rakip_satirlari,
            ], spacing=8), padding=14))

        lobi_kap = ft.Column(oyun_lobi_kartlari(r), spacing=12)
        sosyal["oyun_lobi_kap"] = lobi_kap
        return ft.Column([*ust, lobi_kap, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    def sosyal_sayfasi_olustur(r):
        """Sosyal sekmesi doğrudan fotoğraf akışında açılır.
        Sağ üstte 🎮 Oyunlar ve 💬 Sohbet ikon düğmeleri (okunmamış/sıra rozetli) yer alır.
        """
        alt = ui.get("sosyal_alt")
        if alt == "sohbet":
            return sohbet_ana_gorunumu(r)
        if alt == "oyun":
            return oyun_ana_gorunumu(r)

        aktif_isaretle("akis")
        if time.time() - sosyal["son_cek"].get(0, 0) > 3:
            arka_plan(sosyal_getir, 0)

        def sohbet_ac(e):
            ui["sosyal_alt"] = "sohbet"
            arka_plan(sosyal_getir, "genel" if ui["sohbet_tab"] == 0 else "dm_liste")
            yenile()

        def oyun_ac(e):
            ui["sosyal_alt"] = "oyun"
            arka_plan(sosyal_getir, "oyun_lobi")
            yenile()

        sag_ikonlar = ft.Row([
            rozetli_ikon_buton(r, "SPORTS_ESPORTS", aktif_oyun_bildirim_sayisi(), oyun_ac, "Online Oyunlar 🎮"),
            rozetli_ikon_buton(r, "CHAT_BUBBLE_OUTLINE", okunmamis_sohbet_sayisi(), sohbet_ac, "Sohbet & Seri 💬🔥"),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        ust_baslik = sayfa_basligi(r, "Sosyal", "Fotoğraf akışı • Sağ üstten sohbet ve oyunlara geç", sag=sag_ikonlar)
        kap = ft.Column(akis_kartlari(r), spacing=14)
        sosyal["akis_kap"] = kap
        return ft.Column([ust_baslik, paylas_karti(r), kap, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)


    # ==========================================
    # 13. ARDA'NIN PANELİ (canlı + seri/sohbet istatistikleri + oyun yönetimi + tam hesap temizliği)
    # ==========================================
    panel = {"kap": None, "imza": {}, "veri": {}}

    def imza_hesapla(users):
        return {u: [len(listeye(d.get("gunluk"))), len(listeye(d.get("netler")))]
                for u, d in users.items() if isinstance(d, dict)}

    def hesap_tamamen_sil_bulut(u_):
        """Bir hesabı silerken ilişkili tüm DM, seri, oyun, skor ve paylaşımları da temizler."""
        bulut_sil(f"users/{u_}")
        # 1) Paylaşımları sil
        for pid_, p_ in (bulut_get("sosyal/posts") or {}).items():
            if isinstance(p_, dict) and p_.get("kullanici") == u_:
                bulut_sil(f"sosyal/posts/{pid_}")
                bulut_sil(f"sosyal/resim/{pid_}")
        # 2) Özel sohbetleri, dm_index ve seri kayıtlarını sil
        dm_kendi = bulut_get(f"dm_index/{u_}") or {}
        if isinstance(dm_kendi, dict):
            for pair_id, info in dm_kendi.items():
                u1, u2 = cift_kullanicilar(pair_id)
                diger = (info.get("diger") if isinstance(info, dict) else "") or (u2 if u1 == u_ else u1)
                bulut_sil(f"dm/{pair_id}")
                bulut_sil(f"seri/{pair_id}")
                if diger:
                    bulut_sil(f"dm_index/{diger}/{pair_id}")
        bulut_sil(f"dm_index/{u_}")
        # 3) Seri tablosunda kalmış olabilecek çiftleri sil
        for pair_id in list((bulut_get("seri") or {}).keys()):
            if u_ in cift_kullanicilar(pair_id):
                u1, u2 = cift_kullanicilar(pair_id)
                diger = u2 if u1 == u_ else u1
                bulut_sil(f"seri/{pair_id}")
                bulut_sil(f"dm/{pair_id}")
                if diger:
                    bulut_sil(f"dm_index/{diger}/{pair_id}")
        # 4) Oyunları, oyuncu indekslerini ve oyun skorlarını sil
        oyun_indeks = bulut_get(f"oyuncu_oyunlari/{u_}") or {}
        if isinstance(oyun_indeks, dict):
            for gid in list(oyun_indeks.keys()):
                g_obj = bulut_get(f"oyunlar/{gid}") or {}
                if isinstance(g_obj, dict):
                    oyuncular = g_obj.get("oyuncular") or {}
                    for r_u in (oyuncular.get("a"), oyuncular.get("b")):
                        if r_u and r_u != u_:
                            bulut_sil(f"oyuncu_oyunlari/{r_u}/{gid}")
                bulut_sil(f"oyunlar/{gid}")
        bulut_sil(f"oyuncu_oyunlari/{u_}")
        bulut_sil(f"oyunlar_skor/{u_}")

    def ogrenci_kartlari(r, users, seriler_map=None, dm_index_all=None, oyun_skor_all=None):
        bugun = bugun_str()
        bugun_iso = istanbul_bugun()
        seriler_map = seriler_map if isinstance(seriler_map, dict) else (sosyal.get("seri") or {})
        dm_index_all = dm_index_all if isinstance(dm_index_all, dict) else {}
        oyun_skor_all = oyun_skor_all if isinstance(oyun_skor_all, dict) else (sosyal.get("oyun_skor") or {})
        kartlar = []
        for uname in sorted(users):
            u = users[uname]
            if not isinstance(u, dict):
                continue
            loglar = listeye(u.get("gunluk"))
            netler = listeye(u.get("netler"))
            sn_t = bulut_coz("calisma_sn", u.get("calisma_sn") or {})
            log_t = bulut_coz("calisma_log", u.get("calisma_log") or {})
            bugun_sn_ = int(sayi(sn_t.get(bugun))) + int(sayi(log_t.get(bugun))) * 60
            toplam_ = sum(int(sayi(v)) for v in sn_t.values()) + sum(int(sayi(v)) for v in log_t.values()) * 60
            su = u.get("su") or {}
            bardak = int(sayi(su.get("bardak"))) if su.get("tarih") == bugun else 0
            gun = u.get("gun") or {}
            baslama = gun.get("baslama") if gun.get("tarih") == bugun else None

            # Özel sohbet ve seri istatistikleri
            en_uzun_seri = 0
            aktif_seri_say = 0
            for pid, s_kayit in seriler_map.items():
                if uname in cift_kullanicilar(pid):
                    d_s = seri_gorunum_durumu(s_kayit, bugun_iso)
                    if d_s["sayi"] > en_uzun_seri:
                        en_uzun_seri = d_s["sayi"]
                    if d_s["sayi"] >= 2:
                        aktif_seri_say += 1
            konusma_sayisi = len(dm_index_all.get(uname) or {})
            u_skorlar = oyun_skor_all.get(uname) or {}
            toplam_oyun_puan = sum(int((v or {}).get("puan", 0)) for v in u_skorlar.values() if isinstance(v, dict))

            satirlar = [
                ft.Text(f"👤 {uname.upper()}", weight=ft.FontWeight.BOLD, color=r["hdr"], size=16),
                ft.Text(f"⏱ Bugün {sn_metni(bugun_sn_)}   •   Toplam {sn_metni(toplam_)}", color=r["txt"], size=13),
                ft.Text(f"🌅 Derse başlama: {baslama or 'henüz başlamadı'}   •   💧 {bardak} bardak", color=r["txt"], size=13),
                ft.Text(f"🔥 En uzun seri: {en_uzun_seri} gün ({aktif_seri_say} aktif)   •   💬 {konusma_sayisi} özel sohbet   •   🎮 {toplam_oyun_puan}p",
                        color=r["accent"], size=12, weight=ft.FontWeight.W_600),
            ]
            if loglar:
                son = loglar[-1]
                p = int(sayi(son.get("performans")))
                emoji = PERFORMANS[p - 1][0] if 1 <= p <= 5 else "📝"
                sure = sn_metni(son["sn"]) if "sn" in son else f"{sayi(son.get('saat')):g} sa"
                satirlar.append(ft.Text(f"🌙 Son gün sonu: {son.get('tarih', '-')} • {sure} • {emoji}", color=r["txt"], size=13))
                if son.get("gunluk"):
                    satirlar.append(ft.Text(f"“{str(son['gunluk'])[:90]}”", color=r["muted"], size=12, italic=True))
            else:
                satirlar.append(ft.Text("🌙 Henüz gün sonu kaydı yok.", color=r["muted"], size=13))
            if netler:
                n = netler[-1]
                satirlar.append(ft.Text(f"📈 Son deneme: {n.get('ad', '-')} ({n.get('sinav', '-')}) • {sayi(n.get('toplam')):.2f} net",
                                        color=r["txt"], size=13))
            kartlar.append(kart(r, ft.Column(satirlar, spacing=4), padding=14))
        return kartlar

    def ogrenciye_gonder(ogr, baslik, mesaj):
        """Öğrenciye hem gerçek telefon bildirimi hem uygulama içi sinyal gönderir."""
        def is_():
            try:
                bulut_patch(f"users/{ogr}", {"sinyal": {"aktif": True, "mesaj": mesaj}})
                konu = (bulut_get(f"users/{ogr}/bildirim") or {}).get("konu")
                if konu:
                    ok, hata = ntfy_gonder(konu, baslik, mesaj, 4)
                    snack(f"✅ {ogr} kişisine gönderildi" if ok else f"⚠️ Bildirim gitmedi: {hata}")
                else:
                    snack(f"⚠️ {ogr} bildirimi henüz kurmamış, sadece uygulama içi sinyal gitti.")
            except Exception as ex:
                snack(f"⚠️ Gönderilemedi: {ex}")
        arka_plan(is_)

    def yonetici_kaydet():
        """Panele giren kişi yönetici olur: öğrenci kayıtları bu kişinin telefonuna bildirim düşer."""
        def is_():
            try:
                bildirim_konu_hazirla()
                bulut_patch("yonetici", {"konu": DB["bildirim"].get("konu", ""), "kullanici": oturum["kullanici"]})
            except Exception as ex:
                print("Yönetici kaydı yapılamadı:", ex)
        arka_plan(is_)

    def panel_sayfasi_olustur(r):
        if not ui["panel_giris"]:
            sifre = girdi(r, label="Panel Şifresi", password=True, can_reveal_password=True,
                          keyboard_type=ft.KeyboardType.NUMBER)
            hata = ft.Text(ui["panel_hata"], color=KIRMIZI)

            def giris(e):
                if (sifre.value or "") == PANEL_SIFRESI:
                    ui["panel_giris"] = True
                    ui["panel_hata"] = ""
                    yonetici_kaydet()
                    snack("Giriş Başarılı! ✅")
                else:
                    ui["panel_hata"] = "Şifre yanlış!"
                yenile()

            sifre.on_submit = giris
            return ft.Column([kart(r, ft.Column([
                bolum_basligi(r, ik("LOCK"), "Arda'nın Yönetici Paneli"), sifre, hata,
                buton(r, "Giriş", giris, genis=True)], spacing=12))], expand=True, scroll=ft.ScrollMode.AUTO)

        hata_yazi = ""
        try:
            users = bulut_oku() or {}
            seriler_all = bulut_get("seri") or {}
            dm_index_all = bulut_get("dm_index") or {}
            oyun_skor_all = bulut_get("oyunlar_skor") or {}
        except Exception as ex:
            users, seriler_all, dm_index_all, oyun_skor_all = {}, {}, {}, {}
            hata_yazi = f"Buluttan veriler çekilemedi: {ex}"
        panel["veri"] = users
        panel["imza"] = imza_hesapla(users)
        try:
            notlar = {k: v for k, v in (bulut_get("ayarlar/notlar") or {}).items() if isinstance(v, dict)}
            yon = (bulut_get("yonetici") or {}).get("kullanici", "")
        except Exception:
            notlar, yon = {}, ""
        isimler = sorted(k for k, v in users.items() if isinstance(v, dict))
        if ui["panel_ogrenci"] not in isimler:
            ui["panel_ogrenci"] = isimler[0] if isimler else None
        sec = ui["panel_ogrenci"]

        def ogr_sec(isim):
            def f(e):
                ui["panel_ogrenci"] = isim
                yenile()
            return f

        ciplar = ft.Row([
            ft.Container(
                padding=pad_sim(horizontal=14, vertical=8), border_radius=20, ink=True, on_click=ogr_sec(i),
                bgcolor=r["hdr"] if i == sec else r["card_bg"], border=kenar(1, r["border"]),
                content=ft.Text(i.upper(), size=12, weight=ft.FontWeight.W_700,
                                color=okunur_renk(r["hdr"]) if i == sec else r["txt"]))
            for i in isimler
        ], scroll=ft.ScrollMode.AUTO, spacing=8)

        # --- Sekme 0: canlı öğrenci verileri + seri/sohbet istatistikleri ---
        kap = ft.Column(ogrenci_kartlari(r, users, seriler_all, dm_index_all, oyun_skor_all) or
                        [ft.Text("Henüz kayıtlı öğrenci yok.", color=r["muted"], italic=True)], spacing=10)
        panel["kap"] = kap
        sekme0 = [
            ft.Text("🔴 Canlı: öğrenci çalışma, seri ve oyun verileri burada anlık görünür.", size=12, color=r["muted"]),
            *([ft.Text(hata_yazi, color=KIRMIZI)] if hata_yazi else []),
            kap,
        ]

        # --- Sekme 1: bildirim gönder ---
        mesaj_in = girdi(r, "Kendi mesajını yaz...", label="Mesaj", multiline=True, min_lines=2, max_lines=4)
        HAZIR = [
            ("💧 Su içmeyi unutma!", "Bir bardak su iç, sonra devam. 💧"),
            ("📚 Derse başla!", "Kronometreyi aç ve başla, ben buradayım. 📚"),
            ("😠 Neredesin?", "Saat ilerliyor, ders çalışmayı unutmadın değil mi? 😠"),
            ("☕ Mola zamanı", "Çok güzel çalıştın, 10 dakika mola ver. ☕"),
            ("❤️ Gurur duyuyorum", "Seninle gurur duyuyorum, devam et! ❤️"),
        ]

        def hazir_gonder(baslik, mesaj):
            def f(e):
                if sec:
                    ogrenciye_gonder(sec, baslik, mesaj)
                else:
                    snack("Önce bir öğrenci seç.")
            return f

        def ozel_gonder(e):
            m = (mesaj_in.value or "").strip()
            if not sec:
                snack("Önce bir öğrenci seç.")
            elif not m:
                snack("Önce bir mesaj yaz.")
            else:
                ogrenciye_gonder(sec, "💌 Arda'dan mesaj", m)

        def sinyal_kapat(e):
            if sec:
                arka_plan(lambda: bulut_patch(f"users/{sec}", {"sinyal": {"aktif": False, "mesaj": ""}}))
                snack("Uygulama içi sinyal kapatıldı.")

        sekme1 = [
            ft.Text("Seçili öğrenciye hem telefon bildirimi hem uygulama içi sinyal gider.", size=12, color=r["muted"]),
            kart(r, ft.Column([
                bolum_basligi(r, ik("NOTIFICATIONS_ACTIVE"), "Hazır mesajlar"),
                *[buton(r, b_, hazir_gonder(b_, m_), ikincil=True, genis=True, yukseklik=42) for b_, m_ in HAZIR],
            ], spacing=8)),
            kart(r, ft.Column([
                bolum_basligi(r, ik("EDIT_NOTE"), "Kendi mesajın"),
                mesaj_in,
                buton(r, "Gönder 🚀", ozel_gonder, genis=True),
                buton(r, "Uygulama içi sinyali kapat", sinyal_kapat, ikincil=True, genis=True, yukseklik=42),
            ], spacing=10)),
        ]

        # --- Sekme 2: görev ver ---
        gorev_in = girdi(r, label="Yapılacak görev")
        odul_in = girdi(r, label="Tamamlarsa ödül (Örn: Kahve benden!)")

        def gorev_ver(e):
            g = (gorev_in.value or "").strip()
            o = (odul_in.value or "").strip()
            if not sec or not g:
                snack("Öğrenci seç ve görevi yaz.")
                return

            def is_():
                try:
                    liste = listeye(bulut_get(f"users/{sec}/ozel_gorevler"))
                    liste.append({"gorev": g, "odul": o, "durum": "Bekliyor"})
                    bulut_patch(f"users/{sec}", {"ozel_gorevler": liste})
                    konu = (bulut_get(f"users/{sec}/bildirim") or {}).get("konu")
                    if konu:
                        ntfy_gonder(konu, "🎯 Arda sana yeni görev verdi", f"{g}" + (f"  •  🎁 {o}" if o else ""), 4)
                    snack(f"✅ Görev {sec} kişisine gönderildi")
                except Exception as ex:
                    snack(f"⚠️ Gönderilemedi: {ex}")
            arka_plan(is_)

        mevcut = listeye((users.get(sec) or {}).get("ozel_gorevler")) if sec else []
        gorev_liste = [ft.Text(f"{'✅' if g.get('durum') == 'Tamamlandı' else '⏳'} {g.get('gorev')} → {g.get('odul')}",
                               size=12, color=r["muted"]) for g in mevcut]
        sekme2 = [kart(r, ft.Column([
            bolum_basligi(r, ik("ASSIGNMENT"), "Özel Görev Tanımla"),
            gorev_in, odul_in, buton(r, "Gönder", gorev_ver, genis=True), *gorev_liste,
        ], spacing=10))]

        # --- Sekme 3: sürpriz notlar ---
        not_in = girdi(r, "Örn: Bugün harika gidiyorsun, gurur duyuyorum!", label="Yeni sürpriz not",
                       multiline=True, min_lines=2, max_lines=4)

        def not_ekle(e):
            m = (not_in.value or "").strip()
            if not m:
                snack("Önce notu yaz.")
                return
            hedef = sec if ui["not_hedef"] == 1 and sec else ""

            def is_():
                try:
                    bulut_patch(f"ayarlar/notlar/{yeni_id()}", {"m": m[:300], "k": hedef, "z": int(time.time() * 1000)})
                    snack("💌 Not eklendi, Sürpriz Notu'nda çıkacak")
                    yenile()
                except Exception as ex:
                    snack(f"⚠️ Eklenemedi: {ex}")
            arka_plan(is_)

        def not_sil(nid):
            def f(e):
                def is_():
                    try:
                        bulut_sil(f"ayarlar/notlar/{nid}")
                        yenile()
                    except Exception as ex:
                        snack(f"⚠️ Silinemedi: {ex}")
                arka_plan(is_)
            return f

        def hedef_degisti(i):
            ui["not_hedef"] = i
            yenile()

        not_satirlari = []
        for nid in sorted(notlar, reverse=True):
            v = notlar[nid]
            etiket = f"👤 {v['k']}" if v.get("k") else "👥 herkese"
            not_satirlari.append(ft.Container(
                padding=pad_sim(horizontal=12, vertical=6), border_radius=14, bgcolor=r["bg"], border=kenar(1, r["border"]),
                content=ft.Row([
                    ft.Column([ft.Text(v.get("m", ""), size=13, color=r["txt"]), ft.Text(etiket, size=11, color=r["muted"])],
                              spacing=2, expand=True),
                    ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, on_click=not_sil(nid)),
                ])))
        sekme3 = [kart(r, ft.Column([
            bolum_basligi(r, ik("EDIT_NOTE"), "Günün Sürpriz Notu"),
            ft.Text("Eklediklerin, öğrencinin “Sürpriz Notu Oku” düğmesinde çıkar.", size=12, color=r["muted"]),
            segment(r, ["👥 Herkese", f"👤 {sec.upper() if sec else 'Öğrenci'}"], ui["not_hedef"], hedef_degisti),
            not_in, buton(r, "Notu Ekle 💌", not_ekle, genis=True),
        ], spacing=10)),
            kart(r, ft.Column([bolum_basligi(r, ik("EVENT_NOTE"), f"Eklenen notlar ({len(not_satirlari)})"),
                               *(not_satirlari or [ft.Text("Henüz not eklemedin.", color=r["muted"], italic=True, size=13)])],
                              spacing=8))]

        # --- Sekme 4: 🎮 Oyun ve Sohbet Moderasyonu ---
        try:
            tum_oyunlar = bulut_get("oyunlar") or {}
        except Exception:
            tum_oyunlar = {}

        aktif_oyun_list = [
            (gid, g) for gid, g in sorted(tum_oyunlar.items(), reverse=True)
            if isinstance(g, dict) and g.get("durum") in ("bekliyor", "oynuyor")
        ]

        def oyun_zorla_iptal(gid):
            def f(e):
                def is_():
                    try:
                        bulut_patch(f"oyunlar/{gid}", {"durum": "iptal"})
                        snack("🚫 Oyun iptal edildi.")
                        yenile()
                    except Exception as ex:
                        snack(f"⚠️ Hata: {ex}")
                arka_plan(is_)
            return f

        def eski_oyunlari_temizle(e):
            def is_():
                try:
                    simdi_ms = int(time.time() * 1000)
                    yedi_gun_ms = 7 * 86_400_000
                    silinen = 0
                    for gid, g in list((bulut_get("oyunlar") or {}).items()):
                        if not isinstance(g, dict):
                            continue
                        son_z = int(g.get("sonHamle") or g.get("olusturma") or 0)
                        if g.get("durum") in ("bitti", "iptal") and (simdi_ms - son_z) >= yedi_gun_ms:
                            oyuncular = g.get("oyuncular") or {}
                            for u_o in (oyuncular.get("a"), oyuncular.get("b")):
                                if u_o:
                                    bulut_sil(f"oyuncu_oyunlari/{u_o}/{gid}")
                            bulut_sil(f"oyunlar/{gid}")
                            silinen += 1
                    snack(f"🧹 7 günden eski {silinen} bitmiş/iptal oyun temizlendi.")
                    yenile()
                except Exception as ex:
                    snack(f"⚠️ Temizlenemedi: {ex}")
            arka_plan(is_)

        def genel_sohbeti_temizle(e):
            ui["genel_temizle_onay"] = False

            def is_():
                try:
                    bulut_sil("sosyal/sohbet")
                    sosyal["sohbet"].clear()
                    snack("🧹 Genel sohbet tamamen temizlendi.")
                    yenile()
                except Exception as ex:
                    snack(f"⚠️ Temizlenemedi: {ex}")
            arka_plan(is_)

        oyun_yonetim_satirlari = []
        for gid, g in aktif_oyun_list[:25]:
            oyuncular = g.get("oyuncular") or {}
            tur_ad = (OYUN_TURLERI.get(g.get("tur"), {})).get("ad", g.get("tur", "Oyun"))
            oyun_yonetim_satirlari.append(ft.Container(
                padding=pad_sim(horizontal=10, vertical=8), border_radius=12, bgcolor=r["bg"],
                border=kenar(1, r["border"]),
                content=ft.Row([
                    ft.Column([
                        ft.Text(f"{tur_ad}: {oyuncular.get('a', '?')} vs {oyuncular.get('b', '?')}",
                                size=13, weight=ft.FontWeight.W_700, color=r["txt"]),
                        ft.Text(f"Durum: {g.get('durum')} • Hamle: {g.get('hamleNo', 0)}", size=11, color=r["muted"]),
                    ], spacing=1, expand=True),
                    buton(r, "İptal Et", oyun_zorla_iptal(gid), ikincil=True, yukseklik=34),
                ], spacing=8),
            ))

        sohbet_mod_karti = kart(r, ft.Column([
            bolum_basligi(r, ik("CLEANING_SERVICES"), "Sohbet Moderasyonu"),
            ft.Text("Genel sohbetteki veya akıştaki tekil mesajları/fotoğrafları doğrudan Sosyal sekmesinden çöp kutusu ikonuyla silebilirsin.", size=12, color=r["muted"]),
            *(
                [
                    ft.Text("⚠️ Tüm genel sohbet mesajları kalıcı olarak silinsin mi?", size=13, weight=ft.FontWeight.BOLD, color=KIRMIZI),
                    ft.Row([
                        buton(r, "Evet, Tümünü Sil", genel_sohbeti_temizle, genis=True, yukseklik=40),
                        buton(r, "Vazgeç", lambda e: (ui.update({"genel_temizle_onay": False}), yenile()), ikincil=True, genis=True, yukseklik=40),
                    ], spacing=8),
                ]
                if ui.get("genel_temizle_onay")
                else [
                    buton(r, "Genel Sohbeti Temizle 🗑", lambda e: (ui.update({"genel_temizle_onay": True}), yenile()),
                          ikincil=True, genis=True, yukseklik=42),
                ]
            ),
        ], spacing=8))

        sekme_oyun = [
            kart(r, ft.Column([
                bolum_basligi(r, ik("SPORTS_ESPORTS"), f"Aktif Oyunlar ({len(aktif_oyun_list)})"),
                *(oyun_yonetim_satirlari or [ft.Text("Şu an aktif oyun yok.", size=12, color=r["muted"], italic=True)]),
                buton(r, "7+ Günlük Biten/İptal Oyunları Temizle 🧹", eski_oyunlari_temizle,
                      ikincil=True, genis=True, yukseklik=42),
            ], spacing=10)),
            sohbet_mod_karti,
        ]

        # --- Sekme 5: kullanılmayan hesapları temizle ---
        def son_etkinlik(u):
            adaylar = [sayi(u.get("son_aktif"))] if sayi(u.get("son_aktif")) > 0 else []
            for anahtar in ("calisma_sn", "calisma_log"):
                adaylar += [t for t in (tarih_ms(k) for k in (u.get(anahtar) or {})) if t]
            adaylar += [t for t in (tarih_ms(g.get("tarih", "")) for g in listeye(u.get("gunluk")) if isinstance(g, dict)) if t]
            return max(adaylar) if adaylar else None

        simdi_ms = time.time() * 1000
        esik = [7, 14, 30][ui["panel_esik"]]
        korunan = {oturum["kullanici"], yon}
        satirlar_h, pasifler = [], []
        for uname in isimler:
            ms = son_etkinlik(users[uname])
            gun_ = None if ms is None else (simdi_ms - ms) / 86400000.0
            pasif = gun_ is not None and gun_ >= esik and uname not in korunan
            if pasif:
                pasifler.append(uname)
            satirlar_h.append((gun_ if gun_ is not None else -1, uname, gun_))
        satirlar_h.sort(reverse=True)

        def sil_iste(liste):
            def f(e):
                ui["silinecek"] = list(liste)
                yenile()
            return f

        def vazgec(e):
            ui["silinecek"] = None
            yenile()

        def hesaplari_sil(liste):
            def f(e):
                ui["silinecek"] = None

                def is_():
                    for u_ in liste:
                        try:
                            hesap_tamamen_sil_bulut(u_)
                        except Exception as ex:
                            snack(f"⚠️ {u_} silinemedi: {ex}")
                            continue
                    snack(f"🗑 {len(liste)} hesap ve tüm sosyal/oyun/seri verileri silindi")
                    yenile()
                arka_plan(is_)
            return f

        def esik_degisti(i):
            ui["panel_esik"] = i
            ui["silinecek"] = None
            yenile()

        sekme4 = [segment(r, ["7 gün", "14 gün", "30 gün"], ui["panel_esik"], esik_degisti),
                  ft.Text(f"{esik} günden uzun süredir uygulamayı açmayan hesaplar kırmızı görünür. "
                          "Sildiğinde hesap, paylaşımları, özel sohbetleri, serileri ve oyunları kalıcı olarak gider.",
                          size=12, color=r["muted"])]
        if ui["silinecek"]:
            sekme4.append(kart(r, ft.Column([
                ft.Text(f"⚠️ {len(ui['silinecek'])} hesap kalıcı olarak silinecek:", weight=ft.FontWeight.BOLD, color=KIRMIZI),
                ft.Text(", ".join(u_.upper() for u_ in ui["silinecek"]), size=13, color=r["txt"]),
                ft.Row([buton(r, "Evet, sil", hesaplari_sil(ui["silinecek"]), genis=True, yukseklik=44),
                        buton(r, "Vazgeç", vazgec, genis=True, ikincil=True, yukseklik=44)], spacing=10),
            ], spacing=10), border=kenar(2, KIRMIZI)))
        elif pasifler:
            sekme4.append(buton(r, f"{esik}+ gündür girmeyen {len(pasifler)} hesabı sil", sil_iste(pasifler),
                                ikon=ik("DELETE_OUTLINE"), genis=True, yukseklik=46))
        for _, uname, gun_ in satirlar_h:
            if gun_ is None:
                etiket, renk_ = "son görülme bilinmiyor (eski hesap)", r["muted"]
            elif gun_ < 1:
                etiket, renk_ = "bugün aktif", r["accent"]
            else:
                etiket, renk_ = f"{int(gun_)} gün önce", KIRMIZI if gun_ >= esik else r["muted"]
            sekme4.append(kart(r, ft.Row([
                avatar(r, uname),
                ft.Column([ft.Text(uname.upper(), size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                           ft.Text(etiket, size=12, color=renk_)], spacing=0, expand=True),
                *([ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, on_click=sil_iste([uname]))]
                  if uname not in korunan else [ft.Text("korumalı", size=11, color=r["muted"])]),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=12))

        def degisti(i):
            ui["panel_tab"] = i
            ui["silinecek"] = None
            yenile()

        sekmeler = [sekme0, sekme1, sekme2, sekme3, sekme_oyun, sekme4]
        ust = [segment(r, ["📈 Veri", "🔔 Gönder", "📝 Görev", "💌 Not", "🎮 Oyun", "🗑 Hesap"], ui["panel_tab"], degisti)]
        if ui["panel_tab"] in (1, 2, 3):
            ust.append(ciplar if isimler else ft.Text("Henüz kayıtlı öğrenci yok.", color=r["muted"], italic=True))
        return ft.Column([*ust, *sekmeler[ui["panel_tab"]], ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 14. GÖRÜNÜM (TEMA)
    # ==========================================
    def tema_sayfasi_olustur(r):
        kartlar = []
        for ad, t in TEMA_RENKLERI.items():
            secili = ad == DB["tema"]
            kartlar.append(ft.Container(
                padding=14, border_radius=18, ink=True, on_click=lambda e, a=ad: tema_uygula(a),
                bgcolor=r["card_bg"], border=kenar(2 if secili else 1, r["hdr"] if secili else r["border"]),
                content=ft.Row([
                    ft.Stack([
                        ft.Container(width=40, height=40, border_radius=20, bgcolor=t["bg"], border=kenar(1, t["border"])),
                        ft.Container(width=22, height=22, border_radius=11, bgcolor=t["hdr"], left=9, top=9),
                    ], width=40, height=40),
                    ft.Text(ad, size=15, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    ft.Icon(ik("CHECK_CIRCLE") if secili else ik("CIRCLE_OUTLINED"),
                            color=r["hdr"] if secili else r["muted"]),
                ], spacing=14),
            ))
        return ft.Column([
            ft.Text("Seçtiğin tema kaydedilir, uygulamayı kapatıp açsan da değişmez.", size=12, color=r["muted"]),
            *kartlar, ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    # ==========================================
    # 14b. BİLDİRİMLER (Çalışma + Sosyal + Seri + Oyun Bildirim Tercihleri)
    # ==========================================
    def bildirim_sayfasi_olustur(r):
        bildirim_konu_hazirla()
        b = DB["bildirim"]
        konu = b.get("konu", "")
        host = NTFY_SUNUCU.split("//")[-1]

        def anahtar_degis(anahtar):
            def f(e):
                b[anahtar] = bool(e.control.value)
                kaydet("bildirim")
            return f

        def satir(etiket, aciklama, anahtar, varsayilan=True):
            return ft.Row([
                ft.Column([ft.Text(etiket, size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                           ft.Text(aciklama, size=12, color=r["muted"])], spacing=2, expand=True),
                ft.Switch(value=bool(b.get(anahtar, varsayilan)), active_color=r["hdr"], on_change=anahtar_degis(anahtar)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        saatler = [9, 10, 11, 12]
        try:
            secili = saatler.index(int(b.get("baslama", 11)))
        except (ValueError, TypeError):
            secili = 2

        def saat_sec(i):
            b["baslama"] = saatler[i]
            kaydet("bildirim")
            yenile()

        def test(e):
            def is_():
                ok, hata = ntfy_gonder(konu, "🔔 Test bildirimi", f"Merhaba {kullanici_adi()}! Bildirimler çalışıyor 🎉", 3)
                snack("✅ Test bildirimi gönderildi, telefonuna bak!" if ok else f"⚠️ Gitmedi: {hata}")
            arka_plan(is_)

        kurulum = kart(r, ft.Column([
            bolum_basligi(r, ik("NOTIFICATIONS_ACTIVE"), "Telefon bildirimini kur (1 kere)"),
            ft.Text("1) Play Store / App Store'dan ücretsiz “ntfy” uygulamasını kur.\n"
                    "2) Aşağıdaki düğmeye bas (ya da ntfy'de + ile şu konuya abone ol).\n"
                    "3) Test bildirimi gönder. Uygulama kapalıyken de bildirim gelir.",
                    size=13, color=r["txt"]),
            ft.Container(padding=12, border_radius=12, bgcolor=r["bg"], border=kenar(1, r["border"]),
                         content=ft.Text(konu or "…", selectable=True, size=13, weight=ft.FontWeight.W_700, color=r["hdr"])),
            buton(r, "ntfy uygulamasında abone ol", lambda e: url_ac(f"ntfy://{host}/{konu}"), genis=True),
            buton(r, "Test bildirimi gönder 🔔", test, genis=True, ikincil=True),
        ], spacing=10))

        ayarlar = kart(r, ft.Column([
            bolum_basligi(r, ik("EDIT_NOTE"), "Çalışma Hatırlatmaları"),
            satir("Tüm bildirimler", "Kapatırsan hiçbir bildirim gelmez", "aktif", True),
            satir("☀️ Sabah planı", "Günün ilk görevini hatırlatır", "sabah", True),
            satir("💧 Su hatırlatma", "Geride kalırsan gün içinde dürter", "su", True),
            satir("⏰ Derse başla", "Hedef saatte hâlâ başlamadıysan kızar 😠", "ders", True),
            satir("🌙 Gün sonu", "Gün sonunu doldurmayı hatırlatır", "gunsonu", True),
            ft.Text("Derse başlama hedef saati", size=13, color=r["muted"]),
            segment(r, [f"{h}:00" for h in saatler], secili, saat_sec),
        ], spacing=12))

        sosyal_ayarlar = kart(r, ft.Column([
            bolum_basligi(r, ik("FORUM"), "Sosyal, Seri & Oyun Bildirimleri"),
            satir("📸 Yeni fotoğraf", "Akışa yeni fotoğraf atıldığında haber verir", "sosyal_foto", True),
            satir("💬 Genel sohbet mesajları", "Genel sohbette yeni mesaj olduğunda bildirir", "sosyal_genel", True),
            satir("🔕 Genel sohbeti tamamen sessize al", "Açıkken genel sohbetten hiç bildirim gelmez", "genel_sessiz", False),
            satir("✉️ Özel mesajlar (DM)", "Sana özel mesaj geldiğinde anında bildirir", "sosyal_dm", True),
            satir("🔥 Günlük seri (Streak) uyarıları", "Serin tehlikedeyken ve rekorlarda uyarır", "sosyal_seri", True),
            satir("❤️ Beğeni ve yorumlar", "Fotoğrafın beğenildiğinde veya yorum geldiğinde bildirir", "sosyal_etkilesim", True),
            satir("🎮 Oyun daveti ve sıra bildirimi", "Oyun davetlerinde ve sıra sana geçtiğinde haber verir", "sosyal_oyun", True),
        ], spacing=12))

        not_ = ft.Text("Sessiz saatler (23:30 - 08:30) arasında 23:15 son şans seri uyarısı hariç bildirim gönderilmez.",
                       size=12, color=r["muted"])
        return ft.Column([kurulum, ayarlar, sosyal_ayarlar, not_, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 15. DİĞER MENÜSÜ
    # ==========================================
    ALT_SAYFALAR = {
        "gunsonu": (ik("NIGHTLIGHT_ROUND"), "Gün Sonu", "Süre, performans ve günlük kayıtların", gun_sonu_sayfasi_olustur),
        "bildirim": (ik("NOTIFICATIONS_ACTIVE"), "Bildirimler", "Çalışma, sohbet, seri ve oyun bildirimleri", bildirim_sayfasi_olustur),
        "asistan": (ik("SMART_TOY"), "Asistan", "Sorularına Arda'dan cevap", asistan_sayfasi_olustur),
        "eglence": (ik("SPORTS_ESPORTS"), "Eğlence & Mola", "Botla XOX ve YouTube kısayolları", eglence_sayfasi_olustur),
        "muzik": (ik("HEADPHONES"), "Odak Müzik", "Spotify ve odak sesleri", muzik_sayfasi_olustur),
        "tema": (ik("PALETTE"), "Görünüm", "Tema seç", tema_sayfasi_olustur),
        "panel": (ik("ADMIN_PANEL_SETTINGS"), "Arda'nın Paneli", "Canlı veri, seri, oyun, görev, not, hesap temizliği", panel_sayfasi_olustur),
    }

    def cikis_yap(e):
        bulut_gonder()
        oturumu_kapat()
        ui["giris_mod"] = "giris"
        ui["hata"] = ""
        giris_ac()

    def diger_sayfasi_olustur(r):
        if ui["alt"] is None:
            def ac(anahtar):
                def f(e):
                    ui["alt"] = anahtar
                    yenile()
                return f

            def satir(anahtar, ikon, ad, aciklama, tikla, vurgulu=False):
                on = okunur_renk(r["hdr"])
                return ft.Container(
                    padding=14, border_radius=20, ink=True, on_click=tikla,
                    bgcolor=r["hdr"] if vurgulu else r["card_bg"],
                    border=kenar(1, r["hdr"] if vurgulu else r["border"]),
                    content=ft.Row([
                        ft.Container(width=44, height=44, border_radius=14, alignment=ORTA,
                                     bgcolor=opak(0.22, on) if vurgulu else opak(0.14, r["hdr"]),
                                     content=ft.Icon(ikon, color=on if vurgulu else r["hdr"])),
                        ft.Column([
                            ft.Text(ad, size=15, weight=ft.FontWeight.W_700, color=on if vurgulu else r["txt"]),
                            ft.Text(aciklama, size=12, color=opak(0.85, on) if vurgulu else r["muted"]),
                        ], spacing=2, expand=True),
                        ft.Icon(ik("CHEVRON_RIGHT"), color=on if vurgulu else r["muted"]),
                    ], spacing=14),
                )

            satirlar = [satir(k, ikon, ad, ac_, ac(k), vurgulu=(k == "gunsonu"))
                        for k, (ikon, ad, ac_, _) in ALT_SAYFALAR.items()]
            satirlar.append(satir("cikis", ik("LOGOUT"), "Çıkış Yap",
                                  f"{kullanici_adi()} hesabından çık", cikis_yap))
            return ft.Column([
                sayfa_basligi(r, "Daha Fazla"),
                *satirlar,
                ft.Container(height=24),
            ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

        ikon, baslik, aciklama, olusturucu = ALT_SAYFALAR[ui["alt"]]

        def geri(e):
            ui["alt"] = None
            ui["panel_giris"] = False
            yenile()

        return ft.Column([
            sayfa_basligi(r, baslik, aciklama, geri=geri),
            olusturucu(r),
        ], expand=True, spacing=12)

    # ==========================================
    # 16. GİRİŞ / KAYIT EKRANI
    # ==========================================
    def giris_ekrani_olustur(r):
        mod = ui["giris_mod"]
        hata = ft.Text(ui["hata"], color=KIRMIZI, size=13)
        kullanici = girdi(r, label="Kullanıcı adı (Boşluksuz)", prefix_icon=ik("PERSON"), value=ui["taslak"])
        sifre = girdi(r, label="Şifre", password=True, can_reveal_password=True, prefix_icon=ik("LOCK"))
        sifre2 = girdi(r, label="Şifre (tekrar)", password=True, can_reveal_password=True, prefix_icon=ik("LOCK_OUTLINE"))

        def hata_goster(m):
            ui["hata"] = m
            ui["taslak"] = kullanici.value or ""
            giris_ac()

        def oturum_ac(ad, veri, yeni_hesap=False):
            with kilit:
                DB.clear()
                DB.update(veri)
                oturum["kullanici"] = ad
                oturum["kirli"] = {k: 1 for k in BULUT_ANAHTARLARI} if yeni_hesap else {}
                oturum["surum"] = 1 if yeni_hesap else 0
                yerel_yaz()
            if yeni_hesap:
                bulut_olay.set()
            ui["hata"] = ""
            ui["taslak"] = ""
            tema_uygula(DB["tema"], kaydetme=False)
            uygulama_ac()

        def kayit_ol(e):
            ad = (kullanici.value or "").strip().lower()
            if len(ad) < 3 or not ad.replace("_", "").isalnum():
                return hata_goster("Kullanıcı adı en az 3 karakter olmalı; sadece harf, rakam ve _ kullan.")
            if len(sifre.value or "") < 4:
                return hata_goster("Şifre en az 4 karakter olmalı.")
            if (sifre.value or "") != (sifre2.value or ""):
                return hata_goster("Şifreler aynı değil, ikisini de aynı yaz.")
            try:
                if bulut_oku(ad) is not None:
                    return hata_goster("Bu kullanıcı adı alınmış!")
            except Exception as ex:
                return hata_goster(f"Buluta bağlanılamadı: {ex}")
            tuz = os.urandom(8).hex()
            yeni_db = db_hazirla({"tema": DB["tema"]})
            yeni_db["hesap"] = {"kullanici": ad, "tuz": tuz, "ozet": sifre_ozeti(sifre.value, tuz)}
            oturum_ac(ad, yeni_db, yeni_hesap=True)

        def giris_yap(e):
            ad = (kullanici.value or "").strip().lower()
            if not ad:
                return hata_goster("Kullanıcı adını yaz.")
            try:
                ham = bulut_oku(ad)
            except Exception as ex:
                return hata_goster(f"Buluta bağlanılamadı: {ex}")
            if ham is None:
                return hata_goster("Kullanıcı bulunamadı, önce hesap aç.")
            h = ham.get("hesap") or {}
            if sifre_ozeti(sifre.value or "", h.get("tuz", "")) != h.get("ozet"):
                return hata_goster("Şifre hatalı!")
            veri = db_hazirla(ham)
            oturum_ac(ad, veri)

        if mod == "kayit":
            sifre2.on_submit = kayit_ol
            form = [kullanici, sifre, sifre2, hata, buton(r, "Bulutta Hesap Oluştur", kayit_ol, genis=True, yukseklik=52),
                    metin_dugmesi("Zaten hesabım var", on_click=lambda e: (ui.update({"giris_mod": "giris", "hata": "", "taslak": ""}), giris_ac()))]
        else:
            form = [kullanici, sifre, hata, buton(r, "Giriş Yap", giris_yap, genis=True, yukseklik=52),
                    metin_dugmesi("Yeni hesap aç", on_click=lambda e: (ui.update({"giris_mod": "kayit", "hata": "", "taslak": ""}), giris_ac()))]

        logo = ft.Container(width=88, height=88, border_radius=28, alignment=ORTA,
                            gradient=ft.LinearGradient(begin=UST_SOL, end=ALT_SAG, colors=[karistir(r["hdr"], "#000000", 0.1), karistir(r["hdr"], "#000000", 0.5)]),
                            content=ft.Text("🚀", size=44))
        return ft.Column([ft.Container(height=30), ft.Row([logo], alignment=ft.MainAxisAlignment.CENTER),
                          ft.Text("YKS İstasyonu (Bulut)", size=28, weight=ft.FontWeight.W_800, color=r["txt"], text_align=ft.TextAlign.CENTER),
                          kart(r, ft.Column(form, spacing=12))], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ==========================================
    # 17. ANA İSKELET, NAVİGASYON, TEMA
    # ==========================================
    kok = ft.Container(expand=True, padding=pad_only(left=16, right=16, top=10, bottom=0))
    ui_kapsayici = ft.Container(expand=True)

    def birlestir(eski, yeni):
        """Aynı sayfayı yeniden çizerken eski Column'u korur, sadece içeriğini değiştirir.
        Böylece her dokunuşta sayfa en başa atmaz, kaydırma konumu aynı kalır."""
        if not (isinstance(eski, ft.Column) and isinstance(yeni, ft.Column)):
            return False
        if eski.scroll:
            eski.controls = yeni.controls
            return True
        if len(eski.controls) != len(yeni.controls):
            return False
        for i, (a, b) in enumerate(zip(eski.controls, yeni.controls)):
            if isinstance(a, ft.Column) and isinstance(b, ft.Column) and a.scroll:
                a.controls = b.controls
            else:
                eski.controls[i] = b
        return True

    def sayfa_anahtari():
        s_, a = ui["sekme"], (ui["sekme"], ui["alt"])
        if s_ == 2:
            a += (ui["net_tab"],)
        elif s_ == 4:
            a += (ui["sosyal_alt"], ui["sohbet_tab"], ui["aktif_dm"], ui["aktif_oyun"])
        elif s_ == 5 and ui["alt"] == "eglence":
            a += (ui["eglence_tab"],)
        elif s_ == 5 and ui["alt"] == "panel":
            a += (ui["panel_giris"], ui["panel_tab"])
        return a

    def icerik_guncelle(r):
        s = ui["sekme"]
        if s == 0:
            yeni = ana_sayfa_olustur(r)
        elif s == 1:
            yeni = calisma_sayfasi_olustur(r)
        elif s == 2:
            yeni = net_sayfasi_olustur(r)
        elif s == 3:
            yeni = plan_sayfasi_olustur(r)
        elif s == 4:
            yeni = sosyal_sayfasi_olustur(r)
        else:
            yeni = diger_sayfasi_olustur(r)
        anahtar = sayfa_anahtari()
        eski = ui_kapsayici.content
        if not (ui["_anahtar"] == anahtar and eski is not None and birlestir(eski, yeni)):
            ui_kapsayici.content = yeni
        ui["_anahtar"] = anahtar
        duzelt(ui_kapsayici.content)

    def nav_degisti(e):
        ui["sekme"] = e.control.selected_index
        ui["alt"] = None
        ui["panel_giris"] = False
        ui["surpriz"] = ""
        if ui["sekme"] != 4:
            aktif_isaretle("")
        yenile()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0, on_change=nav_degisti, height=68,
        destinations=[
            ft.NavigationBarDestination(icon=ik("HOME_OUTLINED"), selected_icon=ik("HOME"), label="Ana"),
            ft.NavigationBarDestination(icon=ik("TIMER_OUTLINED"), selected_icon=ik("TIMER"), label="Çalış"),
            ft.NavigationBarDestination(icon=ik("SHOW_CHART_OUTLINED"), selected_icon=ik("SHOW_CHART"), label="Netler"),
            ft.NavigationBarDestination(icon=ik("CALENDAR_MONTH_OUTLINED"), selected_icon=ik("CALENDAR_MONTH"), label="Plan"),
            ft.NavigationBarDestination(icon=ik("FORUM_OUTLINED"), selected_icon=ik("FORUM"), label="Sosyal"),
            ft.NavigationBarDestination(icon=ik("GRID_VIEW_OUTLINED"), selected_icon=ik("GRID_VIEW"), label="Menü"),
        ],
    )

    def giris_ac():
        page.navigation_bar.visible = False
        kok.content = duzelt(giris_ekrani_olustur(renk()))
        page.update()

    def uygulama_ac():
        ui["sekme"] = 0
        ui["alt"] = None
        page.navigation_bar.selected_index = 0
        page.navigation_bar.visible = True
        bildirim_konu_hazirla()
        aktif_isaretle("")
        # Açılışta seri başarımlarının ana sayfada güncel olması için seri tablosunu arka planda çek
        arka_plan(lambda: (sosyal_cek("dm_liste"), yenile()))
        icerik_guncelle(renk())
        kok.content = ui_kapsayici
        page.update()

    def tema_uygula(isim, kaydetme=True):
        DB["tema"] = isim
        if kaydetme:
            kaydet("tema")
        r = TEMA_RENKLERI[isim]
        page.bgcolor = r["bg"]
        page.theme_mode = r["mode"]
        page.theme = ft.Theme(color_scheme_seed=r["hdr"])
        page.dark_theme = ft.Theme(color_scheme_seed=r["hdr"])
        page.navigation_bar.bgcolor = r["card_bg"]
        page.navigation_bar.indicator_color = opak(0.25, r["hdr"])
        if kok.content is ui_kapsayici:
            icerik_guncelle(r)
        elif kok.content is not None:
            kok.content = duzelt(giris_ekrani_olustur(r))
        page.update()

    # ---------- arka plan döngüleri ----------
    def geri_sayim_dongusu():
        """Ana sayfadaki YKS geri sayımını her saniye yeniler."""
        while True:
            time.sleep(1)
            try:
                if kok.content is not ui_kapsayici or ui["sekme"] != 0 or not gk["metinler"]:
                    continue
                toplam = int((YKS_TARIHI - datetime.now()).total_seconds())
                if toplam <= 0:
                    continue
                for t, d in zip(gk["metinler"], (toplam // 86400, (toplam % 86400) // 3600, (toplam % 3600) // 60, toplam % 60)):
                    t.value = str(d)
                    t.update()
            except Exception:
                pass

    def bulut_cek_dongusu():
        """Öğrenci tarafı: yöneticiden gelen sinyal/görevleri alır, hesap silindiyse çıkarır, son_aktif'i tazeler."""
        tur = 0
        while True:
            time.sleep(15)
            tur += 1
            kul = oturum["kullanici"]
            if not kul or oturum["kirli"]:
                continue
            if tur % 80 == 0:
                aktif_isaretle()
            try:
                if bulut_get(f"users/{kul}/hesap/tuz") is None and not oturum["kirli"]:
                    oturumu_kapat()
                    ui["giris_mod"] = "kayit"
                    giris_ac()
                    snack("Hesabın silinmiş. İstersen yeniden hesap açabilirsin.")
                    continue
                sg = bulut_get(f"users/{kul}/sinyal") or {}
                gorev = listeye(bulut_get(f"users/{kul}/ozel_gorevler"))
            except Exception:
                continue
            sinyal = {"aktif": bool(sg.get("aktif")), "mesaj": sg.get("mesaj", "")}
            if sinyal == DB["sinyal"] and gorev == DB["ozel_gorevler"]:
                continue
            yeni_sinyal = bool(sinyal["aktif"] and sinyal["mesaj"] and sinyal != DB["sinyal"])
            with kilit:
                if oturum["kirli"]:
                    continue
                DB["sinyal"] = sinyal
                DB["ozel_gorevler"] = gorev
                yerel_yaz()
            try:
                if kok.content is ui_kapsayici and ui["sekme"] == 0 and ui["alt"] is None:
                    yenile()
                if yeni_sinyal:
                    snack(f"🚨 Arda: {sinyal['mesaj']}")
            except Exception:
                pass

    def sosyal_izle():
        """Sosyal sekmesi görünürken açık alt ekrana göre uyarlamalı hızda yoklama (polling) yapar:
        - Açık oyun ekranı: ~1.5 sn
        - Açık özel sohbet (DM): ~2.0 sn
        - Genel sohbet / Oyun lobisi / Fotoğraf akışı: ~3.0 sn
        - Özel sohbet gelen kutusu: ~4.0 sn
        - Sosyal sekmesi görünür değilken hiçbir ağ çağrısı yapmaz.
        """
        son_zaman = 0.0
        while True:
            time.sleep(0.5)
            try:
                if not (oturum["kullanici"] and kok.content is ui_kapsayici and ui["sekme"] == 4):
                    continue
                simdi = time.time()
                alt = ui.get("sosyal_alt")
                if alt == "oyun" and ui.get("aktif_oyun"):
                    aralik, hedef = 1.5, "oyun_aktif"
                elif alt == "oyun":
                    aralik, hedef = 3.0, "oyun_lobi"
                elif alt == "sohbet" and ui.get("aktif_dm"):
                    aralik, hedef = 2.0, "dm_aktif"
                elif alt == "sohbet" and ui.get("sohbet_tab") == 1:
                    aralik, hedef = 4.0, "dm_liste"
                elif alt == "sohbet":
                    aralik, hedef = 3.0, "genel"
                else:
                    aralik, hedef = 3.0, "akis"

                if (simdi - son_zaman) >= aralik:
                    son_zaman = simdi
                    sosyal_getir(hedef)
            except Exception:
                pass

    def panel_izle():
        """Yönetici tarafı: panel açıkken öğrenci verilerini 4 sn'de bir yeniler, yeni kayıtta haber verir."""
        while True:
            time.sleep(4)
            try:
                if not (kok.content is ui_kapsayici and ui["sekme"] == 5 and ui["alt"] == "panel"
                        and ui["panel_giris"] and ui["panel_tab"] == 0 and panel["kap"] is not None):
                    continue
                users = bulut_oku() or {}
                seriler_all = bulut_get("seri") or {}
                dm_index_all = bulut_get("dm_index") or {}
                oyun_skor_all = bulut_get("oyunlar_skor") or {}
                yeni = imza_hesapla(users)
                for u, (g_, n_) in yeni.items():
                    og, on = panel["imza"].get(u, (g_, n_))
                    if g_ > og:
                        snack(f"🔔 {u} gün sonunu kaydetti!")
                    if n_ > on:
                        snack(f"🔔 {u} yeni deneme ekledi!")
                panel["imza"] = yeni
                panel["veri"] = users
                panel["kap"].controls = ogrenci_kartlari(renk(), users, seriler_all, dm_index_all, oyun_skor_all) or \
                    [ft.Text("Henüz kayıtlı öğrenci yok.", color=renk()["muted"], italic=True)]
                panel["kap"].update()
            except Exception:
                pass

    def buluttan_esitle():
        """Açılışta: gönderilmemiş değişikliği yolla, sonra buluttaki güncel veriyi al."""
        kul = oturum["kullanici"]
        if not kul:
            return
        try:
            if oturum["kirli"] and not bulut_gonder():
                return
            ham = bulut_oku(kul)
            if ham is None:
                return
            yeni = db_hazirla(ham)
            with kilit:
                if oturum["kirli"]:
                    return
                DB.clear()
                DB.update(yeni)
                yerel_yaz()
            tema_uygula(DB["tema"], kaydetme=False)
            bildirim_konu_hazirla()
            aktif_isaretle()
        except Exception as ex:
            print("Bulut eşitleme hatası:", ex)

    # Test ortamında dışarıdan erişim için yardımcı kancalar (hooks)
    page._test_hooks = {
        "DB": DB,
        "ui": ui,
        "oturum": oturum,
        "sosyal": sosyal,
        "yenile": yenile,
        "sosyal_getir": sosyal_getir,
        "dm_mesaj_gonder_islem": dm_mesaj_gonder_islem,
        "oyun_davet_olustur": oyun_davet_olustur,
        "oyun_kabul_islem": oyun_kabul_islem,
        "oyun_iptal_islem": oyun_iptal_islem,
        "oyun_hamle_gonder_islem": oyun_hamle_gonder_islem,
        "oyun_teslim_ol_islem": oyun_teslim_ol_islem,
        "oyun_hukmen_kazan_islem": oyun_hukmen_kazan_islem,
        "oyun_tekrar_oyna_islem": oyun_tekrar_oyna_islem,
        "hesap_tamamen_sil_bulut": hesap_tamamen_sil_bulut,
        "aktif_isaretle": aktif_isaretle,
        "bulut_gonder": bulut_gonder,
    }

    page.add(ft.SafeArea(content=kok, expand=True))
    tema_uygula(DB["tema"], kaydetme=False)
    arka_plan(geri_sayim_dongusu)
    arka_plan(bulut_cek_dongusu)
    arka_plan(panel_izle)
    arka_plan(sosyal_izle)
    if oturum["kullanici"] and DB["hesap"]:
        uygulama_ac()
        arka_plan(buluttan_esitle)
    else:
        giris_ac()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
