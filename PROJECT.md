# PROJECT.md — Dokumentasi Arsitektur & Roadmap `finance-video-skill`

Dokumen ini merangkum arsitektur teknis, kontrak data antar-tahap, tanggung jawab setiap modul di dalam `vengine`, serta daftar pengembangan berikutnya (*backlog/roadmap*).

---

## 1. Visi & Prinsip Desain

`finance-video-skill` dirancang untuk memisahkan **kreativitas penulisan LLM** dari **aturan struktur & produksi yang deterministik**:
- **Agen LLM** bertugas mengumpulkan brief dari pengguna dan menulis narasi per beat sesuai konteks.
- **Engine Python (`vengine`)** bertugas menjaga kontrak data, menghitung target kata/durasi, memvalidasi rumus matematika & klaim keuangan, memetakan jenis halaman visual, serta merakit audio/video.

---

## 2. Alur Data & Kontrak File Proyek

Setiap proyek disimpan di `./video-projects/<slug>/` dengan struktur file berikut:

```text
video-projects/<slug>/
├─ brief.yaml          # Input utama dari pengguna (Brief model)
├─ story_bible.json    # Tokoh, variabel angka kunci, dan kalimat disclaimer (StoryBible model)
├─ beats.json          # Kerangka beat, target kata/detik, dan syarat tag per beat (BeatSheet model)
├─ scenes.json         # Daftar scene tervalidasi beserta page_type, durasi, dan word timings (Storyboard model)
├─ draft/              # File JSON sementara per beat yang ditulis oleh agen
└─ out/
   ├─ naskah.md        # Naskah lengkap dalam format Markdown
   ├─ prompts.json     # Daftar prompt gambar ilustrasi tergabung dengan descriptor tokoh
   ├─ naskah.srt       # File subtitle SubRip (.srt)
   ├─ frames/          # Snapshot thumbnail PNG per scene
   ├─ audio/           # File voiceover MP3 per scene (edge-tts)
   ├─ segments/        # Segmen video MP4 per scene sebelum penggabungan
   └─ video.mp4        # Video MP4 hasil akhir
```

---

## 3. Arsitektur Modul (`skills/finance-video-script/scripts/vengine/`)

| Modul | Tanggung Jawab Utama |
|---|---|
| `schema.py` | Mendefinisikan model Pydantic (`Character`, `StoryBible`, `Beat`, `BeatSheet`, `WordTiming`, `Scene`, `Storyboard`) serta tipe literal `Tag`, `Mood`, dan `PageType`. |
| `brief.py` | Memvalidasi file `brief.yaml` (`topik`, `format: A\|B\|S`, `durasi_menit: 0.5–30`, `angka_kunci`, `tokoh`, `instrumen_boleh_disebut`, `cta`). |
| `formats.py` | Menghasilkan `BeatSheet` berdasarkan format (`A` cerita, `B` panduan langkah, `S` short-form vertikal) dan kecepatan bicara (`WPM`). |
| `project.py` | Mengelola pembuatan direktori proyek, validasi slug, dan penulisan file JSON/YAML secara atomik (`atomic_write`). |
| `lint_script.py` | Mengecek struktur beat, panjang kalimat, rumus matematika di `notes` (`_eval_formula` dengan dukungan tanda kurung), klaim statistik tanpa sumber, kalimat disclaimer, nilai Rupiah tanpa dasar, dan kemiripan *n-gram* dengan referensi. |
| `page_mapper.py` | Memetakan setiap `Scene` secara deterministik ke `PageType` (`section_title`, `punchline_card`, `calc_step`, `number_callout`, `myth_card`, `before_after`, `cta_comment`, `bank_screen`, `chat_bubble`, `phase_cards`, `diagram`, `illustration`). |
| `image_gen.py` | Menyediakan preset `STYLE_PRESETS` & resolusi custom style, meracik prompt visual *full-screen* untuk seluruh scene (`build_scene_prompt`), serta mengunduh aset gambar AI dari Pollinations Flux (`generate_project_images`) ke `out/images/` dengan dukungan *fallback* atmosferik. |
| `workflow.py` | Mengoordinasikan alur `build`, pembuatan prompt tugas per beat (`beat_brief`), penyimpanan scene (`add_scenes`), status, serta ekspor (`export_markdown`, `export_prompts`, `export_srt`). |
| `render.py` | Menghasilkan audio TTS Bahasa Indonesia (`edge-tts`), menghitung timing per kata (`compute_word_timings`), me-render komposisi *full-screen* (`render_scene_frame_at` dengan *Ken Burns*, *vignette*, *glassmorphism* `RGBA`, dan subtitle karaoke tanpa kotak kaku), serta menyatukan segmen via FFmpeg menjadi `out/video.mp4`. |
| `cli.py` | Menyediakan antarmuka baris perintah (`init`, `build`, `beat`, `add`, `status`, `lint`, `map-pages`, `export`, `generate-images`, `render`). |

---

## 4. Spesifikasi Motion & Visual Saat Ini (`render.py`)

Setiap scene di-render pada 15 FPS (dapat dikonfigurasi) dan di-*pipe* langsung sebagai `rawvideo` (`rgb24`) ke FFmpeg:
- **Progress Bar Atas**: Menunjukkan progres waktu di dalam scene.
- **Karaoke Subtitle**: Menyorot kata yang sedang aktif diucapkan dengan pil latar warna aksen (`#E8A33D`).
- **Animasi Spesifik per `PageType`**:
  - `punchline_card`: Kemunculan kata demi kata (*kinetic typography*) + garis bawah yang memanjang.
  - `section_title`: Efek *slide-up* judul bagian + cincin latar berdenyut.
  - `calc_step` / `number_callout`: Efek *live number count-up* (`Rp 0` → nilai akhir) + *progress bar* hijau.
  - `myth_card`: Garis coretan merah menyapu klaim secara diagonal (*strikethrough sweep*).
  - `before_after`: Kartu perbandingan bertahap (*Kondisi Lama* → *Kondisi Sekarang*).
  - `cta_comment`: Efek pengetikan (*typewriter*) dengan kursor berkedip di dalam kotak komentar.
  - `illustration`: Ilustrasi *flat-vector* kontekstual (dompet + koin melayang, dua toples tabungan dengan koin jatuh & tinggi tabungan naik, grafik batang tumbuh) ditambah efek kamera *Ken Burns zoom & pan*.

---

## 5. Backlog & Roadmap Pengembangan Selanjutnya

Berikut adalah area yang masih perlu ditingkatkan pada iterasi berikutnya:

1. **Kualitas Visual & Integrasi AI Image Generator**:
   - Integrasi opsional dengan API pembuat gambar (Imagen / Flux / Stable Diffusion / ComfyUI lokal) menggunakan daftar dari `out/prompts.json` agar scene `illustration` memakai gambar ilustrasi penuh, lalu diberi efek *Ken Burns* dan partikel.
   - Peningkatan kualitas grafis untuk halaman `diagram`, `phase_cards`, `timeline`, `chat_bubble`, dan `bank_screen` yang saat ini masih menggunakan tampilan dasar.
2. **Transisi Antar-Scene & Audio Mixing (BGM + SFX)**:
   - Menambahkan *crossfade* visual 0,3 detik antar-scene `illustration`.
   - Menambahkan efek suara (*whoosh*, *tick* saat *count-up* angka, *click*) dan musik latar (*background music* sesuai `mood` dengan *auto-ducking* saat narasi berbicara) sebagaimana dirancang di `references/design-video.md` Bagian 7.
3. **Word-Level Timestamp Presisi dari `edge-tts`**:
   - Menangkap event `WordBoundary` langsung dari stream `edge-tts` saat sintesis suara agar highlight kata di subtitle karaoke dan animasi `punchline_card` sinkron 100% hingga tingkat milidetik.
4. **Normalisasi Teks Lisan (`tts_text`) Otomatis**:
   - Mengubah penulisan angka/singkatan di `narration` (mis. `Rp20.000`, `KPR`, `DP`) menjadi ejaan lisan di field `tts_text` (`dua puluh ribu rupiah`, `ka pe er`, `de pe`) sebelum dikirim ke TTS.
5. **Aturan Penyeimbang (`Balancing Rules`) di Linter**:
   - Memvalidasi proporsi minimal halaman `illustration` (≥70% untuk Format A, ≥45% untuk Format B) dan mencegah lebih dari 2 halaman non-ilustrasi berturut-turut dengan tipe yang sama.
