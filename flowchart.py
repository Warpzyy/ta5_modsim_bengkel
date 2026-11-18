"""Pembuat flowchart SVG untuk alur hidup satu mobil di bengkel.

Flowchart dibangun dari parameter model dan, bila ada, statistik hasil simulasi,
sehingga isinya (jumlah montir, distribusi waktu, waktu tunggu, utilitas) selalu
mengikuti run terakhir. Tidak memerlukan Graphviz: SVG ditulis langsung dari Python.
"""
import textwrap
from html import escape

STROKE = "#37474f"
FILL = {
    "mulai": "#c8e6c9",
    "selesai": "#ffcdd2",
    "proses": "#e3f2fd",
    "tunggu": "#fff3e0",
    "keputusan": "#fff9c4",
}

CX = 280            # sumbu tengah alur utama
NODE_W = 250        # lebar kotak proses
DIA_W, DIA_H = 210, 78
GAP = 36            # jarak vertikal antar simbol
SIDE_X, SIDE_W = 430, 230
CANVAS_W = SIDE_X + SIDE_W + 20
LINE_H = 15


def _angka(x, desimal=2):
    """Format angka gaya Indonesia: 1.234,56."""
    teks = f"{x:,.{desimal}f}"
    return teks.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _g(x):
    """Format parameter tanpa nol di belakang koma: 12 -> '12', 2.5 -> '2,5'."""
    return f"{x:g}".replace(".", ",")


def _baris(daftar, lebar_char):
    """Pecah baris 'sub' yang terlalu panjang. daftar berisi (teks, gaya)."""
    hasil = []
    for teks, gaya in daftar:
        if gaya == "sub":
            for potong in textwrap.wrap(teks, lebar_char, break_on_hyphens=False) or [""]:
                hasil.append((potong, gaya))
        else:
            hasil.append((teks, gaya))
    return hasil


def _teks(cx, cy, baris):
    n = len(baris)
    y0 = cy - (n - 1) * LINE_H / 2
    out = []
    for i, (teks, gaya) in enumerate(baris):
        y = y0 + i * LINE_H + 4
        if gaya == "judul":
            attr = 'font-size="13" font-weight="600" fill="#1c2b33"'
        else:
            attr = 'font-size="11" fill="#455a64"'
        out.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" text-anchor="middle" {attr}>{escape(teks)}</text>'
        )
    return "".join(out)


def _tinggi(baris, minimum=44):
    return max(minimum, 18 + LINE_H * len(baris))


def _bentuk(jenis, cx, cy, w, h):
    x, y = cx - w / 2, cy - h / 2
    gaya = f'fill="{FILL[jenis]}" stroke="{STROKE}" stroke-width="1.4"'
    if jenis in ("mulai", "selesai"):
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="{min(h / 2, 22):.1f}" {gaya}/>'
    if jenis == "keputusan":
        pts = f"{cx:.1f},{y:.1f} {cx + w / 2:.1f},{cy:.1f} {cx:.1f},{cy + h / 2:.1f} {cx - w / 2:.1f},{cy:.1f}"
        return f'<polygon points="{pts}" {gaya}/>'
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="4" {gaya}/>'


def _panah(x1, y1, x2, y2, putus=False):
    dash = ' stroke-dasharray="5 4"' if putus else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{STROKE}" stroke-width="1.4"{dash} marker-end="url(#ah)"/>')


def _label(x, y, teks, anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="11" '
            f'font-style="italic" fill="#37474f">{escape(teks)}</text>')


def buat_flowchart_svg(p, stats=None):
    """Kembalikan string SVG flowchart.

    p     : parameter simulasi (dict, lihat simulasi.PARAM_DEFAULT)
    stats : statistik hasil simulasi (opsional); bila ada, ditampilkan pada simbol terkait
    """
    s = stats or {}

    def st(kunci, desimal=2):
        return _angka(s[kunci], desimal) if kunci in s else None

    # ---- daftar simbol alur utama, dari atas ke bawah ----
    util_resp = st("util_resepsionis", 1)
    util_mont = st("util_montir", 1)
    pendaftaran = [("Pendaftaran", "judul"),
                   (f"Uniform({_g(p['daftar_min'])}, {_g(p['daftar_max'])}) menit", "sub")]
    if util_resp:
        pendaftaran.append((f"Utilitas resepsionis/kasir: {util_resp}%", "sub"))
    perbaikan = [("Proses perbaikan", "judul"),
                 (f"Normal({_g(p['repair_mean'])}, {_g(p['repair_std'])}), min. {_g(p['repair_min'])} menit", "sub")]
    if util_mont:
        perbaikan.append((f"Utilitas montir: {util_mont}%", "sub"))
    selesai = [("Selesai", "judul")]
    if s:
        selesai.append((f"{s['mobil_selesai']} mobil dilayani", "sub"))
        selesai.append((f"Rata-rata di bengkel {st('rata_waktu_di_bengkel')} menit", "sub"))

    utama = [
        ("mulai", "mulai", [("Mulai", "judul")]),
        ("datang", "proses", [("Kedatangan", "judul"),
                              (f"Antar-kedatangan: Eksponensial, rata-rata {_g(p['mean_iat'])} menit", "sub")]),
        ("cek1", "keputusan", [("Resepsionis", "judul"), ("bebas?", "judul")]),
        ("daftar", "proses", pendaftaran),
        ("cek2", "keputusan", [("Ada montir bebas?", "judul"),
                               (f"(kapasitas {p['jumlah_montir']} montir)", "sub")]),
        ("perbaiki", "proses", perbaikan),
        ("lepas", "proses", [("Perbaikan selesai", "judul"), ("Montir dibebaskan", "sub")]),
        ("cek3", "keputusan", [("Resepsionis/", "judul"), ("kasir bebas?", "judul")]),
        ("bayar", "proses", [("Pembayaran di kasir", "judul"),
                             (f"Uniform({_g(p['bayar_min'])}, {_g(p['bayar_max'])}) menit", "sub")]),
        ("keluar", "proses", [("Kepergian", "judul"), ("Mobil keluar dari bengkel", "sub")]),
        ("akhir", "selesai", selesai),
    ]

    # ---- simbol samping (antrian) untuk tiap pengecekan ----
    tunggu_daftar = [("Antri di resepsionis", "judul"), ("FIFO", "sub")]
    if "rata_tunggu_daftar" in s:
        tunggu_daftar.append((f"Rata-rata tunggu {st('rata_tunggu_daftar')} menit", "sub"))
    ruang = [("Menunggu di ruang tunggu", "judul"), ("FIFO", "sub")]
    if "rata_tunggu_montir" in s:
        ruang.append((f"Rata-rata tunggu {st('rata_tunggu_montir')} menit", "sub"))
        ruang.append((f"{st('persen_menunggu_montir', 1)}% mobil menunggu, antrian maks. {s['maks_ruang_tunggu']}", "sub"))
    kasir = [("Menunggu di antrian kasir", "judul"),
             ("Didahulukan dari pendaftaran" if p.get("prioritas_bayar", True)
              else "FIFO gabungan dengan pendaftaran", "sub")]
    if "rata_tunggu_bayar" in s:
        kasir.append((f"Rata-rata tunggu {st('rata_tunggu_bayar')} menit", "sub"))
    samping = {
        "cek1": ("tunggu", tunggu_daftar, "giliran tiba"),
        "cek2": ("tunggu", ruang, "montir kosong"),
        "cek3": ("tunggu", kasir, "giliran tiba"),
    }

    # ---- hitung posisi ----
    posisi = []  # (kunci, jenis, baris, cy, w, h)
    y = 20.0
    for kunci, jenis, baris in utama:
        if jenis == "keputusan":
            w, h = DIA_W, DIA_H
        elif jenis in ("mulai", "selesai"):
            baris = _baris(baris, 34)
            w, h = 170, _tinggi(baris, 40)
        else:
            baris = _baris(baris, 40)
            w, h = NODE_W, _tinggi(baris)
        cy = y + h / 2
        posisi.append((kunci, jenis, baris, cy, w, h))
        y = cy + h / 2 + GAP
    tinggi_total = y - GAP + 20

    out = []
    for i, (kunci, jenis, baris, cy, w, h) in enumerate(posisi):
        out.append(_bentuk(jenis, CX, cy, w, h))
        out.append(_teks(CX, cy, baris))
        if i < len(posisi) - 1:
            nxt = posisi[i + 1]
            y1, y2 = cy + h / 2, nxt[3] - nxt[5] / 2
            out.append(_panah(CX, y1, CX, y2))
            if jenis == "keputusan":
                out.append(_label(CX + 10, (y1 + y2) / 2 + 4, "Ya", "start"))

        if kunci in samping:
            jenis_s, baris_s, label_loop = samping[kunci]
            baris_s = _baris(baris_s, 38)
            hs = _tinggi(baris_s, 48)
            sx = SIDE_X + SIDE_W / 2
            out.append(_bentuk(jenis_s, sx, cy, SIDE_W, hs))
            out.append(_teks(sx, cy, baris_s))
            # panah "Tidak": dari ujung kanan belah ketupat ke kotak antrian
            out.append(_panah(CX + DIA_W / 2, cy, SIDE_X, cy))
            out.append(_label((CX + DIA_W / 2 + SIDE_X) / 2, cy - 6, "Tidak"))
            # panah putus-putus: dari antrian kembali ke pengecekan
            y_atas = cy - DIA_H / 2 - 14
            x_masuk = CX + DIA_W / 4
            y_masuk = cy - DIA_H / 4
            jalur = (f"M {sx:.1f} {cy - hs / 2:.1f} L {sx:.1f} {y_atas:.1f} "
                     f"L {x_masuk:.1f} {y_atas:.1f} L {x_masuk:.1f} {y_masuk:.1f}")
            out.append(f'<path d="{jalur}" fill="none" stroke="{STROKE}" stroke-width="1.4" '
                       f'stroke-dasharray="5 4" marker-end="url(#ah)"/>')
            out.append(_label((sx + x_masuk) / 2, y_atas - 5, label_loop))

    judul = "Flowchart alur hidup satu mobil di bengkel"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {tinggi_total:.0f}" '
        f'width="{CANVAS_W}" height="{tinggi_total:.0f}" role="img" aria-label="{judul}" '
        f'font-family="Helvetica, Arial, sans-serif" style="max-width:100%;height:auto">'
        f'<title>{judul}</title>'
        '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{STROKE}"/></marker></defs>'
        f'<rect width="{CANVAS_W}" height="{tinggi_total:.0f}" fill="#ffffff"/>'
        + "".join(out) + "</svg>"
    )
    return svg
