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

## C. Standar Subtitle & Safe Area (Typography & Layout Rules)

1. **Semantic Chunking (Pemenggalan Frasa Utuh):**
   - Pecah teks subtitle berdasarkan **kesatuan frasa makna**, bukan sekadar batas jumlah karakter.
   - Kata depan (`di`, `ke`, `dari`, `pada`, `untuk`, `dengan`, `tanpa`, `agar`) dan frasa majemuk (`malam hari`, `masa depanmu`, `tanpa terasa`) **wajib berada dalam satu tampilan layar / baris yang sama**:
     - ❌ `Layar ponsel yang menyala terang di malam | hari menguras energimu.`
     - ✅ `Layar ponsel yang menyala terang | di malam hari menguras energimu.`
   - Batasi maksimal **4–6 kata per tampilan** (maksimal 2 baris seimbang).

2. **Vertical Video Safe Zone (9:16):**
   - Beri jarak aman (*padding*) minimal **10–12% dari tepi atas dan bawah**, serta **8% dari tepi kiri dan kanan**.
   - **Hindari meletakkan progress bar di piksel paling atas (`y = 0`)**; letakkan sedikit di atas area teks subtitle atau hilangkan sepenuhnya agar visual sinematik lebih bersih.
