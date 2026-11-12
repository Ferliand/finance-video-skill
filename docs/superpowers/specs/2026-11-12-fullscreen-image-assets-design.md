# Desain Fitur: Full-Screen AI Image Assets & Custom Style (`finance-video-script`)

- **Tanggal:** 2026-11-12
- **Target:** Repositori `finance-video-skill` & instalasi skill agen (`~/.pi/agent/skills/finance-video-script`, `~/.gemini/config/skills/finance-video-script`, `~/.claude/skills/finance-video-script`)
- **Ukuran Pekerjaan:** Perubahan kecil–menengah (*small change* terfokus pada pipeline aset visual & compositor `vengine`)

---

## 1. Tujuan & Alasan (*Intent and Why*)
Tampilan video yang dihasilkan `finance-video-script` saat ini masih terasa kaku seperti halaman kotak-kotak HTML karena:
1. Ilustrasi digambar secara prosedural menggunakan bentuk geometri dasar Pillow di dalam kotak berbingkai, bukan gambar *full-screen*.
2. Scene bertipe kartu (`calc_step`, `punchline_card`, `myth_card`, `before_after`, `cta_comment`) hanya menampilkan kotak warna polos tanpa aset gambar latar.
3. Gaya visual (*style*) masih terkunci pada satu string statis di kode.

Pembaruan ini menambahkan tahap pembuatan aset gambar AI **terlebih dahulu** (`generate-images`) dengan *style* yang bisa ditentukan pengguna, serta mengubah renderer menjadi komposisi **full-screen sinematik** di semua scene.

---

## 2. Goals, Non-Goals, & Anti-Goals
- **Goals:**
  1. Mendukung penentuan `style` visual melalui `brief.yaml` dan flag CLI `--style` (baik menggunakan nama preset seperti `3d-pixar`, `anime-ghibli`, `cinematic-realistic`, `flat-vector`, `comic-book`, `watercolor`, maupun deskripsi *custom style* bebas).
  2. Menyediakan perintah CLI `generate-images <slug>` sebelum `render` untuk men-generate aset gambar *full-screen* (`1920×1080` untuk Format A/B, `1080×1920` untuk Format S) di **semua scene** ke folder `out/images/scene_XXX.png` menggunakan **Pollinations.ai (model Flux)**.
  3. Mengubah `render.py` agar merender gambar AI *full-screen* dengan efek kamera *Ken Burns* (zoom & pan halus), *vignette* gradasi gelap di bagian bawah untuk subtitle karaoke tanpa kotak kaku, serta overlay *glassmorphism* semi-transparan (`RGBA`) untuk teks *punchline*, angka hitungan, mitos, dan CTA.
  4. Memperbarui dokumentasi `SKILL.md` dan menyinkronkan instalasi skill ke Pi, Antigravity, dan Claude Code.
- **Non-Goals:**
  - Mengubah struktur beat atau aturan validasi klaim/matematika di `lint_script.py`.
  - Mewajibkan pendaftaran API key berbayar untuk dapat menjalankan workflow standar.
- **Anti-Goals:**
  - Menampilkan kembali bingkai kotak kaku bergaya HTML yang mengecilkan gambar di tengah layar.
  - Gagal merender video ketika satu request gambar mengalami *timeout* sementara (wajib ada *retry* dan *fallback* visual).

---

## 3. Batasan (*Constraints*)
- Hanya menggunakan dependensi Python yang sudah ada (`pydantic`, `pyyaml`, `pillow`, `edge-tts`, `imageio-ffmpeg`, dan modul standar `urllib`) agar ringan dan langsung berjalan di semua agen.
- Seluruh suite pengujian `pytest` yang sudah ada harus tetap lulus tanpa regresi.

---

## 4. Pendekatan yang Dipertimbangkan (*Approaches*)
1. **Pendekatan 1 (Dipilih): Modul `image_gen.py` Terintegrasi + Compositor `RGBA` Sinematik di `render.py`**
   - Menambahkan modul `vengine/image_gen.py` untuk mengunduh gambar Pollinations Flux (`nologo=true`, `seed` deterministik) dan meracik prompt latar kontekstual otomatis bila sebuah scene belum memiliki `image_prompt`. Merombak `render.py` memakai `Image.alpha_composite` untuk *full-screen* Ken Burns, *vignette*, dan *glassmorphism*.
   - *Alasan dipilih:* Cepat, bebas dependensi baru, mendukung regenerasi per scene (`--scene N`), dan kompatibel dengan proyek baru maupun lama.
2. **Pendekatan 2: Mewajibkan `image_prompt` Ketat di Linter Tanpa Auto-Prompt di Engine**
   - *Alasan ditolak:* Membuat proyek lama tidak bisa langsung di-render *full-screen* dan meningkatkan kegagalan lint saat agen menulis scene hitungan.
3. **Pendekatan 3: Overlay Berbasis Headless Browser (HTML/CSS + Playwright)**
   - *Alasan ditolak:* Sangat lambat untuk render frame-by-frame dan membutuhkan instalasi Chromium.

---

## 5. Keputusan Desain dari Pengguna (*Decided by Partner*)
- **Layanan Generator Gambar:** Pollinations.ai dengan model `flux` (opsi 1 — gratis & tanpa API key).
- **Tata Letak Visual:** *Full-screen* untuk seluruh scene (gambar memenuhi layar, teks/angka/subtitle tampil sebagai overlay di atas gambar).
- **Alur Kerja:** Aset gambar di-generate terlebih dahulu dengan *style* yang ditentukan sebelum tahap render video.

---

## 6. Detail Teknis untuk Implementasi (*Builder's Calls*)
- **Preset & Resolusi Style (`vengine/image_gen.py`):**
  - Menyediakan dictionary `STYLE_PRESETS` (`flat-vector`, `3d-pixar`, `anime-ghibli`, `cinematic-realistic`, `watercolor`, `comic-book`, `dark-moody`). Jika nilai `style` bukan nama preset, nilai tersebut dipakai langsung sebagai prefix *style prompt*.
  - Setiap prompt selalu diakhiri instruksi negatif eksplisit: `"no text, no letters, no numbers, no watermark, clean composition"`.
- **Auto-Prompt untuk Scene Kartu:**
  - Jika `scene.image_prompt` bernilai `None` (misalnya pada `calc_step`, `punchline_card`, `section_title`, `cta_comment`), `build_scene_prompt(scene, brief, bible)` otomatis membuat prompt visual atmosferik berdasarkan topik, narasi scene, dan `mood` agar setiap scene tetap memiliki gambar latar *full-screen* yang relevan.
- **Penyimpanan & Caching Aset (`out/images/`):**
  - File disimpan di `video-projects/<slug>/out/images/scene_001.png` dst., dan path-nya dicatat ke `scene.image_file`.
  - Secara default `generate-images` melewati file yang sudah ada kecuali diberi flag `--force` atau `--scene <id>`.
  - Saat `render` dijalankan, jika ada `out/images/scene_XXX.png` yang belum dibuat, renderer otomatis memanggil generator untuk scene tersebut agar alur kerja tidak putus.
- **Compositor Sinematik (`vengine/render.py`):**
  - Layer 1: Gambar `out/images/scene_XXX.png` *full-screen* dengan efek *Ken Burns* (zoom `1.0` → `1.10` + pan lembut).
  - Layer 2: *Alpha gradient overlay* (gelap lembut di bagian bawah untuk keterbacaan subtitle, dan penggelapan halus di tengah khusus saat menampilkan kartu hitungan/punchline).
  - Layer 3: Elemen informasi (`calc_step`, `punchline_card`, `myth_card`, `before_after`, `cta_comment`) digambar di atas *glass panel* semi-transparan (`RGBA` gelap transparan dengan aksen tipis elegan, tanpa kotak putih pekat).
  - Layer 4: Subtitle karaoke di bagian bawah dengan teks putih ber-outline/bayangan halus dan sorotan pil warna aksen (`#E8A33D`) pada kata aktif, tanpa kotak pembungkus besar.
