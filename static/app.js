(function () {
  "use strict";

  var form = document.getElementById("form");
  var defaults = JSON.parse(document.getElementById("param-default").textContent);
  var btnRun = document.getElementById("btn-run");
  var statusEl = document.getElementById("status");
  var errorsEl = document.getElementById("errors");
  var hasilEl = document.getElementById("hasil");
  var traceData = [];
  var svgUrl = null;

  var NUMERIC = ["jumlah_mobil", "jumlah_montir", "mean_iat", "seed", "daftar_min", "daftar_max",
    "repair_mean", "repair_std", "repair_min", "bayar_min", "bayar_max", "replikasi"];

  var fmt2 = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var fmt1 = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  // Label dan satuan tiap statistik (urutan tabel "Semua statistik")
  var STATS = [
    ["mobil_selesai", "Total mobil selesai", "mobil", 0],
    ["waktu_simulasi", "Total waktu simulasi", "menit", 2],
    ["rata_tunggu_daftar", "Rata-rata tunggu pendaftaran", "menit", 2],
    ["rata_tunggu_montir", "Rata-rata tunggu montir (ruang tunggu)", "menit", 2],
    ["maks_tunggu_montir", "Tunggu montir maksimum", "menit", 2],
    ["rata_tunggu_bayar", "Rata-rata tunggu kasir", "menit", 2],
    ["rata_waktu_di_bengkel", "Rata-rata waktu total di bengkel", "menit", 2],
    ["persen_menunggu_montir", "Mobil yang harus menunggu montir", "%", 1],
    ["util_montir", "Utilitas montir", "%", 1],
    ["util_resepsionis", "Utilitas resepsionis/kasir", "%", 1],
    ["Lq_ruang_tunggu", "Rata-rata panjang antrian ruang tunggu", "mobil", 2],
    ["maks_ruang_tunggu", "Antrian ruang tunggu maksimum", "mobil", 0],
    ["maks_antrian_resepsionis", "Antrian resepsionis maksimum", "mobil", 0]
  ];
  var KPI = ["rata_tunggu_montir", "rata_waktu_di_bengkel", "persen_menunggu_montir", "util_montir", "util_resepsionis", "maks_ruang_tunggu"];

  function angka(x, d) {
    if (d === 0) return String(x);
    return (d === 1 ? fmt1 : fmt2).format(x);
  }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function kosongkan(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function bacaForm() {
    var p = {};
    NUMERIC.forEach(function (k) { p[k] = form.elements[k].value; });
    p.prioritas_bayar = form.elements.prioritas_bayar.checked;
    return p;
  }
  function isiForm(p) {
    NUMERIC.forEach(function (k) { form.elements[k].value = p[k]; });
    form.elements.prioritas_bayar.checked = !!p.prioritas_bayar;
  }
  function tampilkanError(daftar) {
    kosongkan(errorsEl);
    daftar.forEach(function (m) { errorsEl.appendChild(el("li", m)); });
    errorsEl.hidden = daftar.length === 0;
  }

  function renderStats(stats) {
    var kartu = document.getElementById("kartu");
    kosongkan(kartu);
    var info = {};
    STATS.forEach(function (s) { info[s[0]] = s; });
    KPI.forEach(function (k) {
      var s = info[k], box = el("div", undefined, "kpi");
      box.appendChild(el("div", angka(stats[k], s[3]) + (s[2] === "%" ? "%" : ""), "nilai"));
      box.appendChild(el("div", s[1] + (s[2] === "menit" ? " (menit)" : ""), "nama"));
      kartu.appendChild(box);
    });
    var tbody = document.querySelector("#tabel-stat tbody");
    kosongkan(tbody);
    STATS.forEach(function (s) {
      var tr = el("tr");
      tr.appendChild(el("td", s[1]));
      tr.appendChild(el("td", angka(stats[s[0]], s[3]) + " " + s[2], "num"));
      tbody.appendChild(tr);
    });
  }

  function renderFlowchart(svg) {
    document.getElementById("flowchart").innerHTML = svg; // SVG dibuat server dari angka tervalidasi
    if (svgUrl) URL.revokeObjectURL(svgUrl);
    svgUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    document.getElementById("unduh-svg").href = svgUrl;
  }

  function renderReplikasi(rep) {
    var sec = document.getElementById("sec-rep");
    if (!rep) { sec.hidden = true; return; }
    sec.hidden = false;
    document.getElementById("ket-rep").textContent =
      rep.jumlah + " replikasi dengan seed berurutan mulai dari seed di atas. Satu run hanya satu sampel acak, jadi rata-rata replikasi lebih layak dipegang.";
    var cols = [["seed", "Seed", 0], ["rata_tunggu_montir", "Tunggu montir (menit)", 2],
      ["rata_waktu_di_bengkel", "Waktu di bengkel (menit)", 2], ["util_montir", "Utilitas montir (%)", 1],
      ["util_resepsionis", "Utilitas resepsionis (%)", 1], ["maks_ruang_tunggu", "Antrian maks.", 0]];
    var thead = document.querySelector("#tabel-rep thead"), tbody = document.querySelector("#tabel-rep tbody");
    kosongkan(thead); kosongkan(tbody);
    var hr = el("tr");
    cols.forEach(function (c, i) { hr.appendChild(el("th", c[1], i ? "num" : "")); });
    thead.appendChild(hr);
    rep.baris.forEach(function (b) {
      var tr = el("tr");
      cols.forEach(function (c, i) { tr.appendChild(el("td", angka(b[c[0]], c[2]), i ? "num" : "")); });
      tbody.appendChild(tr);
    });
    var tr = el("tr");
    cols.forEach(function (c, i) {
      var teks = i === 0 ? "Rata-rata" : angka(rep.rata[c[0]], c[0] === "maks_ruang_tunggu" ? 2 : c[2]);
      var td = el("td", teks, i ? "num" : "");
      td.style.fontWeight = "700";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }

  function renderTrace() {
    var f = document.getElementById("filter").value;
    var rows = f ? traceData.filter(function (r) { return r.event === f; }) : traceData;
    document.getElementById("ket-trace").textContent =
      "Menampilkan " + rows.length + " dari " + traceData.length + " event.";
    var tbody = document.querySelector("#tabel-trace tbody");
    kosongkan(tbody);
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("td", fmt2.format(r.clock), "num"));
      tr.appendChild(el("td", r.event));
      tr.appendChild(el("td", String(r.mobil), "num"));
      tr.appendChild(el("td", String(r.q_daftar), "num"));
      tr.appendChild(el("td", String(r.r_tunggu), "num"));
      tr.appendChild(el("td", String(r.q_bayar), "num"));
      tr.appendChild(el("td", String(r.montir_bebas), "num"));
      tr.appendChild(el("td", r.resepsionis));
      tr.appendChild(el("td", r.keterangan));
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    tampilkanError([]);
    btnRun.disabled = true;
    statusEl.textContent = "Menjalankan simulasi...";
    fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bacaForm())
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (!r.ok) {
        tampilkanError(r.data.errors || ["Terjadi kesalahan."]);
        statusEl.textContent = "";
        return;
      }
      traceData = r.data.trace;
      renderStats(r.data.stats);
      renderFlowchart(r.data.flowchart_svg);
      renderReplikasi(r.data.replikasi);
      document.getElementById("filter").value = "";
      renderTrace();
      hasilEl.hidden = false;
      statusEl.textContent = "Selesai: " + r.data.stats.mobil_selesai + " mobil dalam " + fmt2.format(r.data.stats.waktu_simulasi) + " menit simulasi.";
    }).catch(function () {
      tampilkanError(["Tidak bisa menghubungi server. Pastikan aplikasi Flask masih berjalan."]);
      statusEl.textContent = "";
    }).then(function () { btnRun.disabled = false; });
  });

  document.getElementById("btn-reset").addEventListener("click", function () {
    isiForm(defaults);
    tampilkanError([]);
  });
  document.getElementById("filter").addEventListener("change", renderTrace);
})();
