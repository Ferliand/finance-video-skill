# finance-video-skill

Skill (format [Agent Skills](https://agentskills.io): `SKILL.md` + `scripts/` + `references/`) untuk menulis, memvalidasi, memetakan halaman visual, dan me-render video keuangan pribadi berbahasa Indonesia untuk channel *faceless* (narasi suara + animasi kartu/ilustrasi).
Satu folder skill yang sama dapat dipakai di **Claude Code**, **Antigravity**, dan **Pi**.

---

## Fitur Utama

1. **3 Format Video Terstruktur**:
   - **Format A (Cerita Bertokoh, 8–11 menit)**: Sudut pandang orang ketiga (`protagonis`, `pembanding`, `figuran`) dengan pola transformasi *kondisi lama → kondisi sekarang → ironi*.
   - **Format B (Panduan Langkah Bernomor, 10–21 menit)**: Narator *"saya"* berbicara langsung ke penonton (`hook` → `mitos` → `angka` → `strategi` → `simulasi` → `emosi` → `penutup`).
   - **Format S (Short-Form / Shorts / TikTok / Reels, 30–60 detik)**: Rasio vertikal `9:16` (`1080×1920`) dengan 3 beat padat (`hook` → `inti` → `penutup`).
2. **Validasi & Linter Naskah Otomatis (`lint`)**:
   - Memeriksa syarat tag per beat (`SECTION`, `PUNCH`, `BRIDGE`, `CALC`, `NUMBER`, `CTA`).
   - Mengevaluasi kebenaran rumus matematika di `notes` (mendukung operasi aritmatika dan tanda kurung `()`).
   - Mencegah klaim statistik tanpa sumber, janji hasil investasi, nominal Rupiah tanpa dasar di `angka_kunci`, serta ketiadaan kalimat disclaimer.
   - Mendeteksi kemiripan *n-gram* dengan transkrip referensi.
3. **Pemetaan Visual Otomatis (`map-pages`)**:
   - Memetakan setiap scene ke 15 jenis katalog halaman (`page_type` seperti `punchline_card`, `section_title`, `calc_step`, `myth_card`, `before_after`, `cta_comment`, `illustration`) secara deterministik.
4. **Ekspor Downstream (`export`)**:
   - Menghasilkan `out/naskah.md`, `out/prompts.json` (prompt ilustrasi siap *batch-generate* lengkap dengan *character descriptor*), dan `out/naskah.srt` (subtitle).
5. **Per-Frame Motion Video Renderer (`render`)**:
   - Menghasilkan voiceover Bahasa Indonesia natural menggunakan `edge-tts` (`id-ID-ArdiNeural` / `id-ID-GadisNeural`).
   - Me-render animasi per-frame langsung ke pipe FFmpeg (`video.mp4`): *kinetic typography*, *live number count-up*, *strikethrough sweep*, *typewriter CTA*, ilustrasi *flat-vector* kontekstual dengan *Ken Burns zoom & pan*, serta *karaoke active-word subtitle*.

---

## Struktur Repositori

```text
finance-video-skill/
├─ README.md                        # Panduan instalasi & penggunaan cepat
├─ PROJECT.md                       # Dokumentasi arsitektur teknis & roadmap pengembangan
├─ skills/finance-video-script/
│  ├─ SKILL.md                      # Instruksi utama untuk AI Agent
│  ├─ references/
│  │  ├─ panduan-naskah.md          # Aturan gaya, struktur beat, angka, dan kepatuhan
│  │  └─ design-video.md            # Spesifikasi visual, katalog halaman, audio, dan gerak
│  ├─ assets/brief.template.yaml    # Template input brief proyek video
│  └─ scripts/
│     ├─ vengine_cli.py             # Entrypoint CLI: init | build | beat | add | status | lint | map-pages | export | render
│     └─ vengine/                   # Paket inti (schema, brief, formats, lint_script, page_mapper, render, workflow, project)
├─ scripts/
│  ├─ install.sh                    # Installer untuk Linux / macOS / WSL / Git Bash
│  └─ install.ps1                   # Installer untuk Windows PowerShell
└─ tests/                           # Suite pengujian pytest (49 unit & end-to-end tests)
```

---

## Instalasi

### Prasyarat
Python 3.10+ beserta dependensi:
```bash
pip install pydantic pyyaml pillow edge-tts imageio-ffmpeg
```

### Lokasi Skill per Agen

| Agen | Global | Per Proyek |
|---|---|---|
| **Claude Code** | `~/.claude/skills/finance-video-script/` | `.claude/skills/finance-video-script/` |
| **Antigravity** | `~/.gemini/config/skills/finance-video-script/` | `.agents/skills/finance-video-script/` |
| **Pi** | `~/.pi/agent/skills/finance-video-script/` | `.pi/skills/finance-video-script/` |

### Windows PowerShell
```powershell
.\scripts\install.ps1 -All                      # Pasang ke semua agen (atau pilih -Claude / -Antigravity / -Pi)
.\scripts\install.ps1 -All -Link                # Gunakan symbolic link agar otomatis ter-update saat git pull
.\scripts\install.ps1 -All -Project C:\proyek   # Pasang khusus di level proyek
```

### Linux / macOS / WSL / Git Bash
```bash
./scripts/install.sh --all                      # atau --claude / --antigravity / --pi
./scripts/install.sh --all --link               # symlink: ikut ter-update saat git pull
./scripts/install.sh --all --project ~/proyek   # pasang di level proyek
```

Setelah memasang, mulai ulang sesi agen Anda.

---

## Cara Pakai

### 1. Lewat Percakapan Agen
Contoh prompt ke agen:
> Buat naskah video Shorts 1 menit (Format S) tentang trik menabung Rp20.000 per hari untuk ojol dan pekerja harian. Setoran harian 20000, sebulan 600000, setahun 7200000. Ajakan komentar: "Tulis: Hari ke-1". Setelah lulus lint, petakan halaman dan render videonya.

### 2. Perintah CLI Manual
```bash
# 1. Buat proyek baru (Format: A | B | S)
python skills/finance-video-script/scripts/vengine_cli.py init uang-harian --topic "Rp20.000 per hari" --format B --minutes 10

# 2. Bangun story_bible.json dan beats.json dari brief.yaml
python skills/finance-video-script/scripts/vengine_cli.py build uang-harian

# 3. Lihat instruksi tugas untuk beat berikutnya
python skills/finance-video-script/scripts/vengine_cli.py beat uang-harian

# 4. Tambahkan scene untuk beat tertentu (divalidasi otomatis)
python skills/finance-video-script/scripts/vengine_cli.py add uang-harian --beat hook --file hook.json

# 5. Cek progres dan jalankan linter penuh
python skills/finance-video-script/scripts/vengine_cli.py status uang-harian
python skills/finance-video-script/scripts/vengine_cli.py lint uang-harian

# 6. Petakan katalog halaman visual (page_type)
python skills/finance-video-script/scripts/vengine_cli.py map-pages uang-harian

# 7. Ekspor naskah.md, prompts.json, dan naskah.srt
python skills/finance-video-script/scripts/vengine_cli.py export uang-harian

# 8. Render video MP4 beranimasi + voiceover Bahasa Indonesia
python skills/finance-video-script/scripts/vengine_cli.py render uang-harian --voice id-ID-ArdiNeural
```

Hasil akhir tersimpan di `./video-projects/<slug>/out/` (`naskah.md`, `prompts.json`, `naskah.srt`, `video.mp4`).

---

## Pengembangan & Pengujian

```bash
pip install pytest pydantic pyyaml pillow edge-tts imageio-ffmpeg
python -m pytest -v
```

Lihat [PROJECT.md](./PROJECT.md) untuk detail arsitektur modul, kontrak data, dan daftar pengembangan lanjutan (*roadmap*).
