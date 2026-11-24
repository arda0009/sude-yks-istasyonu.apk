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
import sqlite3
from datetime import datetime, date, timedelta, timezone

try:
    import requests
except ImportError:
    requests = None

# Modüler Mimari İçe Aktarımları
from ayarlar import *
from bilesenler import *
from oyun_mantik import *
from evcil_gorseller import *
from evcil_motoru import *
from netler_excel import *


# ==========================================
# BULUT (FIREBASE), BİLDİRİM (NTFY) VE YAPAY ZEKA İSTEKLERİ
# ==========================================
def bulut_oku(kullanici=None):
    if requests is None:
        raise RuntimeError("'requests' paketi yüklü değil")
    yol = f"{FIREBASE_URL}/users/{kullanici}.json" if kullanici else f"{FIREBASE_URL}/users.json"
    r = requests.get(yol, timeout=10)
    r.raise_for_status()
    return r.json()


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
    if requests is None:
        return False, "'requests' paketi yüklü değil"
    if not konu:
        return False, "bildirim konusu yok"
    try:
        r = requests.post(
            NTFY_SUNUCU,
            json={"topic": konu, "title": baslik, "message": mesaj, "priority": oncelik},
            timeout=10,
        )
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
    prompt = (
        "Sen YKS sınavına hazırlanan bir öğrenciye destek olan ve ismi Arda olan "
        f"profesyonel bir rehberlik asistanısın. Öğrenci sana şunu sordu: '{soru}'. "
        "Motive edici, çok tatlı, samimi, pratik ve eğitici bir cevap ver (maksimum 3-4 cümle)."
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
        "genel_temizle_onay": False,
        "calis_tab": 0,                           # 0: Sayaç & Pomodoro, 1: Haftalık Plan
        "evcil_tab": 0,                           # 0: Oda & Yoldaş, 1: Mağaza & Oda, 2: Postacı & Günlük, 3: Soru Sor
        "evcil_panel": None,                      # None (Oda), "magaza", "besle", "mektup", "oyun" (Soru Sor)
        "evcil_uyku_isik": False,                 # Oda gece lambası / uyku modu
        "pomo_ders_kat": "Matematik (Protein)",   # Pomodoro çalışırken seçilen ders besin grubu
        "evcil_soru_cevap": "",
        "mektup_hedef": 0,
        "acik_mektup": None,
        "son_excel_bilgi": None,
        "secili_netler": set(),                   # Seçilen deneme indeksleri (silme için)
        "duzenlenen_net_idx": None,               # Düzenlenen denemenin DB['netler'] içindeki indeksi
        "panel_kopya_kaynak": None,               # Panelde denemeleri kopyalanacak kaynak öğrenci
        "panel_kopya_hedef": "",                  # Panelde denemelerin kopyalanacağı hedef öğrenci
        "panel_secili_netler": set(),             # Panelde seçilen deneme indeksleri
        "panel_net_sinav": "TYT",                 # Paneldeki deneme kopyalama sınav filtresi
        "panel_gs_filtre": 0,                     # 0: Tümü, 1..5: Performans puanı filtresi
        "panel_gs_arama": "",
        "ilk_ders_paylasim_acik": False,          # Günün ilk dersine başlarken açılan fotoğraf/açıklama paylaşım ekranı
        "oda_secili_uye": None,                   # Canlı Çalışma Odası'nda tıklanan üye
        "_anahtar": None,
    }
    oyun = {"xox": [""] * 9, "xox_kazanan": None}
    zm = {
        "mod": "krono", "durum": "bos", "birikmis": 0.0, "t0": None, "son_kayit": 0,
        "son_su_saat": 0,                         # Kronometrede her 1 saatte (3600 sn) su bildirimi takibi
        "label": ft.Text("00:00:00", size=44, weight=ft.FontWeight.W_800),
        "ring": ft.ProgressRing(value=0.0, width=240, height=240, stroke_width=12),
        "durum_txt": ft.Text("Odaklanmaya Hazır", size=13, weight=ft.FontWeight.W_600),
        "bugun_txt": ft.Text("0 dk", size=18, weight=ft.FontWeight.W_800),
        "toplam_txt": ft.Text("0 dk", size=18, weight=ft.FontWeight.W_800),
        "ust_rozet_txt": ft.Text("00:00:00", size=13, weight=ft.FontWeight.W_800),
        "oda_odak_txt": ft.Text("0:00:00", size=28, weight=ft.FontWeight.W_800, color="#F3E8EE"),
        "oda_bugun_txt": ft.Text("0:00:00", size=12, weight=ft.FontWeight.W_700, color="#F49EC0"),
        "thread": None, "async_aktif": False, "bildirildi": False,
    }
    gk = {
        "metinler": [
            ft.Text("0", size=22, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ft.Text("0", size=22, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ft.Text("0", size=22, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ft.Text("0", size=22, weight=ft.FontWeight.W_800, color="#FFFFFF"),
        ],
        "aktif": True,
    }   # ana sayfadaki canlı geri sayım yazıları (kalıcı referanslar)

    # Sanal Evcil Hayvan & Çalışma Yoldaşı Motoru (SQLite + Bulut Senkronizasyonu)
    _ilk_kullanici = (DB.get("hesap") or {}).get("kullanici") or oturum.get("kullanici") or "Öğrenci"
    _evcil_senkron_kilit = {"aktif": False}
    evcil_motor = EvcilHayvanMotoru(evcil_db_dosyasi(oturum["kullanici"] or "sude"), kullanici_adi=_ilk_kullanici)

    def evcil_buluta_kaydet():
        """Evcil hayvanın altın, besin, seviye ve eşya durumunu anında DB['evcil'] ve Firebase buluta yazar."""
        if _evcil_senkron_kilit["aktif"]:
            return
        try:
            DB["evcil"] = evcil_motor.bulut_disa_aktar()
            kaydet("evcil")
        except Exception as ex:
            print("Evcil bulut kayıt hatası:", ex)

    def evcil_buluttan_yukle(bulut_evcil=None, zorla=False):
        """Firebase buluttaki evcil hayvan ve altın verisini yerel SQLite motoruna eşitler."""
        veri = bulut_evcil if isinstance(bulut_evcil, dict) else DB.get("evcil")
        if not isinstance(veri, dict) or not veri:
            return False
        _evcil_senkron_kilit["aktif"] = True
        try:
            degisti = evcil_motor.buluttan_ice_aktar(veri, zorla=zorla)
            if degisti:
                DB["evcil"] = evcil_motor.bulut_disa_aktar()
                yerel_yaz()
            return degisti
        finally:
            _evcil_senkron_kilit["aktif"] = False

    if DB.get("evcil"):
        evcil_buluttan_yukle(DB["evcil"], zorla=True)
    _decay_bilgi = evcil_motor.uygula_zaman_asim_kaybi()
    evcil_motor.on_degisim = evcil_buluta_kaydet
    if not DB.get("evcil"):
        DB["evcil"] = evcil_motor.bulut_disa_aktar()

    evcil_ui = {
        "mesaj": _decay_bilgi.get("mesaj", f"Hoş geldin {_ilk_kullanici.capitalize()}! Bugün birlikte çalışıp bol bol 🪙 Altın kazanalım mı? 🐾"),
        "balon_txt": None,
        "daktilo_surum": 0,
    }

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
        """Column içindeki 'expand' düğmeleri ve wrap=True olan Row içindeki 'expand' çocukları
        sınırsız yükseklik/genişlik (gri kutu) hatası vermemesi için otomatik düzeltir."""
        if isinstance(c, ft.Column):
            for k in c.controls:
                if isinstance(k, DUGME) and k.expand:
                    k.expand = False
                    c.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        elif isinstance(c, ft.Row) and getattr(c, "wrap", False):
            for k in c.controls:
                if getattr(k, "expand", False):
                    k.expand = False
        for k in (getattr(c, "controls", None) or []):
            duzelt(k)
        icerik = getattr(c, "content", None)
        if icerik is not None and not isinstance(icerik, str):
            duzelt(icerik)
        return c

    ui_kilit = threading.RLock()
    _ortak_snack_txt = ft.Text("")
    _ortak_snack = ft.SnackBar(_ortak_snack_txt)

    def _flet_agac_onar(ctrl=None, ziyaret=None):
        """Flet 0.2x (flet_core) içinde eşzamanlı güncelleme nedeniyle __uid değeri None kalmış
        kontrolleri __previous_children listesinden temizleyerek AssertionError kilitlenmesini önler."""
        if ziyaret is None:
            ziyaret = set()
        hedefler = [ctrl] if ctrl is not None else [
            page,
            getattr(page, "_offstage", None),
            getattr(page, "_Page__offstage", None),
        ]
        for h in hedefler:
            if h is None or id(h) in ziyaret:
                continue
            ziyaret.add(id(h))
            try:
                prev = getattr(h, "_Control__previous_children", None)
                if isinstance(prev, list):
                    prev[:] = [c for c in prev if getattr(c, "_Control__uid", "ok") is not None]
                for ch in list(getattr(h, "controls", None) or []):
                    _flet_agac_onar(ch, ziyaret)
                ic = getattr(h, "content", None)
                if ic is not None and not isinstance(ic, str):
                    _flet_agac_onar(ic, ziyaret)
            except Exception:
                pass

    def yenile():
        with ui_kilit:
            icerik_guncelle(renk())
            try:
                page.update()
            except Exception as ex:
                try:
                    page.overlay.clear()
                    _flet_agac_onar()
                    ui["_anahtar"] = None
                    icerik_guncelle(renk())
                    page.update()
                except Exception as ex2:
                    print("Yenile hatasi:", ex, ex2)

    def snack(mesaj):
        with ui_kilit:
            try:
                _ortak_snack_txt.value = str(mesaj)
                if hasattr(page, "open"):
                    page.open(_ortak_snack)
                elif hasattr(page, "snack_bar"):
                    page.snack_bar = _ortak_snack
                    _ortak_snack.open = True
                    page.update()
                elif hasattr(page, "show_dialog"):
                    page.show_dialog(_ortak_snack)
            except Exception:
                try:
                    _flet_agac_onar()
                    if hasattr(page, "snack_bar"):
                        page.snack_bar = ft.SnackBar(ft.Text(str(mesaj)), open=True)
                        page.update()
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
        if ui.get("_kutlama_aktif"):
            return
        ui["_kutlama_aktif"] = True

        def isle():
            kat = None
            try:
                time.sleep(0.18)
                w = int(page.width or 400)
                h = int(page.height or 800)
                kat = ft.Stack(expand=True)
                for _ in range(12):
                    kat.controls.append(ft.Container(
                        content=ft.Text(random.choice(["🎈", "🎉", "💖", "✨", "🌹", "🔥"]), size=random.randint(24, 36)),
                        left=random.randint(0, max(10, w - 40)), top=h,
                        animate_position=ft.Animation(random.randint(1600, 2600), ft.AnimationCurve.EASE_OUT),
                    ))
                with ui_kilit:
                    page.overlay.append(kat)
                    page.update()
                time.sleep(0.15)
                with ui_kilit:
                    if kat in page.overlay and getattr(kat, "_Control__uid", "ok") is not None:
                        for c in kat.controls:
                            c.top = -90
                        page.update()
                time.sleep(2.6)
            except Exception:
                with ui_kilit:
                    _flet_agac_onar()
            finally:
                with ui_kilit:
                    try:
                        if kat is not None and kat in page.overlay:
                            page.overlay.remove(kat)
                            page.update()
                    except Exception:
                        _flet_agac_onar()
                    ui["_kutlama_aktif"] = False

        threading.Thread(target=isle, daemon=True).start()

    def kart(r, icerik, padding=18, border=None, **kw):
        return ft.Container(
            bgcolor=r["card_bg"], border_radius=24, padding=padding,
            border=border or kenar(1, opak(0.75, r["border"])),
            shadow=ft.BoxShadow(blur_radius=18, color=opak(0.04, "#000000"), offset=ft.Offset(0, 4)),
            content=icerik, **kw
        )

    def buton(r, metin, on_click, ikon=None, genis=False, ikincil=False, data=None, yukseklik=48):
        return dugme_olustur(
            metin, icon=ikon, on_click=on_click, data=data, expand=genis, height=yukseklik,
            bgcolor=r["card_bg"] if ikincil else r["hdr"],
            color=r["hdr"] if ikincil else okunur_renk(r["hdr"]),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=16),
                side=ft.BorderSide(1, r["border"]) if ikincil else None,
                elevation=0,
            ),
        )

    def girdi(r, ipucu="", **kw):
        return ft.TextField(
            hint_text=ipucu, bgcolor=r["bg"], border_color=r["border"], focused_border_color=r["hdr"],
            color=r["txt"], cursor_color=r["hdr"], content_padding=15, border_radius=16,
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
        """Üstte yan yana seçim butonları (wrap=True gri kutu hatası çıkarmaması için 5+ sekmede 2 satırlı Row kullanır)."""
        def tik(i):
            def f(e):
                degisti(i)
            return f
        coklu_mu = len(etiketler) >= 5
        ogeler = []
        for i, etiket in enumerate(etiketler):
            aktif = i == secili
            ogeler.append(ft.Container(
                expand=True,
                padding=pad_sim(horizontal=4, vertical=8 if coklu_mu else 10),
                border_radius=12,
                alignment=ORTA, ink=True, on_click=tik(i),
                bgcolor=r["hdr"] if aktif else (r["bg"] if coklu_mu else SEFFAF),
                content=ft.Text(etiket, size=11 if coklu_mu else 12, weight=ft.FontWeight.W_700,
                                text_align=ft.TextAlign.CENTER,
                                color=okunur_renk(r["hdr"]) if aktif else r["muted"]),
            ))
        if coklu_mu:
            bol = (len(ogeler) + 1) // 2
            ic_icerik = ft.Column([
                ft.Row(ogeler[:bol], spacing=4),
                ft.Row(ogeler[bol:], spacing=4),
            ], spacing=4)
        else:
            ic_icerik = ft.Row(ogeler, spacing=4)
        return ft.Container(
            bgcolor=r["card_bg"], border_radius=16, padding=4, border=kenar(1, r["border"]),
            content=ic_icerik,
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

        # --- YKS geri sayım (hero kart - her saniye kesintisiz güncellenir) ---
        fark = YKS_TARIHI - simdi
        beyaz = "#FFFFFF"
        beyaz_sonuk = opak(0.78, beyaz)
        if not isinstance(gk.get("metinler"), list) or len(gk["metinler"]) != 4:
            gk["metinler"] = [
                ft.Text("0", size=22, weight=ft.FontWeight.W_800, color=beyaz),
                ft.Text("0", size=22, weight=ft.FontWeight.W_800, color=beyaz),
                ft.Text("0", size=22, weight=ft.FontWeight.W_800, color=beyaz),
                ft.Text("0", size=22, weight=ft.FontWeight.W_800, color=beyaz),
            ]

        def zaman_kutu(idx, deger, etiket):
            t = gk["metinler"][idx]
            t.value = str(deger)
            t.color = beyaz
            return ft.Container(
                expand=True, padding=pad_sim(vertical=10), border_radius=16,
                bgcolor=opak(0.18, beyaz), alignment=ORTA,
                content=ft.Column([t, ft.Text(etiket, size=11, color=beyaz_sonuk)],
                                  spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        kalan_sn = int(fark.total_seconds())
        if kalan_sn > 0:
            kutular = ft.Row([
                zaman_kutu(0, kalan_sn // 86400, "Gün"),
                zaman_kutu(1, (kalan_sn % 86400) // 3600, "Saat"),
                zaman_kutu(2, (kalan_sn % 3600) // 60, "Dakika"),
                zaman_kutu(3, kalan_sn % 60, "Saniye"),
            ], spacing=6)
            gk["aktif"] = True
        else:
            gk["aktif"] = False
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

        # --- Sanal Evcil Hayvan & Çalışma Yoldaşı Özet Kartı ---
        evcil_postaci_kontrol_et()
        yoldas_karti = evcil_ana_sayfa_karti(r)

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
            header, *sinyal_banner, hero, istatistikler, yoldas_karti,
            program_karti, todo_karti, su_karti, odul_karti, surpriz_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 7B. YOLDAŞ (SANAL EVCİL HAYVAN) YARDIMCILARI
    # ==========================================
    def evcil_konustur(metin):
        """Yoldaşın konuşma balonunu güvenli şekilde günceller (arka planda çoklu .update() yarışı oluşturmaz)."""
        metin = str(metin or "").strip()
        if not metin:
            return
        evcil_ui["mesaj"] = metin
        evcil_ui["daktilo_surum"] = int(evcil_ui.get("daktilo_surum") or 0) + 1
        with ui_kilit:
            try:
                hedef_ctrl = evcil_ui.get("balon_txt")
                if hedef_ctrl is not None and getattr(hedef_ctrl, "_Control__uid", "ok") is not None:
                    hedef_ctrl.value = f"💬 \"{metin}\""
                    if getattr(hedef_ctrl, "page", None) is not None:
                        hedef_ctrl.update()
            except Exception:
                pass

    def evcil_postaci_kontrol_et(bildirim_goster=False):
        """Öğrencinin çalışma saati, deneme rekoru, seri durumu ve panelden eklenen bulut mektuplarına göre Postacı Kuş mektuplarını açar."""
        try:
            evcil_motor.kullanici_ayarla(kullanici_adi())
            tyt_netler = [n["toplam"] for n in DB["netler"] if n.get("sinav") == "TYT"]
            tyt_rekor = max(tyt_netler) if tyt_netler else 0.0
            en_uzun_seri = max(
                [int(v.get("mevcut") or 0) for v in (sosyal.get("seri") or {}).values() if isinstance(v, dict)] or [0]
            )
            yeni_mektuplar = evcil_motor.postaci_kus_kontrol(
                toplam_saat=toplam_sn() / 3600.0,
                seri_gun=max(en_uzun_seri, len(DB["gunluk"])),
                tyt_rekor=tyt_rekor,
                bugun_saat=gun_sn(bugun_str()) / 3600.0,
                deneme_sayisi=len(DB["netler"]),
            )
            if yeni_mektuplar and bildirim_goster:
                snack("🐦 Pencerene Postacı Kuş kondu! Yoldaşının odasında yeni bir sürpriz mektup var ✉️")

            simdi_z = time.time()
            if (simdi_z - float(evcil_ui.get("son_mektup_cek") or 0.0)) >= 45.0:
                evcil_ui["son_mektup_cek"] = simdi_z

                def _bulut_mektup_cek():
                    try:
                        bm = bulut_get("ayarlar/evcil_mektuplar") or {}
                        if isinstance(bm, dict) and bm:
                            eklenen = evcil_motor.bulut_mektuplari_senkronla(bm, kullanici_adi())
                            if eklenen:
                                snack("🐦 Postacı Kuş Arda'dan yeni bir mektup getirdi! ✉️")
                                yenile()
                    except Exception:
                        pass
                arka_plan(_bulut_mektup_cek)
        except Exception:
            pass

    def evcil_besin_cubugu(r, etiket, emoji, deger, renk_hex):
        oran = max(0.0, min(1.0, float(deger or 0) / 100.0))
        return ft.Column([
            ft.Row([
                ft.Text(f"{emoji} {etiket}", size=11, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                ft.Text(f"%{int(round(deger))}", size=11, weight=ft.FontWeight.W_800,
                        color=KIRMIZI if deger < 25 else renk_hex),
            ]),
            ilerleme_cubugu(r, oran, KIRMIZI if deger < 25 else renk_hex),
        ], spacing=3)

    def evcil_aktif_sahne_anahtari(st):
        """Mevcut çalışma, uyku, açlık ve duygu durumuna göre hangi 3D fotoğraf sahnesinin gösterileceğini belirler."""
        if bool(st.get("evden_gitti")) or st.get("durum") == "GONE":
            return "GONE"
        if zm["durum"] == "calisiyor":
            return "STUDYING"
        if bool(ui.get("evcil_uyku_isik")) or st.get("durum") == "SLEEPING":
            return "SLEEPING"
        if st.get("durum") == "HUNGRY" or min(float(st.get("karbonhidrat", 50)), float(st.get("protein", 50)), float(st.get("vitamin", 50))) < 30.0:
            return "HUNGRY"
        if st.get("durum") == "SAD":
            return "SAD"
        if st.get("durum") in ("HAPPY_JUMP", "EATING"):
            return "HAPPY_JUMP"
        return "IDLE"

    def evcil_karakter_gorseli(r, st, boyut=96, tikla_fn=None):
        """Ana sayfa ve Pomodoro kartları için kedinin büyüme aşamasına (1-4) uygun 3D fotoğrafı."""
        sahne_kod = evcil_aktif_sahne_anahtari(st)
        gorsel_anahtar = "PORTRE" if sahne_kod == "IDLE" else sahne_kod
        b64 = evcil_sahne_b64_getir(
            gorsel_anahtar,
            ozel_sozluk=DB.get("evcil_ozel_gorsel"),
            evrim_asamasi=st.get("evrim_asamasi"),
        )
        sapka_emoji = {
            "sapka_tac": "👑",
            "sapka_mezun": "🎓",
            "sapka_bere": "🧢",
        }.get(st.get("secili_sapka") or "", "")

        resim_ctrl = resim_olustur(b64, width=boyut, height=boyut, fit=FIT.COVER) if FIT else resim_olustur(b64, width=boyut, height=boyut)
        icerik = ft.Stack([
            ft.Container(
                width=boyut, height=boyut, border_radius=20,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=resim_ctrl,
            ),
            *([ft.Container(right=2, top=2, padding=2, border_radius=10, bgcolor=opak(0.75, "#FFFFFF"),
                            content=ft.Text(sapka_emoji, size=14))] if sapka_emoji else []),
        ], width=boyut, height=boyut)

        return ft.Container(
            width=boyut + 6, height=boyut + 6, border_radius=22, alignment=ORTA,
            ink=True, on_click=tikla_fn,
            bgcolor=opak(0.14, r["hdr"]), border=kenar(2, opak(0.45, r["hdr"])),
            shadow=ft.BoxShadow(blur_radius=10, color=opak(0.18, "#000000"), offset=ft.Offset(0, 3)),
            content=icerik,
        )

    def evcil_ana_sayfa_karti(r):
        """Ana sayfadaki (Sekme 0) canlı Çalışma Yoldaşı & Besin Dengesi özet kartı."""
        evcil_motor.kullanici_ayarla(kullanici_adi())
        st = evcil_motor.durum_oku()
        dengesiz, uyari_metni = evcil_motor.kontrol_dengesiz_beslenme()
        evrim_ad = dict((k, ad) for k, ad, _ in EVCIL_EVRIMLER).get(st["evrim_asamasi"], "🐾 1. Aşama: Bebek Kedi")

        def odaya_git(e):
            ui["sekme"] = 3
            ui["alt"] = None
            ui["evcil_panel"] = None
            page.navigation_bar.selected_index = 3
            yenile()

        def karakter_tikla(e):
            gece_mi = datetime.now().hour >= 23 or datetime.now().hour < 7 or ui.get("evcil_uyku_isik")
            soz = evcil_motor.pomodoro_tikla_tepki(calisiyor_mu=(zm["durum"] == "calisiyor"), gece_mi=gece_mi)
            evcil_ui["mesaj"] = soz
            snack(f"🐾 {st['isim']}: {soz}")
            yenile()

        ust_rozetler = [
            ft.Container(
                padding=pad_sim(horizontal=8, vertical=4), border_radius=10, bgcolor=opak(0.14, r["hdr"]),
                content=ft.Text(f"{evrim_ad} • Sv.{st['seviye']}", size=11, weight=ft.FontWeight.W_700, color=r["hdr"]),
            ),
            ft.Container(
                padding=pad_sim(horizontal=8, vertical=4), border_radius=10, bgcolor=opak(0.16, r["accent"]),
                content=ft.Text(f"🪙 {st['altin']} Altın", size=11, weight=ft.FontWeight.W_800, color=r["txt"]),
            ),
        ]
        if st["okunmamis_mektup"] > 0:
            ust_rozetler.append(ft.Container(
                padding=pad_sim(horizontal=8, vertical=4), border_radius=10, bgcolor=opak(0.20, "#FF9800"),
                content=ft.Text(f"🐦 {st['okunmamis_mektup']} Mektup!", size=11, weight=ft.FontWeight.W_800, color="#E65100"),
            ))

        uyari_kutu = []
        if dengesiz:
            uyari_kutu.append(ft.Container(
                padding=10, border_radius=12, bgcolor=opak(0.14, KIRMIZI), border=kenar(1, KIRMIZI),
                content=ft.Text(f"⚠️ {uyari_metni}", size=12, weight=ft.FontWeight.W_600, color=KIRMIZI),
            ))

        return kart(r, ft.Column([
            bolum_basligi(r, ik("PETS"), f"Evcil Hayvanım: {st['isim']}"),
            ft.Row(ust_rozetler, wrap=True, spacing=6, run_spacing=6),
            ft.Row([
                evcil_karakter_gorseli(r, st, boyut=92, tikla_fn=karakter_tikla),
                ft.Column([
                    evcil_besin_cubugu(r, "Karbonhidrat (Enerji)", "🥐", st["karbonhidrat"], "#FB8C00"),
                    evcil_besin_cubugu(r, "Protein (Beyin Gücü)", "🥩", st["protein"], "#1E88E5"),
                    evcil_besin_cubugu(r, "Vitamin (Bağışıklık)", "🍊", st["vitamin"], "#43A047"),
                ], spacing=6, expand=True),
            ], spacing=12),
            ft.Container(
                padding=10, border_radius=12, bgcolor=r["bg"], border=kenar(1, r["border"]),
                content=ft.Text(f"💬 \"{evcil_ui['mesaj']}\"", size=12, italic=True, color=r["txt"]),
            ),
            *uyari_kutu,
            buton(r, "Evcil Hayvanımın Odasına Git 🐾", odaya_git, ikon=ik("PETS"), genis=True, ikincil=True, yukseklik=42),
        ], spacing=10))

    # ==========================================
    # 8. KALICI ZAMAN DAMGALI KRONOMETRE & POMODORO
    #    (Başladığı zamanı hafızaya atar; ekran kapansa bile durdurunca aradaki farkı çalışma saatine ekler)
    # ==========================================
    def gecen_sn():
        g = float(zm.get("birikmis") or 0.0)
        if zm["durum"] == "calisiyor" and zm["t0"] is not None:
            g += max(0.0, time.time() - float(zm["t0"]))
        return int(g)

    def canli_eklenmemis_sn():
        """Henüz DB['calisma_sn'] içine yazılmamış canlı saniye farkını döndürür."""
        if zm["durum"] == "bos":
            return 0
        return max(0, gecen_sn() - int(zm.get("son_kayit") or 0))

    def aktif_sayac_kaydet():
        """Kronometrenin başlangıç zamanını (baslangic_ts) ve birikmiş süresini kalıcı hafızaya yazar."""
        DB["aktif_sayac"] = {
            "mod": zm.get("mod", "krono"),
            "durum": zm.get("durum", "bos"),
            "baslangic_ts": float(zm["t0"]) if (zm["durum"] == "calisiyor" and zm.get("t0") is not None) else 0.0,
            "birikmis_sn": int(round(float(zm.get("birikmis") or 0.0))),
            "son_kayit_sn": int(zm.get("son_kayit") or 0),
            "son_su_saat": int(zm.get("son_su_saat") or 0),
            "tarih": bugun_str(),
            "ders": ui.get("pomo_ders_kat", "Matematik (Protein)"),
        }
        kaydet("aktif_sayac")

    def sayac_farkini_ekle():
        """Kronometrenin başladığı zaman ile durdurulduğu zaman arasındaki farkı çalışma saatine ekler."""
        toplam = gecen_sn()
        onceden = int(zm.get("son_kayit") or 0)
        fark = max(0, toplam - onceden)
        if fark > 0:
            t = bugun_str()
            DB["calisma_sn"][t] = int(DB["calisma_sn"].get(t, 0)) + fark
            zm["son_kayit"] = toplam
            kaydet("calisma_sn")
        return fark

    def aktif_sayac_yukle():
        """Uygulama yeniden açıldığında veya arka plandan döndüğünde hafızadaki aktif sayacı geri yükler."""
        s = DB.get("aktif_sayac")
        if not isinstance(s, dict):
            return
        durum_s = s.get("durum", "bos")
        if durum_s not in ("calisiyor", "durakladi"):
            return
        zm["mod"] = s.get("mod", "krono")
        zm["birikmis"] = float(sayi(s.get("birikmis_sn"), 0.0))
        zm["son_kayit"] = int(sayi(s.get("son_kayit_sn"), 0))
        zm["son_su_saat"] = int(sayi(s.get("son_su_saat"), 0))
        if s.get("ders"):
            ui["pomo_ders_kat"] = s["ders"]
        ts = float(sayi(s.get("baslangic_ts"), 0.0))
        if durum_s == "calisiyor" and ts > 0:
            zm["durum"] = "calisiyor"
            zm["t0"] = ts
            tik_baslat()
        else:
            zm["durum"] = "durakladi"
            zm["t0"] = None

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

    def oda_sure_metni(sn_deger):
        sn_i = max(0, int(sn_deger or 0))
        return f"{sn_i // 3600}:{(sn_i % 3600) // 60:02d}:{sn_i % 60:02d}"

    def kronometre_su_bildirim_kontrol(senkron=False):
        """Kronometre çalışırken geçen her 1 saatte (3600 sn) bir su içme bildirimi gönderir."""
        if zm.get("durum") != "calisiyor":
            return False
        g_sn = gecen_sn()
        saat_sayisi = int(g_sn // 3600)
        son_bildirilen = int(zm.get("son_su_saat") or 0)
        if saat_sayisi >= 1 and saat_sayisi > son_bildirilen:
            zm["son_su_saat"] = saat_sayisi
            aktif_sayac_kaydet()
            kul = kullanici_adi() or "Şampiyon"
            baslik = f"💧 {saat_sayisi} Saattir Çalışıyorsun: Su İçme Zamanı!"
            mesaj = f"Harika odaklandın {kul}! Tam {saat_sayisi} saat oldu, zihnini tazelemek için şimdi 1 bardak su içmeyi unutma 💧✨"
            snack(f"{baslik} — {mesaj}")

            def _ntfy_su():
                try:
                    b_ayar = DB.get("bildirim") or {}
                    if b_ayar.get("aktif", True) and b_ayar.get("su", True) and b_ayar.get("konu"):
                        ntfy_gonder(b_ayar["konu"], baslik, mesaj, 4)
                except Exception:
                    pass

            if senkron:
                _ntfy_su()
            else:
                arka_plan(_ntfy_su)
            return True
        return False

    def _sayac_ui_tik_uygula():
        """Sayacın ekrandaki metin ve halka kontrollerini yerinde günceller (Flet 0.2x ve 1.0 tam uyumlu)."""
        if zm["mod"] == "pomo" and gecen_sn() >= 25 * 60 and not zm["bildirildi"]:
            zm["bildirildi"] = True
            snack("🍅 Pomodoro bitti! Bitir'e basıp süreni ve yoldaş ödülünü kaydedebilirsin.")
        kronometre_su_bildirim_kontrol()
        if kok.content is not ui_kapsayici or ui["sekme"] != 1:
            return
        with ui_kilit:
            z_txt = zaman_metni()
            h_deg = halka_degeri()
            canli_ek = canli_eklenmemis_sn()
            bugun_toplam_sn = gun_sn(bugun_str()) + canli_ek
            lbl = zm.get("label")
            rng = zm.get("ring")
            ust_r = zm.get("ust_rozet_txt")
            b_txt = zm.get("bugun_txt")
            t_txt = zm.get("toplam_txt")
            oda_o = zm.get("oda_odak_txt")
            oda_b = zm.get("oda_bugun_txt")
            if lbl is not None:
                lbl.value = z_txt
                try:
                    lbl.update()
                except Exception:
                    pass
            if rng is not None:
                rng.value = h_deg
                try:
                    rng.update()
                except Exception:
                    pass
            if ust_r is not None:
                ust_r.value = f"⏱ {z_txt}"
                try:
                    ust_r.update()
                except Exception:
                    pass
            if b_txt is not None:
                b_txt.value = sn_metni(bugun_toplam_sn)
                try:
                    b_txt.update()
                except Exception:
                    pass
            if t_txt is not None:
                t_txt.value = sn_metni(toplam_sn() + canli_ek)
                try:
                    t_txt.update()
                except Exception:
                    pass
            if oda_o is not None:
                oda_o.value = oda_sure_metni(gecen_sn())
                try:
                    oda_o.update()
                except Exception:
                    pass
            if oda_b is not None:
                oda_b.value = oda_sure_metni(bugun_toplam_sn)
                try:
                    oda_b.update()
                except Exception:
                    pass
            try:
                page.update()
            except Exception:
                try:
                    _flet_agac_onar()
                    page.update()
                except Exception:
                    pass

    async def _async_tik_dongusu():
        zm["async_aktif"] = True
        try:
            while zm["durum"] == "calisiyor":
                try:
                    _sayac_ui_tik_uygula()
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        finally:
            zm["async_aktif"] = False

    def tik_dongusu():
        while zm["durum"] == "calisiyor":
            try:
                if not zm.get("async_aktif"):
                    _sayac_ui_tik_uygula()
            except Exception:
                pass
            time.sleep(0.5)

    def tik_baslat():
        if hasattr(page, "run_task") and not zm.get("async_aktif"):
            try:
                page.run_task(_async_tik_dongusu)
            except Exception:
                pass
        if not (zm["thread"] and zm["thread"].is_alive()):
            zm["thread"] = threading.Thread(target=tik_dongusu, daemon=True)
            zm["thread"].start()

    def gun_baslangicini_kaydet():
        """Günün ilk kronometre başlatışı 'derse başlama saati' olur. İlk başlatışsa True döner."""
        bugun_t = bugun_str()
        ilk_mi = (DB["gun"].get("tarih") != bugun_t)
        if ilk_mi:
            DB["gun"] = {
                "tarih": bugun_t,
                "baslama": datetime.now().strftime("%H:%M"),
                "paylasim_yapildi": "",
            }
            kaydet("gun")
        return ilk_mi

    def ders_baslangic_postu_olustur(foto_b64, aciklama_metni, senkron=False):
        """Günün ilk dersi / ders başlangıç paylaşımını fotoğraf, açıklama, tarih ve 'Ders Başlangıç Paylaşımı' etiketiyle yayınlar."""
        ben = oturum["kullanici"] or kullanici_adi()
        if not ben or not foto_b64:
            return None
        pid = yeni_id()
        bugun_t = bugun_str()
        saat_str = (DB.get("gun") or {}).get("baslama") or datetime.now().strftime("%H:%M")
        aciklama_temiz = (aciklama_metni or "").strip()[:500]
        zaman_ms = int(time.time() * 1000)
        alt_etiket = f"{bugun_t} • Ders Başlangıç Paylaşımı"
        post_veri = {
            "kullanici": ben,
            "aciklama": aciklama_temiz,
            "zaman": zaman_ms,
            "tarih": bugun_t,
            "baslama_saati": saat_str,
            "tur": "ders_baslangic",
            "alt_etiket": alt_etiket,
        }
        sosyal["posts"][pid] = post_veri
        sosyal["resim"][pid] = foto_b64
        DB.setdefault("gun", {})["paylasim_yapildi"] = bugun_t
        if DB["gun"].get("tarih") != bugun_t:
            DB["gun"]["tarih"] = bugun_t
            DB["gun"]["baslama"] = saat_str
        kaydet("gun")

        def is_():
            try:
                bulut_patch(f"sosyal/resim/{pid}", {"d": foto_b64})
                bulut_patch(f"sosyal/posts/{pid}", post_veri)
                toplu_sosyal_bildirim_yolla(
                    "sosyal_foto",
                    f"📚 {ben} günün ilk dersine başladı!",
                    f"{aciklama_temiz[:90]} ({alt_etiket})" if aciklama_temiz else f"📅 {alt_etiket}",
                    oncelik=3, beklenen_ekran="akis", senkron=True,
                )
            except Exception as ex:
                print("Ders başlangıç paylaşımı gönderilemedi:", ex)

        if senkron:
            is_()
        else:
            arka_plan(is_)
        return pid

    def krono_bitir_kaydet():
        """Çalışan/duraklatılmış oturumun başlangıç zamanıyla şu an arasındaki farkı bugüne ekler ve sıfırlar."""
        toplam = gecen_sn()
        sayac_farkini_ekle()
        zm.update({"durum": "bos", "birikmis": 0.0, "t0": None, "son_kayit": 0, "son_su_saat": 0, "bildirildi": False})
        aktif_sayac_kaydet()
        return toplam

    aktif_sayac_yukle()

    def ilk_ders_paylasim_karti_olustur(r, kapat_fn=None, sayac_bekliyor=False):
        """Günün ilk dersine başlarken açılan fotoğraf + açıklama paylaşım ekranı.
        Fotoğraf koymak zorunludur; fotoğraf seçilip paylaşılmadan kronometre başlamaz."""
        bugun_t = bugun_str()
        baslama_s = (DB.get("gun") or {}).get("baslama") or datetime.now().strftime("%H:%M")

        def foto_secildi(veri, hata):
            if hata:
                sosyal["foto_mesaj"] = hata
            elif veri:
                b64, h = foto_hazirla(veri)
                sosyal["yeni_foto"] = b64
                sosyal["foto_mesaj"] = h
            yenile()

        def foto_sec_tikla(e):
            sosyal["foto_mesaj"] = ""
            foto_sec(foto_secildi)

        def hazir_masa_fotosu_kullan(e):
            st_k = evcil_motor.durum_oku()
            sosyal["yeni_foto"] = evcil_sahne_b64_getir("STUDYING", evrim_asamasi=st_k.get("evrim_asamasi", "BEBEK"))
            sosyal["foto_mesaj"] = ""
            yenile()
            snack("🐾 Çalışma fotoğrafı eklendi! Şimdi Paylaş ve Kronometreyi Başlat'a basabilirsin.")

        def aciklama_degisti(e):
            sosyal["yeni_aciklama"] = e.control.value or ""

        def paylas_ve_devam_et(e):
            aciklama_v = (sosyal.get("yeni_aciklama") or "").strip()
            foto_v = sosyal.get("yeni_foto")
            if not foto_v:
                sosyal["foto_mesaj"] = "⚠️ Derse başlamadan önce fotoğraf eklemen zorunlu! Lütfen fotoğraf seç/çek."
                yenile()
                snack("⚠️ Fotoğraf koymadan kronometre başlamaz! Lütfen önce ders fotoğrafını seç.")
                return
            gun_baslangicini_kaydet()
            ders_baslangic_postu_olustur(foto_v, aciklama_v)
            sosyal["yeni_foto"] = None
            sosyal["yeni_aciklama"] = ""
            sosyal["foto_mesaj"] = ""
            ui["ilk_ders_paylasim_acik"] = False
            ui["sosyal_ek_paylasim_acik"] = False
            # Eğer kronometre fotoğraf paylaşımını bekliyorsa şimdi başlat!
            if sayac_bekliyor or zm.get("durum") == "bos":
                simdi_ts = time.time()
                zm.update({"durum": "calisiyor", "birikmis": 0.0, "t0": simdi_ts, "son_kayit": 0, "son_su_saat": 0, "bildirildi": False})
                aktif_sayac_kaydet()
                soz = evcil_motor.pomodoro_basladi(ui["pomo_ders_kat"])
                evcil_ui["mesaj"] = soz
                yenile()
                tik_baslat()
                evcil_konustur(soz)
            else:
                yenile()
            kutlama()
            snack(f"📸 {bugun_t} • Ders Başlangıç Paylaşımı yayınlandı ve Kronometre başlatıldı! İyi çalışmalar 🔥")

        gn = min(300, max(190, int((page.width or 380) - 56)))
        onizleme = []
        if sosyal.get("yeni_foto"):
            onizleme.append(ft.Container(
                width=gn, height=gn, border_radius=16, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                border=kenar(2, r["hdr"]),
                content=resim_olustur(sosyal["yeni_foto"], width=gn, height=gn),
            ))
        if sosyal.get("foto_mesaj"):
            onizleme.append(ft.Text(sosyal["foto_mesaj"], size=12, weight=ft.FontWeight.W_700, color=KIRMIZI))

        ana_buton_metni = "📸 Paylaş ve Kronometreyi Başlat 🔥" if (sayac_bekliyor or zm.get("durum") == "bos") else "📸 Paylaş ve Derse Devam Et"
        alt_butonlar = [
            buton(r, ana_buton_metni, paylas_ve_devam_et, ikon=ik("PLAY_ARROW") if sayac_bekliyor else ik("SEND"), genis=True, yukseklik=48),
        ]
        if kapat_fn is not None:
            alt_butonlar.append(
                buton(r, "Vazgeç (Kronometreyi Başlatma)" if sayac_bekliyor else "Vazgeç", kapat_fn, ikincil=True, genis=True, yukseklik=40)
            )

        return kart(r, ft.Column([
            ft.Row([
                ft.Container(
                    width=40, height=40, border_radius=12, bgcolor=opak(0.16, r["hdr"]), alignment=ORTA,
                    content=ft.Text("📸", size=22),
                ),
                ft.Column([
                    ft.Text("Derse Başlamak İçin Fotoğraf Ekle!", size=16, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    ft.Text("Fotoğraf koymadan kronometre başlamaz. Fotoğrafını seçip açıklamanı yaz!", size=12, color=r["muted"]),
                ], spacing=2, expand=True),
            ], spacing=10),
            ft.Container(
                padding=pad_sim(horizontal=12, vertical=8), border_radius=12,
                bgcolor=opak(0.14, r["accent"]), border=kenar(1, r["accent"]),
                content=ft.Row([
                    ft.Text(f"📅 {bugun_t} • 🌅 Başlangıç: {baslama_s} • 📚 Ders Başlangıç Paylaşımı (Zorunlu)",
                            size=12, weight=ft.FontWeight.W_800, color=r["txt"], expand=True),
                ]),
            ),
            *([ft.Column(onizleme, horizontal_alignment=ft.CrossAxisAlignment.CENTER)] if onizleme else []),
            buton(
                r,
                "📷 Fotoğrafı Değiştir ✅" if sosyal.get("yeni_foto") else "📷 Ders Fotoğrafı Seç / Çek (Zorunlu)",
                foto_sec_tikla,
                ikon=ik("ADD_PHOTO_ALTERNATE"),
                genis=True,
                ikincil=bool(sosyal.get("yeni_foto")),
                yukseklik=44,
            ),
            buton(
                r,
                "🐾 Kamera Açılmazsa Masa Fotoğrafı Seç",
                hazir_masa_fotosu_kullan,
                ikincil=True,
                genis=True,
                yukseklik=38,
            ),
            girdi(
                r,
                "Bugün hangi derse başlıyorsun? Hedefini ve açıklamanı yaz...",
                label="Ders Başlangıç Açıklaması",
                value=sosyal.get("yeni_aciklama", ""),
                on_change=aciklama_degisti,
                multiline=True,
                min_lines=2,
                max_lines=3,
            ),
            ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=10, bgcolor=r["bg"], border=kenar(1, r["border"]),
                content=ft.Text(
                    f"📌 Postun altında görünecek etiket:  📅 {bugun_t} • Ders Başlangıç Paylaşımı",
                    size=11, weight=ft.FontWeight.W_700, color=r["hdr"],
                ),
            ),
            *alt_butonlar,
        ], spacing=10), padding=16, border=kenar(2, r["hdr"]))

    def canli_calisma_odasi_cek(zorla=False, senkron=False):
        """Buluttaki tüm öğrencilerin anlık çalışma durumunu ve bugünkü sürelerini çeker (Kütüphane için)."""
        simdi_z = time.time()
        if not zorla and panel["son_cek"] > 0 and (simdi_z - panel["son_cek"]) < 5.0 and panel.get("veri"):
            return panel["veri"]

        def _cek():
            try:
                users = bulut_oku() or {}
                if isinstance(users, dict) and users:
                    panel["veri"] = users
                    panel["son_cek"] = time.time()
            except Exception:
                pass

        if senkron:
            _cek()
        else:
            def _arka():
                _cek()
                if kok.content is ui_kapsayici and ui["sekme"] == 1 and int(ui.get("calis_tab") or 0) == 1:
                    yenile()
            arka_plan(_arka)
        return panel.get("veri") or {}

    def masa_svg_b64_olustur(durum_kod="bos", renk_hex="#C8B6C2", vurgu_hex="#E86C8D", uyari_rozet=False, saat_rozet=False):
        """Kütüphane bölümündeki öğrenci çalışma masası & masa lambası ikonlarını temaya uyumlu SVG olarak üretir."""
        ust_ek = ""
        if uyari_rozet:
            ust_ek = (
                f'<rect x="14" y="6" width="22" height="17" rx="4" fill="none" stroke="{vurgu_hex}" stroke-width="2.4"/>'
                f'<line x1="25" y1="10" x2="25" y2="15" stroke="{vurgu_hex}" stroke-width="2.4" stroke-linecap="round"/>'
                f'<circle cx="25" cy="19" r="1.4" fill="{vurgu_hex}"/>'
            )
        elif saat_rozet:
            ust_ek = (
                f'<circle cx="24" cy="15" r="8" fill="none" stroke="{renk_hex}" stroke-width="2.2"/>'
                f'<polyline points="24,10 24,15 28,15" fill="none" stroke="{renk_hex}" stroke-width="2" stroke-linecap="round"/>'
            )

        if durum_kod == "calisiyor_avatar":
            ic_svg = (
                f'<circle cx="50" cy="40" r="24" fill="{opak(0.18, vurgu_hex)}" stroke="{vurgu_hex}" stroke-width="2.2"/>'
                f'<path d="M26 38 A24 24 0 0 1 74 38" fill="none" stroke="{vurgu_hex}" stroke-width="5" stroke-dasharray="6 4"/>'
                '<circle cx="50" cy="36" r="11" fill="#FBD38D"/>'
                '<path d="M38 35 Q50 22 62 35" fill="#744210"/>'
                '<circle cx="46" cy="36" r="1.6" fill="#2D3748"/>'
                '<circle cx="54" cy="36" r="1.6" fill="#2D3748"/>'
                '<path d="M47 41 Q50 43 53 41" fill="none" stroke="#2D3748" stroke-width="1.6" stroke-linecap="round"/>'
                '<path d="M35 58 Q50 46 65 58" fill="#48BB78"/>'
                f'<rect x="24" y="57" width="52" height="6" rx="3" fill="{vurgu_hex}"/>'
                '<rect x="33" y="53" width="16" height="4" rx="1.5" fill="#63B3ED"/>'
                f'<rect x="52" y="53" width="15" height="4" rx="1.5" fill="{renk_hex}"/>'
            )
        elif durum_kod == "calisiyor_renkli":
            ic_svg = (
                f'{ust_ek}'
                f'<circle cx="38" cy="34" r="7.5" fill="none" stroke="{vurgu_hex}" stroke-width="2.6"/>'
                f'<line x1="33" y1="31" x2="43" y2="37" stroke="{vurgu_hex}" stroke-width="2"/>'
                f'<path d="M28 50 Q38 41 48 50" fill="none" stroke="{vurgu_hex}" stroke-width="2.8" stroke-linecap="round"/>'
                f'<line x1="33" y1="16" x2="36" y2="21" stroke="{vurgu_hex}" stroke-width="2" stroke-linecap="round"/>'
                f'<line x1="39" y1="14" x2="41" y2="20" stroke="{vurgu_hex}" stroke-width="2" stroke-linecap="round"/>'
                f'<polygon points="56,24 70,24 73,34 53,34" fill="none" stroke="{vurgu_hex}" stroke-width="2.5" stroke-linejoin="round"/>'
                f'<line x1="63" y1="34" x2="63" y2="50" stroke="{vurgu_hex}" stroke-width="2.6"/>'
                f'<line x1="20" y1="50" x2="80" y2="50" stroke="{vurgu_hex}" stroke-width="3" stroke-linecap="round"/>'
                f'<line x1="25" y1="50" x2="25" y2="66" stroke="{vurgu_hex}" stroke-width="2.8" stroke-linecap="round"/>'
                f'<line x1="75" y1="50" x2="75" y2="66" stroke="{vurgu_hex}" stroke-width="2.8" stroke-linecap="round"/>'
                f'<line x1="25" y1="57" x2="75" y2="57" stroke="{vurgu_hex}" stroke-width="2.4"/>'
            )
        else:
            ic_svg = (
                f'{ust_ek}'
                f'<polygon points="56,22 70,22 73,32 53,32" fill="none" stroke="{renk_hex}" stroke-width="2.4" stroke-linejoin="round"/>'
                f'<line x1="63" y1="32" x2="63" y2="48" stroke="{renk_hex}" stroke-width="2.4"/>'
                f'<line x1="22" y1="48" x2="78" y2="48" stroke="{renk_hex}" stroke-width="2.8" stroke-linecap="round"/>'
                f'<line x1="26" y1="48" x2="26" y2="65" stroke="{renk_hex}" stroke-width="2.6" stroke-linecap="round"/>'
                f'<line x1="74" y1="48" x2="74" y2="65" stroke="{renk_hex}" stroke-width="2.6" stroke-linecap="round"/>'
                f'<line x1="26" y1="55" x2="74" y2="55" stroke="{renk_hex}" stroke-width="2.2"/>'
            )

        svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 76">{ic_svg}</svg>'
        return f"data:image/svg+xml;base64,{base64.b64encode(svg_str.encode('utf-8')).decode('ascii')}"

    def canli_calisma_odasi_olustur(r, ust_sekme_cubugu, baslat_fn, duraklat_fn, devam_fn):
        """Kütüphane sekmesi: Yalnızca uygulamanın gerçek kayıtlı kullanıcılarını gösterir.
        Aktif çalışanlar temanın canlı rengiyle, çalışmayanlar soluk renkle gösterilir;
        her öğrencinin kronometreden gelen çalışma süresi anlık olarak güncellenir."""
        if not panel.get("veri") or (time.time() - panel.get("son_cek", 0) > 6.0):
            canli_calisma_odasi_cek(zorla=False, senkron=not bool(panel.get("veri")))

        bugun_t = bugun_str()
        ben_k = (kullanici_adi() or "sude").strip().lower()
        ben_aktif = (zm["durum"] == "calisiyor")
        ben_odak_sn = gecen_sn()
        ben_bugun_sn = gun_sn(bugun_t) + canli_eklenmemis_sn()

        zm["oda_odak_txt"].value = oda_sure_metni(ben_odak_sn)
        zm["oda_odak_txt"].color = r["txt"]
        zm["oda_bugun_txt"].value = oda_sure_metni(ben_bugun_sn)
        zm["oda_bugun_txt"].color = r["hdr"]

        # YALNIZCA buluttaki gerçek kayıtlı kullanıcılarımızı ve giriş yapmış kullanıcıyı listele
        users_bulut = panel.get("veri") or {}
        uyeler_map = {}

        for u_ad, u_veri in users_bulut.items():
            if not isinstance(u_veri, dict):
                continue
            u_low = str(u_ad).strip().lower()
            sn_t = bulut_coz("calisma_sn", u_veri.get("calisma_sn") or {})
            log_t = bulut_coz("calisma_log", u_veri.get("calisma_log") or {})
            u_bugun_sn = int(sayi(sn_t.get(bugun_t))) + int(sayi(log_t.get(bugun_t))) * 60
            akt_s = u_veri.get("aktif_sayac") if isinstance(u_veri.get("aktif_sayac"), dict) else {}
            u_calisiyor = (akt_s.get("durum") == "calisiyor")
            u_oturum_sn = 0
            if u_calisiyor and float(sayi(akt_s.get("baslangic_ts"), 0.0)) > 0:
                u_oturum_sn = max(0, int(time.time() - float(akt_s["baslangic_ts"])) + int(sayi(akt_s.get("birikmis_sn"), 0)))
                canli_f = max(0, u_oturum_sn - int(sayi(akt_s.get("son_kayit_sn"), 0)))
                u_bugun_sn += canli_f
            elif akt_s.get("durum") == "durakladi":
                u_oturum_sn = int(sayi(akt_s.get("birikmis_sn"), 0))
            uyeler_map[u_low] = {
                "ad": u_ad,
                "sn": u_bugun_sn,
                "oturum_sn": u_oturum_sn,
                "calisiyor": u_calisiyor,
                "ders": akt_s.get("ders") or "YKS Odak",
                "ben": (u_low == ben_k),
            }

        # Giriş yapmış kullanıcının kendi anlık kronometre verisini her zaman en güncel haliyle yaz
        uyeler_map[ben_k] = {
            "ad": kullanici_adi() or "Sude",
            "sn": ben_bugun_sn,
            "oturum_sn": ben_odak_sn,
            "calisiyor": ben_aktif,
            "ders": ui.get("pomo_ders_kat", "Matematik"),
            "ben": True,
        }

        # Sıralama: Önce aktif çalışanlar ve bugünkü çalışma süresi yüksek olanlar
        sirali_uyeler = sorted(
            uyeler_map.values(),
            key=lambda x: (not bool(x.get("calisiyor")), -int(x.get("sn") or 0), str(x.get("ad") or "").lower()),
        )
        calisan_sayisi = sum(1 for u in sirali_uyeler if u.get("calisiyor"))

        def sayac_oynat_duraklat(e):
            if zm["durum"] == "calisiyor":
                duraklat_fn(e)
            elif zm["durum"] == "durakladi":
                devam_fn(e)
            else:
                baslat_fn(e)

        def uye_masa_tikla(u_bilgi):
            def f(e):
                ui["oda_secili_uye"] = u_bilgi
                durum_str = f"🔥 Şu an çalışıyor (Oturum: {oda_sure_metni(u_bilgi.get('oturum_sn', 0))})" if u_bilgi.get("calisiyor") else "⏸ Şu an çalışmıyor"
                snack(f"📚 {u_bilgi['ad']} • Bugün Toplam: {oda_sure_metni(u_bilgi['sn'])} • {durum_str}")
                yenile()
            return f

        # 1) ÜST BAR (Temaya tam uyumlu): Sol üstte "Mevcut odaklanma süresi" + sayaç + (|| / ▶), sağ üstte avatar + bugün toplam
        sag_avatar_svg = masa_svg_b64_olustur("calisiyor_avatar", renk_hex=r["accent"], vurgu_hex=r["hdr"])
        ust_odak_bari = kart(
            r,
            ft.Row([
                ft.Column([
                    ft.Text("Mevcut odaklanma süresi", size=12, color=r["muted"], weight=ft.FontWeight.W_600),
                    ft.Row([
                        zm["oda_odak_txt"],
                        ft.Container(
                            width=38, height=38, border_radius=19,
                            bgcolor=r["hdr"] if ben_aktif else opak(0.18, r["hdr"]),
                            alignment=ORTA, ink=True,
                            on_click=sayac_oynat_duraklat,
                            tooltip="Kronometreyi Başlat / Duraklat",
                            content=ft.Icon(
                                ik("PAUSE") if ben_aktif else ik("PLAY_ARROW"),
                                color=okunur_renk(r["hdr"]) if ben_aktif else r["hdr"], size=20,
                            ),
                        ),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=4, expand=True),
                ft.Column([
                    ft.Container(
                        width=48, height=44, border_radius=22, alignment=ORTA,
                        ink=True, on_click=sayac_oynat_duraklat,
                        content=resim_olustur(sag_avatar_svg, width=48, height=42, fit=FIT.CONTAIN if FIT else None),
                    ),
                    zm["oda_bugun_txt"],
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=16,
        )

        # 2) KÜTÜPHANE MASALARI GRİDİ (Aktif çalışanlar renkli ve parlak, çalışmayanlar soluk renkli)
        ekran_gen = int(page.width or 400)
        sutun_sayisi = 4 if ekran_gen >= 480 else 3
        soluk_renk = opak(0.45, r["muted"])

        masa_kutulari = []
        for u in sirali_uyeler:
            aktif_mi = bool(u.get("calisiyor"))
            ben_mi = bool(u.get("ben"))
            # Aktif çalışan öğrenci kronometredeki süresini / bugünkü toplam çalışma süresini canlı gösterir
            gosterilen_sn = int(u.get("sn") or 0)
            if aktif_mi and int(u.get("oturum_sn") or 0) > gosterilen_sn:
                gosterilen_sn = int(u["oturum_sn"])

            if aktif_mi:
                svg_kod = masa_svg_b64_olustur("calisiyor_avatar", renk_hex=r["accent"], vurgu_hex=r["hdr"])
                isim_renk = r["hdr"]
                sure_renk = r["hdr"]
                kutu_bg = opak(0.14, r["hdr"])
                kutu_kenar = kenar(2, r["hdr"])
            else:
                svg_kod = masa_svg_b64_olustur(
                    "bos",
                    renk_hex=soluk_renk,
                    vurgu_hex=soluk_renk,
                    saat_rozet=(gosterilen_sn > 0),
                )
                isim_renk = r["muted"]
                sure_renk = opak(0.65, r["muted"])
                kutu_bg = opak(0.45, r["bg"])
                kutu_kenar = kenar(1, opak(0.45, r["border"]))

            masa_kutulari.append(ft.Container(
                expand=True,
                padding=pad_sim(horizontal=6, vertical=10),
                border_radius=16,
                bgcolor=kutu_bg,
                border=kutu_kenar,
                ink=True,
                on_click=uye_masa_tikla(u),
                content=ft.Column([
                    resim_olustur(svg_kod, width=58, height=46, fit=FIT.CONTAIN if FIT else None),
                    ft.Text(
                        f"{u['ad']} (Sen)" if ben_mi else str(u["ad"]),
                        size=12,
                        weight=ft.FontWeight.W_800 if aktif_mi else ft.FontWeight.W_500,
                        color=isim_renk,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                    ),
                    ft.Text(
                        oda_sure_metni(gosterilen_sn),
                        size=11,
                        weight=ft.FontWeight.W_800 if aktif_mi else ft.FontWeight.W_600,
                        color=sure_renk,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        padding=pad_sim(horizontal=6, vertical=2),
                        border_radius=8,
                        bgcolor=opak(0.18, r["hdr"]) if aktif_mi else SEFFAF,
                        content=ft.Text(
                            "🔥 Çalışıyor" if aktif_mi else "⏸ Molada",
                            size=9,
                            weight=ft.FontWeight.W_700,
                            color=r["hdr"] if aktif_mi else soluk_renk,
                        ),
                    ),
                ], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ))

        grid_satirlari = []
        for i in range(0, len(masa_kutulari), sutun_sayisi):
            dilim = list(masa_kutulari[i:i + sutun_sayisi])
            while len(dilim) < sutun_sayisi:
                dilim.append(ft.Container(expand=True))
            grid_satirlari.append(ft.Row(dilim, spacing=8))

        secili_uye = ui.get("oda_secili_uye")
        secili_uye_bandi = []
        if isinstance(secili_uye, dict) and secili_uye.get("ad"):
            secili_uye_bandi.append(ft.Container(
                padding=pad_sim(horizontal=12, vertical=8),
                border_radius=14,
                bgcolor=opak(0.12, r["hdr"]),
                border=kenar(1, r["hdr"]),
                content=ft.Row([
                    ft.Text("📚", size=16),
                    ft.Text(
                        f"{secili_uye['ad']} • Bugün: {oda_sure_metni(secili_uye.get('sn', 0))} • "
                        f"{'🔥 Şu an çalışıyor' if secili_uye.get('calisiyor') else '⏸ Şu an çalışmıyor'} ({secili_uye.get('ders', 'YKS')})",
                        size=12, weight=ft.FontWeight.W_700, color=r["txt"], expand=True,
                    ),
                ], spacing=8),
            ))

        oda_govde_karti = kart(
            r,
            ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("📚 Kütüphane", size=17, weight=ft.FontWeight.W_800, color=r["txt"]),
                        ft.Row([
                            ft.Text(f"{calisan_sayisi} kişi", size=12, weight=ft.FontWeight.W_800, color=r["hdr"]),
                            ft.Text(f"Çalışıyor • Toplam {len(sirali_uyeler)} öğrenci", size=12, weight=ft.FontWeight.W_600, color=r["muted"]),
                        ], spacing=4),
                    ], spacing=2, expand=True),
                    ft.IconButton(
                        icon=ik("REFRESH"),
                        icon_color=r["hdr"],
                        icon_size=20,
                        tooltip="Kütüphaneyi Yenile 🔄",
                        on_click=lambda e: (canli_calisma_odasi_cek(zorla=True, senkron=False), snack("🔄 Kütüphane verileri yenileniyor...")),
                    ),
                ]),
                *secili_uye_bandi,
                ft.Column(grid_satirlari, spacing=10),
                ft.Row([
                    buton(
                        r,
                        "⏸ Çalışmayı Duraklat" if ben_aktif else "▶ Masana Otur & Kronometreyi Başlat",
                        sayac_oynat_duraklat,
                        ikincil=ben_aktif,
                        genis=True,
                        yukseklik=42,
                    ),
                ]),
            ], spacing=14),
            padding=18,
        )

        return ft.Column([
            sayfa_basligi(r, "Kütüphane", "Öğrencilerin canlı çalışma masaları ve anlık süreleri"),
            ust_sekme_cubugu,
            ust_odak_bari,
            oda_govde_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    def calisma_sayfasi_olustur(r):
        aktif_calis_tab = int(ui.get("calis_tab") or 0)

        def calis_sekme_sec(idx):
            ui["calis_tab"] = idx
            if idx == 1:
                canli_calisma_odasi_cek(zorla=False, senkron=False)
            yenile()

        ust_sekme_cubugu = segment(
            r,
            ["⏱ Sayaç & Pomodoro", "📚 Kütüphane", "📅 Haftalık Plan"],
            aktif_calis_tab if aktif_calis_tab in (0, 1, 2) else 0,
            calis_sekme_sec,
        )

        # Haftalık Plan alt görünümü (indeks 2)
        if aktif_calis_tab == 2:
            plan_col = plan_sayfasi_olustur(r)
            return ft.Column([
                sayfa_basligi(r, "Haftalık Plan", "Görevlerini planla, ana sayfana yansısın"),
                ust_sekme_cubugu,
                *plan_col.controls[1:],
            ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

        durum = zm["durum"]
        ders_secenekleri = ["Sözel (Karbonhidrat)", "Matematik (Protein)", "Fen & Deneme (Vitamin)"]
        if ui["pomo_ders_kat"] not in ders_secenekleri:
            ui["pomo_ders_kat"] = "Matematik (Protein)"

        def mod_sec(mod):
            def f(e):
                if zm["durum"] == "bos":
                    zm["mod"] = mod
                    yenile()
                else:
                    snack("⏱ Sayaç çalışırken mod değiştirmek için önce sayacı bitir veya sıfırla.")
            return f

        def ders_kat_sec(kat_deger):
            def f(e):
                ui["pomo_ders_kat"] = kat_deger
                yenile()
            return f

        def baslat(e):
            bugun_t = bugun_str()
            bugun_paylasildi_mi = (DB.get("gun") or {}).get("paylasim_yapildi") == bugun_t
            # Fotoğraf koymak zorunlu: Bugün henüz ders başlangıç fotoğrafı paylaşılmadıysa kronometreyi BAŞLATMA, önce fotoğraf ekranını aç!
            if not bugun_paylasildi_mi:
                ui["ilk_ders_paylasim_acik"] = True
                sosyal["foto_mesaj"] = ""
                yenile()
                snack("📸 Derse başlamak için önce ders başlangıç fotoğrafını yüklemelisin!")
                return
            gun_baslangicini_kaydet()
            simdi_ts = time.time()
            zm.update({"durum": "calisiyor", "birikmis": 0.0, "t0": simdi_ts, "son_kayit": 0, "son_su_saat": 0, "bildirildi": False})
            aktif_sayac_kaydet()
            soz = evcil_motor.pomodoro_basladi(ui["pomo_ders_kat"])
            evcil_ui["mesaj"] = soz
            yenile()
            tik_baslat()
            evcil_konustur(soz)

        def duraklat(e):
            if zm["t0"] is not None:
                zm["birikmis"] += max(0.0, time.time() - float(zm["t0"]))
            zm.update({"durum": "durakladi", "t0": None})
            eklenen_fark = sayac_farkini_ekle()
            aktif_sayac_kaydet()
            yenile()
            if eklenen_fark > 0:
                snack(f"⏸ Duraklatıldı: Aradaki {sn_metni(eklenen_fark)} fark çalışma saatine eklendi!")

        def devam(e):
            zm.update({"durum": "calisiyor", "t0": time.time()})
            aktif_sayac_kaydet()
            evcil_motor.pomodoro_basladi(ui["pomo_ders_kat"])
            yenile()
            tik_baslat()

        def bitir(e):
            eklenen = krono_bitir_kaydet()
            ui["ilk_ders_paylasim_acik"] = False
            if eklenen >= 300:
                evcil_motor.kullanici_ayarla(kullanici_adi())
                dk = eklenen // 60
                mola_soz = evcil_motor.pomodoro_molasi(dakika=dk, ders_adi=ui["pomo_ders_kat"])
                evcil_ui["mesaj"] = mola_soz
                evcil_postaci_kontrol_et()
                yenile()
                snack(f"🎉 {sn_metni(eklenen)} çalışma kaydedildi! 🪙 Altın ve XP kazandın!")
            elif eklenen > 0:
                yenile()
                snack(f"⏱ {sn_metni(eklenen)} çalışma sürene eklendi! (🪙 Altın kazanmak için en az 5 dakika odaklanmalısın)")
            else:
                yenile()
                snack("Süre 0 olduğu için kayıt eklenmedi.")

        def sifirla(e):
            ceza_soz = evcil_motor.pomodoro_bozuldu()
            evcil_ui["mesaj"] = ceza_soz
            zm.update({"durum": "bos", "birikmis": 0.0, "t0": None, "son_kayit": 0, "son_su_saat": 0, "bildirildi": False})
            ui["ilk_ders_paylasim_acik"] = False
            aktif_sayac_kaydet()
            snack("💥 Kronometre yarıda kesildi! Yoldaşının kafasına silgi düştü 🥺")
            yenile()
            evcil_konustur(ceza_soz)

        # Canlı Çalışma Odası (indeks 1 — Resimdeki YKSPROMAXXX etüt odası görünümü)
        if aktif_calis_tab == 1 and not ui.get("ilk_ders_paylasim_acik"):
            return canli_calisma_odasi_olustur(r, ust_sekme_cubugu, baslat, duraklat, devam)

        # Kalıcı sayaç metni ve halkasını yerinde güncelle (yeni nesne yaratılmaz, böylece canlı tik asla kopmaz!)
        zm["label"].value = zaman_metni()
        zm["label"].color = r["txt"]
        zm["ring"].value = halka_degeri()
        zm["ring"].color = r["hdr"]
        zm["ring"].bgcolor = opak(0.15, r["muted"])
        zm["ust_rozet_txt"].value = f"⏱ {zaman_metni()}"
        zm["ust_rozet_txt"].color = r["hdr"]

        durum_yazi = {"bos": "Odaklanmaya Hazır", "calisiyor": "Çalışıyorsun 🔥", "durakladi": "Duraklatıldı ⏸"}[durum]
        zm["durum_txt"].value = durum_yazi
        zm["durum_txt"].color = r["muted"]

        # Günün ilk dersi paylaşım ekranı açıksa doğrudan en üstte tam ekran kart olarak göster
        if ui.get("ilk_ders_paylasim_acik"):
            sayac_bekliyor_mu = (zm["durum"] == "bos")
            canli_sayac_bandi = kart(r, ft.Row([
                ft.Icon(ik("ADD_PHOTO_ALTERNATE") if sayac_bekliyor_mu else ik("TIMER"), color=r["hdr"], size=22),
                ft.Column([
                    ft.Text(
                        "Fotoğraf Zorunlu: Paylaşınca Kronometre Başlayacak 📸" if sayac_bekliyor_mu else "Kronometre Arka Planda Çalışıyor 🔥",
                        size=13, weight=ft.FontWeight.W_800, color=r["txt"],
                    ),
                    ft.Text(
                        "Ders fotoğrafını seçip paylaşmadan kronometre başlamaz" if sayac_bekliyor_mu else "Paylaşımını tamamla veya sayaca dön",
                        size=11, color=r["muted"],
                    ),
                ], spacing=1, expand=True),
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=6), border_radius=12, bgcolor=opak(0.15, r["hdr"]),
                    content=zm["ust_rozet_txt"],
                ),
            ], spacing=10), padding=12)
            return ft.Column([
                sayfa_basligi(r, "İlk Ders Paylaşımı 📸", "Derse başlamak için fotoğrafını ekle ve paylaş"),
                canli_sayac_bandi,
                ilk_ders_paylasim_karti_olustur(
                    r,
                    kapat_fn=lambda e: (ui.update({"ilk_ders_paylasim_acik": False}), yenile()),
                    sayac_bekliyor=sayac_bekliyor_mu,
                ),
                ft.Container(height=24),
            ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

        daire = ft.Stack([
            ft.Container(content=zm["ring"], width=230, height=230, alignment=ORTA),
            ft.Container(
                width=230, height=230, alignment=ORTA,
                content=ft.Column([
                    zm["label"],
                    zm["durum_txt"],
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            ),
        ], width=230, height=230)

        bugun_paylasildi_mi = (DB.get("gun") or {}).get("paylasim_yapildi") == bugun_str()
        paylasim_hatirlatma_btn = []
        if not bugun_paylasildi_mi and (durum != "bos" or (DB.get("gun") or {}).get("tarih") == bugun_str()):
            paylasim_hatirlatma_btn.append(
                buton(
                    r,
                    "📸 Bugünün Ders Başlangıç Paylaşımını Yap",
                    lambda e: (ui.update({"ilk_ders_paylasim_acik": True}), yenile()),
                    ikon=ik("ADD_PHOTO_ALTERNATE"),
                    ikincil=True,
                    genis=True,
                    yukseklik=42,
                )
            )

        if durum == "bos":
            butonlar = ft.Column([
                buton(r, "Kronometreyi Başlat" if zm["mod"] == "krono" else "25 Dk Pomodoro Başlat", baslat,
                      ikon=ik("PLAY_ARROW"), genis=True, yukseklik=52),
                *paylasim_hatirlatma_btn,
            ], spacing=8)
        else:
            ana_btn = (buton(r, "Duraklat", duraklat, ikon=ik("PAUSE"), genis=True, ikincil=True, yukseklik=48)
                       if durum == "calisiyor" else
                       buton(r, "Devam Et", devam, ikon=ik("PLAY_ARROW"), genis=True, ikincil=True, yukseklik=48))
            butonlar = ft.Column([
                ft.Row([
                    ana_btn,
                    buton(r, "Bitir & Kaydet 🪙", bitir, ikon=ik("STOP_CIRCLE"), genis=True, yukseklik=48),
                ], spacing=8),
                *paylasim_hatirlatma_btn,
                metin_dugmesi("Kaydetmeden sıfırla (Yoldaş üzülür 🥺)", on_click=sifirla, style=ft.ButtonStyle(color=r["muted"])),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)

        # Sayaç kartının içine entegre kompakt mod seçici (Serbest Kronometre vs 25 Dk Pomodoro)
        krono_aktif = (zm["mod"] == "krono")
        kompakt_mod_secici = ft.Container(
            padding=4, border_radius=20, bgcolor=r["bg"], border=kenar(1, r["border"]),
            content=ft.Row([
                ft.Container(
                    padding=pad_sim(horizontal=14, vertical=7), border_radius=16, ink=True,
                    on_click=mod_sec("krono"),
                    bgcolor=r["hdr"] if krono_aktif else SEFFAF,
                    content=ft.Text("⏱ Kronometre", size=12, weight=ft.FontWeight.W_800,
                                    color=okunur_renk(r["hdr"]) if krono_aktif else r["muted"]),
                ),
                ft.Container(
                    padding=pad_sim(horizontal=14, vertical=7), border_radius=16, ink=True,
                    on_click=mod_sec("pomo"),
                    bgcolor=r["hdr"] if not krono_aktif else SEFFAF,
                    content=ft.Text("🍅 Pomodoro (25 dk)", size=12, weight=ft.FontWeight.W_800,
                                    color=okunur_renk(r["hdr"]) if not krono_aktif else r["muted"]),
                ),
            ], spacing=4, tight=True, alignment=ft.MainAxisAlignment.CENTER),
        )

        # Co-Op Pomodoro Yoldaş Kartı (Odak Dersi Rozetleri Kartın İçine Entegre Edildi)
        evcil_motor.kullanici_ayarla(kullanici_adi())
        st = evcil_motor.durum_oku()
        balon_txt = ft.Text(f"💬 \"{evcil_ui['mesaj']}\"", size=12, italic=True, color=r["txt"])
        evcil_ui["balon_txt"] = balon_txt

        def pomo_karakter_tikla(e):
            gece_mi = datetime.now().hour >= 23 or datetime.now().hour < 7
            tepki = evcil_motor.pomodoro_tikla_tepki(calisiyor_mu=(zm["durum"] == "calisiyor"), gece_mi=gece_mi)
            evcil_konustur(tepki)
            if zm["durum"] == "calisiyor":
                snack("🤓 Şşşt! Yoldaşın şu an soru çözüyor, dikkatini dağıtma!")

        ders_etiket_haritasi = [
            ("Sözel (Karbonhidrat)", "🥐 Sözel", "#FB8C00", st["karbonhidrat"]),
            ("Matematik (Protein)", "🥩 Sayısal", "#1E88E5", st["protein"]),
            ("Fen & Deneme (Vitamin)", "🍊 Fen/Deneme", "#43A047", st["vitamin"]),
        ]
        odak_ders_cipleri = []
        for kat_tam, kisa_ad, renk_kod, besin_yuzde in ders_etiket_haritasi:
            secili_mi = (ui["pomo_ders_kat"] == kat_tam)
            odak_ders_cipleri.append(ft.Container(
                padding=pad_sim(horizontal=9, vertical=5),
                border_radius=14,
                ink=True,
                on_click=ders_kat_sec(kat_tam),
                bgcolor=opak(0.22, renk_kod) if secili_mi else r["bg"],
                border=kenar(2 if secili_mi else 1, renk_kod if secili_mi else r["border"]),
                content=ft.Row([
                    ft.Text(f"{kisa_ad} (%{besin_yuzde:.0f})", size=11,
                            weight=ft.FontWeight.W_800 if secili_mi else ft.FontWeight.W_600,
                            color=renk_kod if secili_mi else r["txt"]),
                ], spacing=4, tight=True),
            ))

        coop_karti = kart(r, ft.Column([
            ft.Row([
                evcil_karakter_gorseli(r, st, boyut=80, tikla_fn=pomo_karakter_tikla),
                ft.Column([
                    ft.Row([
                        ft.Text(f"🐾 {st['isim']} (Çalışma Yoldaşın)", size=13, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                        ft.Container(
                            padding=pad_sim(horizontal=8, vertical=3), border_radius=10, bgcolor=opak(0.16, r["accent"]),
                            content=ft.Text(f"🪙 {st['altin']} • 💖 %{st['mutluluk']:.0f}", size=11, weight=ft.FontWeight.W_800, color=r["txt"]),
                        ),
                    ]),
                    ft.Container(padding=8, border_radius=12, bgcolor=r["bg"], border=kenar(1, r["border"]), content=balon_txt),
                    ft.Row([
                        ft.Text("🎯 Odak:", size=11, weight=ft.FontWeight.W_700, color=r["muted"]),
                        *odak_ders_cipleri,
                    ], wrap=True, spacing=6, run_spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=6, expand=True),
            ], spacing=10),
        ], spacing=8), padding=12)

        sayac_karti = kart(r, ft.Column([
            ft.Row([kompakt_mod_secici], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(content=daire, alignment=ORTA, padding=pad_sim(vertical=4)),
            butonlar,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12), padding=16)

        baslama = DB["gun"]["baslama"] if DB["gun"].get("tarih") == bugun_str() else "—"
        canli_ek = canli_eklenmemis_sn()
        zm["bugun_txt"].value = sn_metni(gun_sn(bugun_str()) + canli_ek)
        zm["bugun_txt"].color = r["hdr"]
        zm["toplam_txt"].value = sn_metni(toplam_sn() + canli_ek)
        zm["toplam_txt"].color = r["txt"]
        bugun_karti = kart(r, ft.Row([
            ft.Column([ft.Text("Bugün", size=12, color=r["muted"]), zm["bugun_txt"]],
                      spacing=2, expand=True),
            ft.Column([ft.Text("Başlama saati", size=12, color=r["muted"]),
                       ft.Text(baslama, size=18, weight=ft.FontWeight.W_800, color=r["txt"])],
                      spacing=2, expand=True),
            ft.Column([ft.Text("Toplam", size=12, color=r["muted"]), zm["toplam_txt"]],
                      spacing=2, expand=True),
        ]), padding=14)

        return ft.Column([
            sayfa_basligi(r, "Çalışma İstasyonu", "Yoldaşın ve arkadaşlarınla birlikte odaklan"),
            ust_sekme_cubugu,
            coop_karti,
            sayac_karti,
            bugun_karti,
            ft.Container(height=24),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 9. NETLER, SVG GRAFİK & EXCEL (.XLSX) RAPORU, DENEME SİLME & FARKLI HESABA KOPYALAMA
    # ==========================================
    def excel_olustur_islem(kayitlar, sinav_adi="TYT", oto_ac=True):
        """Hem PC hem Mobil için 5 grafikli Excel (.xlsx) tablosu oluşturur, kaydeder ve indirme bağlantısı üretir."""
        kul = kullanici_adi() or "Ogrenci"
        sonuc = deneme_excel_disa_aktar(kayitlar, kullanici_adi=kul, sinav_adi=sinav_adi, oto_ac=oto_ac)
        ui["son_excel_bilgi"] = sonuc
        return sonuc

    def deneme_sil_islem(indeksler):
        """Verilen indeks (int) veya indeks kümesindeki denemeleri DB['netler'] içinden siler."""
        if isinstance(indeksler, int):
            sil_set = {indeksler}
        else:
            sil_set = {int(i) for i in (indeksler or []) if isinstance(i, int) or str(i).isdigit()}
        if not sil_set:
            return 0
        mevcut = list(DB.get("netler") or [])
        yeni_liste = [k for idx, k in enumerate(mevcut) if idx not in sil_set]
        silinen_sayi = len(mevcut) - len(yeni_liste)
        if silinen_sayi > 0:
            DB["netler"] = yeni_liste
            ui["secili_netler"] = set()
            kaydet("netler")
        return silinen_sayi

    def deneme_duzenle_islem(indeks, yeni_ad=None, yeni_tarih=None, yeni_sinav=None, tr=None, sos=None, mat=None, fen=None):
        """Verilen indeksteki denemenin adını, tarihini, sınav türünü ve ders netlerini günceller."""
        mevcut = list(DB.get("netler") or [])
        idx = int(indeks)
        if not (0 <= idx < len(mevcut)):
            return False, "Düzenlenecek deneme bulunamadı."
        eski = deneme_satiri_ayristir(mevcut[idx])
        eski_sinav = str((mevcut[idx] or {}).get("sinav") or "TYT").upper()
        ad_v = (str(yeni_ad).strip() if yeni_ad is not None else eski["ad"]) or eski["ad"]
        tarih_v = (str(yeni_tarih).strip() if yeni_tarih is not None else eski["tarih"]) or eski["tarih"]
        sinav_v = (str(yeni_sinav).strip().upper() if yeni_sinav is not None else eski_sinav) or "TYT"
        if sinav_v not in ("TYT", "AYT"):
            sinav_v = "TYT"
        tr_v = round(sayi(tr, eski["tr"]), 2) if tr is not None else eski["tr"]
        sos_v = round(sayi(sos, eski["sos"]), 2) if sos is not None else eski["sos"]
        mat_v = round(sayi(mat, eski["mat"]), 2) if mat is not None else eski["mat"]
        fen_v = round(sayi(fen, eski["fen"]), 2) if fen is not None else eski["fen"]
        toplam_v = round(tr_v + sos_v + mat_v + fen_v, 2)
        guncel = {
            "ad": ad_v,
            "tarih": tarih_v,
            "sinav": sinav_v,
            "tr": tr_v,
            "sos": sos_v,
            "mat": mat_v,
            "fen": fen_v,
            "dersler": {"Türkçe": tr_v, "Sosyal": sos_v, "Matematik": mat_v, "Fen": fen_v},
            "toplam": toplam_v,
        }
        DB["netler"][idx] = guncel
        ui["duzenlenen_net_idx"] = None
        kaydet("netler")
        return True, f"✅ '{ad_v}' denemesi güncellendi! (Yeni Toplam: {toplam_v:.2f} Net)"

    def denemeleri_baska_hesaba_kopyala_islem(hedef_kullanici, indeksler=None, sinav_filtresi=None, senkron=True, kaynak_kullanici=None):
        """Arda'nın Paneli üzerinden kaynak hesaptaki seçili (veya filtrelenen) deneme netlerini buluttaki
        farklı bir kullanıcı hesabına kopyalar. Döndürür: (basarili_mi, mesaj, kopyalanan_adet)
        """
        hedef = (hedef_kullanici or "").strip().lower()
        kaynak = (kaynak_kullanici or kullanici_adi() or "").strip().lower()
        if not hedef:
            return False, "Lütfen kopyalanacak hedef kullanıcı adını seç veya yaz.", 0
        if hedef == kaynak:
            return False, "Denemeler zaten bu hesapta kayıtlı! Farklı bir hedef kullanıcı adı seç.", 0

        if kaynak_kullanici and kaynak != (kullanici_adi() or "").strip().lower():
            kaynak_veri = (panel.get("veri") or {}).get(kaynak)
            if not isinstance(kaynak_veri, dict):
                try:
                    kaynak_veri = bulut_oku(kaynak) or {}
                except Exception:
                    kaynak_veri = {}
            mevcut = listeye(kaynak_veri.get("netler"))
        else:
            mevcut = list(DB.get("netler") or [])

        if indeksler:
            sec_set = {int(i) for i in indeksler if 0 <= int(i) < len(mevcut)}
            kaynak_denemeler = [copy.deepcopy(mevcut[i]) for i in sorted(sec_set)]
        elif sinav_filtresi:
            kaynak_denemeler = [copy.deepcopy(k) for k in mevcut if k.get("sinav", "TYT") == sinav_filtresi]
        else:
            kaynak_denemeler = [copy.deepcopy(k) for k in mevcut]

        if not kaynak_denemeler:
            return False, "Kopyalanacak deneme bulunamadı.", 0

        def _kopyala():
            try:
                hedef_veri = bulut_oku(hedef)
                if hedef_veri is None:
                    return False, f"'{hedef}' adlı kullanıcı bulutta bulunamadı!", 0
                hedef_netler = listeye(hedef_veri.get("netler"))
                eklenen = 0
                for d in kaynak_denemeler:
                    hedef_netler.append(copy.deepcopy(d))
                    eklenen += 1
                bulut_patch(f"users/{hedef}", {"netler": hedef_netler})
                if isinstance(panel.get("veri"), dict) and hedef in panel["veri"] and isinstance(panel["veri"][hedef], dict):
                    panel["veri"][hedef]["netler"] = hedef_netler
                if hedef == (kullanici_adi() or "").strip().lower():
                    DB["netler"] = hedef_netler
                    yerel_yaz()
                return True, f"✅ {eklenen} deneme '{hedef}' hesabına başarıyla kopyalandı!", eklenen
            except Exception as ex:
                return False, f"⚠️ Kopyalama hatası: {ex}", 0

        if senkron:
            return _kopyala()

        def _arka():
            ok, msg, _ = _kopyala()
            snack(msg)
            if ok:
                ui["panel_secili_netler"] = set()
                yenile()
        arka_plan(_arka)
        return True, "Kopyalanıyor...", len(kaynak_denemeler)

    def net_grafigi(r, kayitlar, indeksli_kayitlar=None):
        n = len(kayitlar)
        if n == 0:
            return ft.Text("Henüz deneme eklenmemiş.", color=r["muted"], italic=True)

        secili_sinav = ui.get("net_sinav", "TYT")
        kul_ad = kullanici_adi() or "ÖĞRENCİ"
        svg_b64 = net_svg_grafik_olustur(kayitlar, r, sinav_adi=secili_sinav, kullanici=kul_ad)
        genislik = max(320, int((page.width or 400) - 48))
        yukseklik = int(genislik * 0.72)

        def grafige_tiklandi(e):
            sonuc = excel_olustur_islem(kayitlar, sinav_adi=secili_sinav, oto_ac=True)
            yenile()
            snack(f"📊 {sonuc['dosya_adi']} oluşturuldu! ({sonuc['yol']})")

        def tarayicidan_indir(e):
            sonuc = ui.get("son_excel_bilgi") or excel_olustur_islem(kayitlar, sinav_adi=secili_sinav, oto_ac=False)
            if sonuc.get("indir_url"):
                url_ac(sonuc["indir_url"])
                snack(f"📱 {sonuc['dosya_adi']} indiriliyor...")
            else:
                snack(f"📁 Dosya kaydedildi: {sonuc.get('yol')}")

        grafik_kutu = ft.Container(
            border_radius=16,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border=kenar(2, r["hdr"]),
            ink=True,
            on_click=grafige_tiklandi,
            tooltip="📊 Excel Tablosu (.xlsx) Oluşturmak İçin Grafiğe Tıkla!",
            content=resim_olustur(svg_b64, width=genislik, height=yukseklik, fit=FIT.CONTAIN if FIT else None),
        )

        excel_btn = buton(
            r,
            f"📊 Grafiğe Bas / {tr_buyuk(kul_ad)} {secili_sinav} Excel Tablosu Oluştur (.xlsx)",
            grafige_tiklandi,
            ikon=ik("TABLE_CHART"),
            genis=True,
            yukseklik=48,
        )

        son_excel = ui.get("son_excel_bilgi")
        excel_bilgi_karti = []
        if isinstance(son_excel, dict) and son_excel.get("dosya_adi"):
            excel_bilgi_karti.append(ft.Container(
                padding=12, border_radius=14, bgcolor=opak(0.14, r["hdr"]), border=kenar(1.5, r["hdr"]),
                content=ft.Column([
                    ft.Text(f"✅ Excel Hazır: {son_excel['dosya_adi']}", size=13, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    ft.Text(f"📁 Kayıt Yeri: {son_excel['yol']}", size=11, color=r["txt"], selectable=True),
                    ft.Row([
                        buton(r, "📱 Telefona / Tarayıcıdan İndir", tarayicidan_indir, ikon=ik("DOWNLOAD"), genis=True, yukseklik=40),
                        buton(r, "💻 PC'de Aç", grafige_tiklandi, ikon=ik("OPEN_IN_NEW"), ikincil=True, genis=True, yukseklik=40),
                    ], spacing=8),
                ], spacing=6),
            ))

        # --- DENEME DÜZENLEME & SİLME YÖNETİMİ (Kopyalama işlemi yalnızca Arda'nın Paneli'ndedir) ---
        if indeksli_kayitlar is None:
            indeksli_kayitlar = [(idx, k) for idx, k in enumerate(DB["netler"]) if k.get("sinav", "TYT") == secili_sinav]
        gorunen_indeksler = [idx for idx, _ in indeksli_kayitlar]
        secili_set = ui.setdefault("secili_netler", set())
        secili_gorunen = [idx for idx in gorunen_indeksler if idx in secili_set]

        def tumunu_sec_degistir(e):
            if len(secili_gorunen) == len(gorunen_indeksler):
                for idx in gorunen_indeksler:
                    secili_set.discard(idx)
            else:
                for idx in gorunen_indeksler:
                    secili_set.add(idx)
            yenile()

        def tek_sec_degistir(gercek_idx):
            def f(e):
                if e.control.value:
                    secili_set.add(gercek_idx)
                else:
                    secili_set.discard(gercek_idx)
                yenile()
            return f

        def tek_deneme_sil(gercek_idx, ad_str):
            def f(e):
                if deneme_sil_islem(gercek_idx) > 0:
                    if ui.get("duzenlenen_net_idx") == gercek_idx:
                        ui["duzenlenen_net_idx"] = None
                    yenile()
                    snack(f"🗑 '{ad_str}' denemesi silindi.")
            return f

        def secili_denemeleri_sil(e):
            adet = deneme_sil_islem(secili_gorunen)
            if adet > 0:
                ui["duzenlenen_net_idx"] = None
                yenile()
                snack(f"🗑 Seçilen {adet} deneme silindi.")

        def tek_deneme_duzenle_ac(gercek_idx):
            def f(e):
                if ui.get("duzenlenen_net_idx") == gercek_idx:
                    ui["duzenlenen_net_idx"] = None
                else:
                    ui["duzenlenen_net_idx"] = gercek_idx
                yenile()
            return f

        hepsi_secili_mi = (len(secili_gorunen) == len(gorunen_indeksler) and len(gorunen_indeksler) > 0)
        yonetim_butonlari = [
            ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=12, ink=True,
                on_click=tumunu_sec_degistir,
                bgcolor=opak(0.16, r["hdr"]) if hepsi_secili_mi else r["bg"],
                border=kenar(1, r["hdr"] if hepsi_secili_mi else r["border"]),
                content=ft.Text("☑️ Seçimi Kaldır" if hepsi_secili_mi else "☑️ Tümünü Seç",
                                size=11, weight=ft.FontWeight.W_700, color=r["hdr"] if hepsi_secili_mi else r["txt"]),
            ),
        ]
        if secili_gorunen:
            yonetim_butonlari.append(ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=12, ink=True,
                on_click=secili_denemeleri_sil,
                bgcolor=opak(0.16, KIRMIZI), border=kenar(1, KIRMIZI),
                content=ft.Text(f"🗑 Seçilenleri Sil ({len(secili_gorunen)})", size=11, weight=ft.FontWeight.W_800, color=KIRMIZI),
            ))

        duzenleme_karti = []
        duz_idx = ui.get("duzenlenen_net_idx")
        if isinstance(duz_idx, int) and 0 <= duz_idx < len(DB["netler"]):
            mevcut_d = deneme_satiri_ayristir(DB["netler"][duz_idx])
            mevcut_sinav = str((DB["netler"][duz_idx] or {}).get("sinav") or "TYT").upper()
            duz_ad_in = girdi(r, label="Deneme Adı", value=mevcut_d["ad"], expand=True)
            duz_tarih_in = girdi(r, label="Tarih", value=mevcut_d["tarih"], width=130)
            duz_sinav_radyo = ft.RadioGroup(
                value=mevcut_sinav,
                content=ft.Row([
                    ft.Radio(value="TYT", label="TYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
                    ft.Radio(value="AYT", label="AYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
                ]),
            )
            duz_tr_in = girdi(r, label="Türkçe / Edb", value=f"{mevcut_d['tr']:g}", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            duz_sos_in = girdi(r, label="Sosyal", value=f"{mevcut_d['sos']:g}", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            duz_mat_in = girdi(r, label="Matematik", value=f"{mevcut_d['mat']:g}", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            duz_fen_in = girdi(r, label="Fen", value=f"{mevcut_d['fen']:g}", keyboard_type=ft.KeyboardType.NUMBER, expand=True)

            def duzenleme_kaydet_tikla(e):
                ok, msg = deneme_duzenle_islem(
                    duz_idx,
                    yeni_ad=duz_ad_in.value,
                    yeni_tarih=duz_tarih_in.value,
                    yeni_sinav=duz_sinav_radyo.value,
                    tr=duz_tr_in.value,
                    sos=duz_sos_in.value,
                    mat=duz_mat_in.value,
                    fen=duz_fen_in.value,
                )
                snack(msg)
                if ok:
                    yenile()

            def duzenleme_iptal_tikla(e):
                ui["duzenlenen_net_idx"] = None
                yenile()

            duzenleme_karti.append(ft.Container(
                padding=14, border_radius=16, bgcolor=opak(0.10, r["hdr"]), border=kenar(1.5, r["hdr"]),
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"✏️ Deneme Netlerini Düzenle: {mevcut_d['ad']}", size=14, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                        buton(r, "✕ Vazgeç", duzenleme_iptal_tikla, ikincil=True, yukseklik=32),
                    ]),
                    ft.Row([duz_ad_in, duz_tarih_in], spacing=8),
                    duz_sinav_radyo,
                    ft.Row([duz_tr_in, duz_sos_in], spacing=8),
                    ft.Row([duz_mat_in, duz_fen_in], spacing=8),
                    buton(r, "💾 Değişiklikleri Kaydet", duzenleme_kaydet_tikla, genis=True, yukseklik=42),
                ], spacing=8),
            ))

        satir_listesi = []
        for gercek_idx, k in reversed(indeksli_kayitlar):
            d_s = deneme_satiri_ayristir(k)
            isaretli = gercek_idx in secili_set
            duzenleniyor_mu = (ui.get("duzenlenen_net_idx") == gercek_idx)
            satir_listesi.append(ft.Container(
                padding=pad_sim(horizontal=8, vertical=6), border_radius=14,
                bgcolor=opak(0.12, r["hdr"]) if (isaretli or duzenleniyor_mu) else r["bg"],
                border=kenar(1.5 if (isaretli or duzenleniyor_mu) else 1, r["hdr"] if (isaretli or duzenleniyor_mu) else r["border"]),
                content=ft.Row([
                    ft.Checkbox(
                        value=isaretli,
                        on_change=tek_sec_degistir(gercek_idx),
                        fill_color=r["hdr"],
                        check_color=okunur_renk(r["hdr"]),
                    ),
                    ft.Column([
                        ft.Text(f"{d_s['ad']} ({d_s['tarih']})", size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                        ft.Text(
                            f"Türkçe: {d_s['tr']:g} • Sosyal: {d_s['sos']:g} • Mat: {d_s['mat']:g} • Fen: {d_s['fen']:g}",
                            size=11, color=r["muted"],
                        ),
                    ], spacing=2, expand=True),
                    ft.Container(
                        padding=pad_sim(horizontal=8, vertical=4), border_radius=10, bgcolor=opak(0.16, r["hdr"]),
                        content=ft.Text(f"{d_s['toplam']:.2f}", size=12, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    ),
                    ft.IconButton(
                        icon=ik("EDIT_NOTE"), icon_color=r["hdr"], icon_size=20,
                        tooltip="Bu denemenin netlerini düzenle ✏️",
                        on_click=tek_deneme_duzenle_ac(gercek_idx),
                    ),
                    ft.IconButton(
                        icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, icon_size=20,
                        tooltip="Bu denemeyi sil 🗑",
                        on_click=tek_deneme_sil(gercek_idx, d_s["ad"]),
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ))

        return ft.Column([
            ft.Text("💡 Grafiğin üzerine veya aşağıdaki butona basarak 5 grafikli Excel (.xlsx) tablosu oluşturabilirsin.",
                    size=11, color=r["muted"], italic=True),
            grafik_kutu,
            excel_btn,
            *excel_bilgi_karti,
            ft.Divider(height=6, color=r["border"]),
            ft.Row(yonetim_butonlari, spacing=6),
            *duzenleme_karti,
            *satir_listesi,
        ], spacing=10)

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

        ad_input = girdi(r, label="Deneme Adı (Örn: Bilgi Sarmal)", expand=True)
        tarih_input = girdi(r, label="Tarih", value=bugun_str(), width=130)
        sinav_radyo = ft.RadioGroup(
            value="TYT",
            content=ft.Row([
                ft.Radio(value="TYT", label="TYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
                ft.Radio(value="AYT", label="AYT", fill_color=r["hdr"], label_style=ft.TextStyle(color=r["txt"])),
            ]),
        )
        tr_in = girdi(r, label="Türkçe / Edb", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        sos_in = girdi(r, label="Sosyal", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        mat_in = girdi(r, label="Matematik", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        fen_in = girdi(r, label="Fen", keyboard_type=ft.KeyboardType.NUMBER, expand=True)

        def net_kaydet(e):
            ad = (ad_input.value or "").strip()
            if not ad:
                snack("Önce deneme adını yaz 📝")
                return
            tarih_str = (tarih_input.value or "").strip() or bugun_str()
            tr_, mat_, sos_, fen_ = sayi(tr_in.value), sayi(mat_in.value), sayi(sos_in.value), sayi(fen_in.value)
            toplam_net = round(tr_ + mat_ + sos_ + fen_, 2)
            DB["netler"].append({
                "ad": ad, "tarih": tarih_str, "sinav": sinav_radyo.value,
                "tr": tr_, "sos": sos_, "mat": mat_, "fen": fen_,
                "dersler": {"Türkçe": tr_, "Sosyal": sos_, "Matematik": mat_, "Fen": fen_},
                "toplam": toplam_net,
            })
            kaydet("netler")
            # Deneme kaydıyla 🪙 Altın ve XP kazandır
            evcil_motor.kullanici_ayarla(kullanici_adi())
            odul_bilgi = evcil_motor.besle_ders_ile("Deneme Vitamin", soru_sayisi=max(20, int(toplam_net)), dakika=60)
            if tr_ + sos_ > 0:
                evcil_motor.besle_ders_ile("Türkçe Sözel", soru_sayisi=int(tr_ + sos_), dakika=15)
            if mat_ > 0:
                evcil_motor.besle_ders_ile("Matematik", soru_sayisi=int(mat_), dakika=15)
            evcil_ui["mesaj"] = odul_bilgi["mesaj"]
            evcil_postaci_kontrol_et()
            yonetici_haber(f"📈 {kullanici_adi()} yeni deneme ekledi",
                           f"{ad} ({tarih_str} • {sinav_radyo.value}) • {toplam_net:.2f} net")
            snack(f"Deneme eklendi! ✅ +{odul_bilgi['kazanilan_altin']} 🪙 Altın kazandın!")
            yenile()

        form = kart(r, ft.Column([
            bolum_basligi(r, ik("EDIT_NOTE"), "Yeni Deneme Ekle"),
            ft.Row([ad_input, tarih_input], spacing=10),
            sinav_radyo,
            ft.Row([tr_in, sos_in], spacing=10),
            ft.Row([mat_in, fen_in], spacing=10),
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
            bolum_basligi(r, ik("INSIGHTS"), "Analiz & Excel Tablosu"),
            ft.Row([
                buton(r, "TYT", sinav_sec("TYT"), genis=True, ikincil=secili != "TYT", yukseklik=42),
                buton(r, "AYT", sinav_sec("AYT"), genis=True, ikincil=secili != "AYT", yukseklik=42),
            ], spacing=10),
        ]
        if kayitlar:
            ilk, son = deneme_satiri_ayristir(kayitlar[0]), deneme_satiri_ayristir(kayitlar[-1])
            ders_adlari = [("tr", "Türkçe" if secili == "TYT" else "Edb"), ("sos", "Sosyal"), ("mat", "Mat"), ("fen", "Fen"), ("toplam", "TOPLAM")]
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
            odulluler = DB.setdefault("konu_odul_alindi", [])
            if e.control.value and anahtar not in DB["konu_bitti"]:
                DB["konu_bitti"].append(anahtar)
                if anahtar not in odulluler:
                    odulluler.append(anahtar)
                    besin = evcil_motor.besle_ders_ile(ui["ders"], soru_sayisi=15, dakika=15)
                    evcil_ui["mesaj"] = besin["mesaj"]
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
    def plan_gecmise_ekle(gorev_metni):
        """Haftalık plana eklenen görevi otomatik tamamlama (autocomplete) geçmişine kaydeder."""
        m = str(gorev_metni or "").strip()
        if not m:
            return
        gecmis = listeye(DB.get("plan_gecmis"))
        mevcut_low = {str(x).strip().lower(): str(x).strip() for x in gecmis if str(x).strip()}
        if m.lower() in mevcut_low:
            gecmis = [x for x in gecmis if str(x).strip().lower() != m.lower()]
        gecmis.insert(0, m)
        DB["plan_gecmis"] = gecmis[:150]
        kaydet("plan_gecmis")

    def plan_onerileri_bul(yazilan_metin):
        """Yazılmaya başlanan metne göre daha önce eklenmiş görev önerilerini döndürür."""
        q = str(yazilan_metin or "").strip().lower()
        havuz = []
        gorulen = set()
        for x in listeye(DB.get("plan_gecmis")):
            s = str(x or "").strip()
            if s and s.lower() not in gorulen:
                gorulen.add(s.lower())
                havuz.append(s)
        for g_k in GUNLER:
            for t in (DB.get("plan", {}).get(g_k) or []):
                s = str((t or {}).get("gorev") or "").strip()
                if s and s.lower() not in gorulen:
                    gorulen.add(s.lower())
                    havuz.append(s)
        for g_k in GUNLER:
            for t in (HAFTALIK_PLAN.get(g_k) or []):
                s = str((t or {}).get("gorev") or "").strip()
                if s and s.lower() not in gorulen:
                    gorulen.add(s.lower())
                    havuz.append(s)
        if not q:
            return []
        baslayanlar = [s for s in havuz if s.lower().startswith(q)]
        icerenler = [s for s in havuz if not s.lower().startswith(q) and q in s.lower()]
        return (baslayanlar + icerenler)[:6]

    def haftalik_programi_tamamen_sifirla_islem():
        """Mevcut haftalık programdaki görevleri otomatik tamamlama geçmişine yedekleyip tüm haftayı sıfırlar."""
        gecmis = listeye(DB.get("plan_gecmis"))
        gorulen = {str(x).strip().lower() for x in gecmis if str(x).strip()}
        for g in GUNLER:
            for t in (DB.get("plan", {}).get(g) or []):
                m = str((t or {}).get("gorev") or "").strip()
                if m and m.lower() not in gorulen:
                    gecmis.insert(0, m)
                    gorulen.add(m.lower())
            DB["plan"][g] = []
        DB["plan_gecmis"] = gecmis[:150]
        kaydet("plan")
        kaydet("plan_gecmis")
        return len(DB["plan_gecmis"])

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

        yeni_in = girdi(r, f"{g_ad} gününe görev ekle (Örn: tyt 25 soru)...", expand=True)
        oneri_kutusu = ft.Column(spacing=4)

        def oneri_sec_ve_ekle(secilen_metin):
            def f(e):
                DB["plan"][g_ad].append({"gorev": secilen_metin, "bitti": False})
                plan_gecmise_ekle(secilen_metin)
                kaydet("plan")
                yenile()
                snack(f"✅ '{secilen_metin}' {g_ad} planına eklendi!")
            return f

        def oneri_kutuya_doldur(secilen_metin):
            def f(e):
                yeni_in.value = secilen_metin
                oneri_kutusu.controls.clear()
                try:
                    yeni_in.update()
                    oneri_kutusu.update()
                except Exception:
                    page.update()
            return f

        def yazarken_oneri_guncelle(e):
            metin = (e.control.value or "").strip()
            eslesenler = plan_onerileri_bul(metin)
            oneri_kutusu.controls.clear()
            if eslesenler:
                oneri_satirlari = []
                for o_metin in eslesenler:
                    oneri_satirlari.append(ft.Container(
                        padding=pad_sim(horizontal=10, vertical=7),
                        border_radius=12,
                        bgcolor=opak(0.12, r["hdr"]),
                        border=kenar(1, opak(0.35, r["hdr"])),
                        content=ft.Row([
                            ft.Icon(ik("HISTORY"), color=r["hdr"], size=16),
                            ft.Container(
                                expand=True,
                                ink=True,
                                on_click=oneri_kutuya_doldur(o_metin),
                                content=ft.Text(o_metin, size=13, weight=ft.FontWeight.W_700, color=r["txt"]),
                            ),
                            ft.Container(
                                padding=pad_sim(horizontal=10, vertical=4),
                                border_radius=10,
                                bgcolor=r["hdr"],
                                ink=True,
                                on_click=oneri_sec_ve_ekle(o_metin),
                                content=ft.Text("＋ Ekle", size=11, weight=ft.FontWeight.W_800, color=okunur_renk(r["hdr"])),
                            ),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ))
                oneri_kutusu.controls.append(ft.Container(
                    padding=8,
                    border_radius=14,
                    bgcolor=r["bg"],
                    border=kenar(1, r["border"]),
                    content=ft.Column([
                        ft.Text("💡 Önceden eklediğin görevler (Tıkla tamamla veya ＋ Ekle):", size=11, weight=ft.FontWeight.W_700, color=r["hdr"]),
                        *oneri_satirlari,
                    ], spacing=5),
                ))
            try:
                oneri_kutusu.update()
            except Exception:
                try:
                    page.update()
                except Exception:
                    pass

        yeni_in.on_change = yazarken_oneri_guncelle

        def ekle(e):
            v = (yeni_in.value or "").strip()
            if v:
                DB["plan"][g_ad].append({"gorev": v, "bitti": False})
                plan_gecmise_ekle(v)
                kaydet("plan")
                yenile()

        yeni_in.on_submit = ekle

        def tikla(e):
            DB["plan"][g_ad][e.control.data]["bitti"] = e.control.value
            kaydet("plan")
            yenile()

        def sil(e):
            silinen = DB["plan"][g_ad][e.control.data]
            if isinstance(silinen, dict) and silinen.get("gorev"):
                plan_gecmise_ekle(silinen["gorev"])
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

        def programi_tamamen_temizle(e):
            haftalik_programi_tamamen_sifirla_islem()
            snack("🗑 Haftalık program tamamen sıfırlandı! (Eski görevlerin yazarken altta otomatik önerilir 💡)")
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
        sifirlama_alani = kart(r, ft.Column([
            bolum_basligi(r, ik("CLEANING_SERVICES"), "Haftalık Programı Sıfırlama Alanı"),
            ft.Text(
                "Yeni haftaya geçerken sadece tikleri kaldırabilir veya tüm haftalık programı sıfırlayabilirsin. "
                "(Sıfırlasan bile önceden yazdığın görevler hafızada kalır; tekrar yazmaya başladığında altta otomatik çıkar.)",
                size=12, color=r["muted"],
            ),
            ft.Row([
                buton(r, "🔄 Tikleri Sıfırla", haftayi_sifirla, ikincil=True, genis=True, yukseklik=42),
                buton(r, "🗑 Programı Tamamen Sıfırla", programi_tamamen_temizle, ikincil=True, genis=True, yukseklik=42),
            ], spacing=8),
        ], spacing=10))

        return ft.Column([
            sayfa_basligi(r, "Haftalık Plan", "Eklediklerin ana sayfana yansır"),
            ft.Row(cipler, scroll=ft.ScrollMode.AUTO, spacing=8),
            kart(r, ft.Column([
                bolum_basligi(r, ik("EVENT_NOTE"), g_ad,
                              ft.Text(f"{biten}/{len(gorevler)}", size=13, color=r["hdr"], weight=ft.FontWeight.BOLD)),
                ft.Row([yeni_in, ft.IconButton(icon=ik("ADD_CIRCLE"), icon_color=r["hdr"], icon_size=38, on_click=ekle)]),
                oneri_kutusu,
                *satirlar,
            ], spacing=10)),
            sifirlama_alani,
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

        canli = canli_eklenmemis_sn()
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
            # Yoldaşın Günlüğü kaydını otomatik oluştur ve Postacı Kuş kontrolü yap
            evcil_motor.gunluk_olustur(tarih_str=bugun, calisma_dk=sn // 60)
            evcil_postaci_kontrol_et()
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
        """Cihazdan fotoğraf seçtirir (Windows masaüstünde yerel dosya penceresi, mobilde Flet servisi kullanır;
        page.overlay içine FilePicker ekleyip 'Unknown control: FilePicker' kırmızı hatası çıkarmaz)."""
        try:
            page.overlay[:] = [
                c for c in page.overlay
                if type(c).__name__ != "FilePicker" and getattr(c, "_get_control_name", lambda: "")() != "filepicker"
            ]
        except Exception:
            pass

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

        # 1) Windows masaüstünde yerel dosya seçici (Unknown control: FilePicker hatasını %100 önler)
        if os.name == "nt" and not os.environ.get("ANDROID_ARGUMENT") and not os.environ.get("FLET_PLATFORM") == "android":
            def _win_dosya_sec():
                secilen_yol = ""
                try:
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.withdraw()
                    try:
                        root.attributes("-topmost", True)
                    except Exception:
                        pass
                    secilen_yol = filedialog.askopenfilename(
                        title="Ders Başlangıç Fotoğrafı Seç",
                        filetypes=[("Resim Dosyaları", "*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp"), ("Tüm Dosyalar", "*.*")],
                    )
                    root.destroy()
                except Exception:
                    try:
                        import subprocess
                        ps_cmd = (
                            "Add-Type -AssemblyName System.Windows.Forms; "
                            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                            "$f.Filter = 'Resim Dosyalari|*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp'; "
                            "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
                        )
                        out = subprocess.check_output(["powershell", "-NoProfile", "-Sta", "-Command", ps_cmd], timeout=120)
                        secilen_yol = out.decode("utf-8", errors="ignore").strip()
                    except Exception as ex:
                        sonra(None, f"Fotoğraf seçici açılamadı: {ex}")
                        return
                if not secilen_yol:
                    sonra(None, "")
                    return
                try:
                    with open(secilen_yol, "rb") as fh:
                        veri = fh.read()
                    sonra(veri, "" if veri else "Dosya boş")
                except Exception as ex:
                    sonra(None, f"Dosya okunamadı: {ex}")

            arka_plan(_win_dosya_sec)
            return

        # 2) Flet 1.0 / 0.8x async FilePicker servisi (page.overlay KULLANILMAZ)
        if hasattr(ft, "run") or hasattr(page, "services"):
            async def _sec():
                try:
                    secici = ft.FilePicker()
                    if hasattr(page, "services"):
                        try:
                            page.services.append(secici)
                            page.update()
                        except Exception:
                            pass
                    dosyalar = await secici.pick_files(
                        allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE, with_data=True
                    )
                    dosyalar_islensin(dosyalar)
                except Exception as ex:
                    sonra(None, f"Fotoğraf seçici açılamadı (Hazır masa fotoğrafını kullanabilirsin): {ex}")
            try:
                page.run_task(_sec)
                return
            except Exception as ex:
                sonra(None, f"Fotoğraf seçici açılamadı: {ex}")
                return

        # 3) Eski Flet 0.2x (flet_core) geri dönüşü
        try:
            secici = ft.FilePicker(on_result=lambda e: dosyalar_islensin(e.files))
            page.overlay.append(secici)
            page.update()
            secici.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
        except Exception as ex:
            sonra(None, f"Fotoğraf seçici açılamadı: {ex}")

    def gonderi_karti(r, pid, p):
        ben = oturum["kullanici"]
        sahip = p.get("kullanici", "")
        begeniler = p.get("begeni") or {}
        yorumlar = p.get("yorumlar") or {}
        beniyor = ben in begeniler
        genislik = max(230, int((page.width or 380) - 48))
        b64 = sosyal["resim"].get(pid)

        post_tarih = p.get("tarih")
        if not post_tarih:
            try:
                z_ms = sayi(p.get("zaman"), time.time() * 1000)
                post_tarih = datetime.fromtimestamp(z_ms / 1000.0).strftime("%d.%m.%Y")
            except Exception:
                post_tarih = bugun_str()
        baslama_saat_ek = f" ({p['baslama_saati']})" if p.get("baslama_saati") else ""
        alt_ders_etiketi = f"📅 {post_tarih}{baslama_saat_ek} • Ders Başlangıç Paylaşımı"

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
                        sahip, "sosyal_etkilesim", "❤️ Ders Paylaşımın Beğenildi",
                        f"{ben} ders başlangıç paylaşımını beğendi!", oncelik=3,
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
            ft.Column([
                ft.Row([
                    ft.Text(sahip or "?", size=14, weight=ft.FontWeight.W_800, color=r["txt"]),
                    ft.Container(
                        padding=pad_sim(horizontal=8, vertical=2), border_radius=8, bgcolor=opak(0.14, r["hdr"]),
                        content=ft.Text("📚 Derse Başladı", size=10, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    ),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(zaman_oncesi(p.get("zaman")), size=11, color=r["muted"]),
            ], spacing=1, expand=True),
            *([ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=r["muted"], on_click=sil)] if silebilir(sahip) else []),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        if b64:
            gorsel = ft.Container(
                width=genislik, height=genislik, border_radius=16, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                border=kenar(1, r["border"]),
                content=resim_olustur(b64, width=genislik, height=genislik),
            )
        else:
            gorsel = ft.Container(
                width=genislik, height=genislik, border_radius=16, bgcolor=r["bg"], alignment=ORTA,
                content=ft.ProgressRing(width=28, height=28, color=r["hdr"]),
            )

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
            govde.append(ft.Row([
                ft.Text(sahip, size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                ft.Text(p["aciklama"], size=13, color=r["txt"]),
            ], wrap=True, spacing=6))

        # Postun altında o günün tarihi ve "Ders Başlangıç Paylaşımı" etiketi
        govde.append(ft.Container(
            padding=pad_sim(horizontal=12, vertical=8),
            border_radius=12,
            bgcolor=opak(0.12, r["hdr"]),
            border=kenar(1, opak(0.35, r["hdr"])),
            content=ft.Row([
                ft.Icon(ik("CALENDAR_MONTH"), color=r["hdr"], size=16),
                ft.Text(
                    alt_ders_etiketi,
                    size=12, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True,
                ),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ))

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
                        sahip, "sosyal_etkilesim", f"💬 {ben} ders paylaşımına yorum yaptı",
                        m[:120], oncelik=3,
                    )
                yenile()

            yorum_in.on_submit = yorum_yolla
            govde.append(ft.Row([yorum_in, ft.IconButton(icon=ik("SEND"), icon_color=r["hdr"], on_click=yorum_yolla)]))
        return kart(r, ft.Column(govde, spacing=8), padding=14)

    def akis_kartlari(r):
        if not sosyal["posts"]:
            durum = ("Henüz ders başlangıç paylaşımı yok. Kronometreyi çalıştırarak günün ilk ders paylaşımını sen yap 📸"
                     if sosyal["imza"].get("akis") is not None else "Yükleniyor…")
            return [ft.Text(durum, color=r["muted"], italic=True)]
        return [gonderi_karti(r, pid, sosyal["posts"][pid]) for pid in sorted(sosyal["posts"], reverse=True)]

    def paylas_karti(r):
        bugun_t = bugun_str()
        bugun_paylasildi = (DB.get("gun") or {}).get("paylasim_yapildi") == bugun_t

        def sayaca_git_ve_baslat(e):
            ui["sekme"] = 1
            ui["calis_tab"] = 0
            ui["ilk_ders_paylasim_acik"] = True
            if page.navigation_bar is not None:
                page.navigation_bar.selected_index = 1
            yenile()

        if bugun_paylasildi and not ui.get("sosyal_ek_paylasim_acik"):
            return kart(r, ft.Row([
                ft.Container(
                    width=38, height=38, border_radius=12, bgcolor=opak(0.16, r["accent"]), alignment=ORTA,
                    content=ft.Text("✅", size=18),
                ),
                ft.Column([
                    ft.Text(f"Bugünün ({bugun_t}) Ders Başlangıç Paylaşımı Yapıldı!", size=13, weight=ft.FontWeight.W_800, color=r["txt"]),
                    ft.Text("İstersen yeni bir ders başlangıç fotoğrafı daha ekleyebilirsin.", size=11, color=r["muted"]),
                ], spacing=1, expand=True),
                buton(r, "＋ Yeni Paylaş", lambda e: (ui.update({"sosyal_ek_paylasim_acik": True}), yenile()), ikincil=True, yukseklik=36),
            ], spacing=10), padding=12)

        return ilk_ders_paylasim_karti_olustur(
            r,
            kapat_fn=(lambda e: (ui.update({"sosyal_ek_paylasim_acik": False}), yenile())) if bugun_paylasildi else None,
        )

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
        """Sosyal Medya sekmesi: Günün ilk ders başlangıç paylaşımları akışı ve 💬 Sohbet & Seri."""
        alt = ui.get("sosyal_alt")
        if alt == "sohbet":
            return sohbet_ana_gorunumu(r)

        aktif_isaretle("akis")
        if time.time() - sosyal["son_cek"].get(0, 0) > 3:
            arka_plan(sosyal_getir, 0)

        def sohbet_ac(e=None):
            ui["sosyal_alt"] = "sohbet"
            arka_plan(sosyal_getir, "genel" if ui["sohbet_tab"] == 0 else "dm_liste")
            yenile()

        def ust_sekme_degis(idx):
            if idx == 1:
                sohbet_ac()
            else:
                ui["sosyal_alt"] = None
                yenile()

        okunmamis_dm = okunmamis_sohbet_sayisi()
        sohbet_etiket = f"💬 Sohbet & Seri ({okunmamis_dm})" if okunmamis_dm > 0 else "💬 Sohbet & Seri"
        sag_ikonlar = ft.Row([
            rozetli_ikon_buton(r, "CHAT_BUBBLE_OUTLINE", okunmamis_dm, sohbet_ac, "Sohbet & Seri 💬🔥"),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        ust_baslik = sayfa_basligi(r, "Sosyal Medya", "Günlük ders başlangıç paylaşımları", sag=sag_ikonlar)
        ust_secici = segment(r, ["📸 Ders Paylaşımları", sohbet_etiket], 0, ust_sekme_degis)
        kap = ft.Column(akis_kartlari(r), spacing=14)
        sosyal["akis_kap"] = kap
        return ft.Column([ust_baslik, ust_secici, paylas_karti(r), kap, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)


    # ==========================================
    # 13. ARDA'NIN PANELİ (Önbellekli, anında açılan hızlı mimari + tam hesap temizliği)
    # ==========================================
    panel = {
        "kap": None,
        "imza": {},
        "veri": {},
        "seriler": {},
        "dm_index": {},
        "notlar": {},
        "mektuplar": {},
        "yon": "",
        "hata": "",
        "son_cek": 0.0,
        "yukleniyor": False,
    }

    def imza_hesapla(users):
        return {u: [len(listeye(d.get("gunluk"))), len(listeye(d.get("netler")))]
                for u, d in users.items() if isinstance(d, dict)}

    def panel_veri_cek_islem(zorla=False, senkron=False):
        """Panel verilerini buluttan çeker ve önbelleğe yazar. Sekme/öğrenci geçişlerinde tekrar ağ çağrısı yapmaz."""
        simdi_z = time.time()
        if not zorla and panel["son_cek"] > 0 and (simdi_z - panel["son_cek"]) < 20.0:
            return
        if panel["yukleniyor"] and not senkron:
            return

        def _cek():
            panel["yukleniyor"] = True
            try:
                users = bulut_oku() or {}
                seriler_all = bulut_get("seri") or {}
                dm_index_all = bulut_get("dm_index") or {}
                notlar = {k: v for k, v in (bulut_get("ayarlar/notlar") or {}).items() if isinstance(v, dict)}
                mektuplar = {k: v for k, v in (bulut_get("ayarlar/evcil_mektuplar") or {}).items() if isinstance(v, dict)}
                yon = (bulut_get("yonetici") or {}).get("kullanici", "")
                panel["veri"] = users if isinstance(users, dict) else {}
                panel["seriler"] = seriler_all if isinstance(seriler_all, dict) else {}
                panel["dm_index"] = dm_index_all if isinstance(dm_index_all, dict) else {}
                panel["notlar"] = notlar
                panel["mektuplar"] = mektuplar
                panel["yon"] = yon
                panel["imza"] = imza_hesapla(panel["veri"])
                panel["hata"] = ""
                panel["son_cek"] = time.time()
            except Exception as ex:
                panel["hata"] = f"Buluttan veriler çekilemedi: {ex}"
                panel["son_cek"] = time.time()
            finally:
                panel["yukleniyor"] = False

        if senkron:
            _cek()
        else:
            def _arka():
                _cek()
                if kok.content is ui_kapsayici and ui["sekme"] == 5 and ui["alt"] == "panel":
                    yenile()
            arka_plan(_arka)

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
        # 4) Eski oyun kayıtlarını temizle
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
        seriler_map = seriler_map if isinstance(seriler_map, dict) else (panel.get("seriler") or sosyal.get("seri") or {})
        dm_index_all = dm_index_all if isinstance(dm_index_all, dict) else (panel.get("dm_index") or {})
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

            def ogr_gunsonu_ac(hedef_ogr):
                def f(e):
                    ui["panel_ogrenci"] = hedef_ogr
                    ui["panel_tab"] = 1
                    yenile()
                return f

            def ogr_excel_indir(hedef_ogr, ogr_netler):
                def f(e):
                    tyt_l = [n for n in ogr_netler if n.get("sinav", "TYT") == "TYT"] or ogr_netler
                    sonuc = deneme_excel_disa_aktar(tyt_l, kullanici_adi=hedef_ogr, sinav_adi="TYT", oto_ac=True)
                    snack(f"📊 {sonuc['dosya_adi']} oluşturuldu! ({sonuc['yol']})")
                return f

            evcil_v = u.get("evcil") if isinstance(u.get("evcil"), dict) else {}
            evcil_altin = int(sayi(evcil_v.get("altin", evcil_v.get("yildiz")), 0))
            evcil_sv = int(sayi(evcil_v.get("seviye"), 1))

            satirlar = [
                ft.Row([
                    ft.Text(f"👤 {uname.upper()}", weight=ft.FontWeight.BOLD, color=r["hdr"], size=16, expand=True),
                    *([ft.Container(
                        padding=pad_sim(horizontal=8, vertical=3), border_radius=10, bgcolor=opak(0.16, r["accent"]),
                        content=ft.Text(f"🐾 Sv.{evcil_sv} • 🪙 {evcil_altin} Altın", size=11, weight=ft.FontWeight.W_800, color=r["txt"]),
                    )] if evcil_v else []),
                ]),
                ft.Text(f"⏱ Bugün {sn_metni(bugun_sn_)}   •   Toplam {sn_metni(toplam_)}", color=r["txt"], size=13),
                ft.Text(f"🌅 Derse başlama: {baslama or 'henüz başlamadı'}   •   💧 {bardak} bardak", color=r["txt"], size=13),
                ft.Text(f"🔥 En uzun seri: {en_uzun_seri} gün ({aktif_seri_say} aktif)   •   💬 {konusma_sayisi} özel sohbet",
                        color=r["accent"], size=12, weight=ft.FontWeight.W_600),
            ]
            if loglar:
                son = loglar[-1]
                p = int(sayi(son.get("performans")))
                emoji = PERFORMANS[p - 1][0] if 1 <= p <= 5 else "📝"
                sure = sn_metni(son["sn"]) if "sn" in son else f"{sayi(son.get('saat')):g} sa"
                satirlar.append(ft.Text(f"🌙 Son gün sonu ({len(loglar)} kayıt): {son.get('tarih', '-')} • {sure} • {emoji}", color=r["txt"], size=13))
                if son.get("gunluk"):
                    satirlar.append(ft.Text(f"“{str(son['gunluk'])[:90]}”", color=r["muted"], size=12, italic=True))
            else:
                satirlar.append(ft.Text("🌙 Henüz gün sonu kaydı yok.", color=r["muted"], size=13))
            if netler:
                n = netler[-1]
                satirlar.append(ft.Text(f"📈 Son deneme ({len(netler)} adet): {n.get('ad', '-')} ({n.get('sinav', '-')}) • {sayi(n.get('toplam')):.2f} net",
                                        color=r["txt"], size=13))

            aksiyonlar = [
                buton(r, f"🌙 Gün Sonu ({len(loglar)})", ogr_gunsonu_ac(uname), ikincil=True, genis=True, yukseklik=38),
            ]
            if netler:
                aksiyonlar.append(buton(r, "📊 Excel", ogr_excel_indir(uname, netler), ikincil=True, yukseklik=38))
            satirlar.append(ft.Row(aksiyonlar, spacing=8))
            kartlar.append(kart(r, ft.Column(satirlar, spacing=4), padding=14))
        return kartlar

    def panel_deneme_kopyalama_karti(r, users, isimler):
        """Arda'nın Paneli'ne özel: Bir öğrencinin deneme netlerini seçip başka bir öğrenci hesabına kopyalama kartı."""
        if not isimler:
            return ft.Container()
        kaynak = ui.get("panel_kopya_kaynak")
        if kaynak not in isimler:
            kaynak = ui.get("panel_ogrenci") if ui.get("panel_ogrenci") in isimler else isimler[0]
            ui["panel_kopya_kaynak"] = kaynak

        kaynak_netler = listeye((users.get(kaynak) or {}).get("netler"))
        secili_set = ui.setdefault("panel_secili_netler", set())
        gecerli_secili = [i for i in sorted(secili_set) if 0 <= i < len(kaynak_netler)]

        def kaynak_sec(u_ad):
            def f(e):
                ui["panel_kopya_kaynak"] = u_ad
                ui["panel_secili_netler"] = set()
                yenile()
            return f

        def hedef_sec(u_ad):
            def f(e):
                ui["panel_kopya_hedef"] = u_ad
                yenile()
            return f

        def tek_sec_degistir(idx):
            def f(e):
                if e.control.value:
                    secili_set.add(idx)
                else:
                    secili_set.discard(idx)
                yenile()
            return f

        def tumunu_sec_degistir(e):
            if len(gecerli_secili) == len(kaynak_netler):
                secili_set.clear()
            else:
                for idx in range(len(kaynak_netler)):
                    secili_set.add(idx)
            yenile()

        kaynak_cipleri = ft.Row([
            ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=14, ink=True, on_click=kaynak_sec(u_ad),
                bgcolor=r["hdr"] if u_ad == kaynak else r["bg"],
                border=kenar(1, r["hdr"] if u_ad == kaynak else r["border"]),
                content=ft.Text(f"📤 {u_ad.upper()} ({len(listeye((users.get(u_ad) or {}).get('netler')))})",
                                size=11, weight=ft.FontWeight.W_700,
                                color=okunur_renk(r["hdr"]) if u_ad == kaynak else r["txt"]),
            )
            for u_ad in isimler
        ], scroll=ft.ScrollMode.AUTO, spacing=6)

        diger_hedefler = [u_ad for u_ad in isimler if u_ad != kaynak]
        hedef_cipleri = ft.Row([
            ft.Container(
                padding=pad_sim(horizontal=10, vertical=6), border_radius=14, ink=True, on_click=hedef_sec(u_ad),
                bgcolor=r["accent"] if (ui.get("panel_kopya_hedef") or "").lower() == u_ad else r["bg"],
                border=kenar(1, r["accent"] if (ui.get("panel_kopya_hedef") or "").lower() == u_ad else r["border"]),
                content=ft.Text(f"📥 {u_ad.upper()}", size=11, weight=ft.FontWeight.W_700,
                                color=okunur_renk(r["accent"]) if (ui.get("panel_kopya_hedef") or "").lower() == u_ad else r["txt"]),
            )
            for u_ad in diger_hedefler
        ], scroll=ft.ScrollMode.AUTO, spacing=6)

        hedef_in = girdi(
            r, "Hedef kullanıcı adı (Örn: sude)",
            label="Kopyalanacak Hedef Hesap",
            value=ui.get("panel_kopya_hedef", ""),
            on_change=lambda e: ui.update({"panel_kopya_hedef": e.control.value or ""}),
        )

        def panel_kopyala_calistir(tumunu_mu=False):
            def f(e):
                hedef_k = (hedef_in.value or ui.get("panel_kopya_hedef") or "").strip().lower()
                ui["panel_kopya_hedef"] = hedef_k
                if not tumunu_mu and not gecerli_secili:
                    snack("Önce kopyalanacak denemeleri işaretle veya 'Tümünü Kopyala'ya bas ☑️")
                    return
                ok, msg, _ = denemeleri_baska_hesaba_kopyala_islem(
                    hedef_k,
                    indeksler=None if tumunu_mu else gecerli_secili,
                    senkron=True,
                    kaynak_kullanici=kaynak,
                )
                snack(msg)
                if ok:
                    ui["panel_secili_netler"] = set()
                    yenile()
            return f

        deneme_satirlari = []
        for idx, k in enumerate(kaynak_netler):
            d_s = deneme_satiri_ayristir(k)
            isaretli = idx in secili_set
            deneme_satirlari.append(ft.Container(
                padding=pad_sim(horizontal=8, vertical=5), border_radius=12,
                bgcolor=opak(0.10, r["hdr"]) if isaretli else r["bg"],
                border=kenar(1, r["hdr"] if isaretli else r["border"]),
                content=ft.Row([
                    ft.Checkbox(value=isaretli, on_change=tek_sec_degistir(idx), fill_color=r["hdr"], check_color=okunur_renk(r["hdr"])),
                    ft.Text(f"{d_s['ad']} ({d_s['sinav']} • {d_s['tarih']})", size=12, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    ft.Text(f"{d_s['toplam']:.2f} Net", size=12, weight=ft.FontWeight.W_800, color=r["hdr"]),
                ], spacing=6),
            ))

        return kart(r, ft.Column([
            bolum_basligi(r, ik("CONTENT_COPY"), "📋 Deneme Netlerini Farklı Hesaba Kopyala (Sadece Panel)"),
            ft.Text("1) Denemeleri alınacak kaynak hesabı seç:", size=11, weight=ft.FontWeight.W_700, color=r["muted"]),
            kaynak_cipleri,
            ft.Text("2) Denemelerin kopyalanacağı hedef hesabı seç veya yaz:", size=11, weight=ft.FontWeight.W_700, color=r["muted"]),
            *([hedef_cipleri] if diger_hedefler else []),
            hedef_in,
            *([
                ft.Row([
                    ft.Text(f"📋 {kaynak.upper()} Denemeleri ({len(kaynak_netler)} adet):", size=12, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                    buton(r, "☑️ Tümünü Seç/Kaldır", tumunu_sec_degistir, ikincil=True, yukseklik=32),
                ]),
                *deneme_satirlari,
                ft.Row([
                    buton(r, f"📋 Seçilenleri Kopyala ({len(gecerli_secili)})", panel_kopyala_calistir(False), genis=True, yukseklik=40),
                    buton(r, f"📋 Tümünü Kopyala ({len(kaynak_netler)})", panel_kopyala_calistir(True), ikincil=True, genis=True, yukseklik=40),
                ], spacing=8),
            ] if kaynak_netler else [ft.Text(f"'{kaynak}' hesabında henüz kayıtlı deneme yok.", size=12, italic=True, color=r["muted"])]),
        ], spacing=8))

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
            sifre = girdi(r, label="Panel Şifresi", password=True, can_reveal_password=True)
            hata = ft.Text(ui["panel_hata"], color=KIRMIZI)

            def giris(e):
                if (sifre.value or "").strip() == PANEL_SIFRESI:
                    ui["panel_giris"] = True
                    ui["panel_hata"] = ""
                    yonetici_kaydet()
                    panel_veri_cek_islem(zorla=True, senkron=True)
                    snack("Giriş Başarılı! ✅")
                else:
                    ui["panel_hata"] = "Şifre yanlış!"
                yenile()

            sifre.on_submit = giris
            return ft.Column([kart(r, ft.Column([
                bolum_basligi(r, ik("LOCK"), "Arda'nın Yönetici Paneli"), sifre, hata,
                buton(r, "Giriş", giris, genis=True)], spacing=12))], expand=True, scroll=ft.ScrollMode.AUTO)

        # İlk kez açılıyorsa ve önbellek boşsa çek; sekme veya öğrenci değiştirirken ASLA tekrar ağ çağrısı yapma!
        if panel["son_cek"] == 0.0 and not panel["yukleniyor"]:
            panel_veri_cek_islem(zorla=True, senkron=True)
        elif (time.time() - panel["son_cek"]) > 25.0 and not panel["yukleniyor"]:
            panel_veri_cek_islem(zorla=False, senkron=False)

        users = panel.get("veri") or {}
        seriler_all = panel.get("seriler") or {}
        dm_index_all = panel.get("dm_index") or {}
        notlar = panel.get("notlar") or {}
        evcil_mektuplar_bulut = panel.get("mektuplar") or {}
        yon = panel.get("yon") or ""
        hata_yazi = panel.get("hata") or ""

        isimler = sorted(k for k, v in users.items() if isinstance(v, dict))
        if ui["panel_ogrenci"] not in isimler:
            ui["panel_ogrenci"] = "sude" if "sude" in isimler else (isimler[0] if isimler else None)
        sec = ui["panel_ogrenci"]

        def ogr_sec(isim):
            def f(e):
                ui["panel_ogrenci"] = isim
                yenile()
            return f

        def simdi_yenile_tikla(e):
            snack("🔄 Panel verileri buluttan yenileniyor...")
            panel_veri_cek_islem(zorla=True, senkron=False)

        ciplar = ft.Row([
            ft.Container(
                padding=pad_sim(horizontal=14, vertical=8), border_radius=20, ink=True, on_click=ogr_sec(i),
                bgcolor=r["hdr"] if i == sec else r["card_bg"], border=kenar(1, r["border"]),
                content=ft.Text(i.upper(), size=12, weight=ft.FontWeight.W_700,
                                color=okunur_renk(r["hdr"]) if i == sec else r["txt"]))
            for i in isimler
        ], scroll=ft.ScrollMode.AUTO, spacing=8)

        def degisti(i):
            ui["panel_tab"] = i
            ui["silinecek"] = None
            yenile()

        if ui["panel_tab"] >= 6:
            ui["panel_tab"] = 0
        aktif_tab = ui["panel_tab"]

        ust = [
            ft.Row([
                ft.Text(
                    "🟢 Veriler Önbellekte (Anlık Geçiş)" if not panel["yukleniyor"] else "🔄 Buluttan güncelleniyor...",
                    size=11, weight=ft.FontWeight.W_700, color=r["hdr"], expand=True,
                ),
                buton(r, "🔄 Şimdi Yenile", simdi_yenile_tikla, ikincil=True, yukseklik=32),
            ]),
            segment(r, ["📈 Veri", "🌙 Gün Sonu", "🔔 Gönder", "📝 Görev", "💌 Not", "🗑 Hesap"], aktif_tab, degisti),
        ]
        if aktif_tab in (1, 2, 3, 4):
            ust.append(ciplar if isimler else ft.Text("Henüz kayıtlı öğrenci yok.", color=r["muted"], italic=True))

        # YALNIZCA AKTİF SEKMEYİ İNŞA ET (Diğer 5 sekmenin kontrollerini ve SVG grafiklerini boşuna hesaplama!)
        aktif_icerik = []

        if aktif_tab == 0:
            kap = ft.Column(
                ogrenci_kartlari(r, users, seriler_all, dm_index_all)
                or [ft.Text("Henüz kayıtlı öğrenci yok.", color=r["muted"], italic=True)],
                spacing=10,
            )
            panel["kap"] = kap
            aktif_icerik = [
                ft.Text("🔴 Canlı: öğrenci çalışma ve seri verileri burada anlık görünür.", size=12, color=r["muted"]),
                *([ft.Text(hata_yazi, color=KIRMIZI)] if hata_yazi else []),
                panel_deneme_kopyalama_karti(r, users, isimler),
                kap,
            ]

        elif aktif_tab == 1:
            sec_veri = (users.get(sec) or {}) if sec else {}
            sec_gunlukler = [g for g in listeye(sec_veri.get("gunluk")) if isinstance(g, dict)]
            sec_sn_map = bulut_coz("calisma_sn", sec_veri.get("calisma_sn") or {})
            sec_log_map = bulut_coz("calisma_log", sec_veri.get("calisma_log") or {})
            sec_birlesik_sn = {}
            for t_k in set(list(sec_sn_map.keys()) + list(sec_log_map.keys())):
                sec_birlesik_sn[t_k] = int(sayi(sec_sn_map.get(t_k))) + int(sayi(sec_log_map.get(t_k))) * 60

            bugun_t = bugun_str()
            son7_gunler = [(date.today() - timedelta(days=i)).strftime("%d.%m.%Y") for i in range(7)]
            son30_gunler = [(date.today() - timedelta(days=i)).strftime("%d.%m.%Y") for i in range(30)]
            son7_toplam_sn = sum(int(sec_birlesik_sn.get(g_t, 0)) for g_t in son7_gunler)
            son30_toplam_sn = sum(int(sec_birlesik_sn.get(g_t, 0)) for g_t in son30_gunler)
            tum_toplam_sn = sum(int(v) for v in sec_birlesik_sn.values())

            kayit_sayisi = len(sec_gunlukler)
            puanlar_list = [int(sayi(g.get("performans"), 0)) for g in sec_gunlukler if 1 <= int(sayi(g.get("performans"), 0)) <= 5]
            ort_puan = (sum(puanlar_list) / len(puanlar_list)) if puanlar_list else 0.0
            ort_puan_idx = max(1, min(5, int(round(ort_puan)))) if ort_puan > 0 else 0
            ort_puan_emoji = PERFORMANS[ort_puan_idx - 1][0] if ort_puan_idx else "—"
            ort_puan_etiket = PERFORMANS[ort_puan_idx - 1][1] if ort_puan_idx else "Veri yok"

            rekor_gun_tarih, rekor_gun_sn = "-", 0
            for t_k, sn_v in sec_birlesik_sn.items():
                if sn_v > rekor_gun_sn:
                    rekor_gun_sn = sn_v
                    rekor_gun_tarih = t_k
            for g in sec_gunlukler:
                g_sn = int(sayi(g.get("sn"), float(sayi(g.get("saat"), 0.0)) * 3600))
                if g_sn > rekor_gun_sn:
                    rekor_gun_sn = g_sn
                    rekor_gun_tarih = str(g.get("tarih") or "-")

            p_dagilim = {i: 0 for i in range(1, 6)}
            for p_v in puanlar_list:
                p_dagilim[p_v] = p_dagilim.get(p_v, 0) + 1

            sec_gun_bilgi = sec_veri.get("gun") if isinstance(sec_veri.get("gun"), dict) else {}
            bugun_baslama = sec_gun_bilgi.get("baslama") if sec_gun_bilgi.get("tarih") == bugun_t else "Henüz başlamadı"
            sec_su_bilgi = sec_veri.get("su") if isinstance(sec_veri.get("su"), dict) else {}
            bugun_su = int(sayi(sec_su_bilgi.get("bardak"), 0)) if sec_su_bilgi.get("tarih") == bugun_t else 0
            sec_evcil = sec_veri.get("evcil") if isinstance(sec_veri.get("evcil"), dict) else {}

            def gs_metrik_kutu(baslik_m, deger_m, alt_m, vurgu_renk=None):
                return ft.Container(
                    expand=True, padding=10, border_radius=16, bgcolor=r["bg"], border=kenar(1, r["border"]),
                    content=ft.Column([
                        ft.Text(baslik_m, size=11, color=r["muted"], weight=ft.FontWeight.W_600),
                        ft.Text(deger_m, size=15, weight=ft.FontWeight.W_800, color=vurgu_renk or r["hdr"]),
                        ft.Text(alt_m, size=10, color=r["txt"]),
                    ], spacing=2),
                )

            gs_ozet_karti = kart(r, ft.Column([
                bolum_basligi(
                    r, ik("NIGHTLIGHT_ROUND"),
                    f"🌙 {(sec or 'Öğrenci').upper()} — Gün Sonu & Çalışma Analizi",
                    ft.Text(f"{kayit_sayisi} Kayıt", size=13, weight=ft.FontWeight.W_800, color=r["hdr"]),
                ),
                ft.Row([
                    gs_metrik_kutu("Bugün Çalışma", sn_metni(sec_birlesik_sn.get(bugun_t, 0)), f"🌅 Başlama: {bugun_baslama}"),
                    gs_metrik_kutu("Son 7 Gün", sn_metni(son7_toplam_sn), f"Ort: {sn_metni(son7_toplam_sn // 7)}"),
                ], spacing=8),
                ft.Row([
                    gs_metrik_kutu("Son 30 Gün", sn_metni(son30_toplam_sn), f"Toplam: {sn_metni(tum_toplam_sn)}"),
                    gs_metrik_kutu("Rekor Gün", sn_metni(rekor_gun_sn), f"📅 {rekor_gun_tarih}", r["accent"]),
                ], spacing=8),
                ft.Row([
                    gs_metrik_kutu("Ort. Performans", f"{ort_puan_emoji} {ort_puan:.1f} / 5", ort_puan_etiket),
                    gs_metrik_kutu(
                        "Su & Yoldaş",
                        f"💧 {bugun_su}/8 Bardak",
                        f"🪙 {int(sayi(sec_evcil.get('altin', sec_evcil.get('yildiz')), 0))} Altın • Sv.{int(sayi(sec_evcil.get('seviye'), 1))}"
                        if sec_evcil else "Evcil verisi bekleniyor",
                    ),
                ], spacing=8),
                ft.Divider(height=6, color=r["border"]),
                ft.Text("Performans & Ruh Hali Dağılımı:", size=12, weight=ft.FontWeight.W_700, color=r["muted"]),
                ft.Row([
                    ft.Container(
                        padding=pad_sim(horizontal=10, vertical=6), border_radius=12, bgcolor=r["bg"], border=kenar(1, r["border"]),
                        content=ft.Text(f"{PERFORMANS[i - 1][0]} {PERFORMANS[i - 1][1]}: {p_dagilim[i]} gün", size=11, weight=ft.FontWeight.W_700, color=r["txt"]),
                    )
                    for i in range(5, 0, -1)
                ], scroll=ft.ScrollMode.AUTO, spacing=6),
            ], spacing=10))

            gs_svg_b64 = gun_sonu_svg_grafik_olustur(sec_gunlukler, sec_birlesik_sn, gun_sayisi=14)
            gs_grafik_w = max(280, int((page.width or 380) - 48))
            gs_grafik_karti = kart(r, ft.Column([
                bolum_basligi(r, ik("BAR_CHART"), "Son 14 Gün Çalışma & Performans Grafiği"),
                ft.Container(
                    border_radius=14, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=resim_olustur(gs_svg_b64, width=gs_grafik_w, height=int(gs_grafik_w * 0.34), fit=FIT.CONTAIN if FIT else None),
                ),
            ], spacing=8), padding=14)

            secili_p_filtre = int(ui.get("panel_gs_filtre") or 0)

            def gs_filtre_sec(p_kod):
                def f(e):
                    ui["panel_gs_filtre"] = p_kod
                    yenile()
                return f

            gs_filtre_satiri = ft.Row([
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=6), border_radius=14, ink=True, on_click=gs_filtre_sec(kod),
                    bgcolor=r["hdr"] if secili_p_filtre == kod else r["bg"],
                    border=kenar(1, r["hdr"] if secili_p_filtre == kod else r["border"]),
                    content=ft.Text(
                        etiket, size=11, weight=ft.FontWeight.W_700,
                        color=okunur_renk(r["hdr"]) if secili_p_filtre == kod else r["txt"],
                    ),
                )
                for kod, etiket in [
                    (0, f"📋 Tümü ({kayit_sayisi})"),
                    (5, f"🤩 Harika ({p_dagilim[5]})"),
                    (4, f"🙂 İyi ({p_dagilim[4]})"),
                    (3, f"😐 Normal ({p_dagilim[3]})"),
                    (2, f"😕 İdare Eder ({p_dagilim[2]})"),
                    (1, f"😞 Çok Kötü ({p_dagilim[1]})"),
                ]
            ], scroll=ft.ScrollMode.AUTO, spacing=6)

            gs_arama_in = girdi(
                r, "Tarih veya günlük içinde kelime ara...",
                label="Gün Sonu Kayıtlarında Ara",
                value=ui.get("panel_gs_arama", ""),
                on_change=lambda e: ui.update({"panel_gs_arama": e.control.value or ""}),
                on_submit=lambda e: yenile(),
                expand=True,
            )

            detayli_gs_kartlari = []
            arama_k = (ui.get("panel_gs_arama") or "").strip().lower()
            for sira_idx, k in enumerate(reversed(sec_gunlukler), start=1):
                p = int(sayi(k.get("performans"), 0))
                if secili_p_filtre in (1, 2, 3, 4, 5) and p != secili_p_filtre:
                    continue
                t_str = str(k.get("tarih") or "-")
                not_tam = str(k.get("gunluk") or "").strip()
                if arama_k and (arama_k not in t_str.lower()) and (arama_k not in not_tam.lower()):
                    continue

                emoji, p_ad = PERFORMANS[p - 1] if 1 <= p <= 5 else ("📝", "Belirtilmedi")
                kayit_sn = int(sayi(k.get("sn"), float(sayi(k.get("saat"), 0.0)) * 3600))
                kayit_saat = round(kayit_sn / 3600.0, 2)
                takvim_sn = int(sec_birlesik_sn.get(t_str, kayit_sn))
                bas_saat = str(k.get("baslama") or "-")
                bit_saat = str(k.get("bitis") or "-")

                gun_adi_str = ""
                try:
                    dt_g = datetime.strptime(t_str.replace("-", "."), "%d.%m.%Y")
                    gun_adi_str = f" • {GUNLER[dt_g.weekday()]}"
                except Exception:
                    pass

                detayli_gs_kartlari.append(ft.Container(
                    padding=14, border_radius=18, bgcolor=r["bg"],
                    border=kenar(1.5 if sira_idx == 1 else 1, r["hdr"] if sira_idx == 1 else r["border"]),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"📅 {t_str}{gun_adi_str}", size=14, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                            ft.Container(
                                padding=pad_sim(horizontal=10, vertical=4), border_radius=12,
                                bgcolor=opak(0.16, r["hdr"]),
                                content=ft.Text(f"{emoji} {p_ad} ({p}/5)", size=12, weight=ft.FontWeight.W_800, color=r["hdr"]),
                            ),
                        ]),
                        ft.Container(
                            padding=10, border_radius=12, bgcolor=r["card_bg"], border=kenar(1, r["border"]),
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"🌅 Derse Başlama: {bas_saat}", size=12, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                                    ft.Text(f"🌙 Gün Sonu Bitiş: {bit_saat}", size=12, weight=ft.FontWeight.W_700, color=r["txt"], expand=True),
                                ]),
                                ft.Row([
                                    ft.Text(f"⏱ Kayıt Süresi: {sn_metni(kayit_sn)} ({kayit_saat:g} saat)", size=12, weight=ft.FontWeight.W_700, color=r["accent"], expand=True),
                                    ft.Text(f"📊 Gün Toplamı: {sn_metni(takvim_sn)}", size=12, color=r["muted"], expand=True),
                                ]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            padding=12, border_radius=12,
                            bgcolor=opak(0.08, r["hdr"]) if not_tam else r["card_bg"],
                            border=ft.Border(left=ft.BorderSide(4, r["hdr"] if not_tam else r["muted"])),
                            content=ft.Column([
                                ft.Text("📓 Öğrencinin Gün Sonu Günlüğü & Notu:", size=11, weight=ft.FontWeight.W_700, color=r["hdr"]),
                                ft.Text(
                                    not_tam if not_tam else "Bu gün için yazılı günlük notu bırakılmamış.",
                                    size=13, color=r["txt"] if not_tam else r["muted"],
                                    italic=not bool(not_tam), selectable=True,
                                ),
                            ], spacing=4),
                        ),
                    ], spacing=8),
                ))

            if not detayli_gs_kartlari:
                detayli_gs_kartlari.append(ft.Text(
                    f"{(sec or 'Öğrenci').upper()} için eşleşen gün sonu kaydı bulunamadı.",
                    color=r["muted"], italic=True, size=13,
                ))

            aktif_icerik = [
                gs_ozet_karti,
                gs_grafik_karti,
                kart(r, ft.Column([
                    bolum_basligi(r, ik("HISTORY"), f"📜 {(sec or 'Öğrenci').upper()} — Tüm Gün Sonu Kayıtları ({len(detayli_gs_kartlari)})"),
                    gs_filtre_satiri,
                    ft.Row([gs_arama_in, buton(r, "Ara", lambda e: yenile(), yukseklik=44)], spacing=8),
                    *detayli_gs_kartlari,
                ], spacing=10)),
            ]

        elif aktif_tab == 2:
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

            aktif_icerik = [
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

        elif aktif_tab == 3:
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
                        if sec in panel["veri"] and isinstance(panel["veri"][sec], dict):
                            panel["veri"][sec]["ozel_gorevler"] = liste
                        konu = (bulut_get(f"users/{sec}/bildirim") or {}).get("konu")
                        if konu:
                            ntfy_gonder(konu, "🎯 Arda sana yeni görev verdi", f"{g}" + (f"  •  🎁 {o}" if o else ""), 4)
                        snack(f"✅ Görev {sec} kişisine gönderildi")
                        yenile()
                    except Exception as ex:
                        snack(f"⚠️ Gönderilemedi: {ex}")
                arka_plan(is_)

            mevcut = listeye((users.get(sec) or {}).get("ozel_gorevler")) if sec else []
            gorev_liste = [ft.Text(f"{'✅' if g.get('durum') == 'Tamamlandı' else '⏳'} {g.get('gorev')} → {g.get('odul')}",
                                   size=12, color=r["muted"]) for g in mevcut]
            aktif_icerik = [kart(r, ft.Column([
                bolum_basligi(r, ik("ASSIGNMENT"), "Özel Görev Tanımla"),
                gorev_in, odul_in, buton(r, "Gönder", gorev_ver, genis=True), *gorev_liste,
            ], spacing=10))]

        elif aktif_tab == 4:
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
                        nid = yeni_id()
                        kayit_n = {"m": m[:300], "k": hedef, "z": int(time.time() * 1000)}
                        bulut_patch(f"ayarlar/notlar/{nid}", kayit_n)
                        panel["notlar"][nid] = kayit_n
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
                            panel["notlar"].pop(nid, None)
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

            mektup_baslik_in = girdi(r, "Örn: 🐦 Postacı Kuş'tan Sürpriz Mektup!", label="Mektup Başlığı")
            mektup_kosul_in = girdi(r, "Örn: Arda'dan Özel Motivasyon Mektubu 💌", label="Alt Başlık / Açıklama")
            mektup_mesaj_in = girdi(r, "Öğrencinin evcil hayvan odasındaki Postacı Kuş mektubunda görünecek mesaj...",
                                    label="Mektup İçeriği", multiline=True, min_lines=2, max_lines=5)

            def mektup_ekle_panel(e):
                m_icerik = (mektup_mesaj_in.value or "").strip()
                if not m_icerik:
                    snack("Önce mektup içeriğini yaz 📝")
                    return
                m_baslik = (mektup_baslik_in.value or "").strip() or "🐦 Postacı Kuş'tan Sürpriz Mektup!"
                m_kosul = (mektup_kosul_in.value or "").strip() or "Arda'dan özel Postacı Kuş mektubu 💌"
                hedef = sec if ui.get("not_hedef") == 1 and sec else ""

                def is_():
                    try:
                        mid = yeni_id()
                        veri = {
                            "baslik": m_baslik[:120],
                            "kosul": m_kosul[:140],
                            "m": m_icerik[:600],
                            "k": hedef,
                            "z": int(time.time() * 1000),
                        }
                        bulut_patch(f"ayarlar/evcil_mektuplar/{mid}", veri)
                        panel["mektuplar"][mid] = veri
                        evcil_motor.dis_mektup_ekle(f"panel_{mid}", veri["baslik"], veri["kosul"], veri["m"], unlocked=1)
                        snack("🐦 Evcil hayvan Postacı Kuş mektubu eklendi!")
                        yenile()
                    except Exception as ex:
                        snack(f"⚠️ Mektup eklenemedi: {ex}")
                arka_plan(is_)

            def mektup_sil_panel(mid):
                def f(e):
                    def is_():
                        try:
                            bulut_sil(f"ayarlar/evcil_mektuplar/{mid}")
                            panel["mektuplar"].pop(mid, None)
                            yenile()
                        except Exception as ex:
                            snack(f"⚠️ Silinemedi: {ex}")
                    arka_plan(is_)
                return f

            mektup_panel_satirlari = []
            for mid in sorted(evcil_mektuplar_bulut, reverse=True):
                mv = evcil_mektuplar_bulut[mid]
                m_etiket = f"👤 {mv['k']}" if mv.get("k") else "👥 herkese"
                mektup_panel_satirlari.append(ft.Container(
                    padding=pad_sim(horizontal=12, vertical=8), border_radius=14, bgcolor=r["bg"], border=kenar(1, r["border"]),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"🐦 {mv.get('baslik', 'Postacı Kuş Mektubu')}", size=13, weight=ft.FontWeight.W_700, color=r["hdr"]),
                            ft.Text(mv.get("m", ""), size=12, color=r["txt"]),
                            ft.Text(f"{mv.get('kosul', '')} • {m_etiket}", size=11, color=r["muted"]),
                        ], spacing=2, expand=True),
                        ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, on_click=mektup_sil_panel(mid)),
                    ]),
                ))

            aktif_icerik = [
                kart(r, ft.Column([
                    bolum_basligi(r, ik("PETS"), "🐦 Evcil Hayvan Mektuplarına Ekle (Postacı Kuş)"),
                    ft.Text("Buradan eklediğin mektuplar doğrudan öğrencinin Evcil Hayvan odasındaki Postacı Kuş (🐦✉️) kutusuna düşer.",
                            size=12, color=r["muted"]),
                    segment(r, ["👥 Herkese", f"👤 {sec.upper() if sec else 'Öğrenci'}"], ui["not_hedef"], hedef_degisti),
                    mektup_baslik_in,
                    mektup_kosul_in,
                    mektup_mesaj_in,
                    buton(r, "Evcil Hayvan Mektubu Gönder 🐦✉️", mektup_ekle_panel, genis=True),
                ], spacing=10)),
                kart(r, ft.Column([
                    bolum_basligi(r, ik("MAIL"), f"Gönderilen Postacı Kuş Mektupları ({len(mektup_panel_satirlari)})"),
                    *(mektup_panel_satirlari or [ft.Text("Henüz panelden Postacı Kuş mektubu eklenmedi.", color=r["muted"], italic=True, size=13)]),
                ], spacing=8)),
                kart(r, ft.Column([
                    bolum_basligi(r, ik("EDIT_NOTE"), "Günün Sürpriz Notu (Ana Sayfa)"),
                    ft.Text("Eklediklerin, öğrencinin ana sayfadaki “Sürpriz Notu Oku” düğmesinde çıkar.", size=12, color=r["muted"]),
                    segment(r, ["👥 Herkese", f"👤 {sec.upper() if sec else 'Öğrenci'}"], ui["not_hedef"], hedef_degisti),
                    not_in, buton(r, "Notu Ekle 💌", not_ekle, genis=True),
                ], spacing=10)),
                kart(r, ft.Column([bolum_basligi(r, ik("EVENT_NOTE"), f"Eklenen notlar ({len(not_satirlari)})"),
                                   *(not_satirlari or [ft.Text("Henüz not eklemedin.", color=r["muted"], italic=True, size=13)])],
                                  spacing=8)),
            ]

        else:
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
                                panel["veri"].pop(u_, None)
                            except Exception as ex:
                                snack(f"⚠️ {u_} silinemedi: {ex}")
                                continue
                        snack(f"🗑 {len(liste)} hesap ve tüm verileri silindi")
                        yenile()
                    arka_plan(is_)
                return f

            def esik_degisti(i):
                ui["panel_esik"] = i
                ui["silinecek"] = None
                yenile()

            aktif_icerik = [
                sohbet_mod_karti,
                segment(r, ["7 gün", "14 gün", "30 gün"], ui["panel_esik"], esik_degisti),
                ft.Text(f"{esik} günden uzun süredir uygulamayı açmayan hesaplar kırmızı görünür. "
                        "Sildiğinde hesap, paylaşımları, özel sohbetleri ve serileri kalıcı olarak gider.",
                        size=12, color=r["muted"]),
            ]
            if ui["silinecek"]:
                aktif_icerik.append(kart(r, ft.Column([
                    ft.Text(f"⚠️ {len(ui['silinecek'])} hesap kalıcı olarak silinecek:", weight=ft.FontWeight.BOLD, color=KIRMIZI),
                    ft.Text(", ".join(u_.upper() for u_ in ui["silinecek"]), size=13, color=r["txt"]),
                    ft.Row([buton(r, "Evet, sil", hesaplari_sil(ui["silinecek"]), genis=True, yukseklik=44),
                            buton(r, "Vazgeç", vazgec, genis=True, ikincil=True, yukseklik=44)], spacing=10),
                ], spacing=10), border=kenar(2, KIRMIZI)))
            elif pasifler:
                aktif_icerik.append(buton(r, f"{esik}+ gündür girmeyen {len(pasifler)} hesabı sil", sil_iste(pasifler),
                                          ikon=ik("DELETE_OUTLINE"), genis=True, yukseklik=46))
            for _, uname, gun_ in satirlar_h:
                if gun_ is None:
                    etiket, renk_ = "son görülme bilinmiyor (eski hesap)", r["muted"]
                elif gun_ < 1:
                    etiket, renk_ = "bugün aktif", r["accent"]
                else:
                    etiket, renk_ = f"{int(gun_)} gün önce", KIRMIZI if gun_ >= esik else r["muted"]
                aktif_icerik.append(kart(r, ft.Row([
                    avatar(r, uname),
                    ft.Column([ft.Text(uname.upper(), size=14, weight=ft.FontWeight.W_700, color=r["txt"]),
                               ft.Text(etiket, size=12, color=renk_)], spacing=0, expand=True),
                    *([ft.IconButton(icon=ik("DELETE_OUTLINE"), icon_color=KIRMIZI, on_click=sil_iste([uname]))]
                      if uname not in korunan else [ft.Text("korumalı", size=11, color=r["muted"])]),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=12))

        return ft.Column([*ust, *aktif_icerik, ft.Container(height=24)],
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
    # 14b. BİLDİRİMLER (Çalışma + Sosyal + Seri Bildirim Tercihleri)
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
            bolum_basligi(r, ik("FORUM"), "Sosyal & Seri Bildirimleri"),
            satir("📸 Ders başlangıç paylaşımları", "Akışa yeni ders başlangıç fotoğrafı atıldığında haber verir", "sosyal_foto", True),
            satir("💬 Genel sohbet mesajları", "Genel sohbette yeni mesaj olduğunda bildirir", "sosyal_genel", True),
            satir("🔕 Genel sohbeti tamamen sessize al", "Açıkken genel sohbetten hiç bildirim gelmez", "genel_sessiz", False),
            satir("✉️ Özel mesajlar (DM)", "Sana özel mesaj geldiğinde anında bildirir", "sosyal_dm", True),
            satir("🔥 Günlük seri (Streak) uyarıları", "Serin tehlikedeyken ve rekorlarda uyarır", "sosyal_seri", True),
            satir("❤️ Beğeni ve yorumlar", "Ders paylaşımın beğenildiğinde veya yorum geldiğinde bildirir", "sosyal_etkilesim", True),
        ], spacing=12))

        not_ = ft.Text("Sessiz saatler (23:30 - 08:30) arasında 23:15 son şans seri uyarısı hariç bildirim gönderilmez.",
                       size=12, color=r["muted"])
        return ft.Column([kurulum, ayarlar, sosyal_ayarlar, not_, ft.Container(height=24)],
                         scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ==========================================
    # 14B. SANAL EVCİL HAYVAN & ÇALIŞMA YOLDAŞI EKRANI (MY TALKING TOM TARZI TAM EKRAN ODA)
    # ==========================================
    def evcil_sayfasi_olustur(r):
        AktifKullanici = kullanici_adi() or "Öğrenci"
        evcil_motor.kullanici_ayarla(AktifKullanici)
        evcil_postaci_kontrol_et()
        st = evcil_motor.durum_oku()
        dengesiz, uyari_metni = evcil_motor.kontrol_dengesiz_beslenme()
        evrim_ad = dict((k, ad) for k, ad, _ in EVCIL_EVRIMLER).get(st["evrim_asamasi"], "🐾 1. Evre: Minik Bebek Kedi")
        gece_modu = bool(ui.get("evcil_uyku_isik")) or st["durum"] == "SLEEPING"
        kalan_yks_gun = max(0, (YKS_TARIHI.date() - datetime.now(ISTANBUL_TZ).date()).days)

        # Panel seçimi: None (Tam Ekran Oda), "magaza" (1), "mektup" (2), "oyun" (3: Kedinle Konuş / Soru Sor), "besle" (4)
        aktif_panel = ui.get("evcil_panel")
        if aktif_panel is None and int(ui.get("evcil_tab") or 0) in (1, 2, 3):
            aktif_panel = {1: "magaza", 2: "mektup", 3: "oyun"}[int(ui["evcil_tab"])]

        def panel_ac(p_ad, tab_no=0):
            def f(e):
                ui["evcil_panel"] = None if ui.get("evcil_panel") == p_ad else p_ad
                ui["evcil_tab"] = 0 if ui["evcil_panel"] is None else tab_no
                yenile()
            return f

        def odaya_don(e):
            ui["evcil_panel"] = None
            ui["evcil_tab"] = 0
            yenile()

        def kafa_oksa_tikla(e):
            soz = evcil_motor.oksa_sev()
            evcil_ui["mesaj"] = soz
            yenile()
            snack(soz)

        def karin_gidikla_tikla(e):
            gece_mi = datetime.now().hour >= 23 or datetime.now().hour < 7 or gece_modu
            tepki = evcil_motor.pomodoro_tikla_tepki(calisiyor_mu=(zm["durum"] == "calisiyor"), gece_mi=gece_mi)
            evcil_ui["mesaj"] = tepki
            yenile()
            snack(f"🐾 {st['isim']}: {tepki}")

        def uyku_isik_degistir(e):
            yeni_uyku = not bool(ui.get("evcil_uyku_isik"))
            ui["evcil_uyku_isik"] = yeni_uyku
            evcil_motor.uygula_zaman_asim_kaybi(saat_kontrol=yeni_uyku)
            isim_hitap = AktifKullanici.capitalize()
            soz = (
                f"İyi geceler {isim_hitap}! 🌙 Oda ışığını kapattık, mışıl mışıl uyuyup yarınki testlere enerji toplayalım 💤"
                if yeni_uyku else
                f"Günaydın {isim_hitap}! ☀️ Enerjimizi topladık, bugün hangi dersi çözüp altın kazanıyoruz?"
            )
            evcil_ui["mesaj"] = soz
            yenile()
            snack(soz)

        def vitamin_bakim_tikla(e):
            if dengesiz:
                evcil_ui["mesaj"] = uyari_metni
                yenile()
                snack(f"⚠️ {uyari_metni}")
            else:
                ui["evcil_panel"] = "besle"
                ui["evcil_tab"] = 4
                yenile()
                snack(f"🍊 Vitamin: %{st['vitamin']:.0f} • Karbonhidrat: %{st['karbonhidrat']:.0f} • Protein: %{st['protein']:.0f}")

        # Açık oda eşyalarını ve aktif 3D sahne fotoğrafını (büyüme aşamasına göre) belirle
        acik_esya_set = {e["item_id"] for e in st["esyalar"] if e["unlocked"]}
        sahne_kod = evcil_aktif_sahne_anahtari(st)
        sahne_b64 = evcil_sahne_b64_getir(
            sahne_kod,
            ozel_sozluk=DB.get("evcil_ozel_gorsel"),
            evrim_asamasi=st["evrim_asamasi"],
        )
        sapka_emoji = {
            "sapka_tac": "👑",
            "sapka_mezun": "🎓",
            "sapka_bere": "🧢",
        }.get(st.get("secili_sapka") or "", "")

        # --- 1) TAM EKRAN 3D PIXAR / MY TALKING TOM ODA & KEDİ FOTOĞRAFI (4 BÜYÜME AŞAMALI, MOBİL & PC TAM UYUMLU) ---
        ekran_w = int(page.width or 0)
        oda_genislik = min(410, max(292, ekran_w - 22)) if ekran_w > 0 else 344
        oda_yukseklik = 500
        sahne_resim_ctrl = (
            resim_olustur(sahne_b64, width=oda_genislik, height=oda_yukseklik, fit=FIT.COVER)
            if FIT else resim_olustur(sahne_b64, width=oda_genislik, height=oda_yukseklik)
        )
        arka_plan_sahne = sahne_resim_ctrl

        # --- 2) ÜST HUD SATIRI (SEVİYE, SES, MEKTUP, GÜNLÜK — ÇAKIŞMASIZ & TAŞMASIZ) ---
        sol_ust_seviye = ft.Container(
            width=52, height=52, border_radius=26,
            bgcolor=opak(0.65, "#263238"), border=kenar(3, "#AEEA00"),
            alignment=ORTA, ink=True, on_click=panel_ac("besle", 4),
            shadow=ft.BoxShadow(blur_radius=8, color=opak(0.35, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Container(
                width=40, height=40, border_radius=20, bgcolor="#EDE7F6",
                border=kenar(1.5, "#5E35B1"), alignment=ORTA,
                content=ft.Column([
                    ft.Text(str(st["seviye"]), size=15, weight=ft.FontWeight.W_900, color="#6A1B9A"),
                    ft.Text("SV", size=7, weight=ft.FontWeight.W_800, color="#4527A0"),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            ),
        )

        ses_butonu = ft.Container(
            width=36, height=36, border_radius=18,
            bgcolor="#FFFFFF", border=kenar(2, "#263238"), alignment=ORTA,
            ink=True, on_click=karin_gidikla_tikla,
            tooltip="Kedini konuştur 🔊",
            content=ft.Text("🔊", size=15),
        )

        sag_ust_tv = ft.Container(
            padding=pad_sim(horizontal=9, vertical=6), border_radius=16,
            bgcolor="#29B6F6", border=kenar(2, "#0277BD"),
            ink=True, on_click=panel_ac("mektup", 2),
            shadow=ft.BoxShadow(blur_radius=6, color=opak(0.25, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Row([
                ft.Text("🐦✉️", size=15),
                ft.Text(f"{st['okunmamis_mektup']}" if st["okunmamis_mektup"] else "Mektup",
                        size=11, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ], spacing=4, tight=True),
        )

        sag_orta_buton = ft.Container(
            width=38, height=38, border_radius=19,
            bgcolor="#FFFFFF", border=kenar(2, "#263238"), alignment=ORTA,
            ink=True, on_click=panel_ac("mektup", 2),
            tooltip="Günlük & Mektuplar 📓",
            shadow=ft.BoxShadow(blur_radius=6, color=opak(0.25, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Text("📓", size=18),
        )

        ust_hud_satiri = ft.Container(
            left=8, right=8, top=8,
            content=ft.Row([
                sol_ust_seviye,
                ses_butonu,
                ft.Container(expand=True),
                sag_ust_tv,
                sag_orta_buton,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Konuşma Balonu (Üst HUD satırının hemen altında, hiçbir butonla çakışmaz)
        balon_txt = ft.Text(
            f"💬 \"{evcil_ui['mesaj']}\"",
            size=11, weight=ft.FontWeight.W_700, color="#263238", text_align=ft.TextAlign.CENTER,
        )
        evcil_ui["balon_txt"] = balon_txt

        konusma_balonu = ft.Container(
            left=10, right=10, top=66,
            padding=pad_sim(horizontal=10, vertical=6), border_radius=16,
            bgcolor=opak(0.94, "#FFFFFF"), border=kenar(2, "#263238"),
            shadow=ft.BoxShadow(blur_radius=8, color=opak(0.20, "#000000"), offset=ft.Offset(0, 2)),
            content=balon_txt,
        )

        # Alt Yan Yardımcı Butonlar (Alt 5'li barın hemen üstünde, sol ve sağda)
        konus_butonu = ft.Container(
            width=42, height=42, border_radius=21,
            bgcolor="#FFFFFF", border=kenar(2, "#263238"), alignment=ORTA,
            ink=True, on_click=panel_ac("oyun", 3),
            tooltip="Kedinle Konuş / Soru Sor 💬",
            shadow=ft.BoxShadow(blur_radius=6, color=opak(0.28, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Text("💬", size=19),
        )

        altin_hapi = ft.Container(
            padding=pad_sim(horizontal=9, vertical=4), border_radius=12,
            bgcolor="#FFFFFF", border=kenar(1.5, "#263238"),
            shadow=ft.BoxShadow(blur_radius=6, color=opak(0.22, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Text(f"{st['altin']} 🪙", size=11, weight=ft.FontWeight.W_900, color="#263238"),
        )

        sol_orta_buton = ft.Container(
            width=42, height=42, border_radius=21,
            bgcolor="#FFFFFF", border=kenar(2, "#263238"), alignment=ORTA,
            ink=True, on_click=panel_ac("besle", 4),
            tooltip="Mutfak & Yemekler 🍼🥣",
            shadow=ft.BoxShadow(blur_radius=6, color=opak(0.25, "#000000"), offset=ft.Offset(0, 2)),
            content=ft.Text("🐾", size=19),
        )

        orta_yan_satir = ft.Container(
            left=8, right=8, bottom=74,
            content=ft.Row([
                konus_butonu,
                altin_hapi,
                ft.Container(expand=True),
                sol_orta_buton,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # --- 3) EN ALTTAKİ 5 YUVARLAK EYLEM BUTONU (🛒 😊 🍴 🧪 🌙 — HER TELEFON EKRANINA TAM SIĞAR) ---
        def alt_yuvarlak_buton(emoji_str, alt_yazi, tikla_fn, beyaz_mi=False, parlayan_mi=False, uyari_var=False):
            arka_renk = "#FFFFFF" if beyaz_mi else ("#FF8A80" if uyari_var else "#C6FF00")
            return ft.Column([
                ft.Container(
                    width=46, height=46, border_radius=23,
                    bgcolor=arka_renk,
                    border=kenar(3 if parlayan_mi else 2, "#FFFFFF" if parlayan_mi else "#263238"),
                    shadow=ft.BoxShadow(
                        blur_radius=10 if parlayan_mi else 6,
                        color=opak(0.60, "#FFFFFF") if parlayan_mi else opak(0.35, "#000000"),
                        offset=ft.Offset(0, 2),
                    ),
                    alignment=ORTA, ink=True, on_click=tikla_fn,
                    content=ft.Text(emoji_str, size=20),
                ),
                ft.Text(alt_yazi, size=10, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        alt_bes_buton_Cubugu = ft.Container(
            left=4, right=4, bottom=6,
            content=ft.Row([
                alt_yuvarlak_buton("🛒", "Mağaza", panel_ac("magaza", 1), beyaz_mi=True),
                alt_yuvarlak_buton("😊", f"%{st['mutluluk']:.0f}", kafa_oksa_tikla, parlayan_mi=True),
                alt_yuvarlak_buton("🍴", f"%{min(st['karbonhidrat'], st['protein']):.0f}", panel_ac("besle", 4), uyari_var=dengesiz),
                alt_yuvarlak_buton("🧪", f"%{st['vitamin']:.0f}", vitamin_bakim_tikla, uyari_var=(st["vitamin"] < 25)),
                alt_yuvarlak_buton("🌙", "Uyku" if not gece_modu else "Uyandır", uyku_isik_degistir),
            ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        )

        # --- 4) 3D FOTOĞRAF ÜZERİNDEKİ ETKİLEŞİMLİ DOKUNMA BÖLGELERİ ---
        kafa_dokunma_alani = ft.Container(
            left=70, right=70, top=125, height=145, border_radius=72,
            bgcolor=SEFFAF, ink=True, on_click=kafa_oksa_tikla,
            tooltip=f"{st['isim']} başını okşa 🖐️ (+Mutluluk)",
            alignment=ft.Alignment(0, -0.85),
            content=ft.Text(sapka_emoji, size=32) if sapka_emoji else None,
        )
        govde_dokunma_alani = ft.Container(
            left=70, right=70, top=275, height=140, border_radius=65,
            bgcolor=SEFFAF, ink=True, on_click=karin_gidikla_tikla,
            tooltip=f"{st['isim']} karnını gıdıkla / konuştur 😂",
        )
        pencere_dokunma_alani = ft.Container(
            left=0, top=120, width=68, height=150,
            bgcolor=SEFFAF, ink=True, on_click=panel_ac("mektup", 2),
            tooltip="Pencere & Postacı Kuş Mektupları 🐦",
        )

        # --- TAM EKRAN 3D ODA STACK BİLEŞENİ (MOBİL VE MASAÜSTÜNDE HİÇBİR BUTON KESİLMEZ) ---
        evden_gitti_mi = bool(st.get("evden_gitti")) or st.get("durum") == "GONE"
        evden_gitti_katmani = []
        if evden_gitti_mi:
            evden_gitti_katmani.append(ft.Container(
                left=0, right=0, top=0, bottom=0,
                bgcolor=opak(0.88, "#1E1924"),
                alignment=ORTA,
                padding=22,
                content=ft.Container(
                    padding=20,
                    border_radius=22,
                    bgcolor=r["card_bg"],
                    border=kenar(2, KIRMIZI),
                    content=ft.Column([
                        ft.Text("🐾🥣", size=42, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            f"😿 {st['isim']} Evden Gitti!",
                            size=18, weight=ft.FontWeight.W_800, color=KIRMIZI, text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            f"2 gün (48 saat) boyunca hiç yemek yemediği için {st['isim']} karnını doyurmak üzere evden ayrıldı.\n"
                            f"Onu eve geri çağırmak için 🍴 Mutfak'tan hemen su, süt veya mama ikram et!",
                            size=12, color=r["txt"], text_align=ft.TextAlign.CENTER,
                        ),
                        buton(r, "🍴 Mutfağa Git & Yemek Ver (Eve Çağır)", panel_ac("besle", 4), genis=True, yukseklik=44),
                    ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ))

        oda_sahnesi = ft.Container(
            width=oda_genislik,
            height=oda_yukseklik,
            border_radius=24,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            bgcolor="#1B232A",
            border=kenar(2, r["border"]),
            shadow=ft.BoxShadow(blur_radius=16, color=opak(0.22, "#000000"), offset=ft.Offset(0, 5)),
            content=ft.Stack([
                ft.Container(left=0, right=0, top=0, bottom=0, content=arka_plan_sahne),
                *([ft.Container(
                    left=76, right=76, top=112, padding=pad_sim(horizontal=8, vertical=3),
                    border_radius=10, bgcolor=opak(0.82, "#1A237E"), border=kenar(1.5, "#FFD54F"),
                    alignment=ORTA,
                    content=ft.Text(
                        f"🎓 {'MEZUNİYET ODASI' if st['mezuniyet_odasi'] else HEDEF_UNIVERSITE}",
                        size=10, weight=ft.FontWeight.W_800, color="#FFD54F", text_align=ft.TextAlign.CENTER,
                    ),
                )] if ("kampus_poster" in acik_esya_set or st["mezuniyet_odasi"]) else []),
                pencere_dokunma_alani,
                kafa_dokunma_alani,
                govde_dokunma_alani,
                *evden_gitti_katmani,
                ust_hud_satiri,
                konusma_balonu,
                orta_yan_satir,
                alt_bes_buton_Cubugu,
            ], width=oda_genislik, height=oda_yukseklik),
        )
        oda_sahnesi_sarici = ft.Row([oda_sahnesi], alignment=ft.MainAxisAlignment.CENTER)

        # --- ÜST HIZLI GEÇİŞ ÇUBUĞU (ODA / MUTFAK / MAĞAZA / MEKTUP / KONUŞ) ---
        sekme_kod_haritasi = {None: 0, "besle": 1, "magaza": 2, "mektup": 3, "oyun": 4}
        aktif_sekme_idx = sekme_kod_haritasi.get(aktif_panel, 0)

        def ust_panel_sec(idx):
            hedef = {0: (None, 0), 1: ("besle", 4), 2: ("magaza", 1), 3: ("mektup", 2), 4: ("oyun", 3)}.get(idx, (None, 0))
            ui["evcil_panel"] = hedef[0]
            ui["evcil_tab"] = hedef[1]
            yenile()

        ust_gecis_cubugu = segment(
            r,
            ["🏠 Oda", "🍴 Mutfak", "🛒 Mağaza", "🐦 Mektup", "💬 Konuş"],
            aktif_sekme_idx,
            ust_panel_sec,
        )

        # --- HIZLI SORU SOR & BÜYÜME AŞAMASI ÇUBUĞU (HER ZAMAN ODANIN ALTINDA ERİŞİLEBİLİR) ---
        hizli_soru_in = girdi(r, f"{st['isim']}'e bir soru sor veya sohbet et...", expand=True)

        def hizli_soru_gonder(e):
            soru_metni = (hizli_soru_in.value or "").strip()
            cevap = evcil_motor.soru_cevapla(soru_metni)
            ui["evcil_soru_cevap"] = cevap
            evcil_ui["mesaj"] = cevap
            hizli_soru_in.value = ""
            yenile()
            snack(f"🐾 {st['isim']}: {cevap}")

        hizli_soru_in.on_submit = hizli_soru_gonder

        durum_Cubugu = kart(r, ft.Column([
            ft.Row([
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=4), border_radius=12, bgcolor=opak(0.14, r["hdr"]),
                    content=ft.Text(f"{evrim_ad} • Sv.{st['seviye']} ({st['xp']} XP)", size=11, weight=ft.FontWeight.W_800, color=r["hdr"]),
                ),
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=4), border_radius=12, bgcolor=opak(0.18, r["accent"]),
                    content=ft.Text(f"🪙 {st['altin']} Altın", size=11, weight=ft.FontWeight.W_800, color=r["txt"]),
                ),
                ft.Text(f"⏳ YKS: {kalan_yks_gun}g", size=11, color=r["muted"], weight=ft.FontWeight.W_700),
            ], spacing=6),
            ft.Row([
                hizli_soru_in,
                buton(r, "Sor 💬", hizli_soru_gonder, yukseklik=44),
            ], spacing=8),
        ], spacing=8), padding=12)

        # Alt panel açıkken en üstte gösterilecek kompakt kedi & durum başlığı (kaydırma gerektirmeden anında tepkiyi gösterir)
        kucuk_kedi_resim = (
            resim_olustur(sahne_b64, width=82, height=96, fit=FIT.COVER, border_radius=16)
            if FIT else resim_olustur(sahne_b64, width=82, height=96, border_radius=16)
        )
        panel_ust_kedi_karti = kart(r, ft.Row([
            ft.Container(
                width=82, height=96, border_radius=16, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                border=kenar(1.5, r["hdr"]), ink=True, on_click=odaya_don,
                content=kucuk_kedi_resim,
            ),
            ft.Column([
                ft.Row([
                    ft.Text(f"🐾 {st['isim']} ({evrim_ad})", size=13, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                    ft.Container(
                        padding=pad_sim(horizontal=8, vertical=3), border_radius=10, bgcolor=opak(0.18, r["accent"]),
                        content=ft.Text(f"🪙 {st['altin']} Altın • Sv.{st['seviye']}", size=11, weight=ft.FontWeight.W_800, color=r["txt"]),
                    ),
                ], spacing=6),
                ft.Container(
                    padding=pad_sim(horizontal=10, vertical=6), border_radius=12, bgcolor=r["bg"], border=kenar(1, r["border"]),
                    content=ft.Text(f"💬 \"{evcil_ui['mesaj']}\"", size=12, weight=ft.FontWeight.W_700, color=r["txt"]),
                ),
            ], spacing=6, expand=True),
        ], spacing=10), padding=10)

        # --- AÇILIR ALT PANELLER (BESLE/MUTFAK, MAĞAZA, MEKTUP & GÜNLÜK, KEDİNLE KONUŞ) ---
        acilir_kutu = []

        if aktif_panel == "besle":
            def yemek_satin_al_ve_besle(y_id):
                def f(e):
                    ok, msg = evcil_motor.yemekle_besle(y_id)
                    if ok:
                        evcil_ui["mesaj"] = msg
                    yenile()
                    snack(msg)
                return f

            yemek_satirlari = []
            for y in st["yemekler"]:
                acik_mi = bool(y["acik"])
                katkilar = []
                if y["karb"] > 0:
                    katkilar.append(f"🥐 +{int(y['karb'])} Karb")
                if y["prot"] > 0:
                    katkilar.append(f"🥩 +{int(y['prot'])} Prot")
                if y["vit"] > 0:
                    katkilar.append(f"🍊 +{int(y['vit'])} Vit")
                if y["mut"] > 0:
                    katkilar.append(f"💖 +{int(y['mut'])} Neşe")
                katki_yazi = " • ".join(katkilar)

                if acik_mi:
                    btn_ctrl = buton(
                        r,
                        f"Besle ({y['fiyat']} 🪙)",
                        yemek_satin_al_ve_besle(y["item_id"]),
                        ikincil=False,
                        yukseklik=38,
                    )
                else:
                    btn_ctrl = buton(
                        r,
                        f"🔒 Sv.{y['min_seviye']}'de Açılır",
                        yemek_satin_al_ve_besle(y["item_id"]),
                        ikincil=True,
                        yukseklik=38,
                    )

                yemek_satirlari.append(ft.Container(
                    padding=12, border_radius=16,
                    bgcolor=r["bg"] if acik_mi else opak(0.45, r["bg"]),
                    border=kenar(1.5 if acik_mi else 1, r["hdr"] if acik_mi else r["border"]),
                    content=ft.Row([
                        ft.Text(y["emoji"] if acik_mi else "🔒", size=28),
                        ft.Column([
                            ft.Text(
                                f"{y['ad']} ({y['fiyat']} 🪙 Altın)",
                                size=14, weight=ft.FontWeight.W_800,
                                color=r["txt"] if acik_mi else r["muted"],
                            ),
                            ft.Text(y["aciklama"], size=11, color=r["muted"]),
                            ft.Text(katki_yazi, size=11, weight=ft.FontWeight.W_700, color=r["hdr"] if acik_mi else r["muted"]),
                        ], spacing=2, expand=True),
                        btn_ctrl,
                    ], spacing=10),
                ))

            def calismaya_git(e):
                ui["sekme"] = 1
                ui["calis_tab"] = 0
                if page.navigation_bar is not None:
                    page.navigation_bar.selected_index = 1
                yenile()

            isim_in = girdi(r, st["isim"], label="Evcil Hayvanının Adı", expand=True)

            def isim_kaydet(e):
                if evcil_motor.isim_degistir(isim_in.value):
                    yenile()
                    snack("Evcil hayvanının adı güncellendi! 🐾")

            sahne_etiketleri = {
                "Normal Oda (Ayakta)": "IDLE",
                "Pomodoro (Masada Ders Çalışırken)": "STUDYING",
                "Mutlu / Kutlama (Yemek & Zıplama)": "HAPPY_JUMP",
                "Acıkmış Kedi": "HUNGRY",
                "Üzgün (Bozuk Pomodoro Silgi Cezası)": "SAD",
                "Gece Uyku Modu": "SLEEPING",
            }
            sahne_sec_dd = dd_olustur(
                list(sahne_etiketleri.keys()),
                "Normal Oda (Ayakta)",
                None,
                label="Özel Fotoğraf / GIF Yüklenecek Durum",
                border_color=r["border"], focused_border_color=r["hdr"], color=r["txt"], border_radius=14,
            )

            def ozel_gorsel_yukle(e):
                hedef_kod = sahne_etiketleri.get(sahne_sec_dd.value, "IDLE")

                def _secildi(veri, hata):
                    if hata:
                        snack(f"⚠️ {hata}")
                        return
                    if not veri:
                        return
                    b64, h = foto_hazirla(veri, maks=800, kalite=80)
                    if not b64:
                        snack(f"⚠️ {h or 'Görsel işlenemedi'}")
                        return
                    DB.setdefault("evcil_ozel_gorsel", {})[hedef_kod] = b64
                    kaydet("evcil_ozel_gorsel")
                    yenile()
                    snack("🖼️ Özel oda/kedi fotoğrafı kaydedildi!")

                foto_sec(_secildi)

            def ozel_gorsel_sifirla(e):
                DB["evcil_ozel_gorsel"] = {}
                kaydet("evcil_ozel_gorsel")
                yenile()
                snack("✨ Varsayılan 4 aşamalı 3D kedi ve oda fotoğraflarına dönüldü!")

            acilir_kutu.append(kart(r, ft.Column([
                ft.Row([
                    ft.Text(f"🍴 {st['isim']} Mutfağı & Yemek Menüsü (🪙 {st['altin']} Altın)", size=15, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                    buton(r, "✕ Odaya Dön", odaya_don, ikincil=True, yukseklik=34),
                ]),
                *([ft.Container(
                    padding=10, border_radius=12, bgcolor=opak(0.15, KIRMIZI), border=kenar(1, KIRMIZI),
                    content=ft.Text(f"⚠️ {uyari_metni}", size=12, weight=ft.FontWeight.W_700, color=KIRMIZI),
                )] if dengesiz else []),
                evcil_besin_cubugu(r, "Karbonhidrat / Enerji", "🥐", st["karbonhidrat"], "#FB8C00"),
                evcil_besin_cubugu(r, "Protein / Beyin Gücü", "🥩", st["protein"], "#1E88E5"),
                evcil_besin_cubugu(r, "Vitamin / Bağışıklık", "🍊", st["vitamin"], "#43A047"),
                evcil_besin_cubugu(r, "Neşe & Motivasyon", "💖", st["mutluluk"], r["hdr"]),
                ft.Divider(height=8, color=r["border"]),
                ft.Text("🍼 Yemek Menüsü (Başlangıçta Su, Süt ve Mama Açıktır; Seviye Atladıkça Yeni Yemekler Açılır!)",
                        size=13, weight=ft.FontWeight.W_800, color=r["hdr"]),
                *yemek_satirlari,
                ft.Divider(height=8, color=r["border"]),
                ft.Text("🪙 Nasıl Altın Kazanılır?", size=14, weight=ft.FontWeight.W_800, color=r["hdr"]),
                ft.Text("Altın yalnızca gerçek çalışmayla kazanılır: Kronometre/Pomodoro ile en az 5 dk odaklandığında, deneme neti eklediğinde veya müfredat konusu bitirdiğinde 🪙 Altın ve XP kazanırsın. (Kediyi sevmek altın vermez, yalnızca mutluluğunu artırır.)",
                        size=12, color=r["muted"]),
                buton(r, "⏱ Çalış Sekmesine Git & Altın Kazan 🪙", calismaya_git, genis=True, yukseklik=44),
                ft.Row([isim_in, buton(r, "Adı Kaydet", isim_kaydet, ikincil=True, yukseklik=44)], spacing=8),
                ft.Divider(height=8, color=r["border"]),
                ft.Text("🖼️ Oda & Kedi Görseli Özelleştir (3D Fotoğraf / GIF)", size=13, weight=ft.FontWeight.W_800, color=r["hdr"]),
                sahne_sec_dd,
                ft.Row([
                    buton(r, "Galeriden Fotoğraf/GIF Seç 📷", ozel_gorsel_yukle, ikincil=True, genis=True, yukseklik=40),
                    buton(r, "3D Varsayılana Dön", ozel_gorsel_sifirla, ikincil=True, yukseklik=40),
                ], spacing=8),
            ], spacing=10)))

        elif aktif_panel == "magaza":
            def satin_al_tikla(item_id):
                def f(e):
                    ok, msg = evcil_motor.esya_islem(item_id)
                    if ok:
                        evcil_ui["mesaj"] = msg
                    yenile()
                    if ok:
                        kutlama()
                    snack(msg)
                return f

            kategori_basliklari = [
                ("oda", "🛋️ Oda Eşyaları (Mezuniyet Odası Hedefi)"),
                ("aksesuar", "👓 Kıyafet & Aksesuarlar"),
                ("odul", "☕ Özel İkramlar & Takviyeler"),
            ]
            bolumler = [
                kart(r, ft.Row([
                    ft.Icon(ik("STORE"), color=r["hdr"], size=24),
                    ft.Column([
                        ft.Text("Mağaza & Oda Eşyaları", size=15, weight=ft.FontWeight.W_800, color=r["txt"]),
                        ft.Text(f"Bakiye: 🪙 {st['altin']} Altın • Oda: {st['acik_oda_sayisi']}/{st['toplam_oda_sayisi']}",
                                size=12, color=r["hdr"], weight=ft.FontWeight.W_700),
                    ], spacing=2, expand=True),
                    buton(r, "✕ Odaya Dön", odaya_don, ikincil=True, yukseklik=34),
                ], spacing=10), padding=14)
            ]
            for kat_kod, kat_ad in kategori_basliklari:
                kat_esyalar = [e for e in st["esyalar"] if e["kategori"] == kat_kod]
                satirlar = []
                for e in kat_esyalar:
                    if kat_kod == "odul":
                        btn_etiket, ikincil_mi = f"İkram Et ({e['fiyat']} 🪙)", False
                    elif e["unlocked"]:
                        btn_etiket = ("Çıkar" if e["equipped"] else "Tak") if kat_kod == "aksesuar" else "Odada Kurulu ✅"
                        ikincil_mi = True
                    else:
                        btn_etiket, ikincil_mi = f"Satın Al ({e['fiyat']} 🪙)", False
                    satirlar.append(ft.Container(
                        padding=12, border_radius=16, bgcolor=r["bg"], border=kenar(1, r["border"]),
                        content=ft.Row([
                            ft.Text(e["emoji"], size=28),
                            ft.Column([
                                ft.Text(e["ad"], size=14, weight=ft.FontWeight.W_800, color=r["txt"]),
                                ft.Text(e["aciklama"], size=11, color=r["muted"]),
                            ], spacing=2, expand=True),
                            buton(r, btn_etiket, satin_al_tikla(e["item_id"]), ikincil=ikincil_mi, yukseklik=38),
                        ], spacing=10),
                    ))
                bolumler.append(kart(r, ft.Column([
                    ft.Text(kat_ad, size=15, weight=ft.FontWeight.W_800, color=r["hdr"]),
                    *satirlar,
                ], spacing=10)))
            acilir_kutu.extend(bolumler)

        elif aktif_panel == "mektup":
            mektuplar = evcil_motor.mektuplari_listele()
            gunlukler = evcil_motor.gunlukleri_listele()

            def mektup_tikla(lid):
                def f(e):
                    m = evcil_motor.mektup_oku(lid)
                    if m and m["unlocked"]:
                        ui["acik_mektup"] = m
                        yenile()
                        kutlama()
                    else:
                        snack("🔒 Bu mektup henüz kilitli! Koşulu tamamlayınca Postacı Kuş getirecek 🐦")
                return f

            def bugun_gunluk_uret(e):
                bugun = bugun_str()
                dk = gun_sn(bugun) // 60
                son_net = DB["netler"][-1]["toplam"] if DB["netler"] else 0.0
                kayit = evcil_motor.gunluk_olustur(tarih_str=bugun, calisma_dk=dk, deneme_net=son_net)
                yenile()
                snack(f"📓 {kayit['baslik']} yazıldı!")

            mektup_satirlari = []
            if ui.get("acik_mektup"):
                m = ui["acik_mektup"]
                mektup_satirlari.append(ft.Container(
                    padding=16, border_radius=18, bgcolor=opak(0.14, r["hdr"]), border=kenar(2, r["hdr"]),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"💌 {m['baslik']}", size=15, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                            ft.IconButton(icon=ik("CLOSE"), icon_color=r["muted"],
                                          on_click=lambda e: (ui.update({"acik_mektup": None}), yenile())),
                        ]),
                        ft.Text(f"\"{m['gizli_mesaj']}\"", size=14, italic=True, color=r["txt"]),
                    ], spacing=8),
                ))

            for m in mektuplar:
                acik = bool(m["unlocked"])
                okundu = bool(m["read_status"])
                durum_rozet = "📖 Okundu" if (acik and okundu) else ("✨ YENİ MEKTUP!" if acik else "🔒 Kilitli")
                mektup_satirlari.append(ft.Container(
                    padding=12, border_radius=16, ink=True, on_click=mektup_tikla(m["letter_id"]),
                    bgcolor=r["bg"] if acik else opak(0.4, r["bg"]),
                    border=kenar(1.5 if (acik and not okundu) else 1, r["accent"] if (acik and not okundu) else r["border"]),
                    content=ft.Row([
                        ft.Text("🐦✉️" if acik else "🔒", size=22),
                        ft.Column([
                            ft.Text(m["baslik"], size=13, weight=ft.FontWeight.W_800, color=r["txt"] if acik else r["muted"]),
                            ft.Text(m["kosul_aciklama"], size=11, color=r["muted"]),
                        ], spacing=2, expand=True),
                        ft.Text(durum_rozet, size=11, weight=ft.FontWeight.W_700, color=r["hdr"] if acik else r["muted"]),
                    ], spacing=10),
                ))

            gunluk_satirlari = [
                ft.Container(
                    padding=12, border_radius=16, bgcolor=r["bg"], border=kenar(1, r["border"]),
                    content=ft.Column([
                        ft.Text(g["baslik"], size=13, weight=ft.FontWeight.W_800, color=r["hdr"]),
                        ft.Text(g["icerik"], size=12, color=r["txt"]),
                    ], spacing=4),
                )
                for g in gunlukler
            ] or [ft.Text("Henüz günlük yazılmamış. Aşağıdaki butonla bugünün özetini yazdırabilirsin 📓",
                          size=12, italic=True, color=r["muted"])]

            acilir_kutu.extend([
                kart(r, ft.Column([
                    ft.Row([
                        ft.Text("🐦 Postacı Kuş'un Sürpriz Mektupları", size=15, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                        buton(r, "✕ Odaya Dön", odaya_don, ikincil=True, yukseklik=34),
                    ]),
                    *mektup_satirlari,
                ], spacing=10)),
                kart(r, ft.Column([
                    bolum_basligi(r, ik("MENU_BOOK"), f"📓 {st['isim']} Yoldaşın Günlüğü"),
                    buton(r, "Bugünün Günlüğünü Yazdır ✍️", bugun_gunluk_uret, genis=True, ikincil=True, yukseklik=42),
                    *gunluk_satirlari,
                ], spacing=10)),
            ])

        elif aktif_panel == "oyun":
            soru_kutu_in = girdi(r, f"{st['isim']}'e istediğin soruyu sor...", label="Sorun veya Mesajın", expand=True)

            def soru_sor_tikla(metin_belirli=None):
                def f(e):
                    s_metin = metin_belirli if metin_belirli is not None else (soru_kutu_in.value or "").strip()
                    cevap = evcil_motor.soru_cevapla(s_metin)
                    ui["evcil_soru_cevap"] = cevap
                    evcil_ui["mesaj"] = cevap
                    yenile()
                    snack(f"🐾 {st['isim']}: {cevap}")
                return f

            soru_kutu_in.on_submit = soru_sor_tikla(None)

            hazir_sorular = [
                "Bugün nasılsın?",
                "Karnın aç mı, ne yemek istersin?",
                "YKS'ye nasıl çalışmalıyım?",
                "Matematik netlerim nasıl artar?",
                "Çok yoruldum, bana motivasyon ver!",
                "Türkçe paragraf taktiği ver",
                "Fen derslerini nasıl tekrar edeyim?",
                "Ne zaman büyüyeceksin?",
            ]
            hazir_butonlar = [
                buton(r, f"💬 {hs}", soru_sor_tikla(hs), ikincil=True, genis=True, yukseklik=40)
                for hs in hazir_sorular
            ]

            acilir_kutu.append(kart(r, ft.Column([
                ft.Row([
                    ft.Text(f"💬 {st['isim']} ile Konuş & Soru Sor", size=15, weight=ft.FontWeight.W_800, color=r["hdr"], expand=True),
                    buton(r, "✕ Odaya Dön", odaya_don, ikincil=True, yukseklik=34),
                ]),
                ft.Container(
                    padding=14, border_radius=16, bgcolor=r["bg"], border=kenar(1.5, r["hdr"]),
                    content=ft.Text(
                        f"🐾 {st['isim']}: \"{ui.get('evcil_soru_cevap') or evcil_ui['mesaj']}\"",
                        size=13, weight=ft.FontWeight.W_700, color=r["txt"],
                    ),
                ),
                ft.Row([
                    soru_kutu_in,
                    buton(r, "Sor 💬", soru_sor_tikla(None), yukseklik=46),
                ], spacing=8),
                ft.Text("✨ Hızlı Sorular (Her tıklamada farklı cevaplar verir):", size=12, weight=ft.FontWeight.W_700, color=r["muted"]),
                *hazir_butonlar,
            ], spacing=10)))

        if aktif_panel is not None:
            return ft.Column([
                ust_gecis_cubugu,
                panel_ust_kedi_karti,
                *acilir_kutu,
                ft.Container(height=16),
            ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

        return ft.Column([
            ust_gecis_cubugu,
            oda_sahnesi_sarici,
            durum_Cubugu,
            ft.Container(height=16),
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    # ==========================================
    # 15. DİĞER MENÜSÜ
    # ==========================================
    ALT_SAYFALAR = {
        "evcil": (ik("PETS"), "Evcil Hayvanım 🐾", "Sanal evcil hayvanın, odası, mutfak, mağaza ve mektuplar", evcil_sayfasi_olustur),
        "gunsonu": (ik("NIGHTLIGHT_ROUND"), "Gün Sonu", "Süre, performans ve günlük kayıtların", gun_sonu_sayfasi_olustur),
        "bildirim": (ik("NOTIFICATIONS_ACTIVE"), "Bildirimler", "Çalışma, sohbet, seri ve oyun bildirimleri", bildirim_sayfasi_olustur),
        "asistan": (ik("SMART_TOY"), "Asistan", "Sorularına Arda'dan cevap", asistan_sayfasi_olustur),
        "eglence": (ik("SPORTS_ESPORTS"), "Eğlence & Mola", "Botla XOX ve YouTube kısayolları", eglence_sayfasi_olustur),
        "muzik": (ik("HEADPHONES"), "Odak Müzik", "Spotify ve odak sesleri", muzik_sayfasi_olustur),
        "tema": (ik("PALETTE"), "Görünüm", "Tema seç", tema_sayfasi_olustur),
        "panel": (ik("ADMIN_PANEL_SETTINGS"), "Arda'nın Paneli", "Canlı veri, seri, oyun, görev, not, Postacı Kuş mektubu", panel_sayfasi_olustur),
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
            # Kullanıcıya özel SQLite veritabanına geç ve buluttaki evcil/altın verisini senkronla
            evcil_motor.kapat()
            evcil_motor.__init__(evcil_db_dosyasi(ad), kullanici_adi=ad, on_degisim=evcil_buluta_kaydet)
            if not yeni_hesap and DB.get("evcil"):
                evcil_buluttan_yukle(DB["evcil"], zorla=True)
            else:
                evcil_buluta_kaydet()
            aktif_sayac_yukle()
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
    kok = ft.Container(expand=True, padding=pad_only(left=10, right=10, top=8, bottom=0))
    ui_kapsayici = ft.Container(expand=True)

    def birlestir(eski, yeni):
        """Aynı sayfayı yeniden çizerken eski Column'u korur, sadece içeriğini değiştirir.
        Böylece her dokunuşta sayfa en başa atmaz, kaydırma konumu aynı kalır."""
        if not (isinstance(eski, ft.Column) and isinstance(yeni, ft.Column)):
            return False
        if getattr(eski, "_Control__uid", "ok") is None:
            return False
        if eski.scroll:
            eski.controls = yeni.controls
            return True
        if len(eski.controls) != len(yeni.controls):
            return False
        for i, (a, b) in enumerate(zip(eski.controls, yeni.controls)):
            if isinstance(a, ft.Column) and isinstance(b, ft.Column) and a.scroll and getattr(a, "_Control__uid", "ok") is not None:
                a.controls = b.controls
            else:
                eski.controls[i] = b
        return True

    def sayfa_anahtari():
        s_, a = ui["sekme"], (ui["sekme"], ui["alt"])
        if s_ == 1:
            a += (ui.get("calis_tab", 0), zm["durum"], zm["mod"], bool(ui.get("ilk_ders_paylasim_acik")))
        elif s_ == 2:
            a += (ui["net_tab"], ui.get("duzenlenen_net_idx"))
        elif s_ == 3:
            a += (ui.get("evcil_panel"), ui["evcil_tab"], ui["acik_mektup"]["letter_id"] if isinstance(ui.get("acik_mektup"), dict) else None)
        elif s_ == 4:
            a += (ui["sosyal_alt"], ui["sohbet_tab"], ui["aktif_dm"], bool(ui.get("sosyal_ek_paylasim_acik")))
        elif s_ == 5 and ui["alt"] == "evcil":
            a += (ui.get("evcil_panel"), ui["evcil_tab"], ui["acik_mektup"]["letter_id"] if isinstance(ui.get("acik_mektup"), dict) else None)
        elif s_ == 5 and ui["alt"] == "eglence":
            a += (ui["eglence_tab"],)
        elif s_ == 5 and ui["alt"] == "panel":
            a += (ui["panel_giris"], ui["panel_tab"], ui["panel_ogrenci"], ui.get("panel_kopya_kaynak"))
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
            yeni = evcil_sayfasi_olustur(r)
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
        if ui["sekme"] == 1 and zm["durum"] == "calisiyor":
            tik_baslat()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0, on_change=nav_degisti, height=68,
        destinations=[
            ft.NavigationBarDestination(icon=ik("HOME_OUTLINED"), selected_icon=ik("HOME"), label="Ana"),
            ft.NavigationBarDestination(icon=ik("TIMER_OUTLINED"), selected_icon=ik("TIMER"), label="Çalış"),
            ft.NavigationBarDestination(icon=ik("SHOW_CHART_OUTLINED"), selected_icon=ik("SHOW_CHART"), label="Netler"),
            ft.NavigationBarDestination(icon=ik("PETS"), selected_icon=ik("PETS"), label="Evcil"),
            ft.NavigationBarDestination(icon=ik("FORUM_OUTLINED"), selected_icon=ik("FORUM"), label="Sosyal"),
            ft.NavigationBarDestination(icon=ik("GRID_VIEW_OUTLINED"), selected_icon=ik("GRID_VIEW"), label="Menü"),
        ],
    )

    def giris_ac():
        with ui_kilit:
            page.navigation_bar.visible = False
            kok.content = duzelt(giris_ekrani_olustur(renk()))
            page.update()

    def uygulama_ac():
        with ui_kilit:
            ui["sekme"] = 0
            ui["alt"] = None
            ui["_anahtar"] = None
            page.navigation_bar.selected_index = 0
            page.navigation_bar.visible = True
            bildirim_konu_hazirla()
            aktif_isaretle("")
            icerik_guncelle(renk())
            kok.content = ui_kapsayici
            page.update()
        # Açılışta seri başarımlarının ana sayfada güncel olması için seri tablosunu arka planda çek
        arka_plan(lambda: (sosyal_cek("dm_liste"), yenile()))

    def tema_uygula(isim, kaydetme=True):
        with ui_kilit:
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

    # ---------- arka plan döngüleri (Hem Flet 1.0 asyncio hem 0.2x thread uyumlu) ----------
    def _geri_sayim_tik_uygula():
        if kok.content is not ui_kapsayici or ui["sekme"] != 0 or not gk.get("metinler"):
            return
        toplam = int((YKS_TARIHI - datetime.now()).total_seconds())
        if toplam <= 0:
            return
        degerler = (toplam // 86400, (toplam % 86400) // 3600, (toplam % 3600) // 60, toplam % 60)
        with ui_kilit:
            metin_list = gk.get("metinler") or []
            for t, d in zip(metin_list, degerler):
                t.value = str(d)
                try:
                    t.update()
                except Exception:
                    pass
            try:
                page.update()
            except Exception:
                try:
                    _flet_agac_onar()
                    page.update()
                except Exception:
                    pass

    async def _async_canli_saat_gorevi():
        """Flet'in ana asyncio döngüsü üzerinde her yarım saniyede çalışarak hem Kronometre/Pomodoro'yu
        hem de Ana Sayfa YKS geri sayımını pencere/uygulama değiştirmeye gerek kalmadan kesintisiz akıtır."""
        gk["async_aktif"] = True
        tur_s = 0
        try:
            while True:
                await asyncio.sleep(0.5)
                tur_s += 1
                try:
                    if zm["durum"] == "calisiyor":
                        _sayac_ui_tik_uygula()
                    if tur_s % 2 == 0:
                        _geri_sayim_tik_uygula()
                except Exception:
                    pass
        finally:
            gk["async_aktif"] = False

    def geri_sayim_dongusu():
        """Ana sayfadaki YKS geri sayımını her saniye kesintisiz yeniler (Flet 0.2x thread yedeği)."""
        while True:
            time.sleep(1)
            try:
                if not gk.get("async_aktif"):
                    _geri_sayim_tik_uygula()
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
                bulut_evcil = bulut_get(f"users/{kul}/evcil") or {}
            except Exception:
                continue
            evcil_degisti = False
            if isinstance(bulut_evcil, dict) and bulut_evcil and "evcil" not in oturum["kirli"]:
                evcil_degisti = evcil_buluttan_yukle(bulut_evcil, zorla=False)
            sinyal = {"aktif": bool(sg.get("aktif")), "mesaj": sg.get("mesaj", "")}
            if sinyal == DB["sinyal"] and gorev == DB["ozel_gorevler"] and not evcil_degisti:
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
        - Açık özel sohbet (DM): ~2.0 sn
        - Genel sohbet / Ders başlangıç akışı: ~3.0 sn
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
                if alt == "sohbet" and ui.get("aktif_dm"):
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
        """Yönetici tarafı: panel açıkken öğrenci verilerini arka planda hafifçe yeniler, yeni kayıtta haber verir."""
        while True:
            time.sleep(8)
            try:
                if not (kok.content is ui_kapsayici and ui["sekme"] == 5 and ui["alt"] == "panel"
                        and ui["panel_giris"] and ui["panel_tab"] == 0 and panel["kap"] is not None):
                    continue
                users = bulut_oku() or {}
                seriler_all = bulut_get("seri") or {}
                dm_index_all = bulut_get("dm_index") or {}
                yeni = imza_hesapla(users)
                for u, (g_, n_) in yeni.items():
                    og, on = panel["imza"].get(u, (g_, n_))
                    if g_ > og:
                        snack(f"🔔 {u} gün sonunu kaydetti!")
                    if n_ > on:
                        snack(f"🔔 {u} yeni deneme ekledi!")
                panel["imza"] = yeni
                panel["veri"] = users
                panel["seriler"] = seriler_all
                panel["dm_index"] = dm_index_all
                panel["son_cek"] = time.time()
                panel["kap"].controls = ogrenci_kartlari(renk(), users, seriler_all, dm_index_all) or \
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
            if DB.get("evcil"):
                evcil_buluttan_yukle(DB["evcil"], zorla=True)
            else:
                evcil_buluta_kaydet()
            aktif_sayac_yukle()
            tema_uygula(DB["tema"], kaydetme=False)
            bildirim_konu_hazirla()
            aktif_isaretle()
        except Exception as ex:
            print("Bulut eşitleme hatası:", ex)

    # Test ortamında dışarıdan erişim için yardımcı kancalar (hooks)
    page._test_hooks = {
        "DB": DB,
        "ui": ui,
        "zm": zm,
        "oturum": oturum,
        "sosyal": sosyal,
        "panel": panel,
        "yenile": yenile,
        "sosyal_getir": sosyal_getir,
        "dm_mesaj_gonder_islem": dm_mesaj_gonder_islem,
        "ders_baslangic_postu_olustur": ders_baslangic_postu_olustur,
        "panel_veri_cek_islem": panel_veri_cek_islem,
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
        "buluttan_esitle": buluttan_esitle,
        "evcil_motor": evcil_motor,
        "evcil_ui": evcil_ui,
        "evcil_buluta_kaydet": evcil_buluta_kaydet,
        "evcil_buluttan_yukle": evcil_buluttan_yukle,
        "gecen_sn": gecen_sn,
        "sayac_farkini_ekle": sayac_farkini_ekle,
        "aktif_sayac_kaydet": aktif_sayac_kaydet,
        "aktif_sayac_yukle": aktif_sayac_yukle,
        "krono_bitir_kaydet": krono_bitir_kaydet,
        "excel_olustur_islem": excel_olustur_islem,
        "deneme_sil_islem": deneme_sil_islem,
        "deneme_duzenle_islem": deneme_duzenle_islem,
        "denemeleri_baska_hesaba_kopyala_islem": denemeleri_baska_hesaba_kopyala_islem,
        "kronometre_su_bildirim_kontrol": kronometre_su_bildirim_kontrol,
        "canli_calisma_odasi_cek": canli_calisma_odasi_cek,
        "plan_gecmise_ekle": plan_gecmise_ekle,
        "plan_onerileri_bul": plan_onerileri_bul,
        "haftalik_programi_tamamen_sifirla_islem": haftalik_programi_tamamen_sifirla_islem,
        "gk": gk,
    }

    def _pencere_boyut_degisti(e):
        try:
            w = getattr(e, "width", None) or getattr(getattr(e, "data", None), "width", None)
            h = getattr(e, "height", None) or getattr(getattr(e, "data", None), "height", None)
            if w:
                page.width = float(w)
            if h:
                page.height = float(h)
        except Exception:
            pass
        if kok.content is ui_kapsayici:
            yenile()
        else:
            with ui_kilit:
                try:
                    page.update()
                except Exception:
                    pass

    try:
        page.on_resized = _pencere_boyut_degisti
        page.on_resize = _pencere_boyut_degisti
    except Exception:
        pass

    page.add(ft.SafeArea(content=kok, expand=True))
    tema_uygula(DB["tema"], kaydetme=False)
    if hasattr(page, "run_task"):
        try:
            page.run_task(_async_canli_saat_gorevi)
        except Exception:
            pass
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
