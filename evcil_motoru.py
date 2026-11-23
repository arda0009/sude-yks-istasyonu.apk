import os
import re
import time
import random
import sqlite3
import threading
from datetime import datetime, date, timedelta
from ayarlar import ISTANBUL_TZ, YKS_TARIHI
from bilesenler import sayi, listeye

# ==========================================
# 2D. SANAL EVCİL HAYVAN & ÇALIŞMA YOLDAŞI EKOSİSTEMİ
#     (SQLite + Bulut Senkronizasyonu + Durum Makinesi)
# ==========================================
EVCIL_SQL_SEMA = """
CREATE TABLE IF NOT EXISTS pet_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    isim TEXT NOT NULL DEFAULT 'Pofuduk',
    evrim_asamasi TEXT NOT NULL DEFAULT 'BEBEK',
    xp INTEGER NOT NULL DEFAULT 100,
    seviye INTEGER NOT NULL DEFAULT 1,
    yildiz INTEGER NOT NULL DEFAULT 60,
    karbonhidrat REAL NOT NULL DEFAULT 75.0,
    protein REAL NOT NULL DEFAULT 75.0,
    vitamin REAL NOT NULL DEFAULT 75.0,
    mutluluk REAL NOT NULL DEFAULT 85.0,
    durum TEXT NOT NULL DEFAULT 'IDLE',
    secili_sapka TEXT NOT NULL DEFAULT '',
    secili_gozluk TEXT NOT NULL DEFAULT '',
    last_active_timestamp REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS subject_study_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih TEXT NOT NULL,
    kategori TEXT NOT NULL,
    ders TEXT NOT NULL,
    soru_sayisi INTEGER NOT NULL DEFAULT 0,
    dakika INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_items (
    item_id TEXT PRIMARY KEY,
    kategori TEXT NOT NULL,
    ad TEXT NOT NULL,
    emoji TEXT NOT NULL,
    aciklama TEXT NOT NULL,
    fiyat INTEGER NOT NULL DEFAULT 0,
    unlocked INTEGER NOT NULL DEFAULT 0,
    equipped INTEGER NOT NULL DEFAULT 0,
    unlocked_at REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS pet_diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih TEXT NOT NULL UNIQUE,
    baslik TEXT NOT NULL,
    icerik TEXT NOT NULL,
    calisma_dk INTEGER NOT NULL DEFAULT 0,
    cozulen_soru INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS postman_letters (
    letter_id TEXT PRIMARY KEY,
    baslik TEXT NOT NULL,
    kosul_aciklama TEXT NOT NULL,
    gizli_mesaj TEXT NOT NULL,
    unlocked INTEGER NOT NULL DEFAULT 0,
    read_status INTEGER NOT NULL DEFAULT 0,
    unlocked_at REAL NOT NULL DEFAULT 0.0
);
"""

EVCIL_DURUMLAR = ("IDLE", "EATING", "STUDYING", "SLEEPING", "SAD", "HUNGRY", "HAPPY_JUMP", "TALKING")
EVCIL_EVRIMLER = (
    ("BEBEK", "🐾 1. Evre: Minik Bebek Kedi", 0),
    ("KUCUK", "🐱 2. Evre: Küçük Kedi", 6000),
    ("GENC", "😺 3. Evre: Genç Bilgin Kedi", 18000),
    ("YETISKIN", "🎓 4. Evre: Mezun Şampiyon Kedi", 45000),
)

# Seviye Kilidi Olan Zengin Yemek Sistemi
# (Seviye 1'de Su, Süt ve Mama açıktır; seviye atladıkça Karbonhidrat, Protein, Vitamin ve Enerji yemekleri açılır)
EVCIL_YEMEK_KATALOGU = [
    {"item_id": "su", "ad": "Taze Su", "emoji": "💧", "min_seviye": 1, "fiyat": 5,
     "karb": 6.0, "prot": 0.0, "vit": 8.0, "mut": 6.0,
     "aciklama": "Seviye 1 • Ferahlatıcı taze su (+6 Karb, +8 Vit, +6 Neşe)"},
    {"item_id": "sut", "ad": "Ilık Süt", "emoji": "🥛", "min_seviye": 1, "fiyat": 10,
     "karb": 8.0, "prot": 12.0, "vit": 6.0, "mut": 8.0,
     "aciklama": "Seviye 1 • Kalsiyum ve protein deposu ılık süt (+12 Prot, +8 Karb, +8 Neşe)"},
    {"item_id": "mama", "ad": "Kedi Maması", "emoji": "🥣", "min_seviye": 1, "fiyat": 15,
     "karb": 14.0, "prot": 14.0, "vit": 10.0, "mut": 10.0,
     "aciklama": "Seviye 1 • Dengeli günlük kedi maması (+14 Karb, +14 Prot, +10 Vit)"},
    {"item_id": "simit_peynir", "ad": "Çıtır Simit & Peynir", "emoji": "🥯", "min_seviye": 2, "fiyat": 20,
     "karb": 26.0, "prot": 12.0, "vit": 6.0, "mut": 12.0,
     "aciklama": "Seviye 2 • Sabah etüdü karbonhidrat ve enerji deposu (+26 Karb, +12 Prot)"},
    {"item_id": "portakal_suyu", "ad": "Taze Sıkma Portakal & Elma", "emoji": "🍊", "min_seviye": 2, "fiyat": 22,
     "karb": 12.0, "prot": 2.0, "vit": 28.0, "mut": 14.0,
     "aciklama": "Seviye 2 • C vitamini ve bağışıklık takviyesi (+28 Vit, +12 Karb)"},
    {"item_id": "somon", "ad": "Izgara Somon", "emoji": "🐟", "min_seviye": 2, "fiyat": 25,
     "karb": 6.0, "prot": 24.0, "vit": 14.0, "mut": 14.0,
     "aciklama": "Seviye 2 • Omega-3 zengini beyin dostu somon (+24 Prot, +14 Vit)"},
    {"item_id": "makarna", "ad": "Peynirli Fırın Makarna", "emoji": "🍝", "min_seviye": 3, "fiyat": 28,
     "karb": 34.0, "prot": 14.0, "vit": 8.0, "mut": 16.0,
     "aciklama": "Seviye 3 • Uzun çalışma saatleri için yüksek enerji (+34 Karb, +14 Prot)"},
    {"item_id": "tavuk", "ad": "Tavuklu Gurme Mama", "emoji": "🍗", "min_seviye": 3, "fiyat": 30,
     "karb": 15.0, "prot": 26.0, "vit": 10.0, "mut": 16.0,
     "aciklama": "Seviye 3 • Enerji ve kas gelişimi için tavuklu mama (+26 Prot, +15 Karb)"},
    {"item_id": "avokado_salata", "ad": "Avokadolu Yeşil Salata", "emoji": "🥗", "min_seviye": 3, "fiyat": 32,
     "karb": 10.0, "prot": 10.0, "vit": 34.0, "mut": 16.0,
     "aciklama": "Seviye 3 • Zihin açıcı taze vitamin salatası (+34 Vit, +10 Prot)"},
    {"item_id": "omlet", "ad": "Peynirli Sabah Omleti", "emoji": "🧀", "min_seviye": 4, "fiyat": 35,
     "karb": 18.0, "prot": 22.0, "vit": 16.0, "mut": 16.0,
     "aciklama": "Seviye 4 • Sabah etütleri için doyurucu omlet (+22 Prot, +18 Karb, +16 Vit)"},
    {"item_id": "ton_baligi", "ad": "Konserve Ton Balığı Ziyafeti", "emoji": "🥫", "min_seviye": 4, "fiyat": 38,
     "karb": 8.0, "prot": 32.0, "vit": 16.0, "mut": 20.0,
     "aciklama": "Seviye 4 • Kedilerin favorisi saf protein deposu (+32 Prot, +16 Vit, +20 Neşe)"},
    {"item_id": "meyve_tabagi", "ad": "Vitamin Meyve Tabağı", "emoji": "🍓", "min_seviye": 5, "fiyat": 40,
     "karb": 18.0, "prot": 6.0, "vit": 36.0, "mut": 20.0,
     "aciklama": "Seviye 5 • Bağışıklığı zirveye çıkaran taze meyveler (+36 Vit, +18 Karb)"},
    {"item_id": "balli_pankek", "ad": "Ballı & Muzlu Pankek", "emoji": "🥞", "min_seviye": 5, "fiyat": 45,
     "karb": 40.0, "prot": 12.0, "vit": 18.0, "mut": 24.0,
     "aciklama": "Seviye 5 • Tatlı enerji patlaması (+40 Karb, +18 Vit, +24 Neşe)"},
    {"item_id": "biftek", "ad": "Matematik Protein Bifteği", "emoji": "🥩", "min_seviye": 6, "fiyat": 50,
     "karb": 10.0, "prot": 38.0, "vit": 16.0, "mut": 22.0,
     "aciklama": "Seviye 6 • Zorlu türev ve integral günlerine özel (+38 Prot, +16 Vit)"},
    {"item_id": "enerji_smoothie", "ad": "Süper Vitamin Smoothie", "emoji": "🥤", "min_seviye": 7, "fiyat": 58,
     "karb": 24.0, "prot": 18.0, "vit": 44.0, "mut": 25.0,
     "aciklama": "Seviye 7 • Tüm vitamin ve enerji barlarını tazeler (+44 Vit, +24 Karb)"},
    {"item_id": "kahve_kruvasan", "ad": "Karamel Latte & Kruvasan", "emoji": "☕", "min_seviye": 8, "fiyat": 65,
     "karb": 36.0, "prot": 18.0, "vit": 18.0, "mut": 26.0,
     "aciklama": "Seviye 8 • Uzun deneme maratonu ziyafeti (+36 Karb, +18 Prot, +26 Neşe)"},
    {"item_id": "derece_menusu", "ad": "Derece Öğrencisi Bento Menüsü", "emoji": "🍱", "min_seviye": 9, "fiyat": 75,
     "karb": 40.0, "prot": 40.0, "vit": 40.0, "mut": 30.0,
     "aciklama": "Seviye 9 • Karbonhidrat, Protein ve Vitamini dengeli doldurur (+40 Tüm Besinler)"},
    {"item_id": "sampiyon_pastasi", "ad": "Mezuniyet Ziyafet Pastası", "emoji": "🎂", "min_seviye": 10, "fiyat": 85,
     "karb": 50.0, "prot": 50.0, "vit": 50.0, "mut": 40.0,
     "aciklama": "Seviye 10 • Tüm besin barlarını dolduran efsanevi ziyafet (+50 Tüm Besinler)"},
]

EVCIL_ESYA_KATALOGU = [
    # Oda Eşyaları (Starter Room -> Graduation Room)
    {"item_id": "minder", "kategori": "oda", "ad": "Yer Minderi", "emoji": "🛋️",
     "aciklama": "Başlangıç odasının sıcak ve yumuşak yer minderi.", "fiyat": 0, "baslangic": True},
    {"item_id": "masa", "kategori": "oda", "ad": "Çalışma Masası", "emoji": "🪑",
     "aciklama": "Pomodoro'da kedinin seninle birlikte soru çözdüğü mini masa.", "fiyat": 40, "baslangic": False},
    {"item_id": "kitaplik", "kategori": "oda", "ad": "YKS Kitaplığı", "emoji": "📚",
     "aciklama": "Soru bankaları, denemeler ve konu özetleriyle dolu kütüphane.", "fiyat": 55, "baslangic": False},
    {"item_id": "hali", "kategori": "oda", "ad": "Pofuduk Oda Halısı", "emoji": "🧶",
     "aciklama": "Odayı ısıtan desenli çalışma halısı.", "fiyat": 45, "baslangic": False},
    {"item_id": "lamba", "kategori": "oda", "ad": "Gece Çalışma Lambası", "emoji": "💡",
     "aciklama": "Akşam etütlerinde göz yormayan sıcak masa lambası.", "fiyat": 50, "baslangic": False},
    {"item_id": "pencere_ankara", "kategori": "oda", "ad": "Boğaz & Kampüs Penceresi", "emoji": "🪟",
     "aciklama": "Postacı Kuş'un konduğu ferah şehir ve kampüs manzaralı pencere.", "fiyat": 70, "baslangic": False},
    {"item_id": "kampus_poster", "kategori": "oda", "ad": "Boğaziçi / ODTÜ Posteri", "emoji": "🎓",
     "aciklama": "Duvara asılan hayalindeki üniversitenin motivasyon posteri.", "fiyat": 85, "baslangic": False},
    # Aksesuar & Kıyafetler
    {"item_id": "gozluk_bilge", "kategori": "aksesuar", "ad": "Bilge Gözlüğü", "emoji": "👓",
     "aciklama": "Türev ve paragraf çözerken odaklanmayı artıran çerçeveli gözlük.", "fiyat": 35, "baslangic": False},
    {"item_id": "sapka_bere", "kategori": "aksesuar", "ad": "Kampüs Beresi", "emoji": "🧢",
     "aciklama": "Soğuk sabah etütleri için sevimli öğrenci beresi.", "fiyat": 35, "baslangic": False},
    {"item_id": "sapka_tac", "kategori": "aksesuar", "ad": "Derece Tacı", "emoji": "👑",
     "aciklama": "Deneme rekorları kıranlara özel altın motivasyon tacı.", "fiyat": 65, "baslangic": False},
    {"item_id": "sapka_mezun", "kategori": "aksesuar", "ad": "Mezuniyet Kepi", "emoji": "🎓",
     "aciklama": "YKS zaferini simgeleyen püsküllü mezuniyet kepi.", "fiyat": 90, "baslangic": False},
    # Mağaza Besin & İkram Paketleri (Her seviyede altınla alınıp hemen yedirilebilir)
    {"item_id": "kahve_odul", "kategori": "odul", "ad": "Taze Su & Süt Paketi", "emoji": "🥛",
     "aciklama": "Kedinin susuzluğunu ve açlığını giderir (+12 Karb, +12 Prot, +15 Neşe).", "fiyat": 15, "baslangic": False},
    {"item_id": "protein_bar", "kategori": "odul", "ad": "Kedi Maması Paketi", "emoji": "🥣",
     "aciklama": "Kedinin karnını doyurur! Protein +18, Karb +14, Mutluluk +12 sağlar.", "fiyat": 20, "baslangic": False},
    {"item_id": "vitamin_iksir", "kategori": "odul", "ad": "Tam Bağışıklık Maması", "emoji": "🍊",
     "aciklama": "Vitamin +20 ve tüm besin barlarına +10 destek verir.", "fiyat": 25, "baslangic": False},
    {"item_id": "karb_sandvic", "kategori": "odul", "ad": "Enerji Sandviçi & Kruvasan", "emoji": "🥐",
     "aciklama": "Karbonhidrat / Enerji barını hızla yükseltir (+28 Karb, +8 Prot, +15 Neşe).", "fiyat": 25, "baslangic": False},
    {"item_id": "somon_odul", "kategori": "odul", "ad": "Gurme Somon & Et Tabağı", "emoji": "🍣",
     "aciklama": "Beyin gücü (Protein) barını hızla doldurur (+30 Prot, +12 Vit, +18 Neşe).", "fiyat": 32, "baslangic": False},
    {"item_id": "meyve_kokteyl", "kategori": "odul", "ad": "Tropikal Vitamin Kokteyli", "emoji": "🍍",
     "aciklama": "Vitamin barını hızla doldurur (+32 Vit, +14 Karb, +18 Neşe).", "fiyat": 30, "baslangic": False},
    {"item_id": " kraliyet_paketi".strip(), "kategori": "odul", "ad": "Tam Doyurucu Ziyafet Paketi", "emoji": "🍱",
     "aciklama": "Tüm besin barlarına (+30 Karb, +30 Prot, +30 Vit, +25 Neşe) tam destek verir.", "fiyat": 55, "baslangic": False},
]

POSTACI_MEKTUPLARI = [
    {
        "letter_id": "ilk_adim",
        "baslik": "🐦 İlk Kanat Çırpışı: Kedi Yoldaşın Seninle!",
        "kosul_aciklama": "Kedi yoldaşınla ilk kez tanıştığında açılır.",
        "gizli_mesaj": "Merhaba {isim}, bu sevimli kedi yoldaşını senin için hazırladım. Sen masada ders çalışıp altın kazandıkça onu besleyecek, YKS yaklaştıkça onun büyüyüp mezuniyet kepi taktığını göreceksin. YKS yolculuğunda hiçbir zaman yalnız değilsin, sana sonuna kadar inanıyorum! — Arda 💖",
        "baslangicta_acik": True,
    },
    {
        "letter_id": "seri_5",
        "baslik": "🔥 5 Günlük İstikrar Mektubu",
        "kosul_aciklama": "5 günlük çalışma/sohbet serisine veya 10 saat toplam çalışmaya ulaşınca açılır.",
        "gizli_mesaj": "{isim}! İstikrarın gerçekten hayranlık uyandırıcı. Her gün masanın başına geçip o disiplini göstermek, sınavı kazanmanın yarısıdır. Kedin de seninle gurur duyuyor, böyle devam et şampiyon! — Arda 🌟",
        "baslangicta_acik": False,
    },
    {
        "letter_id": "tyt_rekor",
        "baslik": "📈 Deneme Rekoru & Yükseliş Mektubu",
        "kosul_aciklama": "İlk deneme analizini kaydettiğinde veya TYT 65+ nete ulaştığında açılır.",
        "gizli_mesaj": "Deneme netlerin adım adım yükseliyor {isim}! Unutma, her yanlış aslında sınav gününden eksilen bir tuzak. Netlerini kaydettiğin her gün hayalindeki kampüse bir adım daha yaklaşıyorsun. — Arda 🚀",
        "baslangicta_acik": False,
    },
    {
        "letter_id": "evrim_genc",
        "baslik": "🐱 Kedin Büyüdü: Yeni Evre!",
        "kosul_aciklama": "Kedin büyüyüp yeni bir gelişim evresine ulaştığında açılır.",
        "gizli_mesaj": "Bak kim büyümüş! Çözülen her soru, tamamlanan her Pomodoro ve verdiğin emekler kedini büyüttü. Senin emeğin gözle görülür bir başarıya dönüşüyor {isim}, seninle çok gurur duyuyorum! — Arda 🎓",
        "baslangicta_acik": False,
    },
    {
        "letter_id": "maraton_8s",
        "baslik": "👑 Efsanevi Odak Günü Mektubu",
        "kosul_aciklama": "Tek bir günde 4+ saat çalıştığında veya 30+ toplam saati geçtiğinde açılır.",
        "gizli_mesaj": "Bugün kelimenin tam anlamıyla destan yazdın {isim}! Saatlerce odaklanıp masadan kalkmamak büyük bir irade ister. Şimdi arkana yaslan, güzel bir mola ver; bunu fazlasıyla hak ettin! — Arda 💖✨",
        "baslangicta_acik": False,
    },
]

TOM_ETKILESIM_SOZLERI = [
    "Gıdıklama {isim}! 😂 Az önce türev formüllerini ezberliyordum, sırasını karıştırdım!",
    "Karnım gurulduyor {isim}... 🥣 Ders çalışıp kazandığın altınlarla bana süt veya mama alır mısın?",
    "Biliyor musun {isim}, seninle aynı odada YKS'ye hazırlanmak dünyadaki en güzel şey! 🐾💖",
    "Gözlüklerimi parlatıyorum... 🤓 Bugün o deneme rekorunu kırmaya hazır mıyız {isim}?",
    "Mırıl mırıl... 🎶 Başımı okşadığında bütün yorgunluğum uçup gidiyor {isim}!",
    "Hedefimiz büyük, enerjimiz tam! Hadi bugün çalışıp bol bol 🪙 Altın kazanalım {isim}!",
    "Miyav! 🐱 {isim}, bence bugün 1 Pomodoro daha yaparsak hayalimizdeki üniversite bize el sallayacak!",
    "Patilerimi esnetiyorum... 🐾 Uzun bir paragraf testinden sonra gerinmek gibisi yok {isim}!",
    "Bana biraz 🥛 ılık süt ısmarlarsan sana en zor geometri sorularında şans getireceğim {isim}!",
    "Sen kalem oynattıkça ben de burada gururla seni izliyorum {isim}, iyi ki benim sahibimsin! 🌟",
    "Acaba bugün kaç soru devireceğiz {isim}? Ben şimdiden heyecanlandım! 📚🔥",
    "Kulağımı kaşıdığında mırlama motorum otomatik çalışıyor {isim}... Mırrrr! 🥰",
    "Sınava adım adım yaklaşırken seninle birlikte büyümek çok heyecanlı {isim}! 🎓",
    "Hey {isim}! Telefonu bir kenara bırakıp 25 dakikalık bir odak turuna ne dersin? ⏱️",
    "Bıyıklarım titriyor! Bu kesinlikle bugün yüksek net yapacağımızın işareti {isim}! 📈",
    "Odamız her geçen gün daha güzel oluyor {isim}, mezuniyet günümüzde kepimi takıp poz vereceğim! 🎓🐾",
    "Biraz su içmeyi unutma {isim}! Sen su içerken bana da mutfaktan 💧 Taze Su alabilirsin!",
    "Bugün gözlerinde tam bir derece öğrencisi ışıltısı görüyorum {isim}! ✨",
    "Sakın pes etme {isim}! Zor sorular sadece bizim beynimizi güçlendiren antrenmanlardır 💪",
    "Miyavv! Karnımı doyurduğun ve benimle ilgilendiğin için teşekkür ederim {isim}! 🥣💛",
    "Seviye atladıkça mutfağımızda yeni yemekler açılacak {isim}, sabırsızlıkla bekliyorum! 🐟🥩",
    "Birlikte çalıştığımız her dakika bizi o kampüs kapısına biraz daha yaklaştırıyor {isim}! 🚀",
]

OKSAMA_SOZLERI = [
    "Mırıl mırıl... 🥰 Başımı okşadığın için çok mutluyum {isim}! (+6 Mutluluk)",
    "Mırrrr! 🐾 {isim}, senin sevgin bana bütün vitaminlerden daha çok moral veriyor! (+6 Mutluluk)",
    "Yaşasın! 😊 {isim} beni sevdi, şimdi keyfim tavan yaptı! (+6 Mutluluk)",
    "Kulaklarımın arkasını okşadığında dünyalar benim oluyor {isim}! 💖 (+6 Mutluluk)",
    "En iyi çalışma arkadaşı {isim}! Seninle gurur duyuyorum! 🌟 (+6 Mutluluk)",
    "Miyav! 🐱 Sevginle şarj oldum {isim}, yeni testlere hazırız! (+6 Mutluluk)",
    "Pofuduk tüylerim kabardı, çok teşekkür ederim {isim}! 🥰 (+6 Mutluluk)",
    "Sen bana böyle güzel baktıkça ben de sana şans getireceğim {isim}! 🍀 (+6 Mutluluk)",
    "Mırrr... Kalbim sıcacık oldu {isim}, iyi ki varsın! 💞 (+6 Mutluluk)",
    "Hem ders çalışıp hem beni sevdiğin için dünyanın en tatlı sahibisin {isim}! 🐾 (+6 Mutluluk)",
    "Patimle eline dokunuyorum {isim}, birlikte başaracağız! 🤝 (+6 Mutluluk)",
    "Neşem %100'e doğru uçuyor {isim}, teşekkürler! 🎉 (+6 Mutluluk)",
    "Başımı okşaman bana harika moral oldu {isim}, hadi şimdi ders çalışıp altın kazanalım! (+6 Mutluluk)",
    "Gözlerimi kapatıp mırlıyorum... 😌 Harikasın {isim}! (+6 Mutluluk)",
    "Seninle her mola çok eğlenceli geçiyor {isim}! 🎈 (+6 Mutluluk)",
    "Motivasyon depomuz doldu taştı {isim}! 🚀 (+6 Mutluluk)",
]

POMODORO_ODAK_SOZLERI = [
    "Şşşt! Dikkatimi dağıtma {isim}, şu türev sorusunu çözmeye çalışıyorum! Hadi testine dön! 🤓✏️",
    "Odak modundayız {isim}! 🤫 Gözlüklerimi taktım, mola zilini duyana kadar kalemi bırakmak yok!",
    "Hey {isim}, beni gıdıklama! Şu paragrafın ana düşüncesini bulmak üzereyim! 📚🔍",
    "Sabret {isim}! Pomodoro bitince birlikte gerinip kutlama yapacağız, şimdi tam konsantrasyon! ⏱️🔥",
    "Şu an ikimiz de kütüphane sessizliğindeyiz {isim}... Çözmeye devam, altınları toplayalım! 🪙✨",
    "Patimle işlem yapıyorum {isim}, işlem hatası yaptırma bana! 😂 Hadi soruya odaklan!",
    "Çok az kaldı {isim}! Bu Pomodoro'yu bozmadan tamamlarsak harika altın kazanacağız! 💪",
    "Geometri üçgeninin iç açılarını topluyorum {isim}, bölme beni! 📐🤓",
    "Şşşt {isim}! Rakiplerimiz şu an soru çözüyor, biz de tempoyu düşürmeyelim! 🚀",
    "Masamda not çıkarıyorum {isim}, mola vakti gelince uzun uzun sohbet ederiz! 📝🐾",
    "Dikkatini topla {isim}! Telefon veya başka bir şey bizi hedefimizden saptıramaz! 🎯",
    "Miyav! Şu an 'Bilgin Kedi' modundayım {isim}, lütfen sessizlik! 🤓📖",
    "Her çözdüğün soru bize altın kazandıracak {isim}, sakın yarıda bırakma! 🪙",
    "Bıyıklarım bu sorunun cevabının C şıkkı olduğunu söylüyor {isim}... Şaka şaka, işlem yap! 😄",
    "Odaklanma süremiz devam ediyor {isim}, derin bir nefes al ve önündeki soruya dön! 🌿",
    "Pomodoro'yu yarıda kesersen kafama silgi düşer {isim}, lütfen sonuna kadar devam et! 🥺⏱️",
]

EVCIL_GENEL_SORU_CEVAPLARI = [
    "Bence harika bir fikir {isim}! Bugün küçük bir adımla başlayıp 25 dakikalık bir Pomodoro açalım mı? ⏱️🐾",
    "Sana sonuna kadar güveniyorum {isim}! Düzenli çalıştığında çözemeyeceğin hiçbir YKS sorusu yok! 🚀",
    "Miyav! 🐱 Bıyıklarım bugün çok verimli bir çalışma günü geçireceğimizi söylüyor {isim}!",
    "Unutma {isim}, önemli olan hiç hata yapmamak değil; denemedeki yanlışlarından ders çıkarıp güçlenmek! 📈",
    "Karnım biraz acıktı gibi {isim}... Biraz ders çalışıp altın kazanırsan bana süt veya mama ısmarlayabilirsin! 🥛🥣",
    "Bence önce en çok zorlandığın dersten 20 soru çöz {isim}, arkasından sevdiğin dersle ödül yap! 📚✨",
    "Sen masanın başında emek verdikçe ben de seninle birlikte büyüyorum {isim}. Sınav yaklaştığında mezuniyet kepimi takacağım! 🎓",
    "Yorulduğunu hissediyorsan 1 bardak su iç ve 5 dakika gözlerini dinlendir {isim}, sonra birlikte devam ederiz! 💧",
    "Her gün çözdüğün sorular kumbarada birikiyor {isim}. Sabırlı ol, büyük başarılar adım adım gelir! 🌟",
    "Benim favori dersim senin en yüksek net yaptığın ders {isim}! Hadi bugün yeni bir rekor deneyelim! 🏆",
    "Merak etme {isim}, bazen konular zor görünür ama 2-3 test çözünce elin hemen alışır! 💪",
    "Seviye atladıkça mutfağımızda somon, biftek ve meyve tabağı gibi harika yemekler açılıyor {isim}! 🐟🍊",
    "Bugün kendine bir hedef koy {isim}: Mesela 2 Pomodoro + 40 soru! Tamamlayınca beni beslemeyi unutma 🪙",
    "Gözlerinin içine bakınca geleceğin üniversite öğrencisini görüyorum {isim}! Sakın motivasyonunu düşürme! 🎓💖",
    "Eğer hangi dersten başlayacağını bilemiyorsan 15 dakikalık hızlı bir paragraf veya problem turuyla ısınalım {isim}! 🔥",
    "Seninle sohbet etmek çok keyifli {isim}! Bana istediğin zaman soru sorabilir, dertleşebilirsin 🐾",
    "Sınav günü geldiğinde ikimiz de emeklerimizin karşılığını alacağız {isim}, ben şimdiden kepimi hazırladım! 🎉",
    "Mırıl mırıl... 🎶 Bugün biraz konu tekrarı yapıp Eksik Avcısı'ndaki konuları temizlemeye ne dersin {isim}?",
    "Altın biriktirmek çok kolay {isim}: Kronometreyi çalıştır, deneme netlerini gir veya çözdüğün soruları kaydet! 🪙",
    "Bence sen düşündüğünden çok daha güçlü ve zekisin {isim}! Sadece odaklan ve potansiyelini göster! ✨",
    "Penceredeki Postacı Kuş'u kontrol ettin mi {isim}? Belki sana yeni bir sürpriz mektup getirmiştir! 🐦✉️",
    "Matematikten korkma {isim}! Formülleri küçük notlara yazıp her gün 15 soru çözersen kısa sürede netlerin uçar! 📐",
    "Haftalık planındaki görevlere tek tek tik atmak dünyanın en huzurlu hissi {isim}, hadi birini tamamlayalım! ✅",
    "İyi ki benim sahibimsin {isim}! Seninle birlikte büyümek ve ders çalışmak bana çok mutluluk veriyor 🐱💛",
]

EVCIL_ANAHTAR_CEVAPLARI = [
    (("merhaba", "selam", "naber", "nasilsin", "nasılsın", "gunaydin", "günaydın", "iyi aksamlar"), [
        "Merhaba {isim}! 🐾 Seni gördüğüme çok sevindim, bugün enerjin nasıl? Birlikte soru eritmeye hazır mıyız?",
        "Selam {isim}! 🐱 Ben çok iyiyim, odamda seni bekliyordum! Bugün hangi dersten altın kazanıyoruz?",
        "Harikayım {isim}! Sen yanımda olunca keyfim hep yerinde oluyor 🥰 Senin günün nasıl geçiyor?",
        "Miyav, hoş geldin {isim}! 🌟 Bugün yeni bir deneme veya Pomodoro ile güne hızlı bir başlangıç yapalım mı?",
    ]),
    (("ac", "aç", "yemek", "mama", "sut", "süt", "su", "besle", "acıktın", "aciktin"), [
        "Karnım biraz gurulduyor {isim}! 🥣 Ders çalışarak kazandığın 🪙 Altınlarla mutfaktan bana süt, su veya mama alabilirsin!",
        "Başlangıçta su, süt ve kedi maması yiyebiliyorum {isim}; seviye atladıkça somon, makarna ve biftek de açılacak! 🥛🐟",
        "Beni beslemek için önce ders çalışıp 🪙 Altın kazanmalısın {isim}, sonra 🍴 Mutfak menüsünden yemek seçebilirsin!",
        "Nam nam! 🥛 Bana ılık süt veya mama aldığında hem karnım doyuyor hem de mutluluğum artıyor {isim}!",
    ]),
    (("altin", "altın", "para", "puan", "nasil kazan", "nasıl kazan"), [
        "Altın kazanmak için gerçekten emek vermeliyiz {isim}! 🪙 Pomodoro/Kronometre ile ders çalıştığında, deneme neti girdiğinde veya çözdüğün soruları kaydettiğinde altın kazanırsın!",
        "Çözdüğün her soru ve çalıştığın her dakika sana 🪙 Altın ve XP kazandırır {isim}. Bu altınlarla da beni besleyebilir ve odayı süsleyebilirsin!",
        "Beni sevmek veya okşamak mutluluğumu artırır ama 🪙 Altın kazandırmaz {isim}; altınları yalnızca ders çalışarak kazanabiliriz! 📚💪",
    ]),
    (("buyu", "büyü", "evrim", "seviye", "mezun", "sapka", "şapka", "boyut", "yas", "yaş"), [
        "Ben 4 farklı evrede büyüyorum {isim}! 🐾 Önce 4 ayaklı minik bebek kedi, sonra ayakta duran küçük kedi, sonra genç kedi ve YKS'ye 3 hafta kala kep takmış mezun kedi olacağım! 🎓",
        "Acele etmiyoruz {isim}! Sen çalıştıkça ve YKS sınav tarihi yaklaştıkça adım adım büyüyeceğim. Sınava 3 hafta kala en büyük mezun halime ulaşacağım! 🎓✨",
        "Seviye atladıkça hem ben gelişiyorum hem de mutfağımızda yeni yemeklerin kilidi açılıyor {isim}! 📈",
    ]),
    (("matematik", "geometri", "turev", "türev", "integral", "problem", "sayisal", "sayısal"), [
        "Matematik ve Geometri bizim 'Beyin Gücü' kaynağımız {isim}! 🧮 Düzenli problem ve branş testi çözmek XP kazancımızı hızlandırır!",
        "Türev ve geometri sorularında takılırsan hemen pes etme {isim}, şekli büyütüp verilenleri tek tek yaz! 📐✨",
        "Günde en az 20-30 Matematik sorusu çözmek sınavda seni binlerce kişinin önüne taşır {isim}! 🚀",
    ]),
    (("turkce", "türkçe", "paragraf", "edebiyat", "tarih", "cografya", "coğrafya", "sozel", "sözel"), [
        "Her sabah 20-25 paragraf sorusu çözmek zihni açar ve okuma hızını uçurur {isim}! 📖🔥",
        "Tarih ve Coğrafya konularında harita ve kavram tekrarı yapmak netlerini çok hızlı artırır {isim}! 🌍",
        "Sözel dersler harika enerji verir {isim}, ama yanında Matematik çözmeyi de ihmal etmeyelim ki dengemiz bozulmasın! ⚖️",
    ]),
    (("fen", "fizik", "kimya", "biyoloji", "deneme", "net", "tyt", "ayt"), [
        "Deneme çözdükten sonra yanlışlarının doğrusunu öğrenmek sana en az +5 net kazandırır {isim}! 📈",
        "Fizik, Kimya ve Biyoloji'de çıkmış konuların özetlerini tekrar etmek çok işe yarar {isim}! 🧪🧬",
        "Netlerinin dalgalanması çok normal {isim}, önemli olan sınava kadar istikrarlı şekilde analiz yapmak! 🏆",
    ]),
    (("stres", "kork", "heyecan", "yorul", "bıktım", "biktim", "zor", "yapamiyorum", "yapamıyorum", "motivasyon", "moral"), [
        "Derin bir nefes al {isim}... 🌿 Yorulman çok doğal çünkü gerçekten emek veriyorsun. Kısa bir mola ver, ben hep yanındayım!",
        "Kendine haksızlık etme {isim}! Bugüne kadar gösterdiğin çaba bile senin ne kadar güçlü olduğunu kanıtlıyor 💖",
        "Streslendiğinde sınava değil, sadece bugünkü küçük hedefine odaklan {isim}. Adım adım zirveye çıkacağız! 🏔️✨",
        "Unutma {isim}, en karanlık gecenin bile sabahında güneş doğar. Biz bu sınavı birlikte başaracağız! ☀️🐾",
    ]),
    (("uyku", "gece", "uykum", "yorgun", "dinlen"), [
        "Uyku hafızanın en yakın dostudur {isim}! 🌙 Öğrendiklerinin kalıcı olması için gece güzelce dinlenmelisin 💤",
        "Yorulduysan sağ alttaki 🌙 Uyku butonuna basıp oda ışığımızı kapatabilirsin {isim}, birlikte enerji toplayalım!",
    ]),
    (("seni seviyorum", "seviyorum", "tatli", "tatlı", "canim", "canım", "iyi ki"), [
        "Ben de seni çok seviyorum {isim}! 🐾💖 Dünyanın en harika çalışma arkadaşı sensin!",
        "Mırrrr! 🥰 Bunu duyduğuma o kadar mutlu oldum ki kuyruğum yerinde duramıyor {isim}!",
        "İyi ki birlikteyiz {isim}! Mezuniyet gününe kadar her gün yanındayım! 🎓💞",
    ]),
]


def evcil_db_dosyasi(kullanici=""):
    """SQLite veritabanı dosyasının yazılabilir tam yolunu döndürür."""
    temiz = re.sub(r"[^a-z0-9_]", "", (kullanici or "sude").lower()) or "sude"
    dosya_adi = f"yks_evcil_{temiz}.db"
    adaylar = [
        os.getenv("FLET_APP_STORAGE_DATA"),
        os.path.join(os.path.expanduser("~"), ".yks_asistan"),
        os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None,
        os.getcwd(),
    ]
    for d in adaylar:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            yol = os.path.join(d, dosya_adi)
            with open(yol + ".chk", "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(yol + ".chk")
            return yol
        except Exception:
            continue
    return dosya_adi


class EvcilHayvanMotoru:
    """YKS Çalışma Yoldaşı için SQLite + Bulut (Firebase) senkronlu durum makinesi."""

    def __init__(self, db_path=None, kullanici_adi="", on_degisim=None):
        self.db_path = db_path or ":memory:"
        self.kullanici_adi = str(kullanici_adi or "").strip()
        self.on_degisim = on_degisim
        self._son_cevaplar = []
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._sema_hazirla()

    def _degisim_bildir(self):
        if callable(self.on_degisim):
            try:
                self.on_degisim()
            except Exception:
                pass

    def kullanici_ayarla(self, kullanici_adi):
        ad = str(kullanici_adi or "").strip()
        if ad:
            self.kullanici_adi = ad

    def _isim(self):
        ad = (self.kullanici_adi or "").strip()
        if not ad:
            return "Şampiyon"
        return ad[:1].upper() + ad[1:]

    def _formatla(self, sablon):
        return str(sablon or "").replace("{isim}", self._isim()).replace("Sude", self._isim())

    def _benzersiz_sec(self, havuz):
        secenekler = [self._formatla(s) for s in havuz]
        uygunlar = [s for s in secenekler if s not in self._son_cevaplar[-min(14, max(1, len(secenekler) - 1)):]]
        secilen = random.choice(uygunlar if uygunlar else secenekler)
        self._son_cevaplar.append(secilen)
        if len(self._son_cevaplar) > 25:
            self._son_cevaplar = self._son_cevaplar[-25:]
        return secilen

    def _sema_hazirla(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(EVCIL_SQL_SEMA)
            simdi = time.time()
            cur.execute("SELECT id FROM pet_state WHERE id = 1")
            if cur.fetchone() is None:
                cur.execute(
                    """INSERT INTO pet_state
                    (id, isim, evrim_asamasi, xp, seviye, yildiz, karbonhidrat, protein, vitamin, mutluluk, durum, secili_sapka, secili_gozluk, last_active_timestamp)
                    VALUES (1, 'Pofuduk', 'BEBEK', 0, 1, 60, 75.0, 75.0, 75.0, 85.0, 'IDLE', '', '', ?)""",
                    (simdi,),
                )
            for esya in EVCIL_ESYA_KATALOGU:
                acik = 1 if esya.get("baslangic") else 0
                cur.execute(
                    """INSERT OR IGNORE INTO inventory_items
                    (item_id, kategori, ad, emoji, aciklama, fiyat, unlocked, equipped, unlocked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        esya["item_id"], esya["kategori"], esya["ad"], esya["emoji"],
                        esya["aciklama"], int(esya["fiyat"]), acik, acik,
                        simdi if acik else 0.0,
                    ),
                )
            for m in POSTACI_MEKTUPLARI:
                acik = 1 if m.get("baslangicta_acik") else 0
                cur.execute(
                    """INSERT OR IGNORE INTO postman_letters
                    (letter_id, baslik, kosul_aciklama, gizli_mesaj, unlocked, read_status, unlocked_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)""",
                    (
                        m["letter_id"], m["baslik"], m["kosul_aciklama"],
                        m["gizli_mesaj"], acik, simdi if acik else 0.0,
                    ),
                )
            self._conn.commit()

    def kapat(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # ==========================================
    # BULUT SENKRONİZASYONU (CİHAZLAR ARASI EŞİTLEME: TELEFON <-> TABLET)
    # ==========================================
    def bulut_disa_aktar(self):
        """Kedinin tüm durumunu, altın bakiyesini, besin barlarını, eşyalarını, mektuplarını ve
        çalışma kayıtlarını Firebase'e kaydedilmeye uygun (noktasız anahtarlı) bir sözlük olarak döndürür."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            st = dict(cur.fetchone())

            cur.execute("SELECT item_id, unlocked, equipped, unlocked_at FROM inventory_items")
            esyalar = {
                str(r["item_id"]): {
                    "u": int(r["unlocked"] or 0),
                    "e": int(r["equipped"] or 0),
                    "ts": round(float(r["unlocked_at"] or 0.0), 2),
                }
                for r in cur.fetchall()
            }

            cur.execute("SELECT letter_id, baslik, kosul_aciklama, gizli_mesaj, unlocked, read_status, unlocked_at FROM postman_letters")
            mektuplar = {
                str(r["letter_id"]): {
                    "u": int(r["unlocked"] or 0),
                    "r": int(r["read_status"] or 0),
                    "b": str(r["baslik"] or ""),
                    "k": str(r["kosul_aciklama"] or ""),
                    "m": str(r["gizli_mesaj"] or ""),
                    "ts": round(float(r["unlocked_at"] or 0.0), 2),
                }
                for r in cur.fetchall()
            }

            cur.execute("SELECT tarih, baslik, icerik, calisma_dk, cozulen_soru, created_at FROM pet_diary ORDER BY id DESC LIMIT 30")
            gunlukler = [
                {
                    "t": str(r["tarih"]),
                    "b": str(r["baslik"]),
                    "i": str(r["icerik"]),
                    "dk": int(r["calisma_dk"] or 0),
                    "s": int(r["cozulen_soru"] or 0),
                    "ts": round(float(r["created_at"] or 0.0), 2),
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT tarih, kategori, ders, soru_sayisi, dakika, created_at FROM subject_study_log ORDER BY id DESC LIMIT 60")
            study_log = [
                {
                    "t": str(r["tarih"]),
                    "k": str(r["kategori"]),
                    "d": str(r["ders"]),
                    "s": int(r["soru_sayisi"] or 0),
                    "dk": int(r["dakika"] or 0),
                    "ts": round(float(r["created_at"] or 0.0), 2),
                }
                for r in cur.fetchall()
            ]

            ts_aktif = round(float(st.get("last_active_timestamp") or time.time()), 2)
            return {
                "updated_at": ts_aktif,
                "isim": str(st.get("isim") or "Pofuduk"),
                "evrim_asamasi": str(st.get("evrim_asamasi") or "BEBEK"),
                "xp": int(st.get("xp") or 0),
                "seviye": int(st.get("seviye") or 1),
                "altin": int(st.get("yildiz") or 0),
                "yildiz": int(st.get("yildiz") or 0),
                "karbonhidrat": round(float(st.get("karbonhidrat") or 75.0), 1),
                "protein": round(float(st.get("protein") or 75.0), 1),
                "vitamin": round(float(st.get("vitamin") or 75.0), 1),
                "mutluluk": round(float(st.get("mutluluk") or 85.0), 1),
                "durum": str(st.get("durum") or "IDLE"),
                "secili_sapka": str(st.get("secili_sapka") or ""),
                "secili_gozluk": str(st.get("secili_gozluk") or ""),
                "last_active_timestamp": ts_aktif,
                "esyalar": esyalar,
                "mektuplar": mektuplar,
                "gunlukler": gunlukler,
                "study_log": study_log,
            }

    def buluttan_ice_aktar(self, bulut_veri, zorla=False):
        """Buluttan (Firebase /users/{kullanici}/evcil) gelen veriyi yerel SQLite veritabanına eşitler.
        Böylece tabletten kazanılan altınlar ve telefondan yapılan beslemeler iki cihazda da birebir aynı olur.
        Değişiklik uygulandıysa True döner."""
        if not isinstance(bulut_veri, dict) or not bulut_veri:
            return False
        if "altin" not in bulut_veri and "yildiz" not in bulut_veri and "xp" not in bulut_veri:
            return False

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            yerel = dict(cur.fetchone())

            bulut_ts = float(sayi(bulut_veri.get("updated_at") or bulut_veri.get("last_active_timestamp"), 0.0))
            yerel_ts = float(sayi(yerel.get("last_active_timestamp"), 0.0))

            # Yerel veritabanı henüz başlangıç değerindeyse (xp=0, yildiz=60) veya zorla=True ise veya bulut daha güncelse
            yerel_varsayilan_mi = (int(yerel.get("xp") or 0) == 0 and int(yerel.get("yildiz") or 0) == 60)
            if not zorla and not yerel_varsayilan_mi and bulut_ts > 0 and yerel_ts > bulut_ts + 1.0:
                return False

            isim = str(bulut_veri.get("isim") or yerel.get("isim") or "Pofuduk")[:24]
            xp = max(0, int(sayi(bulut_veri.get("xp"), yerel.get("xp", 0))))
            altin = max(0, int(sayi(bulut_veri.get("altin", bulut_veri.get("yildiz")), yerel.get("yildiz", 60))))
            evrim_h, seviye_h = self.evrim_hesapla(xp)
            seviye = max(int(sayi(bulut_veri.get("seviye"), 1)), seviye_h)
            evrim = str(bulut_veri.get("evrim_asamasi") or evrim_h)
            karb = max(0.0, min(100.0, float(sayi(bulut_veri.get("karbonhidrat"), yerel.get("karbonhidrat", 75.0)))))
            prot = max(0.0, min(100.0, float(sayi(bulut_veri.get("protein"), yerel.get("protein", 75.0)))))
            vit = max(0.0, min(100.0, float(sayi(bulut_veri.get("vitamin"), yerel.get("vitamin", 75.0)))))
            mut = max(0.0, min(100.0, float(sayi(bulut_veri.get("mutluluk"), yerel.get("mutluluk", 85.0)))))
            durum = str(bulut_veri.get("durum") or yerel.get("durum") or "IDLE")
            if durum not in EVCIL_DURUMLAR:
                durum = "IDLE"
            sapka = str(bulut_veri.get("secili_sapka") if "secili_sapka" in bulut_veri else (yerel.get("secili_sapka") or ""))
            gozluk = str(bulut_veri.get("secili_gozluk") if "secili_gozluk" in bulut_veri else (yerel.get("secili_gozluk") or ""))
            son_ts = bulut_ts if bulut_ts > 0 else (yerel_ts or time.time())

            cur.execute(
                """UPDATE pet_state
                SET isim = ?, evrim_asamasi = ?, xp = ?, seviye = ?, yildiz = ?,
                    karbonhidrat = ?, protein = ?, vitamin = ?, mutluluk = ?,
                    durum = ?, secili_sapka = ?, secili_gozluk = ?, last_active_timestamp = ?
                WHERE id = 1""",
                (isim, evrim, xp, seviye, altin, round(karb, 1), round(prot, 1), round(vit, 1), round(mut, 1), durum, sapka, gozluk, son_ts),
            )

            # Envanter eşyalarını birleştir (açılmış eşyalar hiçbir cihazda kaybolmaz)
            esyalar_map = bulut_veri.get("esyalar")
            if isinstance(esyalar_map, dict):
                for item_id, ed in esyalar_map.items():
                    if not isinstance(ed, dict):
                        continue
                    u_val = int(sayi(ed.get("u"), 0))
                    e_val = int(sayi(ed.get("e"), 0))
                    ts_val = float(sayi(ed.get("ts"), son_ts))
                    if u_val:
                        cur.execute(
                            "UPDATE inventory_items SET unlocked = 1, equipped = ?, unlocked_at = MAX(unlocked_at, ?) WHERE item_id = ?",
                            (e_val, ts_val, str(item_id)),
                        )

            # Postacı Kuş mektuplarını birleştir
            mektuplar_map = bulut_veri.get("mektuplar")
            if isinstance(mektuplar_map, dict):
                for lid, md in mektuplar_map.items():
                    if not isinstance(md, dict):
                        continue
                    u_val = int(sayi(md.get("u"), 0))
                    r_val = int(sayi(md.get("r"), 0))
                    ts_val = float(sayi(md.get("ts"), son_ts))
                    cur.execute("SELECT letter_id FROM postman_letters WHERE letter_id = ?", (str(lid),))
                    if cur.fetchone() is None and md.get("m"):
                        cur.execute(
                            """INSERT INTO postman_letters
                            (letter_id, baslik, kosul_aciklama, gizli_mesaj, unlocked, read_status, unlocked_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (str(lid), str(md.get("b") or "🐦 Postacı Kuş"), str(md.get("k") or ""), str(md.get("m")), u_val, r_val, ts_val),
                        )
                    else:
                        cur.execute(
                            """UPDATE postman_letters
                            SET unlocked = MAX(unlocked, ?), read_status = MAX(read_status, ?), unlocked_at = MAX(unlocked_at, ?)
                            WHERE letter_id = ?""",
                            (u_val, r_val, ts_val, str(lid)),
                        )

            # Günlük kayıtlarını birleştir
            for g in listeye(bulut_veri.get("gunlukler")):
                if isinstance(g, dict) and g.get("t") and g.get("i"):
                    cur.execute(
                        """INSERT INTO pet_diary (tarih, baslik, icerik, calisma_dk, cozulen_soru, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(tarih) DO UPDATE SET
                            baslik = excluded.baslik,
                            icerik = excluded.icerik,
                            calisma_dk = MAX(pet_diary.calisma_dk, excluded.calisma_dk),
                            cozulen_soru = MAX(pet_diary.cozulen_soru, excluded.cozulen_soru)""",
                        (str(g["t"]), str(g.get("b") or ""), str(g["i"]), int(sayi(g.get("dk"), 0)), int(sayi(g.get("s"), 0)), float(sayi(g.get("ts"), son_ts))),
                    )

            # Çalışma loglarını (3 gün dengesiz beslenme kontrolü için) senkronla
            bulut_logs = listeye(bulut_veri.get("study_log"))
            if bulut_logs:
                cur.execute("SELECT COUNT(*) AS c FROM subject_study_log")
                if int(cur.fetchone()["c"]) == 0:
                    for sl in reversed(bulut_logs):
                        if isinstance(sl, dict) and sl.get("t"):
                            cur.execute(
                                """INSERT INTO subject_study_log (tarih, kategori, ders, soru_sayisi, dakika, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (str(sl["t"]), str(sl.get("k") or "karbonhidrat"), str(sl.get("d") or "Genel"), int(sayi(sl.get("s"), 0)), int(sayi(sl.get("dk"), 0)), float(sayi(sl.get("ts"), son_ts))),
                            )

            self._conn.commit()
            return True

    @staticmethod
    def ders_kategorisi_bul(ders_adi):
        d = (ders_adi or "").strip().lower()
        tr_map = str.maketrans("çğıöşüâîû", "cgiosuaiu")
        d_norm = d.translate(tr_map)
        if any(k in d_norm for k in ("mat", "geometri", "turev", "integral", "limit", "problem", "sayisal", "protein")):
            return "protein"
        if any(k in d_norm for k in ("fizik", "kimya", "biyoloji", "fen", "deneme", "vitamin")):
            return "vitamin"
        return "karbonhidrat"

    @staticmethod
    def yks_kalan_gun_sayisi(simdi_dt=None):
        simdi_dt = simdi_dt or datetime.now()
        return max(0, (YKS_TARIHI - simdi_dt).days)

    @classmethod
    def evrim_hesapla(cls, xp, kalan_gun=None):
        xp = max(0, int(xp or 0))
        if kalan_gun is None:
            kalan_gun = cls.yks_kalan_gun_sayisi()
        else:
            kalan_gun = int(kalan_gun)

        if kalan_gun <= 21 or xp >= 45000:
            asama = "YETISKIN"
        elif kalan_gun <= 60 or xp >= 18000:
            asama = "GENC"
        elif kalan_gun <= 120 or xp >= 6000:
            asama = "KUCUK"
        else:
            asama = "BEBEK"

        seviye = max(1, 1 + xp // 350)
        return asama, seviye

    def yemek_katalogu_durumu(self, seviye=None):
        if seviye is None:
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("SELECT seviye FROM pet_state WHERE id = 1")
                r = cur.fetchone()
                seviye = int(r["seviye"]) if r else 1
        seviye = int(seviye or 1)
        sonuc = []
        for y in EVCIL_YEMEK_KATALOGU:
            kopya = dict(y)
            kopya["acik"] = seviye >= int(y["min_seviye"])
            sonuc.append(kopya)
        return sonuc

    def durum_oku(self, kalan_gun=None):
        """Kedinin güncel durumunu, altın bakiyesini, oda ilerlemesini ve okunmamış mektup sayısını döndürür."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            row = dict(cur.fetchone())
            hesaplanan_evrim, hesaplanan_seviye = self.evrim_hesapla(row["xp"], kalan_gun=kalan_gun)
            guncel_seviye = max(int(row["seviye"] or 1), hesaplanan_seviye)
            if hesaplanan_evrim != row["evrim_asamasi"] or guncel_seviye != row["seviye"]:
                row["evrim_asamasi"] = hesaplanan_evrim
                row["seviye"] = guncel_seviye
                if hesaplanan_evrim == "YETISKIN" and not row.get("secili_sapka"):
                    row["secili_sapka"] = "sapka_mezun"
                cur.execute(
                    "UPDATE pet_state SET evrim_asamasi = ?, seviye = ?, secili_sapka = ? WHERE id = 1",
                    (row["evrim_asamasi"], row["seviye"], row["secili_sapka"]),
                )
                self._conn.commit()

            cur.execute("SELECT * FROM inventory_items ORDER BY fiyat ASC")
            esyalar = [dict(r) for r in cur.fetchall()]
            oda_esyalari = [e for e in esyalar if e["kategori"] == "oda"]
            acik_oda = [e for e in oda_esyalari if e["unlocked"]]
            mezuniyet_odasi = len(acik_oda) == len(oda_esyalari) and len(oda_esyalari) > 0
            cur.execute("SELECT COUNT(*) AS c FROM postman_letters WHERE unlocked = 1 AND read_status = 0")
            okunmamis_mektup = int(cur.fetchone()["c"])
            row["altin"] = int(row["yildiz"])
            row["esyalar"] = esyalar
            row["yemekler"] = self.yemek_katalogu_durumu(row["seviye"])
            row["acik_oda_sayisi"] = len(acik_oda)
            row["toplam_oda_sayisi"] = len(oda_esyalari)
            row["mezuniyet_odasi"] = mezuniyet_odasi
            row["okunmamis_mektup"] = okunmamis_mektup
            return row

    def isim_degistir(self, yeni_isim):
        ad = (yeni_isim or "").strip()[:24]
        if not ad:
            return False
        with self._lock:
            self._conn.execute("UPDATE pet_state SET isim = ?, last_active_timestamp = ? WHERE id = 1", (ad, time.time()))
            self._conn.commit()
        self._degisim_bildir()
        return True

    def uygula_zaman_asim_kaybi(self, simdi_ts=None, saat_kontrol=None):
        """Çevrimdışı geçen her saat için karbonhidrat, protein, vitamin ve mutluluk barlarından
        %5 düşer (Offline Time Decay). Gece geç saatlerde (23:30 - 06:59) SLEEPING durumuna alır.
        """
        simdi_ts = float(simdi_ts if simdi_ts is not None else time.time())
        isim = self._isim()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            st = dict(cur.fetchone())
            son_ts = float(st.get("last_active_timestamp") or simdi_ts)
            gecen_saat = max(0.0, (simdi_ts - son_ts) / 3600.0)
            kayip = round(5.0 * gecen_saat, 2) if gecen_saat >= 0.05 else 0.0

            karb = max(0.0, min(100.0, float(st["karbonhidrat"]) - kayip))
            prot = max(0.0, min(100.0, float(st["protein"]) - kayip))
            vit = max(0.0, min(100.0, float(st["vitamin"]) - kayip))
            mut = max(0.0, min(100.0, float(st["mutluluk"]) - (kayip * 0.8)))

            if saat_kontrol is None:
                dt = datetime.fromtimestamp(simdi_ts, ISTANBUL_TZ)
                gece_mi = (dt.hour == 23 and dt.minute >= 30) or (0 <= dt.hour < 7)
            else:
                gece_mi = bool(saat_kontrol)

            if gece_mi:
                yeni_durum = "SLEEPING"
                mesaj = f"Esniyor... 🥱 Saat geç oldu {isim}, yarına dinç uyanmak için uyku vakti! 🌙💤"
            elif min(karb, prot, vit) < 25.0:
                yeni_durum = "HUNGRY"
                mesaj = f"Miyavv... Karnım çok acıktı {isim}! 🥣 Altınlarınla mutfaktan bana süt veya mama alır mısın? 🥺"
            elif mut < 25.0:
                yeni_durum = "SAD"
                mesaj = f"Enerjim ve neşem düştü {isim}... Beni biraz sevip yemek ısmarlar mısın? 🥺📉"
            else:
                yeni_durum = st["durum"] if st["durum"] == "STUDYING" else "IDLE"
                mesaj = f"Hoş geldin {isim}! Ben {st['isim']}, bugün birlikte çalışıp bol bol 🪙 Altın kazanalım mı? 🐾✨"

            cur.execute(
                """UPDATE pet_state
                SET karbonhidrat = ?, protein = ?, vitamin = ?, mutluluk = ?,
                    durum = ?, last_active_timestamp = ?
                WHERE id = 1""",
                (round(karb, 1), round(prot, 1), round(vit, 1), round(mut, 1), yeni_durum, simdi_ts),
            )
            self._conn.commit()
            sonuc = {
                "gecen_saat": round(gecen_saat, 2),
                "kayip": kayip,
                "karbonhidrat": round(karb, 1),
                "protein": round(prot, 1),
                "vitamin": round(vit, 1),
                "mutluluk": round(mut, 1),
                "durum": yeni_durum,
                "mesaj": mesaj,
            }
        if kayip > 0 or saat_kontrol is not None:
            self._degisim_bildir()
        return sonuc

    def besle_ders_ile(self, ders_adi, soru_sayisi=0, dakika=0, tarih_str=None, simdi_ts=None, kalan_gun=None):
        """DERS ÇALIŞMA ÖDÜLÜ: Ders çalışmak kediyi doğrudan doyurmaz!
        Çözülen soruları ve çalışılan dakikayı kaydeder, 🪙 Altın ve XP kazandırır.
        """
        soru_sayisi = max(0, int(soru_sayisi or 0))
        dakika = max(0, int(dakika or 0))
        simdi_ts = float(simdi_ts if simdi_ts is not None else time.time())
        tarih_str = tarih_str or datetime.fromtimestamp(simdi_ts, ISTANBUL_TZ).strftime("%Y-%m-%d")
        kategori = self.ders_kategorisi_bul(ders_adi)
        isim = self._isim()

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            st = dict(cur.fetchone())

            prot = float(st["protein"])
            mut = min(100.0, float(st["mutluluk"]) + 2.0)

            xp_carpan = 1.25 if prot >= 70.0 else (1.10 if prot >= 45.0 else 1.0)
            baz_xp = max(12, int(soru_sayisi * 1.5 + dakika * 1.2))
            kazanilan_xp = int(round(baz_xp * xp_carpan))
            kazanilan_altin = max(8, int(soru_sayisi // 2 + dakika // 2))

            eski_evrim = st["evrim_asamasi"]
            yeni_xp = int(st["xp"]) + kazanilan_xp
            yeni_altin = int(st["yildiz"]) + kazanilan_altin
            yeni_evrim, yeni_seviye = self.evrim_hesapla(yeni_xp, kalan_gun=kalan_gun)
            evrim_atladi = yeni_evrim != eski_evrim

            secili_sapka = st["secili_sapka"]
            if yeni_evrim == "YETISKIN" and not secili_sapka:
                secili_sapka = "sapka_mezun"

            cur.execute(
                """INSERT INTO subject_study_log (tarih, kategori, ders, soru_sayisi, dakika, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (tarih_str, kategori, str(ders_adi), soru_sayisi, dakika, simdi_ts),
            )
            cur.execute(
                """UPDATE pet_state
                SET mutluluk = ?, xp = ?, seviye = ?, yildiz = ?, evrim_asamasi = ?,
                    secili_sapka = ?, durum = 'HAPPY_JUMP', last_active_timestamp = ?
                WHERE id = 1""",
                (
                    round(mut, 1), yeni_xp, yeni_seviye, yeni_altin, yeni_evrim,
                    secili_sapka, simdi_ts,
                ),
            )
            self._conn.commit()

            if yeni_evrim in ("KUCUK", "GENC", "YETISKIN"):
                self._mektup_ac("evrim_genc", simdi_ts)

            mesaj = (
                f"Harika çalıştın {isim}! 📚 +{kazanilan_altin} 🪙 Altın ve +{kazanilan_xp} XP kazandın! "
                f"Kazandığın altınlarla mutfaktan bana yemek alabilirsin 🐾"
            )
            if evrim_atladi:
                evrim_etiket = dict((k, ad) for k, ad, _ in EVCIL_EVRIMLER).get(yeni_evrim, yeni_evrim)
                mesaj = (
                    f"🎉 BÜYÜDÜM {isim.upper()}! Artık '{evrim_etiket}' oldum! "
                    f"(+{kazanilan_altin} 🪙 Altın, +{kazanilan_xp} XP)"
                )
            sonuc = {
                "kategori": kategori,
                "besin_artisi": 0.0,
                "kazanilan_xp": kazanilan_xp,
                "kazanilan_altin": kazanilan_altin,
                "kazanilan_yildiz": kazanilan_altin,
                "evrim_atladi": evrim_atladi,
                "yeni_evrim": yeni_evrim,
                "seviye": yeni_seviye,
                "mesaj": mesaj,
            }
        self._degisim_bildir()
        return sonuc

    def yemekle_besle(self, yemek_id, simdi_ts=None):
        """Kediyi doyurmak için 🪙 Altın harcayarak yemek satın alır ve besin barlarını doldurur."""
        simdi_ts = float(simdi_ts if simdi_ts is not None else time.time())
        yemek = next((y for y in EVCIL_YEMEK_KATALOGU if y["item_id"] == yemek_id), None)
        if yemek is None:
            return False, "Yemek bulunamadı!"

        isim = self._isim()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            st = dict(cur.fetchone())
            mevcut_seviye = int(st["seviye"] or 1)
            mevcut_altin = int(st["yildiz"] or 0)
            min_sv = int(yemek["min_seviye"])
            fiyat = int(yemek["fiyat"])

            if mevcut_seviye < min_sv:
                return False, f"🔒 {yemek['emoji']} {yemek['ad']} Seviye {min_sv} olduğunda açılır! (Senin seviyen: Sv.{mevcut_seviye})"
            if mevcut_altin < fiyat:
                return False, f"Yeterli altının yok {isim}! ({fiyat} 🪙 Altın gerekiyor, sende {mevcut_altin} 🪙 var)"

            yeni_altin = mevcut_altin - fiyat
            karb = min(100.0, float(st["karbonhidrat"]) + float(yemek["karb"]))
            prot = min(100.0, float(st["protein"]) + float(yemek["prot"]))
            vit = min(100.0, float(st["vitamin"]) + float(yemek["vit"]))
            mut = min(100.0, float(st["mutluluk"]) + float(yemek["mut"]))

            cur.execute(
                """UPDATE pet_state
                SET yildiz = ?, karbonhidrat = ?, protein = ?, vitamin = ?, mutluluk = ?,
                    durum = 'EATING', last_active_timestamp = ?
                WHERE id = 1""",
                (yeni_altin, round(karb, 1), round(prot, 1), round(vit, 1), round(mut, 1), simdi_ts),
            )
            self._conn.commit()
        self._degisim_bildir()
        return (
            True,
            f"Nam nam! 😋 {yemek['emoji']} {yemek['ad']} çok lezzetliydi {isim}, karnım doydu! (-{fiyat} 🪙 Altın)",
        )

    def kontrol_dengesiz_beslenme(self, bugun_iso=None):
        isim = self._isim()
        if bugun_iso:
            baz_gun = date.fromisoformat(bugun_iso)
        else:
            baz_gun = datetime.now(ISTANBUL_TZ).date()
        gunler = [(baz_gun - timedelta(days=i)).isoformat() for i in range(3)]

        with self._lock:
            cur = self._conn.cursor()
            placeholders = ",".join("?" for _ in gunler)
            cur.execute(
                f"""SELECT tarih, kategori, SUM(soru_sayisi + dakika) AS hacim
                FROM subject_study_log
                WHERE tarih IN ({placeholders})
                GROUP BY tarih, kategori""",
                gunler,
            )
            kayitlar = cur.fetchall()

        gun_kat = {g: {"karbonhidrat": 0, "protein": 0, "vitamin": 0} for g in gunler}
        for r in kayitlar:
            t, k, h = r["tarih"], r["kategori"], int(r["hacim"] or 0)
            if t in gun_kat and k in gun_kat[t]:
                gun_kat[t][k] += h

        uc_gun_sozel = all(gun_kat[g]["karbonhidrat"] > 0 for g in gunler)
        uc_gun_mat_yok = sum(gun_kat[g]["protein"] for g in gunler) == 0
        if uc_gun_sozel and uc_gun_mat_yok:
            return (
                True,
                f"{isim}, 3 gündür hep sözel çalıştık! Yakında biraz Matematik proteini almazsak beynim uyuşacak! 🧮🥺",
            )

        durum = self.durum_oku()
        if durum["protein"] < 25.0 and durum["karbonhidrat"] >= 60.0:
            return (
                True,
                f"{isim}, karbonhidratımız tam ama proteinim çok düştü! Mutfaktan bana süt/mama alabilir veya biraz Matematik çözebilirsin! 🥛📐",
            )
        return False, ""

    def pomodoro_basladi(self, ders_adi="Matematik"):
        isim = self._isim()
        with self._lock:
            self._conn.execute(
                "UPDATE pet_state SET durum = 'STUDYING', last_active_timestamp = ? WHERE id = 1",
                (time.time(),),
            )
            self._conn.commit()
        self._degisim_bildir()
        return f"Gözlüklerimi taktım, masama oturdum! 🤓✏️ Sen {ders_adi} çözerken ben de yanındayım {isim}, tam odak!"

    def pomodoro_tikla_tepki(self, calisiyor_mu=False, gece_mi=False):
        isim = self._isim()
        if calisiyor_mu:
            return self._benzersiz_sec(POMODORO_ODAK_SOZLERI)
        if gece_mi:
            return f"Esniyor... 🥱 {isim}, saat epey geç oldu. Beynimizin öğrendiklerini kaydetmesi için uyku şart! 🌙💤"
        with self._lock:
            self._conn.execute(
                "UPDATE pet_state SET mutluluk = MIN(100.0, mutluluk + 3.0), durum = 'TALKING', last_active_timestamp = ? WHERE id = 1",
                (time.time(),),
            )
            self._conn.commit()
        self._degisim_bildir()
        dengesiz, uyari = self.kontrol_dengesiz_beslenme()
        if dengesiz and random.random() < 0.35:
            return uyari
        return self._benzersiz_sec(TOM_ETKILESIM_SOZLERI)

    def soru_cevapla(self, soru_metni=""):
        soru = str(soru_metni or "").strip()
        with self._lock:
            self._conn.execute(
                "UPDATE pet_state SET mutluluk = MIN(100.0, mutluluk + 2.0), durum = 'TALKING', last_active_timestamp = ? WHERE id = 1",
                (time.time(),),
            )
            self._conn.commit()
        self._degisim_bildir()

        if not soru:
            return self._benzersiz_sec(EVCIL_GENEL_SORU_CEVAPLARI)

        s_low = soru.lower()
        eslesen_havuz = []
        for anahtarlar, cevaplar in EVCIL_ANAHTAR_CEVAPLARI:
            if any(k in s_low for k in anahtarlar):
                eslesen_havuz.extend(cevaplar)

        birlesik = eslesen_havuz + EVCIL_GENEL_SORU_CEVAPLARI
        return self._benzersiz_sec(birlesik)

    def pomodoro_molasi(self, dakika=25, ders_adi="Matematik", tarih_str=None):
        isim = self._isim()
        odul = self.besle_ders_ile(ders_adi, soru_sayisi=max(10, dakika // 2), dakika=dakika, tarih_str=tarih_str)
        with self._lock:
            self._conn.execute("UPDATE pet_state SET durum = 'HAPPY_JUMP', last_active_timestamp = ? WHERE id = 1", (time.time(),))
            self._conn.commit()
        self._degisim_bildir()
        return (
            f"Oh be {isim}! Beynim yandı ama değdi! ☕🎉 Hadi biraz su içelim ve kazandığın altınlarla mutfaktan bana yemek al! "
            f"(+{odul['kazanilan_altin']} 🪙 Altın, +{odul['kazanilan_xp']} XP)"
        )

    def pomodoro_bozuldu(self):
        isim = self._isim()
        with self._lock:
            self._conn.execute(
                """UPDATE pet_state
                SET durum = 'SAD', mutluluk = MAX(0.0, mutluluk - 10.0), last_active_timestamp = ?
                WHERE id = 1""",
                (time.time(),),
            )
            self._conn.commit()
        self._degisim_bildir()
        return f"Ahh! Kafama dev bir silgi düştü, bütün kağıtlarım etrafa saçıldı! 📄💥 Pomodoro'yu yarıda bırakınca çok üzüldüm {isim}... 🥺"

    def oksa_sev(self):
        with self._lock:
            self._conn.execute(
                """UPDATE pet_state
                SET mutluluk = MIN(100.0, mutluluk + 6.0),
                    durum = 'HAPPY_JUMP', last_active_timestamp = ?
                WHERE id = 1""",
                (time.time(),),
            )
            self._conn.commit()
        self._degisim_bildir()
        return self._benzersiz_sec(OKSAMA_SOZLERI)

    def esya_islem(self, item_id):
        """Mağazadan eşya/ödül satın alır veya zaten alınmış aksesuarı takıp çıkarır (Altın ile)."""
        isim = self._isim()
        simdi = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM inventory_items WHERE item_id = ?", (item_id,))
            item = cur.fetchone()
            if item is None:
                return False, "Eşya bulunamadı!"
            item = dict(item)
            cur.execute("SELECT * FROM pet_state WHERE id = 1")
            st = dict(cur.fetchone())

            if item["kategori"] == "odul":
                if int(st["yildiz"]) < int(item["fiyat"]):
                    return False, f"Yeterli altının yok {isim}! ({item['fiyat']} 🪙 Altın gerekiyor)"
                yeni_altin = int(st["yildiz"]) - int(item["fiyat"])
                karb, prot, vit, mut = float(st["karbonhidrat"]), float(st["protein"]), float(st["vitamin"]), float(st["mutluluk"])
                if item_id == "kahve_odul":
                    karb = min(100.0, karb + 12.0)
                    prot = min(100.0, prot + 12.0)
                    mut = min(100.0, mut + 15.0)
                elif item_id == "protein_bar":
                    prot = min(100.0, prot + 18.0)
                    karb = min(100.0, karb + 14.0)
                    mut = min(100.0, mut + 12.0)
                elif item_id == "karb_sandvic":
                    karb = min(100.0, karb + 28.0)
                    prot = min(100.0, prot + 8.0)
                    mut = min(100.0, mut + 15.0)
                elif item_id == "somon_odul":
                    prot = min(100.0, prot + 30.0)
                    vit = min(100.0, vit + 12.0)
                    mut = min(100.0, mut + 18.0)
                elif item_id == "meyve_kokteyl":
                    vit = min(100.0, vit + 32.0)
                    karb = min(100.0, karb + 14.0)
                    mut = min(100.0, mut + 18.0)
                elif item_id == "kraliyet_paketi":
                    karb = min(100.0, karb + 30.0)
                    prot = min(100.0, prot + 30.0)
                    vit = min(100.0, vit + 30.0)
                    mut = min(100.0, mut + 25.0)
                else:
                    vit = min(100.0, vit + 20.0)
                    karb = min(100.0, karb + 10.0)
                    prot = min(100.0, prot + 10.0)
                    mut = min(100.0, mut + 12.0)
                cur.execute(
                    """UPDATE pet_state
                    SET yildiz = ?, karbonhidrat = ?, protein = ?, vitamin = ?, mutluluk = ?,
                        durum = 'EATING', last_active_timestamp = ?
                    WHERE id = 1""",
                    (yeni_altin, round(karb, 1), round(prot, 1), round(vit, 1), round(mut, 1), simdi),
                )
                self._conn.commit()
                self._degisim_bildir()
                return True, f"{item['emoji']} {item['ad']} ikram edildi! Kedin bayıldı {isim} 🎉"

            if not item["unlocked"]:
                if int(st["yildiz"]) < int(item["fiyat"]):
                    return False, f"Yeterli altının yok {isim}! ({item['fiyat']} 🪙 Altın gerekiyor)"
                yeni_altin = int(st["yildiz"]) - int(item["fiyat"])
                cur.execute("UPDATE pet_state SET yildiz = ?, durum = 'HAPPY_JUMP', last_active_timestamp = ? WHERE id = 1", (yeni_altin, simdi))
                cur.execute(
                    "UPDATE inventory_items SET unlocked = 1, equipped = 1, unlocked_at = ? WHERE item_id = ?",
                    (simdi, item_id),
                )
                if item["kategori"] == "aksesuar":
                    if item_id.startswith("gozluk"):
                        cur.execute("UPDATE pet_state SET secili_gozluk = ? WHERE id = 1", (item_id,))
                    elif item_id.startswith("sapka"):
                        cur.execute("UPDATE pet_state SET secili_sapka = ? WHERE id = 1", (item_id,))
                self._conn.commit()
                durum = self.durum_oku()
                self._degisim_bildir()
                if durum["mezuniyet_odasi"]:
                    return True, f"🎓 TEBRİKLER {isim.upper()}! Tüm eşyaları açarak odayı 'Mezuniyet Odası'na dönüştürdün! ({item['ad']} eklendi)"
                return True, f"🎉 {item['emoji']} {item['ad']} satın alındı ve odaya/kedine eklendi!"

            if item["kategori"] == "aksesuar":
                yeni_eq = 0 if item["equipped"] else 1
                cur.execute("UPDATE inventory_items SET equipped = ? WHERE item_id = ?", (yeni_eq, item_id))
                if item_id.startswith("gozluk"):
                    cur.execute("UPDATE pet_state SET secili_gozluk = ?, last_active_timestamp = ? WHERE id = 1", (item_id if yeni_eq else "", simdi))
                elif item_id.startswith("sapka"):
                    cur.execute("UPDATE pet_state SET secili_sapka = ?, last_active_timestamp = ? WHERE id = 1", (item_id if yeni_eq else "", simdi))
                self._conn.commit()
                self._degisim_bildir()
                return True, f"{item['emoji']} {item['ad']} {'takıldı' if yeni_eq else 'çıkarıldı'}!"

            return True, f"{item['emoji']} {item['ad']} zaten odanda kurulu!"

    def _mektup_ac(self, letter_id, simdi_ts=None):
        simdi_ts = float(simdi_ts if simdi_ts is not None else time.time())
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT unlocked FROM postman_letters WHERE letter_id = ?", (letter_id,))
            r = cur.fetchone()
            if r and not r["unlocked"]:
                cur.execute(
                    "UPDATE postman_letters SET unlocked = 1, unlocked_at = ? WHERE letter_id = ?",
                    (simdi_ts, letter_id),
                )
                self._conn.commit()
                return True
        return False

    def dis_mektup_ekle(self, letter_id, baslik, kosul_aciklama="", gizli_mesaj="", unlocked=1, simdi_ts=None):
        letter_id = str(letter_id or "").strip()
        baslik = str(baslik or "🐦 Sürpriz Postacı Kuş Mektubu").strip()
        kosul_aciklama = str(kosul_aciklama or "Arda'dan Postacı Kuş ile özel mektup 💌").strip()
        gizli_mesaj = str(gizli_mesaj or "").strip()
        if not letter_id or not gizli_mesaj:
            return False
        simdi_ts = float(simdi_ts if simdi_ts is not None else time.time())
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT letter_id FROM postman_letters WHERE letter_id = ?", (letter_id,))
            mevcut = cur.fetchone()
            if mevcut is None:
                cur.execute(
                    """INSERT INTO postman_letters
                    (letter_id, baslik, kosul_aciklama, gizli_mesaj, unlocked, read_status, unlocked_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)""",
                    (letter_id, baslik, kosul_aciklama, gizli_mesaj, int(bool(unlocked)), simdi_ts),
                )
                self._conn.commit()
                self._degisim_bildir()
                return True
            return False

    def bulut_mektuplari_senkronla(self, bulut_mektuplar, aktif_kullanici=""):
        if not isinstance(bulut_mektuplar, dict):
            return []
        yeni_eklenenler = []
        kul = str(aktif_kullanici or self.kullanici_adi or "").strip().lower()
        for mid, veri in sorted(bulut_mektuplar.items()):
            if not isinstance(veri, dict):
                continue
            hedef = str(veri.get("k") or "").strip().lower()
            if hedef and kul and hedef != kul:
                continue
            lid = f"panel_{mid}"
            baslik = veri.get("baslik") or "🐦 Postacı Kuş'tan Yeni Mektup!"
            kosul = veri.get("kosul") or "Arda'dan özel Postacı Kuş mektubu 💌"
            mesaj = veri.get("m") or ""
            z_ts = float(veri.get("z") or (time.time() * 1000)) / 1000.0
            if self.dis_mektup_ekle(lid, baslik, kosul, mesaj, unlocked=1, simdi_ts=z_ts):
                yeni_eklenenler.append(lid)
        return yeni_eklenenler

    def postaci_kus_kontrol(self, toplam_saat=0.0, seri_gun=0, tyt_rekor=0.0, bugun_saat=0.0, deneme_sayisi=0):
        yeni_acilanlar = []
        simdi = time.time()
        if seri_gun >= 5 or toplam_saat >= 10.0:
            if self._mektup_ac("seri_5", simdi):
                yeni_acilanlar.append("seri_5")
        if deneme_sayisi >= 1 or tyt_rekor >= 65.0:
            if self._mektup_ac("tyt_rekor", simdi):
                yeni_acilanlar.append("tyt_rekor")
        durum = self.durum_oku()
        if durum["evrim_asamasi"] in ("KUCUK", "GENC", "YETISKIN") or int(durum["xp"]) >= 6000:
            if self._mektup_ac("evrim_genc", simdi):
                yeni_acilanlar.append("evrim_genc")
        if bugun_saat >= 4.0 or toplam_saat >= 30.0:
            if self._mektup_ac("maraton_8s", simdi):
                yeni_acilanlar.append("maraton_8s")
        if yeni_acilanlar:
            self._degisim_bildir()
        return yeni_acilanlar

    def mektuplari_listele(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM postman_letters ORDER BY unlocked DESC, unlocked_at DESC")
            sonuc = []
            for r in cur.fetchall():
                d = dict(r)
                d["baslik"] = self._formatla(d["baslik"])
                d["kosul_aciklama"] = self._formatla(d["kosul_aciklama"])
                d["gizli_mesaj"] = self._formatla(d["gizli_mesaj"])
                sonuc.append(d)
            return sonuc

    def mektup_oku(self, letter_id):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("UPDATE postman_letters SET read_status = 1 WHERE letter_id = ? AND unlocked = 1", (letter_id,))
            self._conn.commit()
            cur.execute("SELECT * FROM postman_letters WHERE letter_id = ?", (letter_id,))
            r = cur.fetchone()
            if not r:
                return None
            d = dict(r)
            d["baslik"] = self._formatla(d["baslik"])
            d["kosul_aciklama"] = self._formatla(d["kosul_aciklama"])
            d["gizli_mesaj"] = self._formatla(d["gizli_mesaj"])
        self._degisim_bildir()
        return d

    def gunluk_olustur(self, tarih_str=None, calisma_dk=0, cozulen_soru=0, deneme_net=0.0, yeni_esya=""):
        tarih_str = tarih_str or datetime.now(ISTANBUL_TZ).strftime("%d.%m.%Y")
        calisma_dk = int(calisma_dk or 0)
        cozulen_soru = int(cozulen_soru or 0)
        isim = self._isim()
        st = self.durum_oku()

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT SUM(soru_sayisi) AS s, SUM(dakika) AS d FROM subject_study_log")
            toplam_log = cur.fetchone()
            if cozulen_soru == 0 and toplam_log and toplam_log["s"]:
                cozulen_soru = int(toplam_log["s"])
            if calisma_dk == 0 and toplam_log and toplam_log["d"]:
                calisma_dk = int(toplam_log["d"])

            parcalar = [f"Sevgili Günlük ({tarih_str}),"]
            if calisma_dk >= 120 or cozulen_soru >= 100:
                baslik = f"🔥 {tarih_str}: {isim} ile Soruları Eritme Günü!"
                parcalar.append(
                    f"Bugün {isim} ile tam {calisma_dk} dakika masanın başındaydık ve {cozulen_soru} soruyu devirdik! "
                    f"Kazandığımız altınlarla karnım da güzelce doydu."
                )
            elif calisma_dk > 0 or cozulen_soru > 0:
                baslik = f"🐾 {tarih_str}: {isim} ile Adım Adım Hedefe Doğru"
                parcalar.append(
                    f"Bugün {isim} ile {calisma_dk} dakika odaklandık ve {cozulen_soru} soru çözdük. "
                    f"Yarın tempoyu biraz daha artırıp daha çok altın kazanacağımıza söz verdik!"
                )
            else:
                baslik = f"🌙 {tarih_str}: Dinlenme ve Enerji Toplama Günü"
                parcalar.append(
                    f"Bugün {isim} biraz dinlendi, ben de odamdaki minderde şekerleme yaptım. Yarın bomba gibi bir Pomodoro bizi bekliyor!"
                )

            if deneme_net > 0:
                parcalar.append(f"Ayrıca denemede {deneme_net:g} net çıkardık! 📈")
            if yeni_esya:
                parcalar.append(f"Bana aldığı yeni '{yeni_esya}' hediyesine bayıldım!")
            elif st["secili_sapka"] or st["secili_gozluk"]:
                parcalar.append("Yeni aksesuarlarımla odada çok havalı duruyorum! 😎")

            dengesiz, _ = self.kontrol_dengesiz_beslenme()
            if dengesiz:
                parcalar.append(f"Not: Yarın {isim}'ye mutlaka biraz Matematik çözdürmem lazım! 🧮")
            else:
                parcalar.append(f"Beslenme dengemiz harika (Karb %{st['karbonhidrat']:.0f}, Prot %{st['protein']:.0f}, Vit %{st['vitamin']:.0f}). İyi geceler! 💖")

            icerik = " ".join(parcalar)
            cur.execute(
                """INSERT INTO pet_diary (tarih, baslik, icerik, calisma_dk, cozulen_soru, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tarih) DO UPDATE SET
                    baslik = excluded.baslik,
                    icerik = excluded.icerik,
                    calisma_dk = excluded.calisma_dk,
                    cozulen_soru = excluded.cozulen_soru,
                    created_at = excluded.created_at""",
                (tarih_str, baslik, icerik, calisma_dk, cozulen_soru, time.time()),
            )
            self._conn.commit()
        self._degisim_bildir()
        return {"tarih": tarih_str, "baslik": baslik, "icerik": icerik, "calisma_dk": calisma_dk, "cozulen_soru": cozulen_soru}

    def gunlukleri_listele(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM pet_diary ORDER BY id DESC LIMIT 30")
            return [dict(r) for r in cur.fetchall()]
