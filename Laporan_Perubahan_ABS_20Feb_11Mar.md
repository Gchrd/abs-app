# Penjelasan Lengkap Fitur Baru & Revisi ABS
**Pembaruan: 20 Februari 2026 & Revisi 11 Maret 2026**


---

## 🟦 Grup A — Integritas

---

### ✅ 1. Active Backup Tracking

**Apa itu?**

Active Backup Tracking adalah mekanisme untuk menandai satu backup tertentu sebagai **referensi resmi** dari setiap perangkat. Sistem akan secara otomatis membandingkan backup referensi ini dengan backup terbaru yang berhasil diambil. Jika hash-nya berbeda, artinya konfigurasi perangkat telah berubah, dan status akan ditampilkan sebagai "🔄 Changed".

**Bagaimana cara kerjanya?**

Dua kolom baru ditambahkan ke tabel `devices` di database. Kolom `active_backup_id` menyimpan ID backup yang saat ini dijadikan referensi. Kolom `last_ack_backup_id` menyimpan ID backup terbaru yang sudah diakui (di-acknowledge) oleh admin, yang digunakan untuk menekan notifikasi perubahan.

```python
# backend/app/models.py — class Device
active_backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
last_ack_backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Endpoint `GET /backups/active` mengambil satu backup aktif per perangkat dan menentukan apakah konfigurasi telah berubah. Logikanya: ambil backup terbaru yang sukses, bandingkan dengan backup yang sedang menjadi referensi aktif. Jika keduanya berbeda hash, maka `status_changed` diset `True`.

```python
# backend/app/api/backups.py
@router.get("/active")
def list_active_backups(...):
    for dev in devices:
        latest  = # backup paling baru yang sukses
        active  = # backup yang ditunjuk active_backup_id
                  # jika belum di-set, pakai latest

        if active.id == latest.id:
            status_changed = False           # Tidak ada backup baru
        elif dev.last_ack_backup_id == latest.id:
            status_changed = False           # Admin sudah acknowledge ini
        else:
            status_changed = (latest.hash != active.hash)
```

Endpoint `PUT /backups/{id}/set-active` digunakan untuk menetapkan backup manapun sebagai referensi aktif. Setiap perubahan dicatat ke audit log.

```python
# backend/app/api/backups.py
@router.put("/{backup_id}/set-active")
def set_active_backup(backup_id: int, ...):
    dev.active_backup_id = backup_id
    db.commit()
    audit_event(user=..., action="backup_set_active", ...)
```

Di sisi frontend, tabel "Active Backup" menampilkan satu baris per perangkat beserta badge status. Jika status berubah, tombol "View Diff" juga muncul untuk membuka perbandingan.

---

### ✅ 2. Acknowledge

**Apa itu?**

Acknowledge adalah aksi yang memungkinkan admin untuk menyatakan **"saya sudah melihat perubahan ini"** tanpa harus mengganti referensi aktif. Ini berguna ketika admin sudah mereview backup terbaru, memutuskan untuk tetap menggunakan konfigurasi lama sebagai referensi, namun tidak ingin notifikasi "🔄 Changed" terus muncul.

**Bagaimana cara kerjanya?**

Endpoint `PUT /backups/{id}/acknowledge` hanya memperbarui kolom `last_ack_backup_id` di tabel `devices`, tanpa menyentuh `active_backup_id`.

```python
# backend/app/api/backups.py
@router.put("/{backup_id}/acknowledge")
def acknowledge_backup(backup_id: int, ...):
    dev.last_ack_backup_id = backup_id
    db.commit()
```

Setelah ini, ketika endpoint `/backups/active` kembali diperiksa, kondisi `last_ack_backup_id == latest.id` akan bernilai `True` sehingga `status_changed` dikembalikan sebagai `False` — notifikasi "Changed" hilang.

Di dalam Diff Viewer, terdapat dua pilihan eksplisit bagi admin. Tombol **"Use Previous Config"** memanggil dua endpoint sekaligus: set-active untuk mempertahankan referensi lama, dan acknowledge untuk menandai backup terbaru sebagai "sudah dilihat".

```typescript
// frontend/src/views/backups.tsx
const handleKeepPrevious = async () => {
    // 1. Pertahankan backup lama sebagai referensi aktif
    await apiPut(`/backups/${diffActiveBackup.backup_id}/set-active`, {});

    // 2. Acknowledge backup terbaru agar notifikasi "Changed" hilang
    await apiPut(`/backups/${diffActiveBackup.previous_backup_id}/acknowledge`, {});
};
```

Sedangkan tombol **"Use Latest Config"** hanya memanggil set-active untuk backup terbaru, menjadikannya referensi aktif yang baru.

```typescript
// frontend/src/views/backups.tsx
const handleAcceptLatest = async () => {
    await apiPut(`/backups/${diffActiveBackup.previous_backup_id}/set-active`, {});
};
```

---

### ✅ 3. Config Sanitization

**Apa itu?**

Config Sanitization adalah proses pembersihan konten konfigurasi dari baris-baris yang berisi **timestamp otomatis dari vendor** sebelum menghitung hash SHA-256. Tanpa proses ini, hash backup akan selalu berbeda setiap kali diambil meskipun konfigurasi perangkat tidak berubah sama sekali — kondisi ini disebut *false positive*.

**Mengapa perlu?**

Perangkat seperti Cisco IOS secara otomatis menyisipkan baris berisi waktu perubahan konfigurasi dan waktu update NVRAM. MikroTik RouterOS menyisipkan baris berisi tanggal dan versi OS di bagian atas file ekspor. Baris-baris ini berubah setiap kali backup diambil, sehingga hash-nya pun selalu berbeda meskipun isi konfigurasi yang sebenarnya identik.

**Bagaimana cara kerjanya?**

File `config_sanitizer.py` mendefinisikan pola regex untuk setiap vendor. Fungsi `sanitize_regex` memproses konten baris per baris, membuang baris yang cocok dengan salah satu pola.

```python
# backend/app/utils/config_sanitizer.py

def sanitize_regex(content: str, patterns: list[str]) -> str:
    lines = content.splitlines()
    compiled_patterns = [re.compile(p) for p in patterns]
    cleaned_lines = []
    for line in lines:
        should_ignore = any(p.search(line) for p in compiled_patterns)
        if not should_ignore:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def sanitize_cisco_ios(content: str) -> str:
    patterns = [
        r"^! Last configuration change at",
        r"^! NVRAM config last updated at",
        r"^ntp clock-period",
        r"^Current configuration :",
        r"^! Time: ",
    ]
    return sanitize_regex(content, patterns)


def sanitize_mikrotik_routeros(content: str) -> str:
    patterns = [
        r"^# \w+/\d+/\d+ .* by RouterOS",
    ]
    return sanitize_regex(content, patterns)


def sanitize_config(content: str, vendor: str = 'cisco_ios') -> str:
    if vendor == 'cisco_ios':
        return sanitize_cisco_ios(content)
    elif 'mikrotik' in vendor:
        return sanitize_mikrotik_routeros(content)
    return content
```

Fungsi ini dipanggil di dalam scheduler, tepat setelah backup berhasil diambil dan sebelum hash dihitung. File `.cfg` yang disimpan ke disk tetap mengandung konten asli (termasuk timestamp). Sanitasi hanya dilakukan untuk keperluan komputasi hash.

```python
# backend/app/services/scheduler.py
content_str = content.decode('utf-8', errors='ignore')
clean_content_str = sanitize_config(content_str, vendor=device_info['vendor'])
clean_hash = sha256(clean_content_str.encode('utf-8')).hexdigest()[:8]

b = Backup(hash=clean_hash, path=str(path), ...)
```

---

### ✅ 4. Diff Viewer

**Apa itu?**

Diff Viewer adalah tampilan perbandingan dua file konfigurasi secara berdampingan (*side-by-side*). Baris yang hilang di versi lama diberi latar merah, dan baris yang baru muncul di versi terbaru diberi latar hijau. Fitur ini memungkinkan admin melihat dengan jelas perubahan apa yang terjadi pada konfigurasi perangkat.

**Bagaimana cara kerjanya?**

Di backend, endpoint `GET /backups/diff` menerima dua ID backup sebagai parameter, membaca kedua file `.cfg` dari disk, lalu mengembalikan isi teksnya sebagai JSON.

```python
# backend/app/api/backups.py
@router.get("/diff")
def get_diff(current: int, previous: int, ...):
    def read_file(path: str) -> str:
        p = Path(path)
        if not p.exists():
            return "(File not found on disk)"
        return p.read_text(encoding="utf-8", errors="replace")

    return {
        "current":  read_file(b_current.path),
        "previous": read_file(b_previous.path),
    }
```

Di frontend, komponen `DiffViewer` membandingkan kedua teks baris per baris. Setiap baris diklasifikasikan ke tiga tipe: `same`, `added`, atau `removed`. Tipe inilah yang menentukan warna latar yang ditampilkan.

```typescript
// frontend/src/views/backups.tsx — komponen DiffViewer
for (let i = 0; i < maxLen; i++) {
    const leftText  = previousLines[i] ?? '';
    const rightText = currentLines[i]  ?? '';

    if (leftText === rightText) {
        leftLines.push({ type: 'same',    text: leftText  });
        rightLines.push({ type: 'same',   text: rightText });
    } else {
        leftLines.push({ type: 'removed', text: leftText  });
        rightLines.push({ type: 'added',  text: rightText });
    }
}
```

Warna untuk setiap tipe ditentukan oleh fungsi pembantu berikut.

```typescript
// frontend/src/views/backups.tsx
const bgColor = (type) => {
    if (type === 'added')   return 'bg-green-950 text-green-300';
    if (type === 'removed') return 'bg-red-950 text-red-300';
    return 'text-gray-300';
};
```

Hasil render adalah dua kolom sejajar. Panel kiri bertuliskan "← Previous" (versi referensi), panel kanan bertuliskan "Current →" (versi terbaru). Nomor baris ditampilkan di tepi kiri setiap panel.

---

## 🟦 Grup B — Keandalan

---

### ✅ 5. Retry Otomatis

**Apa itu?**

Retry Otomatis adalah mekanisme yang membuat sistem secara otomatis mencoba ulang proses backup ketika terjadi kegagalan koneksi. Sistem akan mencoba hingga 4 kali dengan jeda waktu yang semakin panjang di setiap percobaan berikutnya, sebelum akhirnya menyerah dan mencatat kegagalan.

**Bagaimana cara kerjanya?**

Di dalam scheduler, setiap perangkat diproses menggunakan loop retry. Konstanta `max_attempts` menentukan batas maksimal percobaan, dan `retry_delays` mendefinisikan durasi jeda (dalam detik) sebelum percobaan ke-2, ke-3, dan ke-4.

```python
# backend/app/services/scheduler.py
max_attempts = 4
retry_delays = [15, 30, 60]
```

Loop utama menjalankan percobaan satu per satu. Jika berhasil, langsung keluar dari loop dengan `break`. Jika gagal dan masih ada percobaan tersisa, sistem menunggu sesuai jeda yang telah ditentukan sebelum mencoba lagi. Jika ini sudah percobaan terakhir, kegagalan dicatat dan loop berakhir.

```python
# backend/app/services/scheduler.py
for attempt in range(max_attempts):
    try:
        path, content = fetch_running_config(...)
        # ... simpan backup ke database ...
        break  # Berhasil, hentikan retry

    except Exception as e:
        if attempt < max_attempts - 1:
            delay = retry_delays[attempt]
            await asyncio.sleep(delay)
        else:
            log_lines.append(f"[{hostname}] Backup failed> ({str(e)})")
```

Pola jeda yang dihasilkan adalah sebagai berikut.

| Percobaan | Jeda Sebelum Percobaan Ini |
|---|---|
| 1 (pertama) | — (langsung) |
| 2 | 15 detik |
| 3 | 30 detik |
| 4 | 60 detik |

Setiap percobaan dan hasilnya dicatat di log job, sehingga admin bisa menelusuri riwayat retry di halaman Jobs.

---

### ✅ 6. Accordion UI

**Apa itu?**

Accordion UI adalah tampilan riwayat backup yang dikelompokkan berdasarkan tanggal. Setiap kelompok tanggal ditampilkan sebagai satu baris header yang bisa diklik untuk membuka atau menutup daftar backup di dalamnya. Ini menggantikan tampilan tabel panjang yang sebelumnya memuat semua backup sekaligus tanpa pengelompokan.

**Bagaimana cara kerjanya?**

Di frontend, backup pertama-tama dikelompokkan berdasarkan tanggal lokal menggunakan fungsi `reduce`. Kelompok kemudian diurutkan dari tanggal terbaru ke terlama.

```typescript
// frontend/src/views/backups.tsx
const groupedBackups = filteredBackups.reduce((groups, backup) => {
    const d = new Date(backup.timestamp);
    const dateKey = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(backup);
    return groups;
}, {});

const sortedDates = Object.keys(groupedBackups).sort((a, b) => b.localeCompare(a));
```

State `expandedDates` menyimpan informasi tanggal mana saja yang sedang terbuka. Fungsi `toggleDate` membalik status buka/tutup setiap kali header diklik.

```typescript
// frontend/src/views/backups.tsx
const [expandedDates, setExpandedDates] = useState<Record<string, boolean>>({});

const toggleDate = (date: string) => {
    setExpandedDates(prev => ({ ...prev, [date]: !prev[date] }));
};
```

Setiap header accordion juga menampilkan badge "⭐ Active Backup Present" jika ada backup aktif di tanggal tersebut, dan dua tombol aksi batch: Download Folder dan Delete Folder.

---

### ✅ 7. Batch Download ZIP

**Apa itu?**

Batch Download ZIP memungkinkan admin mengunduh seluruh backup dalam satu tanggal sekaligus sebagai satu file `.zip`. Admin tidak perlu mengunduh setiap file satu per satu.

**Bagaimana cara kerjanya?**

Di backend, endpoint `GET /backups/download-date/{date_str}` mengambil semua record backup yang timestampnya jatuh pada tanggal yang diminta. Semua file dikemas ke dalam satu arsip ZIP yang dibangun di memori, kemudian di-stream langsung ke browser.

```python
# backend/app/api/backups.py
@router.get("/download-date/{date_str}")
def download_backup_date(date_str: str, ...):
    backups = db.query(Backup).filter(
        func.date(Backup.timestamp) == target_date.isoformat()
    ).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for b in backups:
            timestamp_str = b.timestamp.strftime('%H%M%S')
            filename = f"{dev.hostname}_{timestamp_str}_{p.name}"
            zip_file.write(p, arcname=filename)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=backups_{date_str}.zip"}
    )
```

Di frontend, tombol "📁 Download Folder" di header accordion memanggil fungsi `handleDownloadDate`. Fungsi ini menerima response blob dari API dan memicunya sebagai unduhan browser.

```typescript
// frontend/src/views/backups.tsx
const handleDownloadDate = async (date: string) => {
    const blob = await downloadBackupDate(date);
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `backups_${date}.zip`;
    a.click();
    URL.revokeObjectURL(url);
};
```

ZIP dibangun sepenuhnya di dalam memori server menggunakan `io.BytesIO`, tanpa membuat file sementara di disk.

---

### ✅ 8. Batch Delete

**Apa itu?**

Batch Delete memungkinkan admin menghapus seluruh backup dalam satu tanggal sekaligus — baik record di database maupun file `.cfg` fisik di server. Fitur ini dilindungi oleh beberapa lapisan keamanan untuk mencegah penghapusan yang tidak disengaja atau berbahaya.

**Bagaimana cara kerjanya?**

Di backend, endpoint `DELETE /backups/date/{date_str}` terlebih dahulu memvalidasi apakah ada backup dalam tanggal tersebut yang sedang dikunci sebagai referensi aktif atau sudah di-acknowledge. Jika ada, request ditolak dengan HTTP 403.

```python
# backend/app/api/backups.py
@router.delete("/date/{date_str}")
def delete_backup_date(date_str: str, ...):
    # Validasi: tolak jika ada backup yang sedang aktif atau di-acknowledge
    for b in backups:
        dev = db.get(Device, b.device_id)
        if dev.active_backup_id == b.id or dev.last_ack_backup_id == b.id:
            raise HTTPException(403, f"Cannot delete: backup #{b.id} is locked for {dev.hostname}")

    # Hapus file fisik dari disk, lalu hapus record dari database
    for b in backups:
        Path(b.path).unlink(missing_ok=True)
        db.delete(b)
    db.commit()
```

Di frontend, terdapat dua lapisan perlindungan sebelum request dikirim ke server. Pertama, tombol "Delete Folder" hanya dimunculkan apabila tidak ada backup aktif di tanggal tersebut. Kedua, setelah tombol diklik, dialog konfirmasi muncul dan admin diwajibkan mengetik teks **"I am sure"** secara manual. Tombol konfirmasi hanya bisa diklik setelah teks tersebut diketik dengan tepat.

```typescript
// frontend/src/views/backups.tsx

// Lapisan 1: Tombol hanya muncul jika tidak ada backup aktif
{!hasActiveBackup && isAdmin && (
    <Button onClick={() => setDeletingDate(dateKey)}>
        Delete Folder
    </Button>
)}

// Lapisan 2: Tombol konfirmasi hanya aktif setelah teks diketik tepat
<Button
    variant="destructive"
    disabled={deleteConfirmText !== "I am sure"}
    onClick={handleDeleteDate}
>
    Yes, Delete Permanently
</Button>
```

Ringkasan seluruh lapisan perlindungan yang bekerja secara berurutan.

| Lapisan | Mekanisme | Lokasi |
|---|---|---|
| 1 — UI Guard | Tombol tidak muncul jika ada backup aktif | `backups.tsx` |
| 2 — Input Konfirmasi | Wajib ketik "I am sure" | `backups.tsx` |
| 3 — Backend Lock | HTTP 403 jika backup sedang aktif/ack | `api/backups.py` |
| 4 — Audit Log | Setiap penghapusan dicatat | `api/backups.py` |
