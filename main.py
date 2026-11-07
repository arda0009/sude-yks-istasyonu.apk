import flet as ft
import random
import math
import time
import threading
import copy
import json
import os
import hashlib
from datetime import datetime, date, timedelta

# Firebase Realtime Database adresin (Console > Realtime Database sayfasının en üstünde yazar).
# Avrupa bölgesi seçtiysen şuna benzer olur: https://PROJE-default-rtdb.europe-west1.firebasedatabase.app
FIREBASE_URL = "https://yks-istasyonu-default-rtdb.firebaseio.com"
try:
    import requests
except ImportError:  # requests yoksa uygulama yine açılır, sadece Asistan çalışmaz
    requests = None

# ==========================================
# 0. AYARLAR (BURAYI KENDİNE GÖRE DÜZENLE)
# ==========================================
HEDEF_UNIVERSITE = "Güneş Üniversitesi Tıp Fakültesi"
HEDEF_TYT = 105.0
HEDEF_AYT = 64.0
YKS_TARIHI = datetime(2027, 6, 19, 10, 15)
PANEL_SIFRESI = "1905"
SPOTIFY_URL = "https://open.spotify.com/playlist/0zHr4z4SfUeKZOXv3rxVIV"

# Asistan için anahtarlar (Streamlit'te st.secrets içindeydi).
# DİKKAT: APK'nın içine yazılan anahtar, APK'yı açan biri tarafından okunabilir.
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

# Müfredat (Streamlit'teki varsayılan konu listesiyle birebir aynı)
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
    klasor = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(klasor, exist_ok=True)
    except Exception:
        pass
    return os.path.join(klasor, "yks_asistan_veri.json")


# ==========================================
# FIREBASE YARDIMCILARI
# ==========================================
BULUT_ANAHTARLARI = [k for k in VARSAYILAN_VERI if k != "oturum"]
TARIHLI_ANAHTARLAR = ("calisma_sn", "calisma_log")   # içindeki anahtarlar "07.11.2026" gibi tarih
LISTE_ANAHTARLARI = ("todo", "netler", "konu_bitti", "kumbara", "gunluk", "ozel_gorevler")


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
    for k in ("su", "gun", "sinyal", "calisma_sn", "calisma_log"):
        if not isinstance(db[k], dict):
            db[k] = copy.deepcopy(VARSAYILAN_VERI[k])
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


def main(page: ft.Page):
    page.title = "YKS Asistanım 🚀"
    page.padding = 0
    page.spacing = 0
    page.window.width = 400
    page.window.height = 820

    # ==========================================
    # 3. KALICI VERİ
    #    Önce telefondaki dosyaya, ayrıca client_storage'a yazılır. Açılışta dosya okunur.
    # ==========================================
    DOSYA = depo_dosyasi()
    kilit = threading.RLock()
    oturum = {"kullanici": "", "senkron": True}   # kim giriş yapmış, buluta yazılmamış değişiklik var mı
    bulut = {"bekleyen": set(), "olay": threading.Event()}
    DB = {}   # DİKKAT: hiçbir yerde yeniden atanmaz, DB.clear()/DB.update() ile yerinde değişir

    def yerel_yaz():
        """Telefondaki yedeği yazar (internet yokken de veri kaybolmasın)."""
        with kilit:
            try:
                gecici = DOSYA + ".tmp"
                with open(gecici, "w", encoding="utf-8") as f:
                    json.dump({"kullanici": oturum["kullanici"], "senkron": oturum["senkron"], "db": DB},
                              f, ensure_ascii=False)
                os.replace(gecici, DOSYA)
            except Exception as ex:
                print("Yerel kayıt hatası:", ex)

    def yerelden_yukle():
        try:
            with open(DOSYA, "r", encoding="utf-8") as f:
                veri = json.load(f)
        except Exception:
            return "", True, {}
        if not isinstance(veri, dict):
            return "", True, {}
        if "db" not in veri:                      # eski sürümün düz dosya biçimi
            return "", True, veri
        return str(veri.get("kullanici") or ""), bool(veri.get("senkron", True)), veri.get("db") or {}

    _k, _s, _ham = yerelden_yukle()
    DB.update(db_hazirla(_ham))
    oturum["kullanici"], oturum["senkron"] = _k, _s

    def bulut_gonder():
        """Bekleyen değişiklikleri Firebase'e yollar. Başarılıysa True döner."""
        with kilit:
            kul = oturum["kullanici"]
            anahtarlar = set(bulut["bekleyen"])
            bulut["bekleyen"].clear()
            veri = {a: bulut_hazirla(a, copy.deepcopy(DB.get(a))) for a in anahtarlar}
        if not kul or not anahtarlar:
            return True
        try:
            bulut_guncelle(kul, veri)
        except Exception as ex:
            print("Bulut kayıt hatası:", ex)
            with kilit:
                bulut["bekleyen"].update(anahtarlar)
            return False
        with kilit:
            if not bulut["bekleyen"]:
                oturum["senkron"] = True
                yerel_yaz()
        return True

    def bulut_isci():
        """Tek bir arka plan işçisi: yazmalar sırayla gider, internet yoksa 5 sn'de bir tekrar dener."""
        while True:
            bulut["olay"].wait()
            bulut["olay"].clear()
            while not bulut_gonder():
                time.sleep(5)

    threading.Thread(target=bulut_isci, daemon=True).start()

    def kaydet(anahtar=None):
        """Önce telefona, sonra arka planda Firebase'e kaydeder."""
        with kilit:
            if oturum["kullanici"]:
                oturum["senkron"] = False
                bulut["bekleyen"].update([anahtar] if anahtar else BULUT_ANAHTARLARI)
            yerel_yaz()
        if oturum["kullanici"]:
            bulut["olay"].set()

    ui = {
        "sekme": 0, "alt": None, "net_tab": 0, "net_sinav": "TYT", "ders": None,
        "surpriz": "", "panel_giris": False, "panel_tab": 0, "eglence_tab": 0, "panel_hata": "",
        "plan_gun": datetime.now().weekday(), "giris_mod": "giris" if oturum["kullanici"] else "kayit", "hata": "",
        "gs_tarih": "", "gs_puan": 0, "gs_not": "",
    }
    oyun = {"xox": [""] * 9, "xox_kazanan": None}
    zm = {"mod": "krono", "durum": "bos", "birikmis": 0.0, "t0": None,
          "label": None, "ring": None, "thread": None, "bildirildi": False}

    # --- çalışma süresi yardımcıları ---
    def gun_sn(tarih):
        return int(DB["calisma_sn"].get(tarih, 0)) + int(DB["calisma_log"].get(tarih, 0)) * 60

    def toplam_sn():
        return sum(int(v) for v in DB["calisma_sn"].values()) + sum(int(v) for v in DB["calisma_log"].values()) * 60

    def kullanici_adi():
        return (DB["hesap"] or {}).get("kullanici", "")

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
                if isinstance(k, ft.ElevatedButton) and k.expand:
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
            page.open(ft.SnackBar(ft.Text(mesaj)))
        except Exception:
            pass

    def kutlama():
        def isle():
            try:
                w = int(page.width or 400)
                h = int(page.height or 800)
                kat = ft.Stack(expand=True)
                for _ in range(14):
                    kat.controls.append(ft.Container(
                        content=ft.Text(random.choice(["🎈", "🎉", "💖", "✨", "🌹"]), size=random.randint(24, 38)),
                        left=random.randint(0, max(10, w - 40)), top=h,
                        animate_position=ft.animation.Animation(random.randint(1800, 3000), ft.AnimationCurve.EASE_OUT),
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
            border=border or ft.border.all(1, r["border"]),
            shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.06, "#000000"), offset=ft.Offset(0, 4)),
            content=icerik, **kw
        )

    def buton(r, metin, on_click, ikon=None, genis=False, ikincil=False, data=None, yukseklik=48):
        return ft.ElevatedButton(
            text=metin, icon=ikon, on_click=on_click, data=data, expand=genis, height=yukseklik,
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
                width=34, height=34, border_radius=12, alignment=ft.alignment.center,
                bgcolor=ft.colors.with_opacity(0.14, r["hdr"]),
                content=ft.Icon(ikon, color=r["hdr"], size=19),
            ),
            ft.Text(metin, size=16, color=r["txt"], weight=ft.FontWeight.W_700, expand=True),
        ]
        if sag is not None:
            satir.append(sag)
        return ft.Row(satir, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def sayfa_basligi(r, baslik, alt=None, geri=None):
        baslik_kolon = ft.Column([
            ft.Text(baslik, size=26, weight=ft.FontWeight.W_800, color=r["txt"]),
            *([ft.Text(alt, size=13, color=r["muted"])] if alt else []),
        ], spacing=2, expand=True)
        satir = []
        if geri:
            satir.append(ft.IconButton(ft.icons.ARROW_BACK_IOS_NEW, icon_color=r["hdr"], icon_size=20, on_click=geri))
        satir.append(baslik_kolon)
        return ft.Row(satir, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def gorev_satiri(r, metin, bitti, data, on_change):
        bg_renk = ft.colors.with_opacity(0.10, r["accent"]) if bitti else r["bg"]
        txt_renk = r["muted"] if bitti else r["txt"]
        decor = ft.TextDecoration.LINE_THROUGH if bitti else ft.TextDecoration.NONE
        return ft.Container(
            padding=ft.padding.only(left=4, right=12, top=2, bottom=2),
            border_radius=16, bgcolor=bg_renk,
            border=ft.border.all(1, ft.colors.with_opacity(0.5, r["border"])),
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
                                   bgcolor=ft.colors.with_opacity(0.2, r["muted"]), bar_height=12),
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
                expand=True, padding=ft.padding.symmetric(vertical=10), border_radius=12,
                alignment=ft.alignment.center, ink=True, on_click=tik(i),
                bgcolor=r["hdr"] if aktif else ft.colors.TRANSPARENT,
                content=ft.Text(etiket, size=12, weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER,
                                color=okunur_renk(r["hdr"]) if aktif else r["muted"]),
            ))
        return ft.Container(
            bgcolor=r["card_bg"], border_radius=16, padding=4, border=ft.border.all(1, r["border"]),
            content=ft.Row(ogeler, spacing=4),
        )

    def stat_kutusu(r, ikon, deger, etiket):
        return ft.Container(
            expand=True, padding=ft.padding.only(left=14, right=10, top=14, bottom=14), border_radius=20,
            bgcolor=r["card_bg"], border=ft.border.all(1, r["border"]),
            content=ft.Column([
                ft.Icon(ikon, color=r["accent"], size=22),
                ft.Text(deger, size=16, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text(etiket, size=11, color=r["muted"]),
            ], spacing=4),
        )

    # ==========================================
    # 6. ÖDÜL SİSTEMİ (ana sayfada gösterilir)
    # ==========================================
    def oduller_listesi(r):
        tyt = [n["toplam"] for n in DB["netler"] if n["sinav"] == "TYT"]
        max_tyt = max(tyt) if tyt else 0.0
        max_saat = max([sayi(g.get("saat")) for g in DB["gunluk"]] + [gun_sn(bugun_str()) / 3600.0])
        kayitli_gun = len({g["tarih"] for g in DB["gunluk"]})

        def basari(ad, aciklama, acik, odul):
            return ft.Container(
                padding=12, border_radius=16,
                bgcolor=ft.colors.with_opacity(0.12, r["accent"]) if acik else r["bg"],
                border=ft.border.all(2 if acik else 1, r["accent"] if acik else r["border"]),
                content=ft.Row([
                    ft.Text("🔓" if acik else "🔒", size=26),
                    ft.Column([
                        ft.Text(ad, size=14, weight=ft.FontWeight.W_700, color=r["hdr"] if acik else r["txt"]),
                        ft.Text(odul if acik else aciklama, size=12, color=r["accent"] if acik else r["muted"]),
                    ], spacing=2, expand=True),
                ], spacing=12),
            )

        ogeler = [
            basari("Demir İrade (8 Saat!)", f"Bir günde en az 8 saat çalış. (Rekorun: {max_saat:.1f} sa)",
                   max_saat >= 8.0, "Ödül: İlk fırsatta favori yemeğin benden!"),
            basari("İstikrar Zinciri (5 Gün!)", f"Gün sonunu 5 gün kaydet. (Mevcut: {kayitli_gun} gün)",
                   kayitli_gun >= 5, "Ödül: Ufak bir sürpriz hediye seni bekliyor!"),
            basari(f"Zirve Yürüyüşü ({HEDEF_TYT:g} Net!)", f"TYT'de {HEDEF_TYT:g} neti aş! (Rekorun: {max_tyt:g} net)",
                   max_tyt >= HEDEF_TYT, "Ödül: Birlikte geziyor ve tatlı yiyoruz! 🎉"),
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
                    padding=12, border_radius=16, bgcolor=r["bg"], border=ft.border.all(1, r["hdr"]),
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
        avatar = ft.Container(
            width=46, height=46, border_radius=23, alignment=ft.alignment.center, bgcolor=r["hdr"],
            content=ft.Text(isim[:1].upper(), size=20, weight=ft.FontWeight.BOLD, color=okunur_renk(r["hdr"])),
        )
        header = ft.Row([
            ft.Column([
                ft.Text(f"{bugun_ad}, {simdi.day} {AYLAR[simdi.month - 1]}", size=12, color=r["muted"]),
                ft.Text(f"Merhaba {isim}! 👋", size=24, weight=ft.FontWeight.W_800, color=r["txt"]),
            ], spacing=2, expand=True),
            avatar,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # --- Arda'dan canlı sinyal ---
        sinyal_banner = []
        if DB["sinyal"].get("aktif") and DB["sinyal"].get("mesaj"):
            sinyal_banner.append(ft.Container(
                padding=14, border_radius=18, bgcolor=ft.colors.with_opacity(0.15, r["hdr"]),
                border=ft.border.all(1, r["hdr"]),
                content=ft.Row([
                    ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE, color=r["hdr"]),
                    ft.Column([
                        ft.Text("Arda'dan Sinyal 🚨", size=12, color=r["hdr"], weight=ft.FontWeight.BOLD),
                        ft.Text(DB["sinyal"]["mesaj"], color=r["txt"], weight=ft.FontWeight.W_600),
                    ], spacing=2, expand=True),
                ]),
            ))

        # --- YKS geri sayım (hero kart) ---
        fark = YKS_TARIHI - simdi
        beyaz = "#FFFFFF"
        beyaz_sonuk = ft.colors.with_opacity(0.78, beyaz)

        def zaman_kutu(deger, etiket):
            return ft.Container(
                expand=True, padding=ft.padding.symmetric(vertical=10), border_radius=16,
                bgcolor=ft.colors.with_opacity(0.18, beyaz), alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Text(str(deger), size=26, weight=ft.FontWeight.W_800, color=beyaz),
                    ft.Text(etiket, size=11, color=beyaz_sonuk),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        if fark.total_seconds() > 0:
            kutular = ft.Row([
                zaman_kutu(fark.days, "Gün"), zaman_kutu(fark.seconds // 3600, "Saat"),
                zaman_kutu((fark.seconds % 3600) // 60, "Dakika"),
            ], spacing=8)
        else:
            kutular = ft.Text("Sınav Başladı! 🚀", size=24, weight=ft.FontWeight.BOLD, color=beyaz)
        hero = ft.Container(
            padding=20, border_radius=26,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                colors=[karistir(r["hdr"], "#000000", 0.12), karistir(r["hdr"], "#000000", 0.5)],
            ),
            shadow=ft.BoxShadow(blur_radius=20, color=ft.colors.with_opacity(0.25, r["hdr"]), offset=ft.Offset(0, 8)),
            content=ft.Column([
                ft.Row([ft.Icon(ft.icons.ROCKET_LAUNCH_ROUNDED, color=beyaz, size=20),
                        ft.Text(f"YKS {YKS_TARIHI.year}'ye kalan süre", size=14, color=beyaz_sonuk, weight=ft.FontWeight.W_600)]),
                kutular,
                ft.Text(f"🎓 {HEDEF_UNIVERSITE}", size=13, color=beyaz, weight=ft.FontWeight.W_600),
            ], spacing=14),
        )

        # --- İstatistik kutuları ---
        su = su_guncel()
        mevcut_su = int(su["bardak"])
        istatistikler = ft.Row([
            stat_kutusu(r, ft.icons.TODAY, sn_kisa(gun_sn(bugun_str())), "Bugün"),
            stat_kutusu(r, ft.icons.HOURGLASS_BOTTOM, sn_kisa(toplam_sn()), "Toplam"),
            stat_kutusu(r, ft.icons.WATER_DROP, f"{mevcut_su}/8", "Su"),
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
            bolum_basligi(r, ft.icons.EVENT_AVAILABLE, f"{bugun_ad} Programı",
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
            bolum_basligi(r, ft.icons.CHECKLIST, "Yapılacaklar"),
            ft.Row([todo_input, ft.IconButton(ft.icons.ADD_CIRCLE, icon_color=r["hdr"], icon_size=38, on_click=todo_ekle)]),
        ]
        if DB["todo"]:
            for i, t in enumerate(DB["todo"]):
                todo_kontrolleri.append(gorev_satiri(r, t["gorev"], t["bitti"], i, todo_tikla))
            if any(t["bitti"] for t in DB["todo"]):
                todo_kontrolleri.append(buton(r, "Bitenleri Temizle", todo_temizle, ikon=ft.icons.CLEANING_SERVICES,
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
            ft.Icon(ft.icons.WATER_DROP, size=28,
                    color=r["accent"] if i < mevcut_su else ft.colors.with_opacity(0.25, r["muted"]))
            for i in range(8)
        ], spacing=4, alignment=ft.MainAxisAlignment.CENTER)
        su_karti = kart(r, ft.Column([
            bolum_basligi(r, ft.icons.WATER_DROP, "Su Takibi",
                          ft.Text(f"{mevcut_su} bardak" + (f"  (+{mevcut_su - 8})" if mevcut_su > 8 else ""),
                                  size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
            bardak_ikonlari,
            ft.Row([
                buton(r, "Bir Bardak İçtim 🚰", su_ictim, genis=True),
                ft.IconButton(ft.icons.REMOVE_CIRCLE_OUTLINE, icon_color=r["muted"], on_click=su_geri, tooltip="Geri al"),
            ]),
        ], spacing=12))

        # --- Ödül sistemi ---
        odul_karti = kart(r, ft.Column([
            bolum_basligi(r, ft.icons.CARD_GIFTCARD, "Ödül Sistemi"),
            ft.Text("Kilitli başarıları aç, ödüllerini kazan 👀", size=12, color=r["muted"]),
            *oduller_listesi(r),
        ], spacing=10))

        # --- Günün sürpriz notu ---
        def not_oku(e):
            ui["surpriz"] = random.choice(SURPRIZ_NOTLARI)
            kutlama()
            yenile()

        surpriz_icerik = [
            ft.Text("Günün Notu ❤", size=16, weight=ft.FontWeight.W_700, color=r["hdr"]),
            ft.Text("Bu zorlu maratonda her anında yanındayım. Derin bir nefes al ve asla pes etme.", color=r["txt"], size=13),
            buton(r, "Sürpriz Notu Oku", not_oku, ikon=ft.icons.MAIL, genis=True, ikincil=True, yukseklik=42),
        ]
        if ui["surpriz"]:
            surpriz_icerik.append(ft.Container(
                padding=16, border_radius=14, bgcolor=r["bg"],
                border=ft.border.only(left=ft.BorderSide(5, r["accent"])),
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
            bgcolor=ft.colors.with_opacity(0.15, r["muted"]),
        )
        durum_yazi = {"bos": "Hazır", "calisiyor": "Çalışıyorsun 🔥", "durakladi": "Duraklatıldı ⏸"}[durum]
        daire = ft.Stack([
            ft.Container(content=zm["ring"], width=250, height=250, alignment=ft.alignment.center),
            ft.Container(
                width=250, height=250, alignment=ft.alignment.center,
                content=ft.Column([
                    zm["label"],
                    ft.Text(durum_yazi, size=13, color=r["muted"], weight=ft.FontWeight.W_600),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            ),
        ], width=250, height=250)

        if durum == "bos":
            butonlar = ft.Column([
                buton(r, "Başlat" if zm["mod"] == "krono" else "25 Dk Pomodoro Başlat", baslat,
                      ikon=ft.icons.PLAY_ARROW, genis=True, yukseklik=56),
            ])
        else:
            ana_btn = (buton(r, "Duraklat", duraklat, ikon=ft.icons.PAUSE, genis=True, ikincil=True, yukseklik=56)
                       if durum == "calisiyor" else
                       buton(r, "Devam Et", devam, ikon=ft.icons.PLAY_ARROW, genis=True, ikincil=True, yukseklik=56))
            butonlar = ft.Column([
                ft.Row([ana_btn, buton(r, "Bitir", bitir, ikon=ft.icons.STOP_CIRCLE, genis=True, yukseklik=56)], spacing=12),
                ft.TextButton("Kaydetmeden sıfırla", on_click=sifirla, style=ft.ButtonStyle(color=r["muted"])),
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
            ft.Container(content=daire, alignment=ft.alignment.center, padding=ft.padding.symmetric(vertical=10)),
            butonlar,
            bugun_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 9. NETLER, MÜFREDAT, EKSİKLER
    # ==========================================
    def net_grafigi(r, kayitlar):
        n = len(kayitlar)
        if n == 0:
            return ft.Text("Henüz deneme eklenmemiş.", color=r["muted"], italic=True)
        max_y = max(max(k["toplam"] for k in kayitlar) * 1.15, 10)
        aralik = max(5, int(-(-max_y / 4 // 5) * 5))
        seri = ft.LineChartData(
            data_points=[ft.LineChartDataPoint(i, k["toplam"], tooltip=f"{k['ad']}: {k['toplam']:.2f}") for i, k in enumerate(kayitlar)],
            stroke_width=3, color=r["hdr"], curved=True, stroke_cap_round=True,
            below_line_bgcolor=ft.colors.with_opacity(0.12, r["hdr"]),
        )
        etiketler = [
            ft.ChartAxisLabel(value=i, label=ft.Container(ft.Text(str(i + 1), size=11, color=r["muted"]), padding=ft.padding.only(top=6)))
            for i in range(n)
        ]
        grafik = ft.LineChart(
            data_series=[seri], min_y=0, max_y=max_y, min_x=-0.3, max_x=(n - 1) + 0.3, height=220,
            horizontal_grid_lines=ft.ChartGridLines(color=ft.colors.with_opacity(0.15, r["muted"]), width=1),
            left_axis=ft.ChartAxis(labels_size=38, labels_interval=aralik),
            bottom_axis=ft.ChartAxis(labels=etiketler, labels_size=28),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, r["muted"])),
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
            snack("Eklendi! ✅")
            yenile()

        form = kart(r, ft.Column([
            bolum_basligi(r, ft.icons.EDIT_NOTE, "Yeni Deneme Ekle"),
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
            bolum_basligi(r, ft.icons.INSIGHTS, "Analiz"),
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
                    width=96, padding=10, border_radius=14, bgcolor=r["bg"], border=ft.border.all(1, r["border"]),
                    content=ft.Column([
                        ft.Text(etiket, size=11, color=r["muted"]),
                        ft.Text(f"{son[anahtar]:g}", size=20, weight=ft.FontWeight.BOLD, color=r["txt"]),
                        ft.Text(f"{fark:+.2f}", size=12, weight=ft.FontWeight.BOLD, color=r["accent"] if fark >= 0 else ft.colors.RED_400),
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

        ders_dropdown = ft.Dropdown(
            label="Ders", value=ui["ders"], on_change=ders_degisti,
            options=[ft.dropdown.Option(d) for d in KONULAR], border_color=r["border"],
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
            bolum_basligi(r, ft.icons.TRACK_CHANGES, "Eksik Avcısı"),
            ft.Row([yeni, ft.IconButton(ft.icons.ADD_CIRCLE, icon_color=r["hdr"], icon_size=38, on_click=at)]),
        ]
        for i, k in enumerate(DB["kumbara"]):
            icerik.append(gorev_satiri(r, k["eksik"], k["bitti"], i, tikla))
        if not DB["kumbara"]:
            icerik.append(ft.Text("Eksik listesi şu an boş. Yanlış yaptığın konuları buraya at 🎯", color=r["muted"], italic=True, size=13))
        elif any(k["bitti"] for k in DB["kumbara"]):
            icerik.append(buton(r, "Halledilenleri Temizle", temizle, ikon=ft.icons.CLEANING_SERVICES, ikincil=True, genis=True, yukseklik=42))
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
                width=58, padding=ft.padding.symmetric(vertical=10), border_radius=16, ink=True, on_click=gun_sec(i),
                bgcolor=r["hdr"] if aktif else r["card_bg"],
                border=ft.border.all(2 if i == bugun_i else 1, r["accent"] if i == bugun_i and not aktif else r["border"]),
                content=ft.Column([
                    ft.Text(GUN_KISA[i], size=13, weight=ft.FontWeight.W_700,
                            color=okunur_renk(r["hdr"]) if aktif else r["txt"]),
                    ft.Text(f"{biten}/{toplam}", size=11,
                            color=ft.colors.with_opacity(0.8, okunur_renk(r["hdr"])) if aktif else r["muted"]),
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
                padding=ft.padding.only(left=4, right=4), border_radius=16,
                bgcolor=ft.colors.with_opacity(0.10, r["accent"]) if t["bitti"] else r["bg"],
                border=ft.border.all(1, ft.colors.with_opacity(0.5, r["border"])),
                content=ft.Row([
                    ft.Checkbox(value=t["bitti"], data=i, on_change=tikla, fill_color=r["accent"], check_color=r["card_bg"]),
                    ft.Text(t["gorev"], expand=True, size=14, weight=ft.FontWeight.W_600,
                            color=r["muted"] if t["bitti"] else r["txt"],
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if t["bitti"] else ft.TextDecoration.NONE)),
                    ft.IconButton(ft.icons.DELETE_OUTLINE, icon_color=ft.colors.RED_400, data=i, on_click=sil),
                ], spacing=0),
            ))
        if not satirlar:
            satirlar.append(ft.Text("Bu gün için görev yok. Yukarıdan ekleyebilirsin.", color=r["muted"], italic=True, size=13))

        biten = sum(1 for t in gorevler if t["bitti"])
        return ft.Column([
            sayfa_basligi(r, "Haftalık Plan", "Eklediklerin ana sayfana yansır"),
            ft.Row(cipler, scroll=ft.ScrollMode.AUTO, spacing=8),
            kart(r, ft.Column([
                bolum_basligi(r, ft.icons.EVENT_NOTE, g_ad,
                              ft.Text(f"{biten}/{len(gorevler)}", size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
                ft.Row([yeni_in, ft.IconButton(ft.icons.ADD_CIRCLE, icon_color=r["hdr"], icon_size=38, on_click=ekle)]),
                *satirlar,
            ], spacing=10)),
            buton(r, "Haftanın Tiklerini Sıfırla", haftayi_sifirla, ikon=ft.icons.REFRESH, ikincil=True, genis=True, yukseklik=44),
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
            bolum_basligi(r, ft.icons.NIGHTLIGHT_ROUND, "Bugünün Özeti"),
            bilgi(ft.icons.WB_SUNNY, "Derse başlama", baslama or "Kronometre başlatılmadı"),
            bilgi(ft.icons.TIMER, "Çalışma süresi", sn_metni(bugun_toplam)),
            bilgi(ft.icons.BEDTIME, "Bitiş saati", f"Kaydedince ({datetime.now().strftime('%H:%M')})"),
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
                expand=True, padding=ft.padding.symmetric(vertical=12), border_radius=14, ink=True,
                alignment=ft.alignment.center, on_click=puan_sec(i),
                bgcolor=ft.colors.with_opacity(0.18, r["hdr"]) if secili else r["bg"],
                border=ft.border.all(2 if secili else 1, r["hdr"] if secili else r["border"]),
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
            snack("Gün kaydedildi. İyi uykular! 💖")
            kutlama()
            yenile()

        performans_karti = kart(r, ft.Column([
            bolum_basligi(r, ft.icons.EMOJI_EMOTIONS, "Bugünkü performansın nasıldı?"),
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
                padding=12, border_radius=16, bgcolor=r["bg"], border=ft.border.all(1, r["border"]),
                content=ft.Column(govde, spacing=4)))
        if not gecmis:
            gecmis.append(ft.Text("Henüz kayıtlı gün yok. İlk günü kaydetmeye ne dersin?", color=r["muted"], italic=True, size=13))

        return ft.Column([
            ozet, performans_karti,
            kart(r, ft.Column([bolum_basligi(r, ft.icons.BAR_CHART, "Son 7 Gün (saat)"), haftalik_bar(r)], spacing=12)),
            kart(r, ft.Column([bolum_basligi(r, ft.icons.HISTORY, "Gün Gün Kayıtlar"), *gecmis], spacing=10)),
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
                    sonuc.controls.append(ft.Text("⚠️ Sistem şu an yanıt veremedi. Detaylar:", color=ft.colors.RED_400, weight=ft.FontWeight.BOLD))
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
                width=78, height=78, border_radius=16, bgcolor=r["bg"], border=ft.border.all(2, r["border"]),
                alignment=ft.alignment.center, data=i, on_click=tikla, ink=True,
                content=ft.Text(oyun["xox"][i] or "⬜", size=32),
            ))
        sonuc.value = sonuc_yazisi()
        grid = ft.Column([
            ft.Row(hucreler[0:3], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(hucreler[3:6], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(hucreler[6:9], alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=8)
        return [kart(r, ft.Column([
            bolum_basligi(r, ft.icons.GRID_3X3, "Arda-Bot'a Karşı XOX"),
            grid, sonuc,
            buton(r, "Oyunu Sıfırla 🔄", sifirla, genis=True, ikincil=True),
        ], spacing=14))]

    def youtube_olustur(r):
        def ac(url):
            return lambda e: page.launch_url(url)

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
            return lambda e: page.launch_url(url)

        def liste_karti(emoji, ad, aciklama, url):
            return kart(r, ft.Row([
                ft.Text(emoji, size=30),
                ft.Column([ft.Text(ad, weight=ft.FontWeight.W_700, color=r["txt"]),
                           ft.Text(aciklama, size=12, color=r["muted"])], spacing=2, expand=True),
                ft.IconButton(ft.icons.OPEN_IN_NEW, icon_color=r["hdr"], on_click=ac(url)),
            ], spacing=12), padding=14)

        return ft.Column([
            kart(r, ft.Column([
                ft.Icon(ft.icons.HEADPHONES, size=56, color=r["hdr"]),
                ft.Text("Ders Çalışma Listesi", size=19, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text("Odak listen Spotify'da seni bekliyor. Kulaklığını tak ve başla 🎶", color=r["muted"],
                        text_align=ft.TextAlign.CENTER, size=13),
                buton(r, "Spotify'da Aç", ac(SPOTIFY_URL), ikon=ft.icons.OPEN_IN_NEW, genis=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)),
            ft.Text("Diğer odak sesleri", size=13, color=r["muted"], weight=ft.FontWeight.W_600),
            liste_karti("🎹", "Lofi / Çalışma Müziği", "YouTube'da ara", "https://www.youtube.com/results?search_query=lofi+study+music"),
            liste_karti("🌧️", "Yağmur Sesi", "YouTube'da ara", "https://www.youtube.com/results?search_query=rain+sounds+for+studying"),
            liste_karti("🌊", "Beyaz Gürültü", "YouTube'da ara", "https://www.youtube.com/results?search_query=white+noise+focus"),
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    # ==========================================
    # 13. ARDA'NIN PANELİ
    # ==========================================
    def panel_sayfasi_olustur(r):
        if not ui["panel_giris"]:
            sifre = girdi(r, label="Panel Şifresi", password=True, can_reveal_password=True, keyboard_type=ft.KeyboardType.NUMBER)
            hata = ft.Text(ui["panel_hata"], color=ft.colors.RED_400)
            def giris(e):
                if (sifre.value or "") == PANEL_SIFRESI:
                    ui["panel_giris"] = True; ui["panel_hata"] = ""; snack("Giriş Başarılı! ✅")
                else: ui["panel_hata"] = "Şifre yanlış!"
                yenile()
            sifre.on_submit = giris
            return ft.Column([kart(r, ft.Column([bolum_basligi(r, ft.icons.LOCK, "Arda'nın Yönetici Paneli"), sifre, hata, buton(r, "Giriş", giris, genis=True)], spacing=12))], expand=True, scroll=ft.ScrollMode.AUTO)

        # Tüm Öğrencilerin Verilerini Çek
        tum_veriler = []
        try:
            users = bulut_oku() or {}
            for uname, udata in users.items():
                udata = udata if isinstance(udata, dict) else {}
                loglar = listeye(udata.get("gunluk"))
                son_log = loglar[-1] if loglar else None
                if son_log:
                    p = int(son_log.get("performans", 0) or 0)
                    emoji = PERFORMANS[p - 1][0] if 1 <= p <= 5 else "-"
                    satir1 = f"Son Kayıt: {son_log.get('tarih', '-')} | Süre: {son_log.get('saat', 0)} saat"
                    satir2 = f"Duygu: {emoji} | Not: {(son_log.get('gunluk') or '-')[:50]}"
                else:
                    satir1, satir2 = "Henüz gün kaydı yok.", ""
                tum_veriler.append(kart(r, ft.Column([
                    ft.Text(f"👤 Öğrenci: {uname.upper()}", weight=ft.FontWeight.BOLD, color=r["hdr"], size=16),
                    ft.Text(satir1, color=r["txt"]),
                    ft.Text(satir2, color=r["muted"], size=12),
                ], spacing=4)))
            if not tum_veriler:
                tum_veriler.append(ft.Text("Henüz kayıtlı öğrenci yok.", color=r["muted"], italic=True))
        except Exception as ex:
            tum_veriler.append(ft.Text(f"Buluttan veriler çekilemedi: {ex}", color=ft.colors.RED_400))

        veri_tab = [bolum_basligi(r, ft.icons.GROUPS, "Tüm Öğrenci Kayıtları"), *tum_veriler]

        def degisti(i): 
            ui["panel_tab"] = i
            yenile()
            
        sekmeler = [veri_tab]
        return ft.Column([segment(r, ["📈 Öğrenci Verileri"], ui["panel_tab"], degisti), *sekmeler[ui["panel_tab"]], ft.Container(height=24)], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)
        # --- Sinyal ---
        sinyal_in = girdi(r, "Örn: Mola verme zamanı! ☕", label="Mesaj")

        def sinyal_gonder(e):
            m = (sinyal_in.value or "").strip()
            if m:
                DB["sinyal"] = {"aktif": True, "mesaj": m}
                kaydet("sinyal")
                snack("Sinyal iletildi! ✨")

        def sinyal_kapat(e):
            DB["sinyal"] = {"aktif": False, "mesaj": ""}
            kaydet("sinyal")
            snack("Sinyal kapatıldı.")

        sinyal_tab = [kart(r, ft.Column([
            bolum_basligi(r, ft.icons.NOTIFICATIONS_ACTIVE, "Canlı Sinyal Gönder"),
            sinyal_in,
            buton(r, "Sinyali Gönder 🚀", sinyal_gonder, genis=True),
            buton(r, "Sinyali Kapat 🛑", sinyal_kapat, genis=True, ikincil=True),
        ], spacing=12))]

        # --- Görev ver ---
        gorev_in = girdi(r, label="Yapılacak görev")
        odul_in = girdi(r, label="Tamamlarsa ödül (Örn: Kahve benden!)")

        def gorev_gonder(e):
            g = (gorev_in.value or "").strip()
            if g:
                DB["ozel_gorevler"].append({"gorev": g, "odul": (odul_in.value or "").strip(), "durum": "Bekliyor"})
                kaydet("ozel_gorevler")
                snack("Görev ana sayfadaki Ödül Sistemi'ne eklendi!")
                yenile()

        gorev_liste = [ft.Text(f"{'✅' if g['durum'] == 'Tamamlandı' else '⏳'} {g['gorev']} → {g['odul']}", size=12, color=r["muted"])
                       for g in DB["ozel_gorevler"]]
        gorev_tab = [kart(r, ft.Column([
            bolum_basligi(r, ft.icons.ASSIGNMENT, "Özel Görev Tanımla"),
            gorev_in, odul_in, buton(r, "Gönder", gorev_gonder, genis=True), *gorev_liste,
        ], spacing=12))]

        # --- Veri ---
        veri_ogeleri = [bolum_basligi(r, ft.icons.INSIGHTS, "Performans ve Günlük")]
        if DB["gunluk"]:
            veri_ogeleri.append(ft.Text("Son 7 gün (saat)", color=r["muted"], size=12))
            veri_ogeleri.append(haftalik_bar(r))
            veri_ogeleri.append(ft.Divider(color=r["border"]))
            for k in reversed(DB["gunluk"]):
                p = int(k.get("performans", 0) or 0)
                emoji = PERFORMANS[p - 1][0] if 1 <= p <= 5 else "📝"
                saat_txt = sn_metni(k["sn"]) if "sn" in k else f"{sayi(k.get('saat')):g} sa"
                govde = [
                    ft.Row([ft.Text(k["tarih"], size=12, color=r["hdr"], weight=ft.FontWeight.BOLD, expand=True), ft.Text(emoji, size=20)]),
                    ft.Text(f"{k.get('baslama', '-')} → {k.get('bitis', '-')}  |  {saat_txt}", size=12, color=r["muted"]),
                ]
                if k.get("gunluk"):
                    govde.append(ft.Text(k["gunluk"], color=r["txt"], size=13))
                veri_ogeleri.append(ft.Container(
                    padding=12, border_radius=12, bgcolor=r["bg"], border=ft.border.all(1, r["border"]),
                    content=ft.Column(govde, spacing=4)))
        else:
            veri_ogeleri.append(ft.Text("Henüz gün sonu verisi girilmemiş.", color=r["muted"], italic=True))
        veri_tab = [kart(r, ft.Column(veri_ogeleri, spacing=10))]

        # --- Ayar ---
        onay_in = girdi(r, label="Silmek için büyük harfle SİL yaz")

        def sifirla(e):
            if (onay_in.value or "") == "SİL":
                for anahtar in ("su", "todo", "gunluk", "konu_bitti", "netler", "ozel_gorevler", "calisma_sn", "calisma_log", "gun"):
                    DB[anahtar] = copy.deepcopy(VARSAYILAN_VERI[anahtar])
                    kaydet(anahtar)
                zm.update({"durum": "bos", "birikmis": 0.0, "t0": None})
                snack("Tüm veriler sıfırlandı.")
                kutlama()
                yenile()
            else:
                snack("Onaylamak için kutucuğa tam olarak SİL yazmalısın.")

        ayar_tab = [kart(r, ft.Column([
            ft.Text("⚠️ Tehlikeli Bölge", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.RED_400),
            ft.Text("Bu işlem geri alınamaz! Su, görev, konu, net, gün sonu ve çalışma verileri silinir. (Hesap ve tema silinmez.)",
                    color=r["txt"], size=13),
            onay_in,
            ft.ElevatedButton("Her Şeyi Sil 🔴", on_click=sifirla, bgcolor=ft.colors.RED_400, color="#FFFFFF", height=46,
                              style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14))),
        ], spacing=12))]

        def degisti(i):
            ui["panel_tab"] = i
            yenile()
        sekmeler = [sinyal_tab, gorev_tab, veri_tab, ayar_tab]
        return ft.Column([
            segment(r, ["🚨 Sinyal", "📝 Görev", "📈 Veri", "⚙️ Ayar"], ui["panel_tab"], degisti),
            *sekmeler[ui["panel_tab"]],
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 14. GÖRÜNÜM (TEMA)
    # ==========================================
    def tema_sayfasi_olustur(r):
        kartlar = []
        for ad, t in TEMA_RENKLERI.items():
            secili = ad == DB["tema"]
            kartlar.append(ft.Container(
                padding=14, border_radius=18, ink=True, on_click=lambda e, a=ad: tema_uygula(a),
                bgcolor=r["card_bg"], border=ft.border.all(2 if secili else 1, r["hdr"] if secili else r["border"]),
                content=ft.Row([
                    ft.Stack([
                        ft.Container(width=40, height=40, border_radius=20, bgcolor=t["bg"], border=ft.border.all(1, t["border"])),
                        ft.Container(width=22, height=22, border_radius=11, bgcolor=t["hdr"], left=9, top=9),
                    ], width=40, height=40),
                    ft.Text(ad, size=15, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    ft.Icon(ft.icons.CHECK_CIRCLE if secili else ft.icons.CIRCLE_OUTLINED,
                            color=r["hdr"] if secili else r["muted"]),
                ], spacing=14),
            ))
        return ft.Column([
            ft.Text("Seçtiğin tema kaydedilir, uygulamayı kapatıp açsan da değişmez.", size=12, color=r["muted"]),
            *kartlar, ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    # ==========================================
    # 15. DİĞER MENÜSÜ
    # ==========================================
    ALT_SAYFALAR = {
        "gunsonu": (ft.icons.NIGHTLIGHT_ROUND, "Gün Sonu", "Süre, performans ve günlük kayıtların", gun_sonu_sayfasi_olustur),
        "asistan": (ft.icons.SMART_TOY, "Asistan", "Sorularına Arda'dan cevap", asistan_sayfasi_olustur),
        "eglence": (ft.icons.SPORTS_ESPORTS, "Eğlence & Mola", "XOX ve YouTube kısayolları", eglence_sayfasi_olustur),
        "muzik": (ft.icons.HEADPHONES, "Odak Müzik", "Spotify ve odak sesleri", muzik_sayfasi_olustur),
        "tema": (ft.icons.PALETTE, "Görünüm", "Tema seç", tema_sayfasi_olustur),
        "panel": (ft.icons.ADMIN_PANEL_SETTINGS, "Arda'nın Paneli", "Sinyal, görev ve veriler", panel_sayfasi_olustur),
    }

    def cikis_yap(e):
        # çıkmadan önce bekleyen değişiklikleri buluta göndermeyi dene
        with kilit:
            bulut["bekleyen"].update(BULUT_ANAHTARLARI if not oturum["senkron"] else [])
        bulut_gonder()
        with kilit:
            oturum["kullanici"] = ""
            oturum["senkron"] = True
            bulut["bekleyen"].clear()
            tema = DB["tema"]
            DB.clear()
            DB.update(db_hazirla({"tema": tema}))
            zm.update({"durum": "bos", "birikmis": 0.0, "t0": None})
            yerel_yaz()
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
                    border=ft.border.all(1, r["hdr"] if vurgulu else r["border"]),
                    content=ft.Row([
                        ft.Container(width=44, height=44, border_radius=14, alignment=ft.alignment.center,
                                     bgcolor=ft.colors.with_opacity(0.22, on) if vurgulu else ft.colors.with_opacity(0.14, r["hdr"]),
                                     content=ft.Icon(ikon, color=on if vurgulu else r["hdr"])),
                        ft.Column([
                            ft.Text(ad, size=15, weight=ft.FontWeight.W_700, color=on if vurgulu else r["txt"]),
                            ft.Text(aciklama, size=12, color=ft.colors.with_opacity(0.85, on) if vurgulu else r["muted"]),
                        ], spacing=2, expand=True),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, color=on if vurgulu else r["muted"]),
                    ], spacing=14),
                )

            satirlar = [satir(k, ikon, ad, ac_, ac(k), vurgulu=(k == "gunsonu"))
                        for k, (ikon, ad, ac_, _) in ALT_SAYFALAR.items()]
            satirlar.append(satir("cikis", ft.icons.LOGOUT, "Çıkış Yap",
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
        hata = ft.Text(ui["hata"], color=ft.colors.RED_400, size=13)
        kullanici = girdi(r, label="Kullanıcı adı (Boşluksuz)", prefix_icon=ft.icons.PERSON)
        sifre = girdi(r, label="Şifre", password=True, can_reveal_password=True, prefix_icon=ft.icons.LOCK)
        
        def hata_goster(m): 
            ui["hata"] = m
            giris_ac()

        def oturum_ac(ad, veri):
            with kilit:
                DB.clear()
                DB.update(veri)
                oturum["kullanici"] = ad
                oturum["senkron"] = False
                bulut["bekleyen"].update(BULUT_ANAHTARLARI)
                yerel_yaz()
            bulut["olay"].set()
            ui["hata"] = ""
            tema_uygula(DB["tema"])
            uygulama_ac()

        def kayit_ol(e):
            ad = (kullanici.value or "").strip().lower()
            if len(ad) < 3 or not ad.replace("_", "").isalnum():
                return hata_goster("Kullanıcı adı en az 3 karakter olmalı; sadece harf, rakam ve _ kullan.")
            if len(sifre.value or "") < 4:
                return hata_goster("Şifre en az 4 karakter olmalı.")
            try:
                if bulut_oku(ad) is not None:
                    return hata_goster("Bu kullanıcı adı alınmış!")
            except Exception as ex:
                return hata_goster(f"Buluta bağlanılamadı: {ex}")
            tuz = os.urandom(8).hex()
            yeni_db = db_hazirla({"tema": DB["tema"]})
            yeni_db["hesap"] = {"kullanici": ad, "tuz": tuz, "ozet": sifre_ozeti(sifre.value, tuz)}
            oturum_ac(ad, yeni_db)

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
            form = [kullanici, sifre, hata, buton(r, "Bulutta Hesap Oluştur", kayit_ol, genis=True, yukseklik=52), ft.TextButton("Zaten hesabım var", on_click=lambda e: (ui.update({"giris_mod": "giris", "hata": ""}), giris_ac()))]
        else:
            form = [kullanici, sifre, hata, buton(r, "Giriş Yap", giris_yap, genis=True, yukseklik=52), ft.TextButton("Yeni hesap aç", on_click=lambda e: (ui.update({"giris_mod": "kayit", "hata": ""}), giris_ac()))]

        logo = ft.Container(width=88, height=88, border_radius=28, alignment=ft.alignment.center, gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[karistir(r["hdr"], "#000000", 0.1), karistir(r["hdr"], "#000000", 0.5)]), content=ft.Text("🚀", size=44))
        return ft.Column([ft.Container(height=30), ft.Row([logo], alignment=ft.MainAxisAlignment.CENTER), ft.Text("YKS İstasyonu (Bulut)", size=28, weight=ft.FontWeight.W_800, color=r["txt"], text_align=ft.TextAlign.CENTER), kart(r, ft.Column(form, spacing=12))], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ==========================================
    # 17. ANA İSKELET, NAVİGASYON, TEMA
    # ==========================================
    kok = ft.Container(expand=True, padding=ft.padding.only(left=16, right=16, top=10, bottom=0))
    ui_kapsayici = ft.Container(expand=True)

    def icerik_guncelle(r):
        s = ui["sekme"]
        if s == 0:
            ui_kapsayici.content = ana_sayfa_olustur(r)
        elif s == 1:
            ui_kapsayici.content = calisma_sayfasi_olustur(r)
        elif s == 2:
            ui_kapsayici.content = net_sayfasi_olustur(r)
        elif s == 3:
            ui_kapsayici.content = plan_sayfasi_olustur(r)
        else:
            ui_kapsayici.content = diger_sayfasi_olustur(r)
        duzelt(ui_kapsayici.content)

    def nav_degisti(e):
        ui["sekme"] = e.control.selected_index
        ui["alt"] = None
        ui["panel_giris"] = False
        ui["surpriz"] = ""
        yenile()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0, on_change=nav_degisti, height=68,
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.HOME_OUTLINED, selected_icon=ft.icons.HOME, label="Ana Sayfa"),
            ft.NavigationBarDestination(icon=ft.icons.TIMER_OUTLINED, selected_icon=ft.icons.TIMER, label="Çalış"),
            ft.NavigationBarDestination(icon=ft.icons.SHOW_CHART_OUTLINED, selected_icon=ft.icons.SHOW_CHART, label="Netler"),
            ft.NavigationBarDestination(icon=ft.icons.CALENDAR_MONTH_OUTLINED, selected_icon=ft.icons.CALENDAR_MONTH, label="Plan"),
            ft.NavigationBarDestination(icon=ft.icons.GRID_VIEW_OUTLINED, selected_icon=ft.icons.GRID_VIEW, label="Daha Fazla"),
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
        icerik_guncelle(renk())
        kok.content = ui_kapsayici
        page.update()

    def tema_uygula(isim):
        DB["tema"] = isim
        kaydet("tema")
        r = TEMA_RENKLERI[isim]
        page.bgcolor = r["bg"]
        page.theme_mode = r["mode"]
        page.theme = ft.Theme(color_scheme_seed=r["hdr"])
        page.dark_theme = ft.Theme(color_scheme_seed=r["hdr"])
        page.navigation_bar.bgcolor = r["card_bg"]
        page.navigation_bar.indicator_color = ft.colors.with_opacity(0.25, r["hdr"])
        if kok.content is ui_kapsayici:
            icerik_guncelle(r)
        elif kok.content is not None:
            kok.content = duzelt(giris_ekrani_olustur(r))
        page.update()

    page.add(ft.SafeArea(content=kok, expand=True))
    tema_uygula(DB["tema"])
    if oturum["kullanici"] and DB["hesap"]:
        uygulama_ac()

        def buluttan_esitle():
            """Açılışta: telefonda gönderilmemiş değişiklik varsa buluta yolla, yoksa buluttaki güncel veriyi al."""
            try:
                if not oturum["senkron"]:
                    with kilit:
                        bulut["bekleyen"].update(BULUT_ANAHTARLARI)
                    bulut_gonder()
                    return
                ham = bulut_oku(oturum["kullanici"])
                if ham is None:
                    return
                yeni = db_hazirla(ham)
                with kilit:
                    DB.clear()
                    DB.update(yeni)
                    yerel_yaz()
                tema_uygula(DB["tema"])
            except Exception as ex:
                print("Bulut eşitleme hatası:", ex)

        threading.Thread(target=buluttan_esitle, daemon=True).start()
    else:
        giris_ac()


ft.app(target=main)
