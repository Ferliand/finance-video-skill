"""Template beat untuk Format A (cerita) dan Format B (panduan langkah).

Porsi durasi dihitung dari timestamp transkrip referensi (lihat prompts/panduan-naskah.md
bagian 2). Semua syarat struktur (tag awal/akhir, minimal PUNCH, dst.) ditulis di sini
dan disimpan ke beats.json, sehingga prompt LLM dan lint memakai sumber yang sama.
"""
from __future__ import annotations

from .brief import Brief
from .schema import Beat, BeatSheet

WPM = {"A": 152, "B": 157, "S": 160}            # tengah rentang yang ditulis di panduan
WORDS_PER_SCENE = 25                  # tengah rentang 15-35 kata

_ORD_A = ["pertama", "kedua", "ketiga", "keempat", "kelima"]
_ORD_S = ["kesatu", "kedua", "ketiga", "keempat", "kelima"]
_T_WEIGHTS = [16, 13, 19, 18, 16]
_T_MOODS = ["neutral", "warm", "uplift", "warm", "neutral"]
_S_MOODS = ["warm", "neutral", "uplift", "warm", "neutral"]


def _templates(brief: Brief) -> list[dict]:
    n = brief.jumlah_bagian
    has_cta = bool(brief.cta.get("komentar"))
    out: list[dict] = []

    if brief.format == "A":
        out.append(dict(
            id="hook", kind="hook", weight=8, mood="tense",
            title="Hook: adegan konkret",
            goal="Tarik perhatian dengan adegan konkret, bantah mitos, lalu pasang tesis.",
            key_points=[
                "Adegan konkret dengan waktu, tempat, dan angka di layar",
                "Bantah mitos tentang asal angka itu (bukan warisan, bukan keberuntungan)",
                "Tesis: angka itu mengubah beberapa hal",
            ],
            last_tag="BRIDGE"))
        for i in range(n):
            out.append(dict(
                id=f"t{i + 1}", kind="transformasi", weight=_T_WEIGHTS[i], mood=_T_MOODS[i],
                title=f"Transformasi {_ORD_A[i]}",
                goal="Kondisi lama -> kondisi sekarang -> ironi.",
                key_points=[
                    "Kontras waktu (dulu ... sekarang ...)",
                    "Satu istilah bernama (jujur soal statusnya) ATAU satu metafora visual",
                    "Satu bukti kecil berangka",
                    "Satu kalimat mantra di akhir bagian",
                ],
                first_tag="SECTION", last_tag="BRIDGE", min_tags={"PUNCH": 1}))
        out.append(dict(
            id="pembanding", kind="pembanding", weight=14, mood="melancholy",
            title="Tokoh pembanding",
            goal="Tokoh yang menempuh jalan sebaliknya, lengkap dengan angka nyata dan akibatnya.",
            key_points=[
                "Angka nyata: nominal, cicilan, durasi",
                "Akibat jangka menengah bagi tokoh pembanding",
            ],
            last_tag="BRIDGE"))
        out.append(dict(
            id="penutup", kind="penutup", weight=12, mood="warm",
            title="Penutup",
            goal="Pembingkaian ulang 'bukan X, tapi Y' lalu kembali ke protagonis.",
            key_points=[
                "Pembingkaian ulang: angka itu bukan garis finish, tapi garis start",
                "Kembali ke adegan protagonis",
                "Satu kalimat disclaimer jika instrumen keuangan disebut",
            ],
            max_tags={"CTA": 1}))
    elif brief.format == "S":
        out.append(dict(
            id="hook", kind="hook", weight=15, mood="tense",
            title="Hook: 3 detik pertama",
            goal="Hentikan scroll dengan pertanyaan mengejutkan atau angka langsung.",
            key_points=[
                "Tantangan cepat atau kontras visual",
                "Masalah yang langsung relevan bagi penonton",
            ],
            last_tag="BRIDGE"))
        out.append(dict(
            id="inti", kind="inti", weight=70, mood="neutral",
            title="Inti: 1 langkah nyata",
            goal="Satu strategi atau hitungan yang langsung bisa dipraktikkan.",
            key_points=[
                "Langkah konkret atau hitungan cepat",
                "Satu kalimat prinsip (PUNCH)",
            ],
            last_tag="BRIDGE", min_tags={"PUNCH": 1}))
        out.append(dict(
            id="penutup", kind="penutup", weight=15, mood="warm",
            title="Penutup & CTA",
            goal="Ajakan bertindak cepat atau simpan video.",
            key_points=[
                "Ajakan simpan/bagikan atau komentar",
            ],
            min_tags={"CTA": 1} if has_cta else {}))
    else:
        out.append(dict(
            id="hook", kind="hook", weight=9, mood="neutral",
            title="Hook: tantangan langsung",
            goal="Tantang penonton, tunjukkan empati ke audiens, janji tanpa mimpi kosong.",
            key_points=[
                "Tantangan langsung ('kalau hari ini saya minta kamu ...')",
                f"Empati ke audiens: {brief.audiens_spesifik or 'pekerja harian'}",
                "Janji: tidak menjual mimpi cepat kaya; cara berpikir dan langkah nyata",
                "Tujuan akhir video",
                "Ajakan komitmen kecil di komentar" if has_cta else "Tanpa ajakan komentar",
            ],
            last_tag="BRIDGE", min_tags={"CTA": 1} if has_cta else {}))
        out.append(dict(
            id="mitos", kind="mitos", weight=11, mood="neutral",
            title="Tiga kebohongan",
            goal="Bantah tiga anggapan keliru bernomor, lalu satu kalimat masalah inti.",
            key_points=[
                "Tiga 'kebohongan' bernomor (pertama, kedua, ketiga)",
                "Satu kalimat masalah inti",
            ],
            last_tag="BRIDGE"))
        out.append(dict(
            id="angka", kind="angka", weight=10, mood="neutral",
            title="Angka",
            goal="Hitungan bertahap yang bisa dicek penonton.",
            key_points=[
                "Hitung terbuka: harian -> bulanan -> tahunan -> beberapa tahun",
                "Tulis rumus di notes tiap scene hitungan",
                "Sebut timeline menuju angka tujuan secara jujur",
            ],
            last_tag="BRIDGE", min_tags={"CALC": 2}))
        for i in range(n):
            out.append(dict(
                id=f"s{i + 1}", kind="strategi", weight=10.5, mood=_S_MOODS[i],
                title=f"Strategi {_ORD_S[i]}",
                goal="Strategi bernomor yang bisa dijalankan.",
                key_points=[
                    "Pembuka bernomor",
                    "Masalah umum",
                    "Langkah konkret",
                    "Cara praktis atau contoh",
                    "Prinsip satu kalimat (mantra)",
                ],
                first_tag="SECTION", last_tag="BRIDGE", min_tags={"PUNCH": 1}))
        out.append(dict(
            id="simulasi", kind="simulasi", weight=11, mood="uplift",
            title="Simulasi",
            goal="Skenario tahun demi tahun dengan total di setiap tahap.",
            key_points=[
                "Tahun demi tahun, setoran dan total tiap tahap",
                "Instrumen disebut sebagai contoh, bukan rekomendasi",
            ],
            last_tag="BRIDGE", min_tags={"CALC": 1}))
        out.append(dict(
            id="emosi", kind="emosi", weight=10, mood="melancholy",
            title="Sisi manusiawi",
            goal="Akui lelah dan takut, beri makna pada kebiasaan kecil.",
            key_points=["Capek itu nyata", "Makna kebiasaan kecil bagi diri sendiri"],
            last_tag="BRIDGE"))
        out.append(dict(
            id="penutup", kind="penutup", weight=7, mood="warm",
            title="Penutup dan ajakan",
            goal="Satu langkah hari ini, ajakan komentar, subscribe, salam penutup.",
            key_points=[
                "Satu langkah yang bisa dilakukan hari ini",
                "Ajakan komentar" if has_cta else "Tanpa ajakan komentar",
                "Ajakan subscribe" if brief.cta.get("subscribe") else "Tanpa ajakan subscribe",
                "Kalimat disclaimer: bukan ajakan membeli produk tertentu",
            ],
            min_tags={"CTA": 1} if has_cta else {}))
    return out


def build_beats(brief: Brief) -> BeatSheet:
    tpl = _templates(brief)
    total_w = sum(t["weight"] for t in tpl)
    total_s = brief.durasi_menit * 60
    wpm = WPM[brief.format]
    beats = []
    for t in tpl:
        seconds = round(total_s * t["weight"] / total_w)
        words = round(seconds / 60 * wpm)
        beats.append(Beat(
            id=t["id"], kind=t["kind"], title=t["title"], goal=t["goal"],
            key_points=t["key_points"], target_seconds=seconds, target_words=words,
            target_scenes=max(2, round(words / WORDS_PER_SCENE)), mood=t["mood"],
            first_tag=t.get("first_tag"), last_tag=t.get("last_tag"),
            min_tags=t.get("min_tags", {}), max_tags=t.get("max_tags", {}),
        ))
    return BeatSheet(beats=beats)


def target_words(brief: Brief) -> int:
    return round(brief.durasi_menit * WPM[brief.format])
