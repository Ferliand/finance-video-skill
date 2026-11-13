# Panduan & Standar Kualitas Generate Video (Visual, Animasi, & Tipografi)

Dokumen ini adalah pedoman wajib yang harus dipatuhi setiap kali membuat aset gambar, menganimasikan keyframe, dan menyusun tata letak subtitle video.

---

## A. Standar Kontinuitas & Fisika Visual (Visual Continuity Rules)

1. **Strict Anchor Locking (Dalam Satu Scene):**
   - Ketika membuat variasi pose dalam satu scene yang sama (misalnya perubahan ekspresi wajah atau gerakan jari), wajib gunakan gambar pertama sebagai referensi komposisi tetap (*Image-to-Image / Reference Frame*).
   - **Dilarang mengubah *focal length*, jarak kamera, atau posisi bahu/tubuh** kecuali diinstruksikan sebagai pergantian shot (*cut to close-up*).

2. **Chronological State Progression (Urutan Sebab-Akibat):**
   - Setiap perubahan status visual harus mengikuti urutan logis dari **Kondisi Awal → Aksi Fisik → Dampak Visual** (satu arah, tanpa pengulangan bolak-balik):
     - **Baterai terkuras:** Mulai dari 2–3 bar → berkurang menjadi 1 bar merah berkedip → karakter tampak lemas.
     - **Menekan sakelar:** Tangan mendekat → jari menekan tombol hingga posisi sakelar berubah → lampu menyala dan menerangi ruangan.

3. **4 Pilar Visual 3D Claymation (Saat `style: claymation`):**
   - **Tekstur & Ketidaksempurnaan Material:** Permukaan *plasticine / polymer clay* wajib memiliki *matte finish* (tidak mengilap seperti kaca/plastik Pixar), sedikit bekas sidik jari (*subtle fingerprints*), dan guratan alat pahat halus.
   - **Lensa Makro & Tilt-Shift:** Gunakan efek *shallow depth of field* (latar depan dan belakang sedikit blur) seolah-olah memotret panggung miniatur setinggi 15 cm dari jarak dekat.
   - **Pencahayaan Studio Lembut:** Gunakan *diffused softbox lighting* dengan bayangan halus di bawah objek dan palet warna pastel *matte*.
   - **Siluet Membulat (*Chunky & Rounded*):** Karakter dan properti berbentuk tebal dan membulat, bebas garis tipis rumit, serta bebas teks/angka di dalam gambar.

---

## B. Standar Transisi & Animasi (Motion & Transition Rules)

1. **Larangan Cross-Dissolve untuk Gerakan Karakter:**
   - **Jangan pernah menggunakan *opacity crossfade (dissolve)*** untuk menganimasikan pergerakan anggota tubuh atau ekspresi wajah karena akan menghasilkan artefak bayangan ganda (*ghosting*).
   - **Jika menggunakan pipeline Image-to-Video (I2V):**
     - Jadikan Keyframe A sebagai *Start Frame* dan Keyframe B sebagai *End Frame* untuk menghasilkan gerakan transisi alami.
   - **Jika menggunakan pipeline Gambar Statis (FFmpeg / Python / Remotion):**
     - Gunakan *inpainting* / *image-edit* pada bagian yang bergerak saja, lalu sambungkan dengan **instant cut bergaya stop-motion (tanpa fade)** ditambah efek gerak kamera (**continuous zoom/pan**) yang membentang mulus di sepanjang scene.
     - Gunakan transisi *cut* tegas hanya saat berpindah scene (misalnya dari kamar tidur ke *close-up* sakelar), atau *whip/fade* singkat (`0,15–0,2 detik`) yang selaras dengan ketukan audio.

---

## C. Standar Subtitle, Tipografi & Safe Area (Typography, Readability & Layout Rules)

1. **Semantic Chunking & Phrase-Aware Tokenization:**
   - Pecah teks subtitle berdasarkan **kesatuan frasa makna** (maksimal **4–6 kata**, maksimal **2 baris** seimbang).
   - Kata depan & kata sambung (`di`, `ke`, `dari`, `pada`, `untuk`, `dengan`, `tanpa`, `agar`, `yang`, `dan`) serta frasa majemuk (`malam hari`, `masa depan`, `tanpa terasa`, `rumah sakit`) **wajib berada dalam satu tampilan layar / baris yang sama**:
     - ❌ `Layar ponsel yang menyala terang di malam | hari menguras energimu.`
     - ✅ `Layar ponsel yang menyala terang | di malam hari menguras energimu.`

2. **Standar Emas Tipografi & Readability (Kanvas `1080×1920`):**
   - **Primary Font:** `Plus Jakarta Sans` ExtraBold (Weight: `800`) atau `Rubik` ExtraBold (`800`), **Size `54px–62px`** (`56px` default vertikal), **`line-height: 1.22`**, **Normal Sentence Case** (hindari ALL CAPS untuk kalimat panjang).
   - **Balanced Lines (`textWrap: 'balance'`):** `maxWidth: 880px` (`82%` lebar kanvas) dengan pembagian panjang baris atas dan bawah yang proporsional agar tidak menyisakan 1 kata yatim di baris kedua.
   - **Wajib `paintOrder: 'stroke fill'` + Multi-Layer Shadow:** Gambar *outer stroke* gelap tebal `10px–12px` (`#0B0F19`) di luar huruf sebelum *fill* (agar huruf tetap bulat utuh, tidak kurus), ditambah bayangan lembut (`0px 8px 16px rgba(0,0,0,0.65)`) agar tetap kontras di latar terang maupun gelap.
   - **Palet Warna Kontras Tinggi:** Teks utama **Putih Bersih (`#FFFFFF`)** dan kata kunci/aktif **Kuning Emas (`#FACC15`)** atau **Hijau Mint (`#4ADE80`)**.

3. **9:16 UI Safe Margin (`1080×1920`):**
   - **Top margin:** minimal **`180px` bersih** (dilarang menaruh progress bar di `y = 0`; letakkan tipis di atas area teks subtitle atau hilangkan).
   - **Bottom margin:** tempatkan subtitle di rentang **`280px` hingga `380px` dari tepi bawah** agar bebas dari UI caption TikTok/Reels/Shorts.
   - **Horizontal padding:** minimal **`90px` kiri dan kanan**.
