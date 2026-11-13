---
name: finance-video-script
description: Menulis, memvalidasi, dan merancang naskah video keuangan pribadi berbahasa Indonesia untuk channel faceless (narasi suara + gambar/halaman) dalam tiga format, A (cerita bertokoh), B (panduan langkah bernomor), dan S (short-form Shorts/TikTok 30–60 dtk). Menyediakan beat sheet, penulisan scene per beat, lint otomatis (struktur, hitungan angka, klaim tanpa sumber, disclaimer, kemiripan dengan referensi), pemetaan halaman visual otomatis (map-pages), dan ekspor (naskah Markdown, prompts.json, subtitle SRT). Gunakan saat pengguna meminta naskah atau script video YouTube, Shorts, atau TikTok tentang menabung, uang harian, kebiasaan finansial; storyboard atau scenes.json; beat sheet; lint naskah; atau susunan gambar/halaman dan audio untuk video. Use for faceless Indonesian personal-finance video scripts, beat sheets, storyboards, and script linting.
---

# Finance Video Script

Agen (kamu) yang menulis naskah. Skrip `scripts/vengine_cli.py` menyiapkan kerangka beat, menerima scene per beat, dan menjalankan lint terhadap panduan gaya.

## Cakupan

- Termasuk: brief (termasuk pilihan `style` visual) → beat sheet → naskah per beat (`scenes.json`) → lint → pemetaan halaman visual (`map-pages`) → ekspor (`naskah.md`, `prompts.json`, `naskah.srt`) → generate aset gambar AI *full-screen* (`generate-images`) → render video MP4 sinematik lengkap dengan TTS Bahasa Indonesia (`render`).
- Belum termasuk: upload otomatis ke platform.

## Persiapan

- Python 3.10+ dengan `pip install pydantic pyyaml pillow edge-tts imageio-ffmpeg`, atau jalankan lewat `uv run` (dependensi otomatis).
- `<skill-dir>` = folder tempat `SKILL.md` ini berada. Semua perintah:
  `python <skill-dir>/scripts/vengine_cli.py <perintah> ...` (di Windows boleh `py` menggantikan `python`).
- Jalankan dari folder kerja pengguna, bukan dari dalam folder skill. Proyek disimpan di `./video-projects/<slug>/` (ubah dengan `--home DIR` atau variabel `VENGINE_HOME`).

## Alur kerja

1. **Kumpulkan brief.** Tanyakan yang belum jelas: topik, format (A = cerita, B = panduan langkah, S = short-form 30–60 detik), durasi, `style` visual (preset: `claymation`, `flat-vector`, `3d-pixar`, `anime-ghibli`, `cinematic-realistic`, `watercolor`, `comic-book`, `dark-moody`, atau deskripsi custom bebas), audiens, `angka_kunci`, dan khusus format A tokoh (protagonis, pembanding, figuran). Tanyakan juga ajakan komentar/subscribe dan instrumen keuangan yang boleh disebut. **Jangan mengarang angka kunci**; angka berasal dari pengguna atau dari hitungan yang kamu tulis rumusnya.
2. **Baca `references/panduan-naskah.md` dan `references/standar-kualitas-animasi.md`** sebelum menulis naskah atau membuat aset visual/animasi. Itu sumber kebenaran gaya, teknik, aturan angka/klaim, serta SOP wajib agar gambar konsisten dan animasi mulus satu arah (tanpa *ping-pong loop* berulang-ulang).
3. **Buat proyek.** `init <slug> --topic "..." --format A|B|S --minutes N --style <style>`, isi `brief.yaml` bersama pengguna, lalu `build <slug>` (membuat story bible dan beat sheet).
4. **Tulis per beat** (ulangi sampai semua beat selesai):
   1. `beat <slug>` menampilkan tugas untuk beat berikutnya: brief, tokoh, tiga scene sebelumnya, poin isi, target kata/scene, dan syarat tag.
   2. Tulis JSON scene ke `video-projects/<slug>/draft/<beat>.json`. Isi `image_prompt` berbahasa Inggris untuk **setiap scene** (karena seluruh scene dirender *full-screen*).
   3. `add <slug> --beat <id> --file video-projects/<slug>/draft/<id>.json`.
   4. Jika ada **error**, beat tidak disimpan. Perbaiki JSON sesuai pesan lalu `add` lagi. Jika beat perlu ditulis ulang setelah tersimpan, tambahkan `--replace`. Jangan memakai `--force` kecuali pengguna meminta.
5. **Periksa.** `status <slug>` untuk progres, `lint <slug>` untuk pemeriksaan penuh. Error harus nol sebelum naskah ditunjukkan sebagai final; warn dibaca dan diputuskan bersama pengguna.
6. **Petakan Halaman Visual.** Jalankan `map-pages <slug>` untuk memetakan `page_type` dan `props` secara otomatis mengikuti katalog `references/design-video.md`.
7. **Ekspor.** `export <slug>` menghasilkan:
   - `video-projects/<slug>/out/naskah.md` (naskah kanonik per babak)
   - `video-projects/<slug>/out/naskah_elevenlabs.md` (panduan lengkap slider ElevenLabs per mood, teks copy-paste per scene untuk Multilingual v2 & Eleven v3 dengan audio tags, serta teks utuh)
   - `video-projects/<slug>/out/naskah_elevenlabs.txt` (naskah bersih siap copy-paste sekali jalan ke ElevenLabs)
   - `video-projects/<slug>/out/prompts.json` (prompt ilustrasi *full-screen* siap generate untuk seluruh scene lengkap dengan karakter & style)
   - `video-projects/<slug>/out/naskah.srt` (subtitle ber-timestamp)
8. **Generate Aset Gambar AI Full-Screen.**
   - **Prioritas Utama (di dalam Agen):** Jika agen memiliki subagent/tool `image-generator` bawaan (Google Imagen / Gemini Image), **wajib gunakan `image-generator`** untuk men-generate gambar dari `video-projects/<slug>/out/prompts.json` langsung ke `video-projects/<slug>/out/images/scene_XXX.png` (serta `scene_XXX_end.png` jika ada `end_prompt`), lalu jalankan `generate-images <slug>` tanpa `--force` untuk menautkan path `image_file` di `storyboard.json`.
   - **Alternatif CLI mandiri:** Jalankan `generate-images <slug>` (bisa tambah `--style <style>`, `--scene <nomor>`, atau `--force`) untuk mengunduh gambar via endpoint CLI ke `video-projects/<slug>/out/images/scene_XXX.png`.
9. **Render Video MP4 (opsional/jika diminta).** Jalankan `render <slug>` (bisa tambah `--voice id-ID-ArdiNeural`, `id-ID-GadisNeural`, atau `elevenlabs:<voice_id>` dengan `ELEVENLABS_API_KEY`; tambahkan `--keep-audio` jika sudah menaruh MP3 manual hasil ElevenLabs di `out/audio/scene_XXX.mp3`; serta `--fps 12` untuk gaya stop-motion `claymation`) untuk menggabungkan gambar latar *full-screen* (dengan gerak *stop-motion* / *Ken Burns*, *vignette*, overlay *glassmorphism* angka/punchline, dan subtitle karaoke), audio voiceover Bahasa Indonesia, menjadi `video-projects/<slug>/out/video.mp4`.

## Format JSON scene

```json
{"scenes": [
  {"narration": "Strategi kesatu, uang harus dipisah di awal.",
   "tags": ["SECTION"], "image_prompt": "clean modern workspace with warm morning sunlight beams", "characters": [], "mood": "warm", "notes": ""},
  {"narration": "Kalau setiap hari kamu menyisihkan dua puluh ribu rupiah, dalam sebulan terkumpul enam ratus ribu rupiah.",
   "tags": ["CALC"], "image_prompt": "neatly stacked glass savings jars with glowing coins on wooden desk",
   "motion_prompt": "Stop-motion claymation, slow subtle push-in camera, soft ambient light flicker", "characters": [], "mood": "neutral",
   "notes": "20.000 x 30 = 600.000"}
]}
```

- `narration`: siap dibacakan, 15–35 kata. Scene `PUNCH` dan `SECTION` maksimal 14 kata dan berdiri sendiri.
- `tags`: `PUNCH`, `BRIDGE`, `SECTION`, `CTA`, `NUMBER`, `CALC`. Syarat per beat ada di tugas dari `beat`.
- `image_prompt`: bahasa Inggris, tanpa teks atau angka di dalam gambar; direkomendasikan diisi pada setiap scene agar latar *full-screen* sesuai konteks (jika `null`, engine otomatis meracik prompt latar kontekstual).
- `end_image_prompt` (opsional): bahasa Inggris untuk *End Frame* jika scene memiliki transisi perubahan objek/pencahayaan (mis. sakelar lampu ditekan dari gelap ke terang; di-generate dengan *seed* yang sama).
- `motion_prompt` (opsional): instruksi gerak per scene (mis. `zoom_flicker`, `bobbing`, `switch_light` untuk animasi *stop-motion claymation*).
- `characters`: id tokoh dari story bible (mis. `protagonis`), bukan nama.
- `mood`: `tense`, `neutral`, `warm`, `uplift`, `melancholy`.
- `notes`: wajib berisi rumus `A x B = C` untuk scene `CALC`/`NUMBER`; tuliskan juga sumber klaim.

## Aturan yang tidak boleh dilanggar

- Tulis orisinal. Jangan menyalin atau memparafrasekan video atau transkrip referensi; hanya struktur dan teknik yang dipakai.
- Hitung ulang semua angka. Timeline menuju angka tujuan harus eksplisit dan jujur.
- Tanpa statistik tanpa sumber ("90% orang..."), tanpa janji hasil. Instrumen keuangan hanya sebagai contoh dan wajib disertai kalimat disclaimer.
- Konten fiksi (format A) diberi label "cerita ilustrasi".
- Jangan mengubah `beats.json` atau `scenes.json` dengan tangan; gunakan `add`, supaya validasi dan penomoran ulang scene tetap berjalan.

## Pemecahan masalah

- `Modul 'pydantic' belum terpasang` → `pip install pydantic pyyaml` atau pakai `uv run`.
- `Proyek ... tidak ditemukan` → periksa folder kerja; proyek berada di `./video-projects/` pada folder tempat perintah dijalankan, atau di `--home`.
- Lint `mirip_referensi` → letakkan transkrip referensi sebagai `.txt` di `./references/` (atau `--refs DIR`); tulis ulang bagian yang dilaporkan dengan kata-katamu sendiri.
- Lint `total_kata` → tambah atau kurangi scene di beat yang menyimpang jauh dari target (lihat `status`), lalu `add --replace`.
