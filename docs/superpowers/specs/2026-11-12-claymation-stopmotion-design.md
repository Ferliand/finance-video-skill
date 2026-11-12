# Desain Fitur: 3D Claymation Style & 12 FPS Stop-Motion Animation Engine

- **Tanggal:** 2026-11-12
- **Target:** `finance-video-skill` (`vengine/schema.py`, `vengine/image_gen.py`, `vengine/render.py`, `vengine/cli.py`, serta proyek simulasi 9 detik `clay-hook`)
- **Ukuran Pekerjaan:** Perubahan kecil–menengah (*small change* terfokus pada preset art direction `claymation` dan animator *stop-motion* 12 FPS di Python)

---

## 1. Tujuan & Alasan (*Intent and Why*)
Mewujudkan gaya visual tunggal yang khas dan berkarakter kuat—**3D Claymation (Stop-Motion)**—lengkap dengan pergerakan per frame pada **12 FPS** yang terasa seperti pemotretan boneka tanah liat fisik di panggung miniatur, lalu membuktikannya lewat simulasi 3 scene pertama (Hook 9 detik: masing-masing 3 detik per scene).

---

## 2. Goals, Non-Goals, & Anti-Goals
- **Goals:**
  1. **Preset Art Direction `claymation` Terkunci:** Mengunci 4 elemen wajib di setiap prompt:
     - Tekstur & ketidaksempurnaan material (`3D claymation style, handmade plasticine polymer clay texture with subtle fingerprints and sculpt tool marks, matte finish`).
     - Lensa makro & *tilt-shift* (`miniature 15cm diorama set, tilt-shift macro photography, shallow depth of field`).
     - Pencahayaan studio lembut (`soft diffused studio softbox lighting, gentle contact shadows, pastel matte color palette`).
     - Siluet membulat (`chunky rounded character and prop silhouettes, clean solid background`).
  2. **Dukungan Dual-Keyframe (`end_image_prompt`) & `motion_prompt` di Schema:**
     - Menambahkan field opsional `end_image_prompt`, `end_image_file`, dan `motion_prompt` pada model `Scene` di `schema.py`.
     - Jika `end_image_prompt` diisi (mis. Scene 3: tangan menekan sakelar lampu dari redup ke terang), `image_gen.py` men-generate *Start Frame* (`scene_XXX.png`) dan *End Frame* (`scene_XXX_end.png`) menggunakan **seed Flux yang sama** agar bentuk objek/ruangan tetap konsisten.
  3. **Animator Stop-Motion 12 FPS di `render.py`:**
     - Mendukung flag `--fps 12` (dan kuantisizer waktu *stepped stop-motion* "on twos" 6–12 pose/detik + *micro-jitter* ±1 px khas stop-motion).
     - Mengimplementasikan 3 perilaku gerak spesifik sesuai spesifikasi:
       - **Scene 1 (`zoom_flicker`):** *Slow push-in* ke wajah karakter + pendaran cahaya biru layar HP berkedip (*soft blue screen light flickering*) + gerak napas mikro (*subtle breathing*).
       - **Scene 2 (`bob_and_sigh`):** Kamera statis + zona atas (ikon baterai merah tanah liat) memantul naik-turun (*gentle bobbing*) secara *stepped stop-motion* + zona bahu karakter sedikit turun (*slump/sigh*).
       - **Scene 3 (`switch_light`):** Transisi *stop-motion* dari *Start Frame* (tangan di sakelar kuning) menuju *End Frame* (sakelar menyala) disertai kilatan pencerahan cahaya studio hangat (*warm bright studio light illumination*).
  4. **Simulasi Proyek `clay-hook` (9 Detik, 9:16, 12 FPS):**
     - Membuat dan me-render proyek uji 3 scene × 3 detik (`00:00–00:09`) untuk memverifikasi hasil MP4 secara nyata.
- **Non-Goals:**
  - Ketergantungan pada API Image-to-Video berbayar eksternal (semua dianimasikan di dalam Python).
- **Anti-Goals:**
  - Tampilan mengilap seperti plastik Pixar biasa (*glossy plastic*).
  - Gerakan kamera 60fps licin yang menghilangkan kesan *tactile stop-motion*.

---

## 3. Batasan (*Constraints*)
- Tetap menggunakan library Python yang sudah ada (`Pillow`, `pydantic`, `pyyaml`, `edge-tts`, `imageio-ffmpeg`) tanpa dependensi berat tambahan.
- Seluruh suite test `pytest` tetap lulus.

---

## 4. Pendekatan yang Dipertimbangkan (*Approaches*)
1. **Pendekatan 1 (Dipilih): Dual-Keyframe (Start & End Frame AI ber-Seed Sama) + Simulator Motion Stop-Motion di Python**
   - Menggabungkan *Start/End Frame* ber-seed sama dengan efek animasi lokal (*screen flicker*, *region bobbing & shoulder slump*, *switch light bloom*, dan *stepped stop-motion cadence* pada 12 FPS).
2. **Pendekatan 2: Single Frame + Efek Kamera Saja** — Ditolak karena sakelar dan ikon baterai tidak benar-benar beraksi.
3. **Pendekatan 3: Generate Banyak Frame AI Berbeda per Scene** — Ditolak karena bentuk wajah/ruangan akan berubah-ubah tanpa ControlNet.

---

## 5. Keputusan Desain dari Pengguna (*Decided by Partner*)
- Menggunakan spesifikasi **3D Claymation** dengan 4 pilar visual terkunci.
- Menggunakan frame rate **12 FPS** dan mengujinya pada simulasi 3 scene pertama (9 detik).
- Seluruh animasi gerak dikerjakan langsung di dalam script Python (`Pendekatan 1`).

---

## 6. Detail Teknis untuk Implementasi (*Builder's Calls*)
- **Deteksi Mode Gerak Otomatis (`_detect_clay_motion_mode`):**
  - Berdasarkan `scene.motion_prompt` (atau narasi/prompt):
    - Jika memuat `"flicker"` / `"screen"` / `"breathing"` → mode `zoom_flicker`.
    - Jika memuat `"bobbing"` / `"battery"` / `"sigh"` / `"slumps"` → mode `bob_and_sigh`.
    - Jika memuat `"switch"` / `"flip"` / `"illuminat"` atau memiliki `end_image_file` → mode `switch_light`.
- **Efek Lensa Tilt-Shift & Tekstur Diorama:**
  - Menambahkan helper `_apply_tilt_shift_dof` (blur lembut di 10% tepi atas dan bawah frame untuk memperkuat efek lensa makro panggung miniatur 15 cm).
- **Opsi Durasi & FPS di CLI (`render`):**
  - Menambahkan `--fps` (default `12` untuk style `claymation`, `15` untuk lainnya) dan mendukung durasi tetap per scene jika `scene.duration` sudah ditentukan pada simulasi visual.
