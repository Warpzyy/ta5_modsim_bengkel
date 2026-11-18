"""Uji otomatis: jalankan dengan `python -m unittest discover -s tests -v` dari folder proyek."""
import os
import sys
import unittest
import xml.dom.minidom

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from simulasi import ParamError, jalankan, validasi_param  # noqa: E402


class TestSimulasi(unittest.TestCase):
    def test_hasil_seed_42_sama_dengan_notebook(self):
        """Angka acuan berasal dari notebook TA5_Bengkel.ipynb (seed 42, 50 mobil)."""
        st = jalankan()["stats"]
        self.assertEqual(st["mobil_selesai"], 50)
        self.assertAlmostEqual(st["waktu_simulasi"], 557.19, places=2)
        self.assertAlmostEqual(st["rata_tunggu_daftar"], 2.58, places=2)
        self.assertAlmostEqual(st["rata_tunggu_montir"], 23.27, places=2)
        self.assertAlmostEqual(st["maks_tunggu_montir"], 74.59, places=2)
        self.assertAlmostEqual(st["rata_tunggu_bayar"], 0.84, places=2)
        self.assertAlmostEqual(st["rata_waktu_di_bengkel"], 52.93, places=2)
        self.assertAlmostEqual(st["persen_menunggu_montir"], 82.0, places=1)
        self.assertAlmostEqual(st["util_montir"], 86.5, places=1)
        self.assertAlmostEqual(st["util_resepsionis"], 62.5, places=1)
        self.assertEqual(st["maks_ruang_tunggu"], 8)
        self.assertEqual(st["maks_antrian_resepsionis"], 3)

    def test_trace_empat_event_per_mobil_dan_terurut(self):
        tr = jalankan()["trace"]
        self.assertEqual(len(tr), 200)
        waktu = [r["clock"] for r in tr]
        self.assertEqual(waktu, sorted(waktu))
        for tipe in ("ARRIVAL", "REG_END", "REPAIR_END", "PAY_END"):
            self.assertEqual(sum(r["event"] == tipe for r in tr), 50)

    def test_reproduksibel(self):
        self.assertEqual(jalankan({"seed": 7})["stats"], jalankan({"seed": 7})["stats"])

    def test_lebih_banyak_montir_mengurangi_tunggu(self):
        a = jalankan({"jumlah_montir": 2, "seed": 3})["stats"]["rata_tunggu_montir"]
        b = jalankan({"jumlah_montir": 4, "seed": 3})["stats"]["rata_tunggu_montir"]
        self.assertLess(b, a)

    def test_kondisi_tepi(self):
        self.assertEqual(jalankan({"jumlah_mobil": 1})["stats"]["mobil_selesai"], 1)
        self.assertEqual(jalankan({"jumlah_mobil": 500, "jumlah_montir": 10})["stats"]["mobil_selesai"], 500)

    def test_validasi_menolak_input_buruk(self):
        for buruk in ({"jumlah_mobil": 0}, {"jumlah_mobil": 501}, {"mean_iat": "abc"},
                      {"daftar_min": 5, "daftar_max": 2}, {"seed": 1.5}, {"jumlah_montir": True},
                      {"mean_iat": float("nan")}, {"prioritas_bayar": "mungkin"}):
            with self.assertRaises(ParamError, msg=str(buruk)):
                validasi_param(buruk)

    def test_validasi_menerima_string_angka_dari_form(self):
        p = validasi_param({"jumlah_mobil": "30", "mean_iat": "10.5", "prioritas_bayar": False})
        self.assertEqual(p["jumlah_mobil"], 30)
        self.assertEqual(p["mean_iat"], 10.5)
        self.assertFalse(p["prioritas_bayar"])


class TestWeb(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def test_halaman_utama(self):
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Simulasi Bengkel", r.get_data(as_text=True))

    def test_api_simulasi_default(self):
        r = self.c.post("/api/simulate", json={})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["stats"]["mobil_selesai"], 50)
        self.assertEqual(len(d["trace"]), 200)
        self.assertIsNone(d["replikasi"])
        xml.dom.minidom.parseString(d["flowchart_svg"])  # SVG harus XML valid
        self.assertIn("Ada montir bebas?", d["flowchart_svg"])
        self.assertIn("kapasitas 2 montir", d["flowchart_svg"])

    def test_flowchart_mengikuti_parameter(self):
        d = self.c.post("/api/simulate", json={"jumlah_montir": 3, "mean_iat": 15}).get_json()
        self.assertIn("kapasitas 3 montir", d["flowchart_svg"])
        self.assertIn("rata-rata 15 menit", d["flowchart_svg"])

    def test_replikasi(self):
        d = self.c.post("/api/simulate", json={"replikasi": 5, "seed": 10}).get_json()
        self.assertEqual(d["replikasi"]["jumlah"], 5)
        self.assertEqual([b["seed"] for b in d["replikasi"]["baris"]], [10, 11, 12, 13, 14])
        self.assertIn("util_montir", d["replikasi"]["rata"])

    def test_error_validasi_jadi_400(self):
        r = self.c.post("/api/simulate", json={"jumlah_mobil": -5, "mean_iat": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.get_json()["errors"]), 2)

    def test_body_bukan_json_object(self):
        self.assertEqual(self.c.post("/api/simulate", data="bukan json").status_code, 400)
        self.assertEqual(self.c.post("/api/simulate", json=[1, 2]).status_code, 400)

    def test_flowchart_svg_endpoint(self):
        r = self.c.get("/flowchart.svg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/svg+xml")
        xml.dom.minidom.parseString(r.get_data(as_text=True))

    def test_body_terlalu_besar(self):
        r = self.c.post("/api/simulate", data="x" * 20000, content_type="application/json")
        self.assertEqual(r.status_code, 413)


if __name__ == "__main__":
    unittest.main()
