---
doc: design-video
versi: 0.1
dipakai_oleh: tahap align → page mapper → images → render (Remotion) → qc
bahasa: id
---

# Design Spec Video — Susunan Halaman, Gambar, dan Audio

Dokumen ini menjelaskan bagaimana naskah (`scenes.json`) diubah menjadi susunan halaman visual dan audio yang pas.

**Status isi.** Bagian yang diturunkan dari transkrip referensi: struktur beat, ritme kalimat, tempat angka dan hitungan muncul, dan keberadaan musik latar (transkrip menandai `[musik]` sepanjang video). Gaya visual (warna, huruf, ilustrasi) dan nilai audio (level, jeda) adalah **usulan awal**, belum dicocokkan dengan tampilan asli video referensi. Lihat bagian 12 untuk hal yang perlu dikalibrasi.

---

## 1. Spesifikasi output

| Item | Nilai |
|---|---|
| Rasio utama | 16:9, 1920×1080, 30 fps |
| Rasio turunan | 9:16, 1080×1920 (komposisi sama, layout berbeda) |
| Safe area | 6% dari tiap tepi; subtitle di 12% dari bawah |
| Kodek | H.264, AAC 192 kbps, 48 kHz |
| Master clock | **Audio.** Semua animasi mengikuti timing audio |

---

## 2. Sistem visual (usulan)

**Warna** (ganti di `theme.json`; satu aksen saja):

| Token | Nilai | Pakai untuk |
|---|---|---|
| `bg` | `#F6F1E7` | Latar halaman non-ilustrasi |
| `ink` | `#1F2937` | Teks utama |
| `accent` | `#E8A33D` | Highlight kata aktif, angka penting |
| `positive` | `#2E7D5B` | Hasil/penambahan |
| `negative` | `#B8432F` | Pengeluaran/kebohongan |
| `bg-dark` | `#14181F` | Halaman dramatis (hook, emosi) |

**Huruf.** Plus Jakarta Sans (judul dan subtitle, Bold/Medium). Angka memakai varian *tabular figures*. Lisensi terbuka (Google Fonts).

**Gaya gambar AI.**
- Gaya tetap: `flat vector illustration, warm palette, soft shadows, minimal detail, no text`.
- Satu titik fokus per gambar. Sisakan ruang kosong ±30% untuk overlay.
- Tokoh tanpa wajah detail (siluet atau wajah minimal) supaya konsisten antarscene.
- Semua teks dan angka dibuat di layer render, **tidak** di dalam gambar AI.

**Karakter.** Tiap tokoh punya `descriptor` tetap di story bible (pakaian, warna, ciri). Descriptor disisipkan persis sama ke setiap prompt yang memuat tokoh itu.

---

## 3. Katalog halaman (page type)

| `page_type` | Dipakai untuk | Isi | Durasi | Gerak | Cue audio |
|---|---|---|---|---|---|
| `illustration` | Default; adegan cerita, emosi, metafora | Gambar AI full-bleed | Sepanjang narasi scene | Zoom 4–6% atau pan pelan, crossfade 0,3 dtk | Tidak ada |
| `section_title` | Kalimat `[SECTION]` ("Strategi kesatu...") | Nomor besar + judul, latar `bg-dark` | 2,5–3,5 dtk | Teks masuk dari bawah 0,4 dtk | Whoosh halus; musik naik 1 dB lalu kembali |
| `number_callout` | Angka kunci (`NUMBER`) | Angka besar di tengah + label kecil | Dari kata angka sampai akhir kalimat | Count-up 0,8 dtk | Tick lembut di akhir count-up |
| `calc_step` | Hitungan bertahap (`CALC`) | Baris: `Rp20.000 × 30 hari = Rp600.000` → baris berikutnya menyusul | Sepanjang rangkaian hitungan | Tiap baris muncul tepat saat angkanya diucapkan | Tick kecil per baris |
| `before_after` | Kontras waktu (format A) | Layar terbelah "3 tahun lalu / hari ini" | Sepanjang kontras | Garis pembelah menyapu 0,5 dtk | Tidak ada |
| `diagram` | Konsep berstruktur (mis. tiga kantong uang) | Komponen vektor berlabel | Sepanjang penjelasan | Tiap elemen muncul saat disebut | Klik lembut per elemen |
| `phase_cards` | Tahapan berurutan (bosan → ingin pakai → hampir nyerah) | Kartu berurutan | Sepanjang penjelasan | Kartu aktif membesar, lainnya redup | Tidak ada |
| `myth_card` | "Kebohongan ke-N" | Kartu berisi klaim yang dicoret | 3–4 dtk | Coretan menyapu 0,4 dtk | Tidak ada |
| `punchline_card` | Kalimat `[PUNCH]` | Kalimat penuh, teks besar di tengah, `bg-dark` | Kalimat + 0,8 dtk | Teks muncul per kata sesuai timing | Musik turun 3 dB, kembali setelahnya |
| `timeline` | Simulasi tahun demi tahun | Sumbu tahun + total per tahun | Sepanjang simulasi | Titik demi titik | Tick per titik |
| `chat_bubble` | Dialog (format A) | Gelembung chat bergantian | Sepanjang dialog | Muncul per baris | Tidak ada |
| `bank_screen` | Saldo/aplikasi (format A) | Mock layar mobile banking dengan angka dari variabel | Sepanjang scene | Count-up saldo | Tidak ada |
| `cta_comment` | Ajakan komentar | Kartu komentar contoh ("Hari ke-1") | 4–5 dtk | Kartu masuk, kursor mengetik | Tidak ada |
| `disclaimer_card` | Awal video (3 dtk) dan akhir | Teks disclaimer / label "cerita ilustrasi" | 3 dtk | Fade | Tidak ada |
| `outro` | Penutup | Ajakan subscribe + salam | 5–6 dtk | Fade | Musik fade out |

`illustration` boleh dipasang bersama overlay ringan (nomor bagian di sudut). Page type selain `illustration` tidak memerlukan gambar AI, sehingga hemat biaya.

---

## 4. Aturan pemetaan naskah → halaman

Pemetaan dilakukan oleh *page mapper* berbasis aturan (bukan LLM), dijalankan setelah alignment. LLM hanya dipanggil untuk menulis `image_prompt` scene `illustration`.

| Pemicu pada scene | `page_type` |
|---|---|
| Tag `SECTION` atau kalimat diawali "Strategi/Transformasi/Kebohongan ke-N" | `section_title` (lalu scene berikutnya `illustration`/`diagram`) |
| Tag `PUNCH` | `punchline_card` |
| Tag `CALC` atau ≥2 angka berurutan dengan operator (kali, jadi, hasilnya) | `calc_step` |
| Tag `NUMBER` atau satu angka kunci dari `angka_kunci` | `number_callout` |
| Pola "3 tahun lalu... hari ini", "dulu... sekarang" | `before_after` |
| Kata kunci tahapan: "fase pertama/kedua/ketiga" | `phase_cards` |
| Daftar tiga hal bernama ("kantong pertama/kedua/ketiga") | `diagram` |
| Kata "kebohongan", "mitos", "anggapan bahwa" di awal scene | `myth_card` |
| Tag `CTA` | `cta_comment` |
| Dialog dengan tanda kutip dan penutur berganti | `chat_bubble` |
| Layar ponsel/saldo/aplikasi disebut | `bank_screen` |
| Selain itu | `illustration` |

Aturan penyeimbang:
1. Maksimal 2 scene berturut-turut dengan `page_type` sama (selain `illustration`).
2. Format A: ≥70% scene berupa `illustration`. Format B: ≥45%.
3. `punchline_card` maksimal 1 per 90 detik.
4. Dua `illustration` berturut-turut harus berbeda komposisi (close-up vs wide, kiri vs kanan).
5. 20 detik pertama: ganti visual minimal tiap 4 detik.

---

## 5. Ritme dan durasi

- Satu scene = satu ide visual, 5–10 detik, mengikuti batas kalimat. Scene >12 detik wajib dipecah atau diberi gerak tambahan.
- Pergantian visual hanya di batas kalimat, kecuali animasi yang memang berjalan per kata (`calc_step`, `punchline_card`).
- Crossfade 0,3 dtk antar `illustration`; potongan langsung (cut) menuju/dari `punchline_card` dan `section_title`.
- Total durasi video = jumlah durasi audio scene + jeda (bagian 7).

---

## 6. Subtitle

| Properti | Nilai |
|---|---|
| Posisi | Tengah bawah, 12% dari tepi bawah |
| Huruf | Plus Jakarta Sans Bold, 46–52 px (16:9), 60 px (9:16) |
| Warna | Putih, bayangan gelap 60% atau latar pil transparan |
| Baris | Maksimal 2, maksimal 42 karakter per baris |
| Highlight | Kata yang sedang diucapkan memakai `accent`; kata lain tetap putih |
| Ejaan | Dari teks naskah asli (bukan hasil ASR); angka ditulis dalam bentuk tampilan ("Rp20.000") |
| Penyembunyian | Tidak tampil di atas `punchline_card` dan `section_title` (teks sudah ada di layar) |

---

## 7. Audio

### 7.1 Suara narasi

| Parameter | Nilai awal |
|---|---|
| Karakter | Tenang, hangat, mantap; tidak seperti pembawa berita |
| Kecepatan | 150–165 kata/menit (format A: 145–160) |
| Pengaturan TTS | Stabilitas tinggi, ekspresi rendah–sedang, kecepatan 0 s.d. −5% |
| Konsistensi | Satu suara untuk seluruh channel. Dialog format A dibacakan suara narator yang sama |

**Jeda** (disisipkan saat merakit audio, bukan diandalkan dari TTS):

| Posisi | Jeda |
|---|---|
| Koma | 0,15–0,25 dtk |
| Akhir kalimat | 0,40 dtk |
| Sebelum dan sesudah `[PUNCH]` | 0,80 dtk |
| Pergantian beat | 1,00–1,40 dtk |
| Setelah `section_title` muncul | 0,40 dtk sebelum narasi dimulai |

### 7.2 Normalisasi teks lisan (`tts_text`)

TTS membaca teks yang sudah dinormalisasi, subtitle membaca teks asli.

| Teks asli | `tts_text` |
|---|---|
| Rp20.000 | dua puluh ribu rupiah |
| Rp7.200.000 | tujuh juta dua ratus ribu rupiah |
| Rp100 juta | seratus juta rupiah |
| 90% | sembilan puluh persen |
| e-wallet | i-walet |
| DP / KPR | de pe / ka pe er |
| FU Money | ef yu money |

Setiap istilah asing yang salah dibaca saat uji suara ditambahkan ke `pronunciations.yaml`.

### 7.3 Musik latar

- Instrumental lembut tanpa vokal, hampir konstan di bawah suara (usulan berdasarkan penanda `[musik]` di transkrip referensi).
- Level di bawah suara: ±−22 dB relatif ke narasi. *Ducking* −8 dB saat narasi aktif, kembali penuh saat jeda ≥1 dtk.
- Siapkan 4–6 trek bebas royalti, crossfade 2 dtk saat mood berganti. Simpan bukti lisensi di `assets/music/LICENSES.md`.

| Mood (field `mood`) | Beat khas | Karakter musik |
|---|---|---|
| `tense` | Hook format A | Denyut rendah, minim melodi |
| `neutral` | Mitos, angka, strategi | Ritme datar, hangat |
| `warm` | Strategi, penutup | Gitar/piano hangat |
| `uplift` | Simulasi, kenaikan setoran | Naik perlahan |
| `melancholy` | Emosi, bagian pembanding | Piano lembut |

### 7.4 Efek suara

Maksimal 1 efek per 20 detik, level −30 dB relatif narasi. Hanya yang tercantum di katalog halaman (whoosh, tick, klik).

### 7.5 Loudness

Target mix akhir −14 s.d. −16 LUFS terintegrasi, true peak ≤ −1 dBTP. Narasi dinormalisasi per scene sebelum dirakit.

---

## 8. Sinkronisasi

1. Audio per scene dirender dulu. `duration` = panjang audio + jeda akhir.
2. *Forced alignment* menghasilkan timing per kata (`words`).
3. Elemen animasi diikat ke kata, bukan ke detik: `anchor_word` (indeks kata) menentukan kapan angka/baris/elemen muncul.
4. Pergantian gambar jatuh pada batas kalimat dengan toleransi ±0,1 dtk.
5. Musik dan efek suara dirakit di `timeline.json`, bukan di scene.

---

## 9. Kontrak data (tambahan pada `scenes.json`)

Field berikut ditambahkan ke model `Scene` (menggantikan `overlay` yang lama):

```json
{
  "id": 42,
  "beat": "s1",
  "narration": "Kalau nunggu sisa, enggak akan pernah ada sisa.",
  "tts_text": "Kalau nunggu sisa, enggak akan pernah ada sisa.",
  "tags": ["PUNCH"],
  "mood": "warm",
  "page_type": "punchline_card",
  "props": {"text": "Kalau nunggu sisa, enggak akan pernah ada sisa."},
  "anchor_word": null,
  "image_prompt": null,
  "characters": [],
  "sfx": [],
  "hold_after": 0.8,
  "audio_file": "audio/042.mp3",
  "duration": 4.6,
  "words": []
}
```

Contoh `calc_step`:

```json
{
  "page_type": "calc_step",
  "props": {"rows": [
    {"text": "Rp20.000 × 30 hari = Rp600.000", "anchor_word": 11},
    {"text": "Rp600.000 × 12 bulan = Rp7.200.000", "anchor_word": 27}
  ]}
}
```

`timeline.json` (hasil perakitan): daftar klip visual dengan `start`/`end`, trek narasi, trek musik (`mood`, `gain_db`, `ducking`), trek efek.

---

## 10. Template prompt gambar

```
{style_prefix}, {deskripsi_adegan}, {descriptor_tokoh_1}, {descriptor_tokoh_2},
{komposisi}, ruang kosong di {sisi} untuk teks
Negative: text, letters, numbers, watermark, logo, realistic face, extra fingers
```

Aturan:
1. `style_prefix` identik di semua gambar dalam satu video.
2. `komposisi` bergantian: close-up / medium / wide / over-the-shoulder.
3. Buat 2 varian per scene `illustration`. Pilih otomatis dengan filter (resolusi, tidak ada teks acak lewat OCR); sisanya ke review manual.
4. Sebelum batch penuh, generate 6 gambar uji (tokoh utama, suasana tegang, suasana hangat) dan setujui dulu sebagai kunci gaya.

---

## 11. QC otomatis (gagal = render ditahan)

- [ ] Total durasi dalam ±5% target brief.
- [ ] Tidak ada scene >12 dtk tanpa perubahan visual.
- [ ] 20 detik pertama punya ≥5 perubahan visual.
- [ ] Subtitle ≤2 baris dan tidak keluar safe area.
- [ ] Loudness terintegrasi dalam rentang target; tidak ada clipping.
- [ ] Tidak ada teks terdeteksi (OCR) di dalam gambar AI.
- [ ] Tidak ada >2 page type non-`illustration` yang sama berturut-turut.
- [ ] Setiap `anchor_word` menunjuk indeks kata yang valid.
- [ ] Disclaimer dan label fiksi (format A) muncul di timeline.

---

## 12. Yang perlu dikalibrasi (belum diketahui)

Hal berikut belum bisa saya amati dari transkrip:
1. **Tampilan asli** video referensi: apakah memakai gambar AI, footage, atau animasi; gaya huruf; ada tidaknya teks di layar. Kirim 3–5 tangkapan layar per referensi untuk menyesuaikan bagian 2–3.
2. **Suara asli**: jenis kelamin, tempo, gaya. Kirim 20–30 detik audio atau sebutkan suara TTS yang mirip.
3. **Musik asli**: genre dan kerasnya. Nilai di bagian 7.3 hanya usulan awal.

Selama tiga hal itu belum ada, anggap semua nilai visual dan audio di dokumen ini default yang boleh diubah di `theme.json` dan `audio.yaml`.
