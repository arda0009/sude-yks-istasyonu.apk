import flet as ft
from datetime import datetime, timedelta, timezone

# Firebase Realtime Database adresi
FIREBASE_URL = "https://yks-istasyonu-default-rtdb.firebaseio.com"
NTFY_SUNUCU = "https://ntfy.sh"
ISTANBUL_TZ = timezone(timedelta(hours=3))

# ==========================================
# 0. AYARLAR (BURAYI KENDİNE GÖRE DÜZENLE)
# ==========================================
HEDEF_UNIVERSITE = "Güneş Üniversitesi Tıp Fakültesi"
HEDEF_TYT = 105.0
HEDEF_AYT = 64.0
YKS_TARIHI = datetime(2027, 6, 19, 10, 15)
PANEL_SIFRESI = "sudesun123"
SPOTIFY_URL = "https://open.spotify.com/playlist/0zHr4z4SfUeKZOXv3rxVIV"

GROQ_API_KEY = ""
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-3.8-flash"

KIRMIZI = "#EF5350"
YESIL = "#2ECC71"
TURUNCU = "#FF9800"
SEFFAF = "#00000000"

# ==========================================
# 1. TEMA VE VERİTABANI ŞEMASI
# ==========================================
TEMA_RENKLERI = {
    "Gündüz Bahçesi 🌻": {"bg": "#FDF7F9", "card_bg": "#FFFFFF", "border": "#F5D9E4", "hdr": "#D96B93", "accent": "#F49EC0", "muted": "#9197A1", "gul_renk": "#F8C8DA", "gul_op": 0.45, "txt": "#464952", "mode": ft.ThemeMode.LIGHT},
    "Gece Moru 🌙": {"bg": "#181722", "card_bg": "#232131", "border": "#393354", "hdr": "#B993F4", "accent": "#DEC7FF", "muted": "#969DB0", "gul_renk": "#362852", "gul_op": 0.35, "txt": "#E8EBF2", "mode": ft.ThemeMode.DARK},
    "Doğa Yeşili 🌿": {"bg": "#F6FAF7", "card_bg": "#FFFFFF", "border": "#CBE5D4", "hdr": "#4E8D6E", "accent": "#74BA97", "muted": "#7C8A83", "gul_renk": "#C4E2CF", "gul_op": 0.45, "txt": "#34463C", "mode": ft.ThemeMode.LIGHT},
    "Coffee Latte ☕": {"bg": "#FBF7F2", "card_bg": "#FFFFFF", "border": "#E6D5C6", "hdr": "#8D6B53", "accent": "#B9967B", "muted": "#9B9690", "gul_renk": "#E4D3C3", "gul_op": 0.45, "txt": "#4B3B2E", "mode": ft.ThemeMode.LIGHT},
    "Kozmik Galaksi 🌌": {"bg": "#13101E", "card_bg": "#1D192B", "border": "#2F2846", "hdr": "#A78BFA", "accent": "#7DD3FC", "muted": "#948FA8", "gul_renk": "#232E5C", "gul_op": 0.3, "txt": "#F1F3F9", "mode": ft.ThemeMode.DARK},
    "Sakura Pembe 🌸": {"bg": "#FFF6F8", "card_bg": "#FFFFFF", "border": "#FAD4DE", "hdr": "#E86C8D", "accent": "#F498B1", "muted": "#9A9FA6", "gul_renk": "#FAD2DC", "gul_op": 0.5, "txt": "#52323B", "mode": ft.ThemeMode.LIGHT},
}
VARSAYILAN_TEMA = "Sakura Pembe 🌸"

HAFTALIK_PLAN = {
    "Pazartesi": [{"gorev": "Matematik (Türev) - 2 Saat", "bitti": False}, {"gorev": "Paragraf - 30 Soru", "bitti": False}],
    "Salı": [{"gorev": "Fizik (Elektrik) - 1.5 Saat", "bitti": False}, {"gorev": "Geometri - 40 Soru", "bitti": False}],
    "Çarşamba": [{"gorev": "Türkçe (Dil Bilgisi) - 1 Saat", "bitti": False}, {"gorev": "Biyoloji (Hücre) - 1 Saat", "bitti": False}],
    "Perşembe": [{"gorev": "Kimya (Organik) - 2 Saat", "bitti": False}, {"gorev": "Problem - 20 Soru", "bitti": False}],
    "Cuma": [{"gorev": "TYT Genel Denemesi", "bitti": False}, {"gorev": "Deneme Analizi", "bitti": False}],
    "Cumartesi": [{"gorev": "AYT Matematik", "bitti": False}, {"gorev": "Dinlenme", "bitti": False}],
    "Pazar": [{"gorev": "Haftalık Tekrar", "bitti": False}, {"gorev": "Kelime Ezberi", "bitti": False}],
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

VARSAYILAN_AKTIF_SAYAC = {
    "mod": "krono",       # "krono" | "pomo"
    "durum": "bos",       # "bos" | "calisiyor" | "durakladi"
    "baslangic_ts": 0.0,  # Kronometrenin son başlatıldığı/devam ettiği zaman (unix timestamp)
    "birikmis_sn": 0,     # Duraklatmalardan önce birikmiş saniye
    "son_kayit_sn": 0,    # Bu oturumdan DB["calisma_sn"]'ye halihazırda eklenmiş saniye
    "tarih": "",          # Sayacın başladığı gün ("gg.aa.yyyy")
    "faz": "odak",        # "odak" | "mola"
    "odak_dk": 25,
    "mola_dk": 5,
    "hedef_sn": 25 * 60,
    "tur": 1,
    "ders": "Genel Çalışma",
}

VARSAYILAN_VERI = {
    "tema": VARSAYILAN_TEMA,
    "hesap": None,         # {"kullanici", "tuz", "ozet"}
    "oturum": False,       # giriş yapılmış mı (uygulama kapanınca hatırlanır)
    "plan": HAFTALIK_PLAN,
    "todo": [],            # {"gorev", "bitti"}
    "su": {"tarih": "", "bardak": 0},
    "netler": [],          # {"ad", "tarih", "sinav", "dersler", "toplam"}
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
    "aktif_sayac": VARSAYILAN_AKTIF_SAYAC,  # Ekran kapansa bile başlangıç zamanını hafızada tutan kalıcı sayaç
    "evcil": {},           # Cihazlar arası (telefon + tablet) bulut senkronlu evcil hayvan ve altın verisi
    "evcil_ozel_gorsel": {},
    "plan_gecmis": [],     # Haftalık planda daha önce eklenen görevler (otomatik tamamlama için)
}

BULUT_ANAHTARLARI = [k for k in VARSAYILAN_VERI if k != "oturum"]
TARIHLI_ANAHTARLAR = ("calisma_sn", "calisma_log")
LISTE_ANAHTARLARI = ("todo", "netler", "konu_bitti", "kumbara", "gunluk", "ozel_gorevler", "acilan_oduller", "plan_gecmis")
