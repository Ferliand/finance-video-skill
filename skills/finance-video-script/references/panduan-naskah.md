---
doc: panduan-naskah
versi: 0.2
dipakai_oleh: pipeline/stages/s3_script.py (system prompt) dan prompts/critique.md (checklist)
bahasa: id
sumber_analisis: transkrip "Jebakan 100 Juta" (format A) dan "Mulai dari 20 Ribu Sehari" (format B)
---

# Panduan Naskah — Keuangan Pribadi untuk Orang Biasa

Dokumen ini adalah sumber kebenaran gaya naskah. Kalau hasil naskah kurang pas, ubah dokumen ini, bukan hasilnya.

Yang diambil dari referensi hanya **struktur dan teknik**. Tokoh, adegan, angka, metafora, dan kalimat harus orisinal. Jangan menyalin atau memparafrasekan dekat dari video referensi.

---

## 1. Posisi channel

| Aspek | Aturan |
|---|---|
| Audiens | Pekerja harian/informal (ojol, pedagang kecil, buruh harian) dan karyawan bergaji pas-pasan di Indonesia |
| Janji | Tidak menjual mimpi cepat kaya. Isinya cara berpikir dan langkah nyata yang bisa dijalani orang biasa |
| Nada | Tenang, empatik, tegas. Tanpa hype, tanpa menggurui |
| Sapaan | "kamu". Narator memakai "saya" (format B) atau sudut pandang ketiga (format A) |
| Bahasa | Indonesia sehari-hari. Boleh "enggak", "ribet", "capek". Jargon wajib dijelaskan dalam satu kalimat |

---

## 2. Pilih format

Isi `format` di brief (bagian 6).

### Format A — Cerita (tokoh bernama, 3 transformasi/pelajaran)

- Durasi 8–11 menit.
- Narator orang ketiga, satu protagonis, satu tokoh pembanding, satu tokoh figuran (mis. bos).
- Seluruh pelajaran disampaikan lewat adegan, bukan ceramah.

| Beat | Porsi durasi | Isi |
|---|---|---|
| `hook` | ≈8% | Adegan konkret (waktu, tempat, angka di layar) → bantah mitos tentang asal angka itu → tesis: angka itu mengubah beberapa hal |
| `t1`–`t4` | ≈16% / 13% / 19% / 18% | Satu transformasi per beat. Pola: **kondisi lama → kondisi sekarang → ironi**. Tiap beat punya satu istilah bernama (bila ada) atau satu metafora, satu bukti kecil berangka, satu kalimat mantra di akhir |
| `pembanding` | ≈14% | Tokoh yang menempuh jalan sebaliknya. Wajib ada angka nyata (nominal, cicilan, durasi) dan akibatnya |
| `penutup` | ≈12% | Pembingkaian ulang: "bukan X, tapi Y". Kembali ke protagonis di adegan penutup |

Jumlah beat `t` boleh 3–4 sesuai brief; porsinya dibagi ulang.

### Format B — Panduan langkah (narator "saya", strategi bernomor)

- Durasi 12–21 menit.
- Seluruh narasi berbicara langsung ke penonton.

| Beat | Porsi durasi | Isi |
|---|---|---|
| `hook` | ≈9% | Tantangan langsung ("kalau hari ini saya minta kamu...") → empati ke audiens → janji "tidak jual mimpi" → tujuan akhir → ajakan komitmen kecil di komentar |
| `mitos` | ≈11% | 3 "kebohongan" bernomor → satu kalimat masalah inti → jembatan |
| `angka` | ≈10% | Hitungan bertahap (harian → bulanan → tahunan → 5 tahunan). Tiap langkah dihitung terbuka |
| `s1`–`s4` | ≈10% / 10% / 10% / 11% | Strategi bernomor. Pola: **pembuka bernomor → masalah umum → langkah konkret → cara praktis/contoh → prinsip satu kalimat → jembatan** |
| `simulasi` | ≈11% | Skenario tahun demi tahun, dengan total di setiap tahap |
| `emosi` | ≈10% | Sisi manusiawi: lelah, takut, makna kebiasaan kecil |
| `penutup` | ≈7% | Ajakan bertindak hari ini, ajakan komentar, ajakan subscribe, salam penutup |

Jumlah strategi boleh 3–5 sesuai brief.

Porsi durasi di atas dihitung dari waktu tiap bagian di dua transkrip referensi. Gunakan sebagai patokan, bukan batas keras.

---

## 3. Teknik gaya (wajib, bisa dicek otomatis)

1. **Kontras "bukan X, tapi Y".** Minimal 0,6 kali per menit durasi (≈6 kali per video 10 menit, ≈12 kali per video 20 menit).
2. **Kalimat mantra/punchline.** Format B: satu per strategi, diawali "Ingat..." atau sejenisnya. Format A: satu per transformasi. Maksimal 14 kata. Kalimat mantra berdiri sendiri sebagai satu scene bertag `PUNCH` (kalimat pengantar "Ingat kalimat ini" ada di scene sebelumnya).
3. **Jembatan antar-bagian.** Setiap beat (kecuali `penutup`) berakhir dengan satu kalimat yang menyebut apa yang dibahas berikutnya. Scene terakhir beat bertag `BRIDGE`.
4. **Penanda urutan.** "Transformasi pertama...", "Strategi kesatu...", "Kebohongan kedua...". Scene pertama beat bertag `SECTION` dan hanya berisi penanda urutan + judul (maksimal 14 kata), mis. "Strategi kesatu, uang harus dipisah di awal."
5. **Angka konkret.** Setiap beat minimal satu angka yang bisa dicek (nominal, durasi, jumlah).
6. **Satu metafora per beat.** Harus visual dan mudah digambar (pemadam kebakaran, bantal pengaman, bola salju, benteng).
7. **Pola sebelum/sesudah (format A).** Gunakan kontras waktu ("3 tahun lalu... hari ini...") di tiap transformasi.
8. **Istilah bernama.** Boleh dipakai, tetapi wajib jujur soal statusnya. Istilah ilmiah ditulis "para psikolog menyebutnya...". Istilah populer ditulis "sering disebut...".
9. **Kalimat pendek untuk didengar.** Rata-rata 12–18 kata, maksimum 30. Tanpa tanda kurung, tanpa daftar bullet di narasi, tanpa singkatan yang tidak jelas cara bacanya.
10. **Ajakan komentar.** Format B: maksimal 2 ajakan (satu di hook, satu di penutup). Format A: maksimal 1 di penutup.
11. **Kecepatan.** Target 150–165 kata per menit (format A: 145–160). Contoh: video 10 menit ≈ 1.500–1.650 kata.

---

## 4. Aturan angka, klaim, dan kepatuhan (wajib)

1. **Hitung ulang semua angka** di tahap kritik. Tulis rumusnya di field `notes` tiap scene. Contoh: `20.000 × 30 = 600.000`; `600.000 × 12 = 7.200.000`.
2. **Timeline harus eksplisit dan jujur.** Contoh: Rp100 juta ÷ Rp7,2 juta per tahun ≈ 14 tahun tanpa imbal hasil. Kalau naskah menjanjikan lebih cepat, sebutkan skema kenaikan setoran dan tuliskan total di tiap tahap sampai angka tujuan. Jangan menyisakan tahapan yang tidak dihitung.
3. **Tanpa statistik tanpa sumber.** Frasa seperti "90% orang..." dilarang kecuali ada sumber yang bisa disebut di deskripsi. Ganti dengan bahasa kualitatif ("banyak orang").
4. **Tanpa janji hasil.** Instrumen (emas digital, reksa dana pasar uang, tabungan berjangka) disebut sebagai contoh, bukan rekomendasi. Wajib satu kalimat disclaimer di narasi dan satu di deskripsi: *"Ini bukan ajakan membeli produk tertentu. Pelajari risikonya dan sesuaikan dengan kondisimu."*
5. **Konten fiksi diberi label.** Format A wajib: kartu "cerita ilustrasi" di awal video dan di deskripsi. Jangan dibingkai sebagai kejadian nyata.
6. **Istilah psikologi dicek dulu.** Kalau tidak yakin istilahnya baku, pakai "sering disebut".
7. **Tanpa saran medis atau hukum spesifik.**
8. **Tanpa merendahkan audiens.** Hindari "orang miskin malas", "orang bodoh", dan sejenisnya.

---

## 5. Prompt sistem untuk LLM (versi ringkas yang dikirim pipeline)

```
Kamu penulis naskah video keuangan pribadi berbahasa Indonesia untuk orang biasa.
Ikuti dokumen PANDUAN di bawah secara ketat: format, beat, teknik gaya, dan aturan
angka/klaim. Tulis orisinal; jangan menyalin dari video lain.

Keluarkan JSON saja (tanpa teks lain) dengan skema:
{
  "title": str,
  "beats": [{"id": str, "title": str, "goal": str, "target_seconds": int}],
  "scenes": [{
    "id": int, "beat": str,
    "narration": str,            // 15–35 kata, siap dibacakan (scene PUNCH/SECTION: maks. 14 kata)
    "tags": ["PUNCH"|"BRIDGE"|"SECTION"|"CTA"|"NUMBER"|"CALC"],
    "image_prompt": str,         // deskripsi visual tanpa teks di dalam gambar
    "characters": [str],
    "mood": "tense|neutral|warm|uplift|melancholy",
    "notes": str                 // rumus hitungan & sumber klaim
  }]
}

Angka kunci selalu memakai variabel dari brief. Jumlah kata total harus sesuai
durasi target. Setiap beat berakhir dengan [BRIDGE] kecuali beat penutup.

BRIEF: {{brief_yaml}}
PANDUAN: {{isi_panduan_ini}}
```

Pipeline menjalankan dua langkah: (1) beat sheet dari brief, (2) draf per beat dengan konteks beat sebelumnya. Setelah itu langkah kritik memakai checklist bagian 7.

---

## 6. Brief per video (yang kamu isi)

```yaml
topik: "Rp20.000 per hari untuk pekerja harian"
format: B                 # A = cerita, B = panduan langkah
durasi_menit: 15
audiens_spesifik: "ojol dan pedagang kecil"
angka_kunci:              # dipakai sebagai variabel di seluruh naskah
  setoran_harian: 20000
  target: 100000000
jumlah_bagian: 3          # jumlah transformasi (A) atau strategi (B)
tokoh:                    # khusus format A
  protagonis: {nama: "...", pekerjaan: "...", umur: 29}
  pembanding: {nama: "...", kesalahan: "..."}
  figuran: {nama: "...", peran: "bos"}
instrumen_boleh_disebut: ["emas digital", "reksa dana pasar uang"]
cta: {komentar: "Tulis: Hari ke-1", subscribe: true}
catatan_khusus: ""
```

---

## 7. Checklist QC naskah (dijalankan otomatis, lalu dibaca manusia)

Otomatis (`python run.py lint <slug>`). Pelanggaran struktur, angka, dan klaim berstatus **error** (menahan pipeline). Pelanggaran gaya (rata-rata panjang kalimat, jumlah kontras) berstatus **warn** dan dibaca manusia:
- [ ] Total kata sesuai durasi (±8%).
- [ ] Rata-rata panjang kalimat 12–18 kata; tidak ada kalimat >30 kata.
- [ ] Tag `PUNCH`, `BRIDGE`, `SECTION` sesuai bagian 3 (syarat per beat tersimpan di `beats.json`).
- [ ] Setiap beat (kecuali `penutup`) berakhir dengan scene bertag `BRIDGE`.
- [ ] Semua angka di `narration` cocok dengan rumus di `notes` (hitung ulang dengan kode).
- [ ] Tidak ada pola statistik tanpa sumber (regex: `\d+\s?%\s+orang`).
- [ ] Disclaimer ada. Label fiksi ada (format A).
- [ ] Jumlah ajakan komentar sesuai batas.
- [ ] Tidak ada rangkaian ≥8 kata yang sama persis dengan teks referensi (teks referensi disimpan di folder `references/`, tidak ikut ke git).

Manual (30 detik per poin):
- [ ] 15 detik pertama menahan perhatian tanpa hype.
- [ ] Metafora tiap beat bisa digambar.
- [ ] Nada tetap empatik; tidak menyalahkan audiens.
- [ ] Penutup memberi satu langkah yang bisa dilakukan hari ini.
