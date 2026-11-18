"""Mesin simulasi bengkel (montir + 1 resepsionis/kasir) dengan Event Calendar manual.

Logikanya sama dengan notebook TA5_Bengkel.ipynb (Event Calendar berupa list yang
selalu diurutkan, satu handler per jenis event), tetapi dibuat sebagai modul yang
mengembalikan data terstruktur, bukan mencetak, supaya bisa dipakai backend Flask.
"""
import math

import numpy as np

PARAM_DEFAULT = {
    "jumlah_mobil": 50,
    "jumlah_montir": 2,
    "mean_iat": 12,        # rata-rata antar-kedatangan (eksponensial), menit
    "daftar_min": 2,       # pendaftaran ~ Uniform(min, max)
    "daftar_max": 4,
    "repair_mean": 20,     # perbaikan ~ Normal(mean, std), dipotong minimal repair_min
    "repair_std": 5,
    "repair_min": 5,
    "bayar_min": 3,        # pembayaran ~ Uniform(min, max)
    "bayar_max": 5,
    "prioritas_bayar": True,
    "seed": 42,
    "replikasi": 1,
}

# nama: (tipe, minimum, maksimum, label)
BATAS = {
    "jumlah_mobil": (int, 1, 500, "Jumlah mobil"),
    "jumlah_montir": (int, 1, 10, "Jumlah montir"),
    "mean_iat": (float, 0.1, 1000, "Rata-rata antar-kedatangan"),
    "daftar_min": (float, 0, 1000, "Waktu pendaftaran minimum"),
    "daftar_max": (float, 0, 1000, "Waktu pendaftaran maksimum"),
    "repair_mean": (float, 0.1, 1000, "Rata-rata waktu perbaikan"),
    "repair_std": (float, 0, 1000, "Simpangan baku waktu perbaikan"),
    "repair_min": (float, 0, 1000, "Waktu perbaikan minimum"),
    "bayar_min": (float, 0, 1000, "Waktu pembayaran minimum"),
    "bayar_max": (float, 0, 1000, "Waktu pembayaran maksimum"),
    "seed": (int, 0, 2**31 - 1, "Seed"),
    "replikasi": (int, 1, 50, "Jumlah replikasi"),
}


class ParamError(ValueError):
    """Parameter tidak valid. Daftar pesan ada di atribut `errors`."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def validasi_param(mentah):
    """Ubah input mentah (dari JSON) menjadi parameter bersih atau lempar ParamError."""
    p = dict(PARAM_DEFAULT)
    errors = []
    for kunci, (tipe, lo, hi, label) in BATAS.items():
        if kunci not in mentah or mentah[kunci] in (None, ""):
            continue
        nilai = mentah[kunci]
        if isinstance(nilai, bool):
            errors.append(f"{label} harus berupa angka.")
            continue
        try:
            angka = float(nilai)
        except (TypeError, ValueError):
            errors.append(f"{label} harus berupa angka.")
            continue
        if not math.isfinite(angka):
            errors.append(f"{label} harus berupa angka yang valid.")
            continue
        if tipe is int:
            if angka != int(angka):
                errors.append(f"{label} harus bilangan bulat.")
                continue
            angka = int(angka)
        if not (lo <= angka <= hi):
            errors.append(f"{label} harus antara {lo:g} dan {hi:g}.")
            continue
        p[kunci] = angka

    if "prioritas_bayar" in mentah:
        v = mentah["prioritas_bayar"]
        if isinstance(v, bool):
            p["prioritas_bayar"] = v
        elif isinstance(v, str) and v.lower() in ("true", "on", "1"):
            p["prioritas_bayar"] = True
        elif isinstance(v, str) and v.lower() in ("false", "off", "0"):
            p["prioritas_bayar"] = False
        else:
            errors.append("Prioritas pembayaran harus true atau false.")

    if not errors:
        if p["daftar_min"] > p["daftar_max"]:
            errors.append("Waktu pendaftaran minimum tidak boleh lebih besar dari maksimum.")
        if p["bayar_min"] > p["bayar_max"]:
            errors.append("Waktu pembayaran minimum tidak boleh lebih besar dari maksimum.")
    if errors:
        raise ParamError(errors)
    return p


# ---------------------------------------------------------------------------
# Fungsi bantu (jadwal event dan mulai layanan)
# ---------------------------------------------------------------------------
def _jadwalkan(s, waktu, tipe, mobil):
    s["kalender"].append([round(waktu, 2), tipe, mobil])
    s["kalender"].sort()


def _mulai_pendaftaran(s, mobil):
    d = s["data"][mobil]
    s["resepsionis"] = "BUSY"
    d["tunggu_daftar"] = s["clock"] - d["datang"]
    s["sibuk_resepsionis"] += d["t_daftar"]
    _jadwalkan(s, s["clock"] + d["t_daftar"], "REG_END", mobil)


def _mulai_pembayaran(s, mobil):
    d = s["data"][mobil]
    s["resepsionis"] = "BUSY"
    d["tunggu_bayar"] = s["clock"] - d["selesai_perbaikan"]
    s["sibuk_resepsionis"] += d["t_bayar"]
    _jadwalkan(s, s["clock"] + d["t_bayar"], "PAY_END", mobil)


def _mulai_perbaikan(s, mobil):
    d = s["data"][mobil]
    s["montir_bebas"] -= 1
    d["tunggu_montir"] = s["clock"] - d["selesai_daftar"]
    s["sibuk_montir"] += d["t_perbaikan"]
    _jadwalkan(s, s["clock"] + d["t_perbaikan"], "REPAIR_END", mobil)


def _pilih_resepsionis(s):
    """Tentukan layanan berikutnya untuk resepsionis: 'bayar', 'daftar', atau None."""
    ab, ad = s["antrian_bayar"], s["antrian_daftar"]
    if ab and ad:
        if s["p"]["prioritas_bayar"]:
            return "bayar"
        masuk_bayar = s["data"][ab[0]]["selesai_perbaikan"]
        masuk_daftar = s["data"][ad[0]]["datang"]
        return "bayar" if masuk_bayar <= masuk_daftar else "daftar"
    if ab:
        return "bayar"
    if ad:
        return "daftar"
    return None


def _layani_resepsionis(s):
    if s["resepsionis"] != "IDLE":
        return
    pilihan = _pilih_resepsionis(s)
    if pilihan == "bayar":
        _mulai_pembayaran(s, s["antrian_bayar"].pop(0))
    elif pilihan == "daftar":
        _mulai_pendaftaran(s, s["antrian_daftar"].pop(0))


# ---------------------------------------------------------------------------
# Event handler (satu fungsi per jenis kejadian)
# ---------------------------------------------------------------------------
def _handle_arrival(s, mobil):
    langsung = s["resepsionis"] == "IDLE"
    s["antrian_daftar"].append(mobil)
    _layani_resepsionis(s)
    return "Langsung didaftar" if langsung else "Antri di resepsionis"


def _handle_reg_end(s, mobil):
    s["resepsionis"] = "IDLE"
    s["data"][mobil]["selesai_daftar"] = s["clock"]
    if s["montir_bebas"] > 0:
        _mulai_perbaikan(s, mobil)
        ket = "Langsung diperbaiki"
    else:
        s["antrian_tunggu"].append(mobil)
        ket = "Masuk ruang tunggu"
    _layani_resepsionis(s)
    return ket


def _handle_repair_end(s, mobil):
    s["montir_bebas"] += 1
    s["data"][mobil]["selesai_perbaikan"] = s["clock"]
    s["antrian_bayar"].append(mobil)
    ket = "Menuju kasir"
    if s["antrian_tunggu"]:
        berikut = s["antrian_tunggu"].pop(0)
        _mulai_perbaikan(s, berikut)
        ket += f", montir ambil mobil {berikut}"
    _layani_resepsionis(s)
    return ket


def _handle_payment_end(s, mobil):
    s["resepsionis"] = "IDLE"
    s["data"][mobil]["pergi"] = s["clock"]
    s["selesai"] += 1
    _layani_resepsionis(s)
    return "Mobil keluar bengkel"


_HANDLER = {
    "ARRIVAL": _handle_arrival,
    "REG_END": _handle_reg_end,
    "REPAIR_END": _handle_repair_end,
    "PAY_END": _handle_payment_end,
}


# ---------------------------------------------------------------------------
# Simulasi utama
# ---------------------------------------------------------------------------
def jalankan(param=None):
    """Jalankan satu simulasi. Mengembalikan {"param", "stats", "trace"}.

    Memakai RandomState milik sendiri (bukan state global NumPy), sehingga aman
    dipanggil dari beberapa request sekaligus dan hasilnya identik dengan
    np.random.seed(seed) pada notebook.
    """
    p = {**PARAM_DEFAULT, **(param or {})}
    n = p["jumlah_mobil"]
    rng = np.random.RandomState(p["seed"])

    iat = rng.exponential(p["mean_iat"], n - 1)
    t_daftar = rng.uniform(p["daftar_min"], p["daftar_max"], n)
    t_perbaikan = np.maximum(p["repair_min"], rng.normal(p["repair_mean"], p["repair_std"], n))
    t_bayar = rng.uniform(p["bayar_min"], p["bayar_max"], n)
    waktu_datang = np.concatenate(([0.0], np.cumsum(iat)))

    s = {
        "p": p,
        "clock": 0.0,
        "resepsionis": "IDLE",
        "montir_bebas": p["jumlah_montir"],
        "antrian_daftar": [],
        "antrian_tunggu": [],
        "antrian_bayar": [],
        "kalender": [],
        "data": {},
        "selesai": 0,
        "sibuk_montir": 0.0,
        "sibuk_resepsionis": 0.0,
    }
    for i in range(n):
        mobil = i + 1
        s["data"][mobil] = {
            "datang": round(float(waktu_datang[i]), 2),
            "t_daftar": round(float(t_daftar[i]), 2),
            "t_perbaikan": round(float(t_perbaikan[i]), 2),
            "t_bayar": round(float(t_bayar[i]), 2),
        }
        s["kalender"].append([s["data"][mobil]["datang"], "ARRIVAL", mobil])
    s["kalender"].sort()

    area_tunggu = 0.0
    maks_tunggu = 0
    maks_resepsionis = 0
    waktu_terakhir = 0.0
    trace = []

    while s["kalender"]:
        waktu, tipe, mobil = s["kalender"].pop(0)

        selang = waktu - waktu_terakhir
        area_tunggu += len(s["antrian_tunggu"]) * selang
        waktu_terakhir = waktu
        s["clock"] = waktu

        ket = _HANDLER[tipe](s, mobil)

        maks_tunggu = max(maks_tunggu, len(s["antrian_tunggu"]))
        maks_resepsionis = max(
            maks_resepsionis, len(s["antrian_daftar"]) + len(s["antrian_bayar"])
        )
        trace.append({
            "clock": waktu,
            "event": tipe,
            "mobil": mobil,
            "q_daftar": len(s["antrian_daftar"]),
            "r_tunggu": len(s["antrian_tunggu"]),
            "q_bayar": len(s["antrian_bayar"]),
            "montir_bebas": s["montir_bebas"],
            "resepsionis": s["resepsionis"],
            "keterangan": ket,
        })

    _validasi_internal(s, n, p)

    T = s["clock"]
    data = list(s["data"].values())

    def rata(kunci):
        return sum(d[kunci] for d in data) / n

    stats = {
        "mobil_selesai": s["selesai"],
        "waktu_simulasi": T,
        "rata_tunggu_daftar": rata("tunggu_daftar"),
        "rata_tunggu_montir": rata("tunggu_montir"),
        "maks_tunggu_montir": max(d["tunggu_montir"] for d in data),
        "rata_tunggu_bayar": rata("tunggu_bayar"),
        "rata_waktu_di_bengkel": sum(d["pergi"] - d["datang"] for d in data) / n,
        "persen_menunggu_montir": 100 * sum(d["tunggu_montir"] > 0 for d in data) / n,
        "util_montir": 100 * s["sibuk_montir"] / (p["jumlah_montir"] * T),
        "util_resepsionis": 100 * s["sibuk_resepsionis"] / T,
        "Lq_ruang_tunggu": area_tunggu / T,
        "maks_ruang_tunggu": maks_tunggu,
        "maks_antrian_resepsionis": maks_resepsionis,
        "validasi_ok": True,
    }
    return {"param": p, "stats": stats, "trace": trace}


def _validasi_internal(s, n, p):
    """Pemeriksaan konsistensi: kalau gagal berarti ada bug di mesin simulasi."""
    if s["selesai"] != n:
        raise RuntimeError("Tidak semua mobil selesai dilayani.")
    if s["antrian_daftar"] or s["antrian_tunggu"] or s["antrian_bayar"]:
        raise RuntimeError("Masih ada mobil di antrian setelah simulasi selesai.")
    if s["montir_bebas"] != p["jumlah_montir"] or s["resepsionis"] != "IDLE":
        raise RuntimeError("Sumber daya tidak kembali bebas setelah simulasi selesai.")
    for d in s["data"].values():
        total = (d["tunggu_daftar"] + d["t_daftar"] + d["tunggu_montir"]
                 + d["t_perbaikan"] + d["tunggu_bayar"] + d["t_bayar"])
        if abs((d["pergi"] - d["datang"]) - total) >= 0.1:
            raise RuntimeError("Waktu di bengkel tidak konsisten dengan jumlah komponennya.")
