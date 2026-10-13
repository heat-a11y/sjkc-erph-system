# eRPH-PM System
Sistem automasi RPH untuk **SJKC Pin Min, Bidor** — Chrome extension, AI content generator, dan modul kehadiran wajah, semua dalam satu monorepo.

## Apa Ini?

Sistem ini menggantikan [ez-rph](https://ez-rph.gataltech.com/) untuk keperluan SJKC Pin Min:

| Komponen | Kegunaan |
|---|---|
| Chrome Extension | Isi otomatis form IDMe MOE (idme.moe.gov.my) dengan data guru & RPH |
| AI Content Generator | Hasilkan aktiviti, objektif, refleksi RPH secara AI (Bahasa Melayu) |
| Face Attendance | Kehadiran kelas dengan pengenecaman wajah (mengganti face_engine.js yang hilang) |

**Palet warna:** `#C4956A` (saiz baju SJKC)

## Struktur Projek

```
Work/
  shared/           # TypeScript interfaces (IdentityProfile, FieldMapping, etc.)
  extension/        # Chrome Extension (MV3)
    manifest.json
    src/            # core.ts, background.ts, content.ts, default-mappings.ts
    popup/          # UI popup (popup.html + popup.js)
    options/        # Halaman pengurusan profil dan field mapping
    test/           # 19 unit tests
  ai-content/       # AI RPH content generator
    src/index.ts     # Prompt builder, OpenRouter client, credit tracker
    api/             # Serverless endpoint (deploy ke Vercel)
    test/            # 31 unit tests
  face-attendance/  # Face recognition attendance
    src/face-attendance.ts
    test/            # 18 unit tests
  SPEC.md           # Spesifikasi penuh
```

## Pemasangan

### Syarat
- Node.js 20+
- npm
- Python 3.11+ (untuk kron sistem)
- Git

### Clone & Install

```bash
git clone https://github.com/heat-a11y/sjkc-erph-system.git
cd sjkc-erph-system
npm install
```

## Penggunaan

### 1. Chrome Extension — Isi Form IDMe Secara Automatik

**Apa yang dilakukan:** Extension ini mendeteksi apabila anda membuka portal IDMe MOE (`idme.moe.gov.my`), kemudian mengisi form dengan data guru (nama, no. KP, email, sekolah, dll.) dan data RPH yang telah anda simpan.

**Cara pakai:**

1. **Build extension:**
```bash
cd extension
node build.js
```

2. **Muat extension di Chrome:**
   - Buka `chrome://extensions/`
   - Aktifkan **Developer mode** (toggle kanan atas)
   - Klik **Load unpacked**
   - Pilih folder `extension/`
   - Extension akan muncul dengan ikon keris petandan (🇲🇾)

3. **Simpan profil guru:**
   - Klik ikon extension → **Options**
   - Isi nama, no. KP, email, telefon, sekolah
   - Simpan profil
   - Pilih profil sebagai "active"

4. **Isi form IDMe:**
   - Buka [idme.moe.gov.my](https://idme.moe.gov.my)
   - Login seperti biasa
   - Klik ikon extension → **Fill Form**
   - Extension otomatis mengisi field yang ada di halaman
   - Badge kuning 🇲🇾 akan muncul di bawah-halaman-kanan bila extension siap

**Field mapping default:** extension sudah termasuk selector untuk field-field biasa di IDMe: nama guru, no. KP, email, telefon, sekolah, negeri, daerah. Kalau ada field baru, edit di Options → Field Mappings.

### 2. AI Content Generator — Hasilkan RPH Secara AI

**Apa yang dilakukan:** AI generator ini menghasilkan perkongsian RPH (Ringkasan Perkongsian Hasil Belajar) penuh — aktiviti, objektif PBD, refleksi, dan cadangan remedial — berdasarkan topik DSKP KSSR yang anda pilih.

**Deploy (Vercel — 1 minit):**

```bash
cd ai-content
npm install          # esbuild, vitest, dll.
vercel --y           # deploy otomatis ke Vercel
# Atau gunakan: vercel --prod
```

**Atau jalankan secara local:**

```bash
cd ai-content
npm install
OPENROUTER_API_KEY=sk-xxxxxxxx npx tsx api/generate-content.ts
# Atau panggil dari CLI:
curl -X POST localhost:3000/api/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "BM",
    "year": 3,
    "theme": "Sayangi Keluarga",
    "unit": "Saya Sayang",
    "topic": "PKJR",
    "sk": ["1.1"],
    "sp": ["1.1.1"],
    "studentCount": 25
  }'
```

**API request format:**
```json
POST /api/generate-content
{
  "subject": "BM",          // [BM|BI|BC|Math|Science| ...]
  "year": 3,                // 1-6 ( tahun SJKC )
  "language": "bm",         // default: bm
  "theme": "Sayangi Keluarga",  // tema DSKP
  "unit": "Saya Sayang",        // unit tema
  "topic": "PKJR",              // pokok konsep
  "sk": ["1.1"],                // standard kurikulum
  "sp": ["1.1.1"],              // standard progres
  "studentCount": 25            // jumlah murid
}
```

**AI model:** `inclusionai/ling-3.0-flash-sante:free` (via OpenRouter)

**Credit system:** 20 kredit percubaan percubaan per hari (reset setiap tengah malam). Bila habis, dapat error `AI_RATE_LIMIT`.

### 3. Face Attendance — Kehadiran Wajah

**Apa yang dilakukan:** Modul ini memindai wajah murid menggunakan kamera, mencocokkkan dengan template yang telah didaftarkan, dan mencatat kehadiran. Mengganti `face_attendance/face_engine.js` yang sudah dihapus dari ez-rph.

**Cara pakai (di dalam erph-pm web app):**

```ts
import { FaceAttendance } from "../../face-attendance/src/face-attendance";

const fa = new FaceAttendance();
await fa.init();  // minta akses kamera

// Daftar template baru (sekali, untuk setiap murid)
const descriptor = await fa.enroll("murid-001", "Ahmad", "3 Blue", videoElement);
// Template disimpan di localStorage otomatis

// Absen kelas
const results = await fa.recognize(videoElement, {
  threshold: 0.6,  // confidence minimum
  timeoutMs: 10000, // batas waktu 10 saat
});
// results: [{ studentId, studentName, confidence, recognized }]
```

**Test:**
```bash
cd face-attendance
npm install
npx vitest run
```

## Penggunaan Kombinasi (Full Workflow)

1. **Generate RPH content** pakai AI generator → dapatkan aktiviti dan objektif
2. **Buka IDMe MOE** → buka profil RPH yang dihasilkan → extension otomatis isi form
3. **Ambil kehadiran** → gunakan face attendance module → export senarai kehadiran

## Testing

```bash
# Semua test (dari root)
cd extension && npx vitest run      # 19 test
cd ../ai-content && npx vitest run  # 31 test
cd ../face-attendance && npx vitest run  # 18 test
```

Total: **68 test, semua lolos.**

## Konfigurasi Cron (Opsional)

Sistem sudah ada kron pekerjaan untuk:

1. **AQI Watchdog** — harian 06:00, semak kualiti udara Ipoh/Tanjung Malim, batalkan baskerball bila AQI > 100
2. **English Homework** — Jumaat 18:00
3. **Bedtime Stories** — Sabtu 20:00
4. **Mini-Quiz** — Minggu 10:00

```bash
cd cron
python3 main.py          # jalankan semua kron
python3 tests/run_tests.py  # test kron
```

## Deploy & CI

- **GitHub repo:** `heat-a11y/sjkc-erph-system` (main branch)
- **AI content:** deploy ke Vercel (`vercel --prod`)
- **Chrome extension:** build → load di `chrome://extensions/`
- **Face attendance:** import ke erph-pm web app

## Kontak

- **WhatsApp:** wa.me/60128756026
- **GitHub:** heat-a11y/sjkc-erph-system
- **Issue?** Buka GitHub issue atau tanya di DM.
