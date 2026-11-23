import copy
import time
import random
from bilesenler import sayi, listeye, istanbul_simdi, onceki_gun_str

# ==========================================
# 2b. SAF (PURE) ÖZEL SOHBET, SERİ (STREAK) VE BİLDİRİM MANTIĞI
# ==========================================
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
    """
    mevcut = mevcut if isinstance(mevcut, dict) else {}
    a, b = sorted([str(u1).strip().lower(), str(u2).strip().lower()])
    gonderen = str(gonderen).strip().lower()
    dun = onceki_gun_str(bugun)

    eski_sayi = int(mevcut.get("sayi") or 0)
    son_gun = str(mevcut.get("sonSayilanGun") or "")
    a_gun = str(mevcut.get("a_gun") or "")
    b_gun = str(mevcut.get("b_gun") or "")

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
    """Sosyal bildirim gönderilip gönderilmeyeceğine karar veren saf fonksiyon."""
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

    aktif_ekran = str(hedef_db.get("aktif_ekran") or "")
    son_aktif = sayi(hedef_db.get("son_aktif"), 0)
    if beklenen_ekran and aktif_ekran == beklenen_ekran and (simdi_ms - son_aktif) < 120_000:
        return False, "ekran_acik"

    oran_durumu = oran_durumu if isinstance(oran_durumu, dict) else {}
    if kategori == "sosyal_genel":
        if b_ayar.get("genel_sessiz", False):
            return False, "genel_sessiz"
        if b_ayar.get("genel_ilk_sonrasi_sessiz", True) and oran_durumu.get(f"genel_bekliyor:{hedef_kullanici}"):
            return False, "genel_ilk_sonrasi_sessiz"
        son_gonderim = sayi(oran_durumu.get(f"genel_oran:{gonderen}:{hedef_kullanici}"), 0)
        if son_gonderim and (simdi_ms - son_gonderim) < 300_000:
            return False, "genel_hiz_siniri"
        oran_durumu[f"genel_oran:{gonderen}:{hedef_kullanici}"] = simdi_ms
        oran_durumu[f"genel_bekliyor:{hedef_kullanici}"] = True

    if kategori == "sosyal_foto":
        son_foto = sayi(oran_durumu.get(f"foto_oran:{hedef_kullanici}"), 0)
        if son_foto and (simdi_ms - son_foto) < 180_000:
            return False, "foto_birlestirildi"
        oran_durumu[f"foto_oran:{hedef_kullanici}"] = simdi_ms

    return True, "ok"


# ==========================================
# 2c. SAF (PURE) 2 KİŞİLİK ONLINE OYUN MOTORU
# ==========================================
OYUN_TURLERI = {
    "xox": {"ad": "XOX Online", "emoji": "❌⭕", "aciklama": "3x3 klasik strateji kapışması"},
    "c4": {"ad": "Dört Bağlama", "emoji": "🔴🟡", "aciklama": "7x6 yerçekimli 4'lü dizme oyunu"},
    "yks_quiz": {"ad": "YKS Bilgi Düellosu", "emoji": "🧠⚡", "aciklama": "10 soruluk TYT bilgi ve hız yarışması"},
    "tkm": {"ad": "Taş-Kâğıt-Makas", "emoji": "✊✋✌️", "aciklama": "3 tur üzerinden eşzamanlı düello"},
    "adam": {"ad": "Adam Asmaca", "emoji": "🔤🎯", "aciklama": "Gizli Türkçe kelimeyi 6 hakta bul"},
}

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
    """XOX hamlesi uygular (saf fonksiyon)."""
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
    """Taş-Kâğıt-Makas (Best of 3 - 2 olan kazanır)."""
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
    """Bilgi Düellosu: Her iki oyuncu 10 soruyu eşzamansız çözebilir."""
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
    """Genel oyun hamlesi uygulayıcı (saf fonksiyon)."""
    simdi_ms = int(simdi_ms if simdi_ms is not None else time.time() * 1000)
    g = copy.deepcopy(oyun_verisi) if isinstance(oyun_verisi, dict) else {}
    if g.get("durum") != "oynuyor":
        return False, "Bu oyun şu an aktif değil!", g

    tur = g.get("tur", "xox")
    oyuncular = g.get("oyuncular") or {}
    a, b = oyuncular.get("a", ""), oyuncular.get("b", "")
    if oyuncu not in (a, b):
        return False, "Bu oyunun oyuncusu değilsin!", g

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
    """Oyunun zaman aşımı durumunu hesaplar."""
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
