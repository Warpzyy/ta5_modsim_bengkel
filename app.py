"""Aplikasi web simulasi bengkel (backend Flask).

Menjalankan:
    flask --app app run          (atau)   python app.py
"""
import os

from flask import Flask, Response, jsonify, render_template, request

from flowchart import buat_flowchart_svg
from simulasi import PARAM_DEFAULT, ParamError, jalankan, validasi_param

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # body JSON kecil saja
app.json.sort_keys = False

# ukuran yang dirangkum pada tabel replikasi
KUNCI_REPLIKASI = [
    "rata_tunggu_montir",
    "rata_waktu_di_bengkel",
    "util_montir",
    "util_resepsionis",
    "maks_ruang_tunggu",
]


@app.get("/")
def index():
    return render_template("index.html", param=PARAM_DEFAULT)


@app.post("/api/simulate")
def api_simulate():
    """Jalankan simulasi dan kembalikan statistik, trace, dan flowchart SVG."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(errors=["Body request harus berupa JSON object."]), 400
    try:
        p = validasi_param(data)
    except ParamError as e:
        return jsonify(errors=e.errors), 400

    hasil = jalankan(p)
    respons = {
        "param": hasil["param"],
        "stats": hasil["stats"],
        "trace": hasil["trace"],
        "flowchart_svg": buat_flowchart_svg(hasil["param"], hasil["stats"]),
        "replikasi": None,
    }

    n_rep = p["replikasi"]
    if n_rep > 1:
        baris = []
        for k in range(n_rep):
            seed = (p["seed"] + k) % (2**31)
            st = jalankan({**p, "seed": seed})["stats"]
            baris.append({"seed": seed, **{kk: st[kk] for kk in KUNCI_REPLIKASI}})
        rata = {kk: sum(b[kk] for b in baris) / n_rep for kk in KUNCI_REPLIKASI}
        respons["replikasi"] = {"jumlah": n_rep, "baris": baris, "rata": rata}
    return jsonify(respons)


@app.get("/flowchart.svg")
def flowchart_default():
    """Flowchart dengan parameter bawaan (tanpa hasil simulasi), bisa diunduh langsung."""
    return Response(buat_flowchart_svg(PARAM_DEFAULT), mimetype="image/svg+xml")


@app.errorhandler(413)
def terlalu_besar(_):
    return jsonify(errors=["Request terlalu besar."]), 413


@app.errorhandler(RuntimeError)
def kesalahan_simulasi(e):
    # RuntimeError dilempar bila pemeriksaan konsistensi internal gagal (bug di mesin simulasi)
    app.logger.exception("Simulasi gagal validasi internal")
    return jsonify(errors=["Terjadi kesalahan internal pada simulasi."]), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
