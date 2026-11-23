import flet as ft
import os
import io
import time
import copy
import base64
import hashlib
from datetime import datetime, date, timedelta
from ayarlar import (
    ISTANBUL_TZ, GUNLER, HAFTALIK_PLAN, TEMA_RENKLERI, VARSAYILAN_TEMA,
    VARSAYILAN_VERI, VARSAYILAN_BILDIRIM, VARSAYILAN_AKTIF_SAYAC,
    TARIHLI_ANAHTARLAR, LISTE_ANAHTARLARI, KIRMIZI, YESIL, TURUNCU, SEFFAF,
)

# ==========================================
# SÜRÜM UYUMLULUK KATMANI
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
    "PETS": ("EMOJI_EMOTIONS", "FAVORITE", "STAR"),
    "STORE": ("SHOPPING_CART", "CARD_GIFTCARD", "STAR"),
    "MENU_BOOK": ("BOOK", "EDIT_NOTE", "EVENT_NOTE"),
    "WEEKEND": ("HOME", "BEDTIME", "STAR"),
    "DOWNLOAD": ("FILE_DOWNLOAD", "SAVE_ALT", "SAVE", "OPEN_IN_NEW"),
    "TABLE_CHART": ("GRID_ON", "BAR_CHART", "SHOW_CHART"),
    "CONTENT_COPY": ("COPY", "FILE_COPY", "SHARE", "SEND"),
    "SELECT_ALL": ("DONE_ALL", "CHECK_BOX", "CHECKLIST"),
}


def ik(ad):
    """İkon adını hangi Flet sürümü olursa olsun bulur, bulamazsa benzerini/yedeğini verir."""
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
    """#AARRGGBB üretir (Flet sürüm farkından bağımsız)."""
    h = renk_hex.lstrip("#")
    if len(h) == 8:
        h = h[2:]
    return "#{:02X}{}".format(int(max(0.0, min(1.0, oran)) * 255), h)


ORTA = ft.Alignment(0, 0)
UST_SOL = ft.Alignment(-1, -1)
ALT_SAG = ft.Alignment(1, 1)


def kenar(genislik, renk_):
    k = ft.BorderSide(genislik, renk_)
    return ft.Border(top=k, right=k, bottom=k, left=k)


def kose(top_left=0, top_right=0, bottom_left=0, bottom_right=0):
    br_cls = getattr(ft, "BorderRadius", None)
    if br_cls is not None:
        try:
            return br_cls(top_left=top_left, top_right=top_right, bottom_left=bottom_left, bottom_right=bottom_right)
        except Exception:
            pass
    br_mod = getattr(ft, "border_radius", None)
    if br_mod is not None and hasattr(br_mod, "only"):
        try:
            return br_mod.only(top_left=top_left, top_right=top_right, bottom_left=bottom_left, bottom_right=bottom_right)
        except Exception:
            pass
    return max(top_left, top_right, bottom_left, bottom_right)


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
    """Base64, data:image/svg+xml;base64 veya dosya yolu resmi gösterir."""
    if FIT is not None:
        kw.setdefault("fit", FIT.COVER)
    if not b64:
        return ft.Container(**{k: v for k, v in kw.items() if k in ("width", "height")})
    if isinstance(b64, str) and len(b64) < 260 and not b64.startswith("data:") and os.path.exists(b64):
        try:
            return ft.Image(src=b64, **kw)
        except Exception:
            try:
                with open(b64, "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode("ascii")
            except Exception:
                pass
    temiz_b64 = b64.split(",", 1)[1] if isinstance(b64, str) and b64.startswith("data:") else b64
    try:
        return ft.Image(src_base64=temiz_b64, **kw)
    except TypeError:
        pass
    try:
        veri_uri = b64 if (isinstance(b64, str) and b64.startswith("data:")) else f"data:image/jpeg;base64,{temiz_b64}"
        return ft.Image(src=veri_uri, **kw)
    except TypeError:
        pass
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


def bugun_str():
    return date.today().strftime("%d.%m.%Y")


def sayi(deger, varsayilan=0.0):
    try:
        return float(str(deger).replace(",", ".").strip())
    except (ValueError, TypeError):
        return varsayilan


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
    """Yazılabilen ilk klasörü seçer (mobilde uygulama klasörü salt-okunur olabilir)."""
    import tempfile
    adaylar = [
        os.environ.get("FLET_APP_STORAGE_DATA"),
        os.environ.get("FLET_APP_STORAGE_TEMP"),
        os.path.expanduser("~"),
        os.path.dirname(os.path.abspath(__file__)),
        tempfile.gettempdir(),
    ]
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
    """Firebase'den (veya dosyadan) gelen ham veriyi eksiksiz bir DB sözlüğüne çevirir."""
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
    for k in ("su", "gun", "sinyal", "bildirim", "calisma_sn", "calisma_log", "aktif_sayac", "evcil", "evcil_ozel_gorsel"):
        if not isinstance(db.get(k), dict):
            db[k] = copy.deepcopy(VARSAYILAN_VERI[k])
    b_ = copy.deepcopy(VARSAYILAN_BILDIRIM)
    b_.update(db["bildirim"])
    db["bildirim"] = b_
    s_ = copy.deepcopy(VARSAYILAN_AKTIF_SAYAC)
    s_.update(db["aktif_sayac"])
    db["aktif_sayac"] = s_
    if db["tema"] not in TEMA_RENKLERI:
        db["tema"] = VARSAYILAN_TEMA
    return db


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
