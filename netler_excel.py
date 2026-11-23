import os
import io
import re
import time
import base64
import zipfile
import threading
import subprocess
from datetime import datetime, date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from xml.sax.saxutils import escape as xml_esc
from ayarlar import PERFORMANS, GUN_KISA
from bilesenler import sayi, bugun_str
from oyun_mantik import tr_buyuk


# ==========================================
# 1. DENEME VERİSİNİ STANDARTLAŞTIRMA
# ==========================================
def deneme_satiri_ayristir(kayit, varsayilan_tarih=None):
    """Deneme kaydından (ad, tarih, tr, sos, mat, fen, toplam, dersler_dict) döndürür."""
    k = kayit if isinstance(kayit, dict) else {}
    ad = str(k.get("ad") or "Genel Deneme").strip()
    tarih = str(k.get("tarih") or varsayilan_tarih or bugun_str()).strip()
    dersler = k.get("dersler") if isinstance(k.get("dersler"), dict) else {}

    def d_al(*anahtarlar):
        for a in anahtarlar:
            if a in dersler and dersler[a] is not None:
                return round(float(sayi(dersler[a], 0.0)), 2)
            if a in k and k[a] is not None:
                return round(float(sayi(k[a], 0.0)), 2)
        return 0.0

    tr_net = d_al("Türkçe", "tr", "TURKCE", "Türk Dili ve Edebiyatı")
    sos_net = d_al("Sosyal", "sos", "SOSYAL", "Tarih-1", "Tarih")
    mat_net = d_al("Matematik", "mat", "MAT", "Geometri")
    fen_net = d_al("Fen", "fen", "FEN", "Fizik")

    if "toplam" in k and k["toplam"] is not None:
        toplam = round(float(sayi(k["toplam"], 0.0)), 2)
    else:
        toplam = round(tr_net + sos_net + mat_net + fen_net, 2)

    return {
        "ad": ad,
        "tarih": tarih,
        "tr": tr_net,
        "sos": sos_net,
        "mat": mat_net,
        "fen": fen_net,
        "toplam": toplam,
        "dersler": dersler,
    }


def _tr_sayi_str(val):
    """Ondalık sayıyı Türkçe Excel biçiminde (90,75 veya 34) gösterir."""
    v = round(float(val or 0.0), 2)
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}".replace(".", ",")


# ==========================================
# 2. UYGULAMA İÇİ SVG GRAFİK ÜRETİCİSİ
#    (Flet sürümünden bağımsız, PC ve Mobilde %100 çalışan 5'li Dashboard Grafiği)
# ==========================================
def net_svg_grafik_olustur(liste, r=None, sinav_adi="TYT", kullanici=""):
    """Deneme listesini kullanıcının istediği 5 grafikli (Türkçe, Sosyal, Matematik, Fen +
    Altta Sütun-Çizgi Genel Grafik) gösterge paneli görünümünde yüksek çözünürlüklü SVG'ye çevirir
    ve data:image/svg+xml;base64,... olarak döndürür.
    """
    satirlar = [deneme_satiri_ayristir(x) for x in (liste or [])][-10:]
    if not satirlar:
        satirlar = [{"ad": "Örnek Deneme", "tarih": bugun_str(), "tr": 0, "sos": 0, "mat": 0, "fen": 0, "toplam": 0}]

    kul_baslik = tr_buyuk((kullanici or "ÖĞRENCİ").strip())
    sinav_u = tr_buyuk(sinav_adi or "TYT")
    ana_baslik = f"{kul_baslik} {sinav_u} DENEMELERİ"

    W, H = 860, 620
    parcalar = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%">',
        "<defs>",
        '<linearGradient id="bgDark" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#3A3A3A"/><stop offset="100%" stop-color="#222222"/></linearGradient>',
        '<linearGradient id="bgLight" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#F7F7F7"/><stop offset="100%" stop-color="#DCDCDC"/></linearGradient>',
        "</defs>",
        f'<rect width="{W}" height="{H}" rx="18" fill="#181820"/>',
        # Üst Mor Başlık Bandı
        f'<rect x="14" y="12" width="{W - 28}" height="40" rx="10" fill="#7030A0"/>',
        f'<text x="{W // 2 - 70}" y="38" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="19" font-weight="bold" text-anchor="middle">{xml_esc(ana_baslik)}</text>',
        f'<rect x="{W - 210}" y="18" width="186" height="28" rx="8" fill="#FFFFFF" fill-opacity="0.18"/>',
        f'<text x="{W - 117}" y="36" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="12" font-weight="bold" text-anchor="middle">📊 Excel İndir (Tıkla)</text>',
    ]

    # Yardımcı mini çizgi grafik çizici
    def mini_cizgi_grafik(x0, y0, gw, gh, baslik, anahtar, koyu_mu=False, maks_y=40.0):
        bg_url = "url(#bgDark)" if koyu_mu else "url(#bgLight)"
        txt_renk = "#FFFFFF" if koyu_mu else "#333333"
        grid_renk = "#555555" if koyu_mu else "#C8C8C8"
        parcalar.append(f'<rect x="{x0}" y="{y0}" width="{gw}" height="{gh}" rx="10" fill="{bg_url}" stroke="#444444" stroke-width="1"/>')
        parcalar.append(
            f'<text x="{x0 + gw / 2:.1f}" y="{y0 + 26}" fill="{txt_renk}" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="16" font-weight="bold" text-anchor="middle">{xml_esc(baslik)}</text>'
        )
        px0, py0 = x0 + 36, y0 + 42
        pw, ph = gw - 54, gh - 70
        degerler = [float(s.get(anahtar, 0.0)) for s in satirlar]
        ust_sinir = max(maks_y, max(degerler or [10.0]) * 1.15, 5.0)
        for i_g in range(4):
            gy = py0 + ph * (i_g / 3.0)
            g_val = ust_sinir * (1.0 - i_g / 3.0)
            parcalar.append(f'<line x1="{px0}" y1="{gy:.1f}" x2="{px0 + pw}" y2="{gy:.1f}" stroke="{grid_renk}" stroke-width="0.8"/>')
            parcalar.append(
                f'<text x="{px0 - 6}" y="{gy + 4:.1f}" fill="{txt_renk}" font-family="Segoe UI, Arial, sans-serif" '
                f'font-size="9" text-anchor="end">{g_val:.0f}</text>'
            )

        n = len(satirlar)
        noktalar = []
        for idx, s in enumerate(satirlar):
            nx = px0 + (pw / 2.0 if n == 1 else (idx * pw / (n - 1)))
            val = float(s.get(anahtar, 0.0))
            ny = py0 + ph - (min(val, ust_sinir) / ust_sinir) * ph
            noktalar.append((nx, ny, val, s["tarih"]))

        if len(noktalar) >= 2:
            poly = " ".join(f"{nx:.1f},{ny:.1f}" for nx, ny, _, _ in noktalar)
            parcalar.append(f'<polyline fill="none" stroke="#156082" stroke-width="3" points="{poly}"/>')

        for nx, ny, val, trh in noktalar:
            parcalar.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="11" fill="#156082"/>')
            parcalar.append(
                f'<text x="{nx:.1f}" y="{ny + 3.5:.1f}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
                f'font-size="8.5" font-weight="bold" text-anchor="middle">{xml_esc(_tr_sayi_str(val))}</text>'
            )
            kisa_trh = trh[:5] if len(satirlar) > 5 else trh
            parcalar.append(
                f'<text x="{nx:.1f}" y="{py0 + ph + 18:.1f}" fill="{txt_renk}" font-family="Segoe UI, Arial, sans-serif" '
                f'font-size="9.5" text-anchor="middle">{xml_esc(kisa_trh)}</text>'
            )

    # Üst 2x2: TÜRKÇE ve SOSYAL (açık tema), MATEMATİK ve FEN (koyu tema)
    mini_cizgi_grafik(14, 62, 265, 165, "TÜRKÇE", "tr", koyu_mu=False, maks_y=40.0)
    mini_cizgi_grafik(290, 62, 265, 165, "SOSYAL", "sos", koyu_mu=False, maks_y=20.0)
    mini_cizgi_grafik(566, 62, 280, 165, "MATEMATİK", "mat", koyu_mu=True, maks_y=40.0)
    mini_cizgi_grafik(566, 238, 280, 165, "FEN", "fen", koyu_mu=True, maks_y=20.0)

    # Sol Orta: Excel Tablosu Önizlemesi (Siyah-Mor Görünüm)
    tx0, ty0, tw, th = 14, 238, 541, 165
    parcalar.append(f'<rect x="{tx0}" y="{ty0}" width="{tw}" height="{th}" rx="10" fill="#111116" stroke="#444444" stroke-width="1"/>')
    parcalar.append(f'<rect x="{tx0}" y="{ty0}" width="{tw}" height="24" rx="8" fill="#7030A0"/>')
    parcalar.append(
        f'<text x="{tx0 + tw / 2:.1f}" y="{ty0 + 16}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="12" font-weight="bold" text-anchor="middle">{xml_esc(ana_baslik)}</text>'
    )
    kolonlar = [("DENEME ADI", 135), ("TARİH", 82), ("TÜRKÇE", 64), ("SOSYAL", 64), ("MAT", 60), ("FEN", 60), ("TOPLAM", 76)]
    cx = tx0
    hy = ty0 + 24
    parcalar.append(f'<rect x="{tx0}" y="{hy}" width="{tw}" height="20" fill="#262626"/>')
    for k_ad, k_w in kolonlar:
        parcalar.append(
            f'<text x="{cx + k_w / 2:.1f}" y="{hy + 14}" fill="#E0E0E0" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" font-weight="bold" text-anchor="middle">{xml_esc(k_ad)}</text>'
        )
        cx += k_w

    gosterilen_satirlar = satirlar[-5:]
    for r_idx, s in enumerate(gosterilen_satirlar):
        ry = hy + 20 + r_idx * 23
        bg_r = "#0D0D0D" if r_idx % 2 == 0 else "#181820"
        parcalar.append(f'<rect x="{tx0}" y="{ry}" width="{tw}" height="22" fill="{bg_r}"/>')
        deger_list = [
            s["ad"][:18], s["tarih"],
            _tr_sayi_str(s["tr"]), _tr_sayi_str(s["sos"]),
            _tr_sayi_str(s["mat"]), _tr_sayi_str(s["fen"]),
            _tr_sayi_str(s["toplam"]),
        ]
        cx = tx0
        for (_, k_w), d_txt in zip(kolonlar, deger_list):
            parcalar.append(
                f'<text x="{cx + k_w / 2:.1f}" y="{ry + 15}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
                f'font-size="10" font-weight="bold" text-anchor="middle">{xml_esc(d_txt)}</text>'
            )
            cx += k_w

    # En Alt: GENEL COMBO GRAFİK (4 Ders Sütun + Toplam Mor Çizgi + Tarih ve Deneme Adı)
    gx0, gy0, gw, gh = 14, 412, W - 28, 196
    parcalar.append(f'<rect x="{gx0}" y="{gy0}" width="{gw}" height="{gh}" rx="12" fill="url(#bgDark)" stroke="#444444" stroke-width="1"/>')
    parcalar.append(
        f'<text x="{gx0 + gw / 2:.1f}" y="{gy0 + 24}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="15" font-weight="bold" text-anchor="middle">{xml_esc(ana_baslik)} - GENEL GRAFİK</text>'
    )
    c_px0, c_py0 = gx0 + 44, gy0 + 36
    c_pw, c_ph = gw - 68, gh - 92
    maks_top = max(120.0, max((s["toplam"] for s in satirlar), default=100.0) * 1.1)

    for i_g in range(5):
        gy = c_py0 + c_ph * (i_g / 4.0)
        g_val = maks_top * (1.0 - i_g / 4.0)
        parcalar.append(f'<line x1="{c_px0}" y1="{gy:.1f}" x2="{c_px0 + c_pw}" y2="{gy:.1f}" stroke="#555555" stroke-width="0.8"/>')
        parcalar.append(
            f'<text x="{c_px0 - 8}" y="{gy + 4:.1f}" fill="#CCCCCC" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" text-anchor="end">{g_val:.0f}</text>'
        )

    n = len(satirlar)
    grup_w = c_pw / max(1, n)
    bar_renkler = [("tr", "#156082"), ("sos", "#E97132"), ("mat", "#196B24"), ("fen", "#0F9ED5")]
    bar_w = min(16.0, max(6.0, (grup_w * 0.62) / 4.0))
    toplam_noktalar = []

    for idx, s in enumerate(satirlar):
        merkez_x = c_px0 + grup_w * (idx + 0.5)
        bas_x = merkez_x - (bar_w * 2.0)
        for b_i, (k_anahtar, b_renk) in enumerate(bar_renkler):
            val = max(0.0, float(s.get(k_anahtar, 0.0)))
            bh = (min(val, maks_top) / maks_top) * c_ph
            bx = bas_x + b_i * bar_w
            by = c_py0 + c_ph - bh
            parcalar.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 1.2:.1f}" height="{max(1.5, bh):.1f}" fill="{b_renk}"/>')

        t_val = max(0.0, float(s["toplam"]))
        ty = c_py0 + c_ph - (min(t_val, maks_top) / maks_top) * c_ph
        toplam_noktalar.append((merkez_x, ty, t_val))

        # 2 katmanlı X ekseni: Üstte Tarih, Altta Deneme Adı
        parcalar.append(
            f'<text x="{merkez_x:.1f}" y="{c_py0 + c_ph + 15:.1f}" fill="#E0E0E0" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" text-anchor="middle">{xml_esc(s["tarih"])}</text>'
        )
        parcalar.append(
            f'<text x="{merkez_x:.1f}" y="{c_py0 + c_ph + 29:.1f}" fill="#BDBDBD" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" text-anchor="middle">{xml_esc(s["ad"][:14])}</text>'
        )

    if len(toplam_noktalar) >= 2:
        t_poly = " ".join(f"{nx:.1f},{ny:.1f}" for nx, ny, _ in toplam_noktalar)
        parcalar.append(f'<polyline fill="none" stroke="#A02B93" stroke-width="3.5" points="{t_poly}"/>')

    for nx, ny, t_val in toplam_noktalar:
        parcalar.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="4.5" fill="#A02B93" stroke="#FFFFFF" stroke-width="1.2"/>')
        parcalar.append(
            f'<text x="{nx:.1f}" y="{max(gy0 + 16, ny - 8):.1f}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="10.5" font-weight="bold" text-anchor="middle">{xml_esc(_tr_sayi_str(t_val))}</text>'
        )

    # Alt Lejant
    lejant = [("TÜRKÇE", "#156082"), ("SOSYAL", "#E97132"), ("MAT", "#196B24"), ("FEN", "#0F9ED5"), ("TOPLAM", "#A02B93")]
    lx = gx0 + gw / 2 - 190
    ly = gy0 + gh - 12
    for l_ad, l_renk in lejant:
        parcalar.append(f'<rect x="{lx:.1f}" y="{ly - 8:.1f}" width="18" height="7" rx="2" fill="{l_renk}"/>')
        parcalar.append(
            f'<text x="{lx + 23:.1f}" y="{ly - 1:.1f}" fill="#E0E0E0" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" font-weight="bold">{xml_esc(l_ad)}</text>'
        )
        lx += 78

    parcalar.append("</svg>")
    svg_str = "".join(parcalar)
    b64 = base64.b64encode(svg_str.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def gun_sonu_svg_grafik_olustur(gunluk_listesi, calisma_sn_map=None, gun_sayisi=14):
    """Arda'nın Panelindeki Gün Sonu Analizi sekmesi için son 14 günün çalışma saatlerini
    ve performans emojilerini gösteren SVG grafik üretir."""
    calisma_sn_map = calisma_sn_map if isinstance(calisma_sn_map, dict) else {}
    kayit_haritasi = {}
    for g in (gunluk_listesi or []):
        if isinstance(g, dict) and g.get("tarih"):
            kayit_haritasi[str(g["tarih"])] = g

    gunler = [date.today() - timedelta(days=i) for i in range(gun_sayisi - 1, -1, -1)]
    veri = []
    for d in gunler:
        t_str = d.strftime("%d.%m.%Y")
        k = kayit_haritasi.get(t_str)
        sn = int(sayi((k or {}).get("sn"), calisma_sn_map.get(t_str, 0)))
        if sn == 0 and k and "saat" in k:
            sn = int(float(sayi(k.get("saat"), 0.0)) * 3600)
        saat = round(sn / 3600.0, 2)
        p = int(sayi((k or {}).get("performans"), 0))
        veri.append((d, t_str, saat, p, k is not None))

    W, H = 760, 230
    maks_saat = max(4.0, max((v[2] for v in veri), default=1.0) * 1.2)
    parcalar = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%">',
        f'<rect width="{W}" height="{H}" rx="16" fill="#181824"/>',
        f'<text x="{W / 2:.1f}" y="24" fill="#E2E8F0" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="14" font-weight="bold" text-anchor="middle">Son {gun_sayisi} Günlük Çalışma Süresi (Saat) &amp; Gün Sonu Performansı</text>',
    ]
    px0, py0 = 42, 40
    pw, ph = W - 64, H - 82

    for i_g in range(4):
        gy = py0 + ph * (i_g / 3.0)
        g_val = maks_saat * (1.0 - i_g / 3.0)
        parcalar.append(f'<line x1="{px0}" y1="{gy:.1f}" x2="{px0 + pw}" y2="{gy:.1f}" stroke="#333348" stroke-width="1"/>')
        parcalar.append(
            f'<text x="{px0 - 6}" y="{gy + 4:.1f}" fill="#94A3B8" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9.5" text-anchor="end">{g_val:.1f}s</text>'
        )

    sutun_aralik = pw / max(1, len(veri))
    bar_w = min(28.0, sutun_aralik * 0.58)
    p_renkler = {1: "#EF5350", 2: "#FF9800", 3: "#42A5F5", 4: "#66BB6A", 5: "#AB47BC"}

    for idx, (d, t_str, saat, p, kayit_var) in enumerate(veri):
        cx = px0 + sutun_aralik * (idx + 0.5)
        bh = (min(saat, maks_saat) / maks_saat) * ph
        bx = cx - bar_w / 2.0
        by = py0 + ph - bh
        renk = p_renkler.get(p, "#8B5CF6" if kayit_var else "#475569")
        parcalar.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{max(3.0, bh):.1f}" rx="6" fill="{renk}"/>')
        if saat > 0:
            parcalar.append(
                f'<text x="{cx:.1f}" y="{max(py0 + 10, by - 5):.1f}" fill="#FFFFFF" font-family="Segoe UI, Arial, sans-serif" '
                f'font-size="9" font-weight="bold" text-anchor="middle">{saat:.1f}</text>'
            )
        p_etiket = f"{p}/5" if 1 <= p <= 5 else ("✓" if kayit_var else "-")
        parcalar.append(
            f'<text x="{cx:.1f}" y="{py0 + ph + 15:.1f}" fill="#CBD5E1" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9" font-weight="bold" text-anchor="middle">{xml_esc(t_str[:5])}</text>'
        )
        parcalar.append(
            f'<text x="{cx:.1f}" y="{py0 + ph + 29:.1f}" fill="{renk}" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="9" font-weight="bold" text-anchor="middle">{xml_esc(p_etiket)}</text>'
        )

    parcalar.append("</svg>")
    b64 = base64.b64encode("".join(parcalar).encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


# ==========================================
# 3. GERÇEK EXCEL (.XLSX) + 5 GÖMÜLÜ GRAFİK ÜRETİCİSİ
#    (Sıfır dış bağımlılık, %100 OpenXML / DrawingML standardı)
# ==========================================
def _tek_ders_cizgi_chart_xml(baslik, ders_sutun_harfi, son_satir, satirlar, ders_anahtari, koyu_tema=False):
    """Excel için tek dersin (TÜRKÇE, SOSYAL, MATEMATİK, FEN) DrawingML chart XML'ini üretir."""
    arka_hex = "333333" if koyu_tema else "EAEAEA"
    yazi_hex = "FFFFFF" if koyu_tema else "333333"
    cizgi_hex = "156082"
    grid_hex = "595959" if koyu_tema else "D0D0D0"

    n = len(satirlar)
    kat_pts = "".join(
        f'<c:pt idx="{i}"><c:v>{xml_esc(s["tarih"])}</c:v></c:pt>'
        for i, s in enumerate(satirlar)
    )
    val_pts = "".join(
        f'<c:pt idx="{i}"><c:v>{float(s.get(ders_anahtari, 0.0)):.2f}</c:v></c:pt>'
        for i, s in enumerate(satirlar)
    )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <c:roundedCorners val="0"/>
  <c:spPr>
    <a:solidFill><a:srgbClr val="{arka_hex}"/></a:solidFill>
    <a:ln w="9525"><a:solidFill><a:srgbClr val="595959"/></a:solidFill></a:ln>
  </c:spPr>
  <c:chart>
    <c:title>
      <c:tx>
        <c:rich>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:pPr><a:defRPr sz="1600" b="1"><a:solidFill><a:srgbClr val="{yazi_hex}"/></a:solidFill></a:defRPr></a:pPr>
            <a:r><a:rPr lang="tr-TR" sz="1600" b="1"><a:solidFill><a:srgbClr val="{yazi_hex}"/></a:solidFill></a:rPr><a:t>{xml_esc(baslik)}</a:t></a:r>
          </a:p>
        </c:rich>
      </c:tx>
      <c:overlay val="0"/>
    </c:title>
    <c:plotArea>
      <c:layout/>
      <c:spPr><a:noFill/></c:spPr>
      <c:lineChart>
        <c:grouping val="standard"/>
        <c:varyColors val="0"/>
        <c:ser>
          <c:idx val="0"/>
          <c:order val="0"/>
          <c:tx><c:v>{xml_esc(baslik)}</c:v></c:tx>
          <c:spPr>
            <a:ln w="31750" cap="rnd"><a:solidFill><a:srgbClr val="{cizgi_hex}"/></a:solidFill></a:ln>
          </c:spPr>
          <c:marker>
            <c:symbol val="circle"/>
            <c:size val="14"/>
            <c:spPr>
              <a:solidFill><a:srgbClr val="{cizgi_hex}"/></a:solidFill>
              <a:ln w="12700"><a:solidFill><a:srgbClr val="{cizgi_hex}"/></a:solidFill></a:ln>
            </c:spPr>
          </c:marker>
          <c:dLbls>
            <c:spPr><a:solidFill><a:srgbClr val="{cizgi_hex}"/></a:solidFill></c:spPr>
            <c:txPr>
              <a:bodyPr/>
              <a:lstStyle/>
              <a:p><a:pPr><a:defRPr sz="950" b="1"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:defRPr></a:pPr></a:p>
            </c:txPr>
            <c:dLblPos val="ctr"/>
            <c:showLegendKey val="0"/>
            <c:showVal val="1"/>
            <c:showCatName val="0"/>
            <c:showSerName val="0"/>
            <c:showPercent val="0"/>
          </c:dLbls>
          <c:cat>
            <c:strRef>
              <c:f>'Denemeler'!$B$3:$B${son_satir}</c:f>
              <c:strCache><c:ptCount val="{n}"/>{kat_pts}</c:strCache>
            </c:strRef>
          </c:cat>
          <c:val>
            <c:numRef>
              <c:f>'Denemeler'!${ders_sutun_harfi}$3:${ders_sutun_harfi}${son_satir}</c:f>
              <c:numCache><c:formatCode>0.##</c:formatCode><c:ptCount val="{n}"/>{val_pts}</c:numCache>
            </c:numRef>
          </c:val>
          <c:smooth val="0"/>
        </c:ser>
        <c:axId val="101"/>
        <c:axId val="102"/>
      </c:lineChart>
      <c:catAx>
        <c:axId val="101"/>
        <c:scaling><c:orientation val="minMax"/></c:scaling>
        <c:delete val="0"/>
        <c:axPos val="b"/>
        <c:txPr>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:pPr><a:defRPr sz="950" b="0"><a:solidFill><a:srgbClr val="{yazi_hex}"/></a:solidFill></a:defRPr></a:pPr></a:p>
        </c:txPr>
        <c:crossAx val="102"/>
        <c:crosses val="autoZero"/>
        <c:auto val="1"/>
        <c:lblAlgn val="ctr"/>
        <c:lblOffset val="100"/>
      </c:catAx>
      <c:valAx>
        <c:axId val="102"/>
        <c:scaling><c:orientation val="minMax"/><c:min val="0"/></c:scaling>
        <c:delete val="0"/>
        <c:axPos val="l"/>
        <c:majorGridlines>
          <c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="{grid_hex}"/></a:solidFill></a:ln></c:spPr>
        </c:majorGridlines>
        <c:numFmt formatCode="0.##" sourceLinked="0"/>
        <c:txPr>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:pPr><a:defRPr sz="900"><a:solidFill><a:srgbClr val="{yazi_hex}"/></a:solidFill></a:defRPr></a:pPr></a:p>
        </c:txPr>
        <c:crossAx val="101"/>
        <c:crosses val="autoZero"/>
        <c:crossBetween val="between"/>
      </c:valAx>
    </c:plotArea>
    <c:plotVisOnly val="1"/>
  </c:chart>
</c:chartSpace>"""


def _genel_combo_chart_xml(ana_baslik, son_satir, satirlar):
    """Alttaki büyük Genel Grafik (4 Ders Sütun + Toplam Mor Çizgi + 2 Katmanlı Tarih & Deneme Adı Ekseni)."""
    n = len(satirlar)
    # 2 Seviyeli Kategori Ekseni (Üst satırda Tarih, Alt satırda Deneme Adı: $A$3:$B$N)
    lvl_tarih = "".join(f'<c:pt idx="{i}"><c:v>{xml_esc(s["tarih"])}</c:v></c:pt>' for i, s in enumerate(satirlar))
    lvl_ad = "".join(f'<c:pt idx="{i}"><c:v>{xml_esc(s["ad"])}</c:v></c:pt>' for i, s in enumerate(satirlar))
    multi_cat_xml = f"""<c:cat>
      <c:multiLvlStrRef>
        <c:f>'Denemeler'!$A$3:$B${son_satir}</c:f>
        <c:multiLvlStrCache>
          <c:ptCount val="{n}"/>
          <c:lvl>{lvl_tarih}</c:lvl>
          <c:lvl>{lvl_ad}</c:lvl>
        </c:multiLvlStrCache>
      </c:multiLvlStrRef>
    </c:cat>"""

    bar_seriler = [
        (0, "TÜRKÇE", "C", "tr", "156082"),
        (1, "SOSYAL", "D", "sos", "E97132"),
        (2, "MAT", "E", "mat", "196B24"),
        (3, "FEN", "F", "fen", "0F9ED5"),
    ]
    bar_ser_xml = []
    for idx, ad, col_h, key_h, renk_hex in bar_seriler:
        pts = "".join(f'<c:pt idx="{i}"><c:v>{float(s.get(key_h, 0.0)):.2f}</c:v></c:pt>' for i, s in enumerate(satirlar))
        bar_ser_xml.append(f"""<c:ser>
          <c:idx val="{idx}"/>
          <c:order val="{idx}"/>
          <c:tx><c:strRef><c:f>'Denemeler'!${col_h}$2</c:f><c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>{ad}</c:v></c:pt></c:strCache></c:strRef></c:tx>
          <c:spPr><a:solidFill><a:srgbClr val="{renk_hex}"/></a:solidFill></c:spPr>
          <c:invertIfNegative val="0"/>
          {multi_cat_xml}
          <c:val>
            <c:numRef>
              <c:f>'Denemeler'!${col_h}$3:${col_h}${son_satir}</c:f>
              <c:numCache><c:formatCode>0.##</c:formatCode><c:ptCount val="{n}"/>{pts}</c:numCache>
            </c:numRef>
          </c:val>
        </c:ser>""")

    top_pts = "".join(f'<c:pt idx="{i}"><c:v>{float(s["toplam"]):.2f}</c:v></c:pt>' for i, s in enumerate(satirlar))

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <c:roundedCorners val="0"/>
  <c:spPr>
    <a:solidFill><a:srgbClr val="333333"/></a:solidFill>
    <a:ln w="9525"><a:solidFill><a:srgbClr val="595959"/></a:solidFill></a:ln>
  </c:spPr>
  <c:chart>
    <c:title>
      <c:tx>
        <c:rich>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:pPr><a:defRPr sz="1600" b="1"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:defRPr></a:pPr>
            <a:r><a:rPr lang="tr-TR" sz="1600" b="1"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr><a:t>{xml_esc(ana_baslik)}</a:t></a:r>
          </a:p>
        </c:rich>
      </c:tx>
      <c:overlay val="0"/>
    </c:title>
    <c:plotArea>
      <c:layout/>
      <c:spPr><a:noFill/></c:spPr>
      <c:barChart>
        <c:barDir val="col"/>
        <c:grouping val="clustered"/>
        <c:varyColors val="0"/>
        {''.join(bar_ser_xml)}
        <c:gapWidth val="150"/>
        <c:axId val="201"/>
        <c:axId val="202"/>
      </c:barChart>
      <c:lineChart>
        <c:grouping val="standard"/>
        <c:varyColors val="0"/>
        <c:ser>
          <c:idx val="4"/>
          <c:order val="4"/>
          <c:tx><c:strRef><c:f>'Denemeler'!$G$2</c:f><c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>TOPLAM</c:v></c:pt></c:strCache></c:strRef></c:tx>
          <c:spPr>
            <a:ln w="38100" cap="rnd"><a:solidFill><a:srgbClr val="A02B93"/></a:solidFill></a:ln>
          </c:spPr>
          <c:marker><c:symbol val="none"/></c:marker>
          <c:dLbls>
            <c:txPr>
              <a:bodyPr/>
              <a:lstStyle/>
              <a:p><a:pPr><a:defRPr sz="1000" b="1"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:defRPr></a:pPr></a:p>
            </c:txPr>
            <c:dLblPos val="t"/>
            <c:showLegendKey val="0"/>
            <c:showVal val="1"/>
            <c:showCatName val="0"/>
            <c:showSerName val="0"/>
            <c:showPercent val="0"/>
          </c:dLbls>
          {multi_cat_xml}
          <c:val>
            <c:numRef>
              <c:f>'Denemeler'!$G$3:$G${son_satir}</c:f>
              <c:numCache><c:formatCode>0.00</c:formatCode><c:ptCount val="{n}"/>{top_pts}</c:numCache>
            </c:numRef>
          </c:val>
          <c:smooth val="0"/>
        </c:ser>
        <c:axId val="201"/>
        <c:axId val="202"/>
      </c:lineChart>
      <c:catAx>
        <c:axId val="201"/>
        <c:scaling><c:orientation val="minMax"/></c:scaling>
        <c:delete val="0"/>
        <c:axPos val="b"/>
        <c:txPr>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:pPr><a:defRPr sz="950"><a:solidFill><a:srgbClr val="E0E0E0"/></a:solidFill></a:defRPr></a:pPr></a:p>
        </c:txPr>
        <c:crossAx val="202"/>
        <c:crosses val="autoZero"/>
        <c:auto val="1"/>
        <c:lblAlgn val="ctr"/>
        <c:lblOffset val="100"/>
        <c:noMultiLvlLbl val="0"/>
      </c:catAx>
      <c:valAx>
        <c:axId val="202"/>
        <c:scaling><c:orientation val="minMax"/><c:min val="0"/></c:scaling>
        <c:delete val="0"/>
        <c:axPos val="l"/>
        <c:majorGridlines>
          <c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="595959"/></a:solidFill></a:ln></c:spPr>
        </c:majorGridlines>
        <c:numFmt formatCode="0" sourceLinked="0"/>
        <c:txPr>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:pPr><a:defRPr sz="950"><a:solidFill><a:srgbClr val="E0E0E0"/></a:solidFill></a:defRPr></a:pPr></a:p>
        </c:txPr>
        <c:crossAx val="201"/>
        <c:crosses val="autoZero"/>
        <c:crossBetween val="between"/>
      </c:valAx>
    </c:plotArea>
    <c:legend>
      <c:legendPos val="b"/>
      <c:overlay val="0"/>
      <c:txPr>
        <a:bodyPr/>
        <a:lstStyle/>
        <a:p><a:pPr><a:defRPr sz="950" b="1"><a:solidFill><a:srgbClr val="E0E0E0"/></a:solidFill></a:defRPr></a:pPr></a:p>
      </c:txPr>
    </c:legend>
    <c:plotVisOnly val="1"/>
  </c:chart>
</c:chartSpace>"""


def deneme_excel_bayt_olustur(liste, kullanici_adi="", sinav_adi="TYT"):
    """Kullanıcının yüklediği referans görseldekiyle birebir aynı tasarımda:
    - Üstte mor (#7030A0) başlık: '{KULLANICI_ADI} TYT DENEMELERİ'
    - Koyu temalı tablo: DENEME ADI | TARİH | TÜRKÇE | SOSYAL | MAT | FEN | TOPLAM
    - 5 gömülü Excel grafiği: TÜRKÇE, SOSYAL, MATEMATİK, FEN ve altta Sütun+Çizgi Genel Grafik
    içeren gerçek .xlsx baytlarını döndürür."""
    satirlar = [deneme_satiri_ayristir(x) for x in (liste or [])]
    if not satirlar:
        satirlar = [{"ad": "Örnek Deneme", "tarih": bugun_str(), "tr": 0.0, "sos": 0.0, "mat": 0.0, "fen": 0.0, "toplam": 0.0}]

    kul = tr_buyuk((kullanici_adi or "ÖĞRENCİ").strip())
    sinav_u = tr_buyuk((sinav_adi or "TYT").strip())
    ana_baslik = f"{kul} {sinav_u} DENEMELERİ"
    son_satir = 2 + len(satirlar)

    # Hücre satırlarını oluştur
    sheet_rows = []
    # Satır 1: Mor Başlık Bandı (A1:G1 birleşik)
    sheet_rows.append(
        f'<row r="1" ht="28" customHeight="1">'
        f'<c r="A1" s="1" t="inlineStr"><is><t>{xml_esc(ana_baslik)}</t></is></c>'
        + "".join(f'<c r="{c}1" s="1"/>' for c in ("B", "C", "D", "E", "F", "G"))
        + "</row>"
    )
    # Satır 2: Tablo Sütun Başlıkları
    basliklar = [("A", "DENEME ADI"), ("B", "TARİH"), ("C", "TÜRKÇE"), ("D", "SOSYAL"), ("E", "MAT"), ("F", "FEN"), ("G", "TOPLAM")]
    sheet_rows.append(
        '<row r="2" ht="20" customHeight="1">'
        + "".join(f'<c r="{col}2" s="2" t="inlineStr"><is><t>{xml_esc(lbl)}</t></is></c>' for col, lbl in basliklar)
        + "</row>"
    )
    # Satır 3..N+2: Deneme Verileri
    for idx, s in enumerate(satirlar, start=3):
        sheet_rows.append(
            f'<row r="{idx}" ht="19" customHeight="1">'
            f'<c r="A{idx}" s="3" t="inlineStr"><is><t>{xml_esc(s["ad"])}</t></is></c>'
            f'<c r="B{idx}" s="4" t="inlineStr"><is><t>{xml_esc(s["tarih"])}</t></is></c>'
            f'<c r="C{idx}" s="5"><v>{s["tr"]:.2f}</v></c>'
            f'<c r="D{idx}" s="6"><v>{s["sos"]:.2f}</v></c>'
            f'<c r="E{idx}" s="5"><v>{s["mat"]:.2f}</v></c>'
            f'<c r="F{idx}" s="6"><v>{s["fen"]:.2f}</v></c>'
            f'<c r="G{idx}" s="6"><f>SUM(C{idx}:F{idx})</f><v>{s["toplam"]:.2f}</v></c>'
            f"</row>"
        )

    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <cols>
    <col min="1" max="1" width="18" customWidth="1"/>
    <col min="2" max="2" width="13" customWidth="1"/>
    <col min="3" max="6" width="10" customWidth="1"/>
    <col min="7" max="7" width="11" customWidth="1"/>
    <col min="8" max="14" width="10" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
  <mergeCells count="1"><mergeCell ref="A1:G1"/></mergeCells>
  <drawing r:id="rId1"/>
</worksheet>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="2">
    <numFmt numFmtId="164" formatCode="0.##"/>
    <numFmt numFmtId="165" formatCode="0.00"/>
  </numFmts>
  <fonts count="4">
    <font><sz val="11"/><color rgb="FF000000"/><name val="Calibri"/></font>
    <font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><sz val="11"/><color rgb="FFD9D9D9"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
  </fonts>
  <fills count="5">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF7030A0"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF262626"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF0D0D0D"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FF595959"/></left>
      <right style="thin"><color rgb="FF595959"/></right>
      <top style="thin"><color rgb="FF595959"/></top>
      <bottom style="thin"><color rgb="FF595959"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="7">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="left" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="164" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="right" vertical="center"/>
    </xf>
    <xf numFmtId="165" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="right" vertical="center"/>
    </xf>
  </cellXfs>
</styleSheet>"""

    # Grafiklerin tablodaki satır sayısına göre dinamik yerleşimi (görseldeki düzene sadık)
    orta_bas_satir = max(9, son_satir + 1)
    orta_bit_satir = orta_bas_satir + 9
    alt_bas_satir = orta_bit_satir + 1
    alt_bit_satir = alt_bas_satir + 12

    def anchor_xml(from_col, from_row, to_col, to_row, r_id, idx, ad):
        return f"""<xdr:twoCellAnchor>
      <xdr:from><xdr:col>{from_col}</xdr:col><xdr:colOff>45720</xdr:colOff><xdr:row>{from_row}</xdr:row><xdr:rowOff>45720</xdr:rowOff></xdr:from>
      <xdr:to><xdr:col>{to_col}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{to_row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>
      <xdr:graphicFrame macro="">
        <xdr:nvGraphicFramePr>
          <xdr:cNvPr id="{idx + 1}" name="{xml_esc(ad)}"/>
          <xdr:cNvGraphicFramePr/>
        </xdr:nvGraphicFramePr>
        <xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">
            <c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
                     xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="{r_id}"/>
          </a:graphicData>
        </a:graphic>
      </xdr:graphicFrame>
      <xdr:clientData/>
    </xdr:twoCellAnchor>"""

    drawing_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  {anchor_xml(0, orta_bas_satir, 3, orta_bit_satir, "rId1", 1, "TÜRKÇE")}
  {anchor_xml(3, orta_bas_satir, 7, orta_bit_satir, "rId2", 2, "SOSYAL")}
  {anchor_xml(7, 0, 13, 9, "rId3", 3, "MATEMATİK")}
  {anchor_xml(7, 9, 13, 18, "rId4", 4, "FEN")}
  {anchor_xml(0, alt_bas_satir, 7, alt_bit_satir, "rId5", 5, "GENEL GRAFİK")}
</xdr:wsDr>"""

    drawing_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart3.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart4.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart5.xml"/>
</Relationships>"""

    sheet_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
</Relationships>"""

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Denemeler" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>
  <Override PartName="/xl/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
  <Override PartName="/xl/charts/chart2.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
  <Override PartName="/xl/charts/chart3.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
  <Override PartName="/xl/charts/chart4.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
  <Override PartName="/xl/charts/chart5.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
</Types>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels_xml)
        zf.writestr("xl/drawings/drawing1.xml", drawing_xml)
        zf.writestr("xl/drawings/_rels/drawing1.xml.rels", drawing_rels_xml)
        zf.writestr("xl/charts/chart1.xml", _tek_ders_cizgi_chart_xml("TÜRKÇE", "C", son_satir, satirlar, "tr", koyu_tema=False))
        zf.writestr("xl/charts/chart2.xml", _tek_ders_cizgi_chart_xml("SOSYAL", "D", son_satir, satirlar, "sos", koyu_tema=False))
        zf.writestr("xl/charts/chart3.xml", _tek_ders_cizgi_chart_xml("MATEMATİK", "E", son_satir, satirlar, "mat", koyu_tema=True))
        zf.writestr("xl/charts/chart4.xml", _tek_ders_cizgi_chart_xml("FEN", "F", son_satir, satirlar, "fen", koyu_tema=True))
        zf.writestr("xl/charts/chart5.xml", _genel_combo_chart_xml(ana_baslik, son_satir, satirlar))
    return buf.getvalue()


# ==========================================
# 4. PC + MOBİL KAYDETME, AÇMA VE YEREL HTTP İNDİRME SUNUCUSU
# ==========================================
_aktif_indir_sunucu = {"port": 0, "bayt": b"", "dosya_adi": "Denemeler.xlsx"}


def excel_http_indir_url_olustur(xlsx_bayt, dosya_adi="Denemeler.xlsx"):
    """Hem PC hem Android Mobilde tarayıcı üzerinden (127.0.0.1:PORT/dosya.xlsx)
    tek dokunuşla gerçek .xlsx dosyasını İndilenler klasörüne indiren mini sunucu."""
    _aktif_indir_sunucu["bayt"] = xlsx_bayt
    _aktif_indir_sunucu["dosya_adi"] = dosya_adi

    if _aktif_indir_sunucu["port"] > 0:
        return f"http://127.0.0.1:{_aktif_indir_sunucu['port']}/{dosya_adi}"

    class IndirHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            veri = _aktif_indir_sunucu["bayt"]
            ad = _aktif_indir_sunucu["dosya_adi"]
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{ad}"')
            self.send_header("Content-Length", str(len(veri)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(veri)

        def log_message(self, format, *args):
            pass

    try:
        srv = HTTPServer(("127.0.0.1", 0), IndirHandler)
        port = srv.server_address[1]
        _aktif_indir_sunucu["port"] = port
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}/{dosya_adi}"
    except Exception:
        return ""


def deneme_excel_disa_aktar(liste, kullanici_adi="", sinav_adi="TYT", oto_ac=False):
    """Hem PC (Masaüstü, İndirilenler, Proje klasörü) hem Mobil (Android Download, Uygulama dizini)
    için .xlsx dosyasını oluşturur, diske kaydeder ve yerel indirme URL'si üretir."""
    temiz_kul = re.sub(r"[^A-Za-z0-9_ÇĞİÖŞÜçğıöşü]", "", (kullanici_adi or "Ogrenci").strip()) or "Ogrenci"
    temiz_sinav = re.sub(r"[^A-Za-z0-9]", "", (sinav_adi or "TYT").strip().upper()) or "TYT"
    dosya_adi = f"{tr_buyuk(temiz_kul)}_{temiz_sinav}_DENEMELERI.xlsx"
    xlsx_bayt = deneme_excel_bayt_olustur(liste, kullanici_adi=kullanici_adi, sinav_adi=sinav_adi)

    ev = os.path.expanduser("~")
    aday_klasorler = [
        os.path.join(ev, "Desktop"),
        os.path.join(ev, "Masaüstü"),
        os.path.join(ev, "Downloads"),
        os.path.join(ev, "İndirilenler"),
        "/storage/emulated/0/Download",
        "/sdcard/Download",
        os.environ.get("FLET_APP_STORAGE_DATA"),
        os.path.dirname(os.path.abspath(__file__)),
    ]

    kaydedilen_yollar = []
    for kl in aday_klasorler:
        if not kl:
            continue
        try:
            if os.path.isdir(kl):
                tam_yol = os.path.join(kl, dosya_adi)
                with open(tam_yol, "wb") as fh:
                    fh.write(xlsx_bayt)
                if tam_yol not in kaydedilen_yollar:
                    kaydedilen_yollar.append(tam_yol)
        except Exception:
            continue

    if not kaydedilen_yollar:
        try:
            import tempfile
            tam_yol = os.path.join(tempfile.gettempdir(), dosya_adi)
            with open(tam_yol, "wb") as fh:
                fh.write(xlsx_bayt)
            kaydedilen_yollar.append(tam_yol)
        except Exception:
            pass

    birincil_yol = kaydedilen_yollar[0] if kaydedilen_yollar else dosya_adi
    indir_url = excel_http_indir_url_olustur(xlsx_bayt, dosya_adi)

    acildi_mi = False
    if oto_ac and kaydedilen_yollar:
        try:
            if hasattr(os, "startfile"):
                os.startfile(birincil_yol)
                acildi_mi = True
        except Exception:
            pass

    return {
        "dosya_adi": dosya_adi,
        "yol": birincil_yol,
        "tum_yollar": kaydedilen_yollar,
        "indir_url": indir_url,
        "bayt": xlsx_bayt,
        "acildi": acildi_mi,
    }
