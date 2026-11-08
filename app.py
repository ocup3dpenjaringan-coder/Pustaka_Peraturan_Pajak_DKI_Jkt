"""Pustaka Peraturan Pajak - versi web (Streamlit), nyaman dipakai di HP.

Data dibaca dari Google Sheet. Atur SHEET_ID dan SHEET_GID di Secrets Streamlit.
"""
import re
from urllib.parse import quote

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Pustaka Peraturan Pajak", page_icon="📚", layout="centered")

ALIAS = {
    "jenis": ["jenis peraturan", "jenis", "tipe", "type"],
    "nomor": ["nomor peraturan", "nomor", "no. peraturan"],
    "tahun": ["tahun", "year"],
    "tentang": ["mengatur tentang", "tentang", "judul", "perihal", "title"],
    "jenis_pajak": ["jenis pajak", "kategori", "pajak", "kategori pajak"],
    "status": ["status", "keterangan status"],
    "tgl_berlaku": ["mulai berlaku tgl", "mulai berlaku", "tanggal berlaku", "tgl berlaku", "berlaku", "tanggal"],
    "ringkasan": ["ringkasan", "abstrak", "isi singkat", "uraian"],
    "link": ["link download", "link", "url", "tautan", "link dokumen", "file"],
    "catatan": ["catatan", "mengubah", "dicabut", "keterangan"],
}
HALAMAN = 20  # jumlah kartu per tampilan


# ----------------------------------------------------------------- fungsi data
def normalisasi_kolom(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lower = {c.lower(): c for c in df.columns}
    rename = {}
    for standar, daftar in ALIAS.items():
        for a in daftar:
            if a in lower and lower[a] not in rename:
                rename[lower[a]] = standar
                break
    df = df.rename(columns=rename)
    for standar in ALIAS:
        if standar not in df.columns:
            df[standar] = ""
    df = df[list(ALIAS)].fillna("").astype(str).apply(lambda s: s.str.strip())
    return df[df.apply(lambda r: any(r), axis=1)]


def tidak_berlaku(status: str) -> bool:
    return bool(re.search(r"\b(TDK|TIDAK|DICABUT|CABUT|BATAL)\b", status.upper()))


def judul_peraturan(d) -> str:
    return f"{d['jenis']} {d['nomor']} Tahun {d['tahun']}".strip()


def teks_kirim(d) -> str:
    baris = [judul_peraturan(d)]
    if d["tentang"]:
        baris.append(f"Tentang: {d['tentang']}")
    if d["status"]:
        baris.append(f"Status: {d['status']}")
    baris.append(f"Dokumen: {d['link']}")
    return "\n".join(baris)


def url_unduh_langsung(url: str) -> str:
    m = re.search(r"drive\.google\.com/file/d/([\w-]+)", url) or (
        re.search(r"[?&]id=([\w-]+)", url) if "drive.google.com" in url else None
    )
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r"docs\.google\.com/(document|spreadsheets|presentation)/d/([\w-]+)", url)
    if m:
        return f"https://docs.google.com/{m.group(1)}/d/{m.group(2)}/export?format=pdf"
    return url


def escape_md(s: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>#$~|])", r"\\\1", s)


def kunci_urut(nilai: str):
    return (0, int(nilai)) if nilai.isdigit() else (1, nilai.lower())


def cocok(d, tokens) -> bool:
    gabungan = " ".join(d[k] for k in ("jenis", "nomor", "tahun", "tentang", "jenis_pajak", "ringkasan", "catatan")).lower()
    return all(t in gabungan for t in tokens)


@st.cache_data(ttl=300, show_spinner="Mengambil data dari Google Sheet...")
def muat_data() -> pd.DataFrame:
    sheet_id = st.secrets["SHEET_ID"]
    gid = st.secrets.get("SHEET_GID", 0)
    if "gcp_service_account" in st.secrets:  # Sheet privat (opsional, butuh: pip install gspread)
        import gspread

        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        ws = gc.open_by_key(sheet_id).get_worksheet_by_id(int(gid))
        nilai = ws.get_all_values()
        df = pd.DataFrame(nilai[1:], columns=nilai[0])
    else:  # Sheet "Anyone with the link"
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(url, dtype=str, keep_default_na=False)
    return normalisasi_kolom(df)


# ------------------------------------------------------------------------ UI
def kartu(d, indeks):
    merah = tidak_berlaku(d["status"])
    with st.container(border=True):
        if merah:
            st.markdown(":red[**⚠ TIDAK BERLAKU**]")
        judul = escape_md(judul_peraturan(d))
        st.markdown(f":red[**{judul}**]" if merah else f"**{judul}**")
        st.write(d["tentang"])
        info = " • ".join(x for x in (d["jenis_pajak"], d["status"]) if x)
        if d["tgl_berlaku"]:
            info += f"  \nMulai berlaku: {d['tgl_berlaku']}"
        if info:
            st.caption(info)
        if d["ringkasan"]:
            st.caption(d["ringkasan"])
        if d["catatan"]:
            st.caption(f"Keterangan: {d['catatan']}")

        if not d["link"]:
            st.caption("_(Belum ada link dokumen)_")
            return
        c1, c2, c3 = st.columns(3)
        c1.link_button("👁 Lihat", d["link"], use_container_width=True)
        with c2.popover("📤 Kirim", use_container_width=True):
            teks = teks_kirim(d)
            st.link_button("💬 WhatsApp", f"https://wa.me/?text={quote(teks)}", use_container_width=True)
            st.link_button(
                "📧 Email",
                f"mailto:?subject={quote('Peraturan: ' + judul_peraturan(d))}&body={quote(teks)}",
                use_container_width=True,
            )
            st.caption("Atau salin teks ini (ikon salin di pojok kanan):")
            st.code(teks, language=None)
        c3.link_button("⬇ Download", url_unduh_langsung(d["link"]), use_container_width=True)


def main():
    kiri, kanan = st.columns([4, 1])
    kiri.title("📚 Pustaka Peraturan Pajak")
    if kanan.button("🔄", help="Muat ulang data dari Google Sheet"):
        muat_data.clear()
        st.rerun()

    try:
        data = muat_data()
    except Exception as e:  # noqa: BLE001
        st.error("Gagal memuat data. Periksa SHEET_ID, SHEET_GID, dan pengaturan Share Google Sheet "
                 "('Anyone with the link' - Viewer).")
        st.exception(e)
        st.stop()

    kata = st.text_input("🔎 Cari", placeholder="mis. pbb 2025 pengurangan", label_visibility="collapsed")

    with st.expander("Filter"):
        def opsi(kolom):
            return sorted({x for x in data[kolom] if x}, reverse=(kolom == "tahun"))

        f_jenis = st.multiselect("Jenis peraturan", opsi("jenis"))
        f_pajak = st.multiselect("Jenis pajak", opsi("jenis_pajak"))
        f_status = st.multiselect("Status", opsi("status"))
        f_tahun = st.multiselect("Tahun", opsi("tahun"))

    tokens = kata.lower().split()
    hasil = []
    for d in data.to_dict("records"):
        if f_jenis and d["jenis"] not in f_jenis:
            continue
        if f_pajak and d["jenis_pajak"] not in f_pajak:
            continue
        if f_status and d["status"] not in f_status:
            continue
        if f_tahun and d["tahun"] not in f_tahun:
            continue
        if tokens and not cocok(d, tokens):
            continue
        hasil.append(d)
    hasil.sort(key=lambda d: (kunci_urut(d["tahun"]), kunci_urut(d["nomor"])), reverse=True)

    # kembali ke 20 kartu pertama bila pencarian/filter berubah
    tanda = (kata, tuple(f_jenis), tuple(f_pajak), tuple(f_status), tuple(f_tahun))
    if st.session_state.get("tanda") != tanda:
        st.session_state["tanda"] = tanda
        st.session_state["batas"] = HALAMAN
    batas = st.session_state.get("batas", HALAMAN)

    jml_merah = sum(tidak_berlaku(d["status"]) for d in hasil)
    st.caption(f"{len(hasil)} dari {len(data)} peraturan  •  🔴 tidak berlaku: {jml_merah}")

    for i, d in enumerate(hasil[:batas]):
        kartu(d, i)

    if len(hasil) > batas:
        if st.button(f"Tampilkan {min(HALAMAN, len(hasil) - batas)} lagi", use_container_width=True):
            st.session_state["batas"] = batas + HALAMAN
            st.rerun()
    elif not hasil:
        st.info("Tidak ada peraturan yang cocok.")


main()
