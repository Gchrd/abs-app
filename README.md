# ABS - Automated Backup System

Enterprise-grade network device configuration backup system dengan scheduling, role-based access control, dan audit logging.

## 🚀 Features

- **Multi-Vendor Support**: Cisco, Aruba, MikroTik, Huawei, Fortinet, Juniper, Allied Telesis
- **Automated Scheduling**: Cron-based backup scheduling
- **Role-Based Access**: Admin & Viewer roles dengan granular permissions
- **Audit Logging**: Comprehensive audit trail untuk semua actions
- **Real-time Monitoring**: Job status tracking dan execution logs
- **Configuration Management**: Preview, download, dan compare backups
- **REST API**: Full-featured API dengan JWT authentication
- **Modern UI**: Responsive Next.js frontend dengan dark mode & real-time updates

## 📦 Quick Start (Production - Docker)

### Prerequisites
- Ubuntu 22.04 LTS VM
- 2+ CPU cores, 2GB+ RAM
- Docker & Docker Compose

### Deployment

```bash
# Clone repository
git clone https://github.com/Gchrd/abs-app.git
cd abs-app

# Run automated deployment
chmod +x deploy.sh
sudo ./deploy.sh

# Access application
# Local:   http://localhost:85
# Network: http://<your-vm-ip>:85
```

**Default credentials:**
- Admin: `admin` / `admin123`
- Viewer: `viewer` / `viewer123`

📖 **Full deployment guide**: See [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 🛠️ Development Setup

### Backend (FastAPI + Python)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
# or
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Frontend (Next.js + React)

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## 🔁 CI/CD: Local Development → Production (Self-Hosted Runner)

Kalau kamu develop di laptop lokal dan mau perubahannya langsung ter-deploy ke VM production tanpa `git pull` manual di server, project ini sudah punya workflow GitHub Actions ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) yang jalan di **self-hosted runner** di VM tersebut.

### Cara kerjanya

```
[Laptop lokal]                [GitHub repo]                 [VM production]
  git push  ────────────────▶   main branch  ──trigger──▶  self-hosted runner
                                                                    │
                                                                    ▼
                                                     cd /opt/abs-app
                                                     git pull origin main
                                                     docker compose down
                                                     docker compose build --no-cache
                                                     docker compose up -d
```

Setiap push ke branch `main` pada remote GitHub yang di-watch runner, workflow otomatis:
1. Checkout kode terbaru
2. `git pull origin main` di `/opt/abs-app` pada VM
3. Rebuild image Docker (`docker compose build --no-cache`)
4. Restart semua service (`docker compose up -d`)

### Setup awal (sekali saja, di VM)

1. **Register self-hosted runner** ke repo GitHub kamu:
   - Buka repo di GitHub → **Settings → Actions → Runners → New self-hosted runner**
   - Ikuti instruksi `config.sh` / `config.cmd` yang diberikan GitHub, jalankan di VM
   - Jalankan runner sebagai service (`./svc.sh install && ./svc.sh start` di Linux) supaya tetap listening walau VM restart
2. Pastikan `/opt/abs-app` di VM adalah clone git dari repo yang sama dan remote `origin`-nya mengarah ke repo yang di-watch runner (workflow menjalankan `git pull origin main`, bukan clone ulang).
3. Pastikan user yang menjalankan runner punya izin menjalankan `docker compose` tanpa `sudo` (lihat commit "Remove sudo from docker compose commands") — biasanya dengan menambahkan user tsb ke group `docker`:
   ```bash
   sudo usermod -aG docker $(whoami)
   ```

### Alur kerja develop harian

```bash
# 1. Clone / pastikan remote fork kamu sudah terpasang
git remote -v
# origin  -> repo upstream (Josether/abs-app)
# fork    -> fork kamu sendiri (mis. Gchrd/abs-app) yang di-watch runner VM

# 2. Develop & test lokal seperti biasa (lihat bagian Development Setup di atas)
npm run dev        # frontend
uvicorn app.main:app --reload --port 8000   # backend

# 3. Commit perubahan
git add <file-yang-diubah>
git commit -m "deskripsi perubahan"

# 4. Push ke branch main pada remote yang di-watch runner
git push fork main

# 5. Cek tab "Actions" di GitHub untuk memantau workflow,
#    atau langsung buka aplikasi di VM setelah beberapa saat
```

> ⚠️ Push ke `main` langsung memicu rebuild + restart di production. Untuk perubahan yang belum siap, kerjakan di branch terpisah dan merge ke `main` baru setelah yakin.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Nginx (Port 80)                        │
│              Reverse Proxy & Load Balancer                │
└───────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
   ┌──────▼──────────┐          ┌───────▼───────────┐
   │    Frontend      │          │      Backend       │
   │  Next.js: 3000    │          │  FastAPI: 8000     │
   └───────────────────┘          └─────────┬───────────┘
                                             │
                                   ┌─────────▼───────────┐
                                   │    SQLite DB         │
                                   │    Backup Files       │
                                   └───────────────────────┘
```

### Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- SQLAlchemy ORM
- SQLite / PostgreSQL
- Netmiko (Network automation)
- APScheduler (Job scheduling)
- JWT Authentication
- Fernet (encrypted device credentials)

**Frontend:**
- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS v4
- Shadcn/ui Components
- next-themes (dark mode)
- Sonner (Toast notifications)

---

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT.md) - Complete deployment instructions
- [Vendor Templates](backend/VENDOR_TEMPLATES.md) - Supported devices & configuration
- [API Documentation](http://localhost:8000/docs) - Swagger API docs (when running)
- [Test Documentation](backend/tests/README.md) - Testing guide

---

## 🔐 Security Features

- JWT token-based authentication
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Encrypted credentials storage (Fernet symmetric encryption)
- Admin-only device password reveal, fully audit-logged
- Audit logging for all actions
- Rate limiting on API endpoints
- CORS protection

---

## 🖥️ Supported Devices

### Cisco
- IOS Router/Switch (`cisco_ios`)
- ASA Firewall (`cisco_asa`)
- NXOS Data Center (`cisco_nxos`)
- WLC Controller (`cisco_wlc_ssh`)

### Aruba
- AOS-CX Switch (`aruba_aoscx`)
- AOS AP/Controller (`aruba_os`)

### MikroTik
- RouterOS (`mikrotik_routeros`)
- SwitchOS (`mikrotik_switchos`)

### Huawei
- Switch/AP (`huawei`)
- OLT (`huawei_olt`)
- SmartAX (`huawei_smartax`)

### Others
- Allied Telesis AWPlus (`cisco_ios`-compatible CLI)
- Fortinet FortiGate (`fortinet`)
- Juniper JunOS (`juniper`)

---

## 📁 Project Structure

```
abs-app/
├── backend/                       # FastAPI backend
│   ├── app/
│   │   ├── api/                   # API endpoints
│   │   ├── routers/                # Route handlers
│   │   ├── services/               # Business logic
│   │   ├── models.py               # Database models
│   │   ├── schemas.py              # Pydantic schemas
│   │   ├── security.py             # Auth & security
│   │   └── main.py                 # FastAPI app
│   ├── tests/                     # Integration tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                      # Next.js frontend
│   ├── src/
│   │   ├── app/                   # Next.js pages (App Router)
│   │   ├── components/            # React components (incl. dashboard widgets, sidebar, theme)
│   │   ├── views/                 # Page views
│   │   └── lib/                   # Utilities
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml              # Docker orchestration
├── nginx.conf                      # Nginx configuration
├── deploy.sh                       # Deployment script
├── DEPLOYMENT.md                   # Deployment guide
└── .github/workflows/deploy.yml    # Self-hosted runner CI/CD
```

---

## 🔄 Workflow

1. **Add Devices**: Konfigurasi perangkat jaringan dengan kredensial
2. **Test Connection**: Verifikasi konektivitas sebelum backup
3. **Create Schedule**: Setup jadwal backup otomatis (tab **Schedules** di halaman **Backup Schedule**)
4. **Monitor Jobs**: Pantau eksekusi & status backup (tab **Job History** di halaman **Backup Schedule**)
5. **Manage Backups**: Download, preview, atau bandingkan konfigurasi — termasuk lewat widget quick search di Dashboard
6. **Audit Trail**: Review semua aktivitas sistem (tab **Audit Logs** di halaman **User Settings**)

---

## 🆕 Recent Updates

- **Zabbix Sync**: tombol "Sync from Zabbix" di halaman Devices - pilih host group, ABS otomatis menyaring device yang sudah ada di ABS + mengecek reachability (port 22/23), lalu satu klik untuk pre-fill form Add Device. Ada dialog bantuan (tombol "?") yang menjelaskan cara kerjanya untuk user non-teknis.
- **Test Connection sebelum Save**: kredensial device bisa dites langsung dari dialog Add Device (tidak perlu save dulu), hasilnya menampilkan cuplikan output asli dari device.
- **Partial backup**: kalau device gagal export sebagian config secara konsisten (bukan sekadar gangguan sesaat), ABS tetap menyimpan backup-nya dengan tanda "Incomplete" alih-alih membuang semuanya - device yang sebagian bermasalah tetap punya cadangan config, bukan nihil.
- **Next Run**: halaman Schedules menampilkan tanggal & jam pasti untuk jadwal backup berikutnya, bukan cuma info interval harinya.
- **Keamanan kredensial**: perbaikan pada penanganan enable-secret device (tidak lagi terhapus saat toggle enable/edit), password/secret di-redact dari job log, dan rotasi `SECRET_KEY` yang sempat ter-commit ke git.
- **Diagnostik lebih jelas**: pesan error autentikasi Telnet/SSH kini spesifik ("Authentication failed", bukan error socket mentah), termasuk untuk device dengan autentikasi password-only (tanpa username).

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License.

---

## 👤 Author

**Joseph Christian Lubis** - Original creator
- GitHub: [@Josether](https://github.com/Josether)
- Email: joseph.lubis@binus.ac.id
- University: Binus University
- Program: Computer Science

**Richard Giansanto** - Editor / maintainer (this fork)
- GitHub: [@Gchrd](https://github.com/Gchrd)

---

## 🙏 Acknowledgments

- [Netmiko](https://github.com/ktbyers/netmiko) - Network automation library
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework
- [Shadcn/ui](https://ui.shadcn.com/) - UI component library

---

*Last Updated: July 31, 2026*
