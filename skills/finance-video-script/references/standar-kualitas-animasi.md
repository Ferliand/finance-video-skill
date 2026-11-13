# Standar Kualitas & Kelancaran Video (SOP Produksi Visual & Animasi)

Dokumen ini adalah standar wajib agar setiap video yang dihasilkan memiliki kualitas visual yang tajam, konsisten, mulus, dan **tidak terlihat berulang-ulang (no ping-pong loop)**.

---

## 1. Syarat Pembuatan Gambar & Keyframe (Image Generation SOP)

1. **Wajib Gunakan `image-generator` Bawaan (Google Imagen / Gemini Image):**
   - Jangan gunakan endpoint publik anonim yang menurunkan kualitas ke model *distilled* kecil.
   - Setiap gambar untuk Format S (Shorts/TikTok) wajib dirender dalam orientasi vertikal **9:16 (`1080×1920`)**, dan Format A/B dalam **16:9 (`1920×1080`)**.
2. **Kunci 4 Pilar Visual 3D Claymation (Jika `style: claymation`):**
   - **Tekstur Taktil Matte:** Permukaan *plasticine / polymer clay* yang *matte* (tidak mengilap seperti plastik Pixar) dengan jejak sidik jari halus (*subtle fingerprints*) dan guratan pahat lembut.
   - **Lensa Makro & Tilt-Shift:** Efek *shallow depth of field* seperti memotret panggung diorama miniatur 15 cm.
   - **Pencahayaan Studio Diffused:** *Softbox lighting* menyebar dengan bayangan kontak halus dan palet warna pastel *matte*.
   - **Siluet Chunky & Membulat:** Hindari detail tipis/rumit; bentuk karakter dan properti tebal membulat serta bebas teks/angka di dalam gambar.
3. **Teknik Anchor Frame untuk Multi-Pose (`scene_XXX_pose1..N.png`):**
   - **Pose 1 (`scene_XXX_pose1.png`)** adalah *Anchor Frame* yang menetapkan komposisi ruangan, sudut kamera, pakaian, dan pencahayaan dasar.
   - **Pose 2, 3, dst.** wajib dibuat menggunakan mode **Edit / Image Reference dari Pose 1**, dengan instruksi eksplisit: *"Pertahankan 100% latar diorama, sudut kamera, dan tubuh karakter; hanya ubah [1 elemen aksi: kelopak mata / lirikan mata / posisi tangan pada sakelar]."*
   - Dilarang men-generate Pose 2 & 3 dari nol tanpa referensi gambar Pose 1 karena akan mengubah bentuk wajah/ latar dan menimbulkan loncatan visual (*jump cut*).

---

## 2. Syarat Pergerakan & Animasi Per Scene (Motion & Interpolation SOP)

1. **Alur Progresif Satu Arah (`Start → Mid → End`, Dilarang Ping-Pong Loop):**
   - Satu scene berdurasi 3–5 detik hanya boleh memuat **1 busur aksi progresif yang berjalan satu kali dari awal hingga akhir kalimat**, tidak boleh bolak-balik (`A → B → A → B`).
   - Contoh pembagian waktu dalam 1 scene:
     - **0% – 30% durasi:** *Hold Pose Awal* (selaras dengan pembuka kalimat narator).
     - **30% – 65% durasi:** *Transisi S-Curve Halus ke Pose Tengah* (reaksi/aksi berlangsung).
     - **65% – 100% durasi:** *Transisi S-Curve Halus & Hold Pose Akhir* (puncak emosi/resolusi kalimat).
2. **Interpolasi S-Curve Halus (Bukan Hard Cut):**
   - Perpindahan antar-pose wajib menggunakan *cosine/cubic S-curve cross-blend* (`_interpolate_progressive_poses`), bukan pergantian gambar mendadak (*instant swap*) yang membuat gambar berkedip kasar.
3. **Kamera Stabil & Mulus (Tanpa Goyangan/Jitter Acak):**
   - Gerakan kamera (*slow push-in* / *zoom*) wajib dihitung secara kontinu menggunakan fungsi *easing* (`_ease_out_cubic`) dengan interpolasi `BICUBIC` pada **24 FPS**, tanpa *random pixel jitter* (`±px`) yang membuat layar bergetar.

---

## 3. Syarat Narator & Sinkronisasi Audio (ElevenLabs & Voiceover SOP)

1. **Naskah Khusus ElevenLabs (`out/naskah_elevenlabs.md` & `.txt`):**
   - Gunakan **Eleven Multilingual v2** atau **Eleven v3** (dengan *Audio Tags* seperti `[serious, low tone]`, `[sighs, tired]`, `[hopeful, energetic]`).
   - Pengaturan slider yang disarankan: `Stability 40%–55%`, `Similarity 80%`, `Style 25%–35%`, `Speaker Boost ON`.
2. **Pemotongan & Sinkronisasi Otomatis (`--audio-file` / `--keep-audio`):**
   - Jika menggunakan 1 file MP3 utuh dari ElevenLabs, jalankan `render <slug> --audio-file <path.mp3>` agar dipotong otomatis pada titik jeda antar-kalimat (`silencedetect` 35% ke dalam jeda, sehingga helaan napas di awal kalimat berikutnya tidak terpotong).
   - Durasi tiap scene dan highlight subtitle karaoke wajib mengikuti durasi riil file audio narator.
