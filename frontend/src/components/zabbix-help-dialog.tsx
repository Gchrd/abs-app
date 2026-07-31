"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RadioTower, Search, ShieldCheck, PlusCircle } from "lucide-react";

export function ZabbixHelpDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RadioTower className="w-4 h-4" /> Apa itu &quot;Sync from Zabbix&quot;?
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 py-2 text-sm">
          <div>
            <p className="font-medium mb-1">Fitur ini buat apa?</p>
            <p className="text-muted-foreground">
              Zabbix (sistem monitoring jaringan yang sudah dipakai perusahaan) sudah tahu daftar semua switch/router yang ada
              di jaringan. Tapi ABS tidak otomatis ikut tahu - kalau ada switch baru yang dipasang dan dimasukkan ke Zabbix,
              admin harus mencatat IP dan hostname-nya secara manual lalu mengetiknya lagi satu-satu di ABS. Itu kerja dua kali
              untuk hal yang sama.
            </p>
            <p className="text-muted-foreground mt-2">
              &quot;Sync from Zabbix&quot; menghilangkan kerja dua kali itu: ABS langsung bertanya ke Zabbix &quot;device apa saja yang
              kamu tau tapi belum ada di saya?&quot;, lalu menampilkannya supaya admin tinggal klik untuk menambahkan.
            </p>
          </div>

          <div>
            <p className="font-medium mb-2">Cara kerjanya (4 langkah)</p>
            <div className="space-y-3">
              <div className="flex gap-3">
                <div className="shrink-0 w-7 h-7 rounded-full bg-muted flex items-center justify-center font-medium">1</div>
                <div>
                  <p className="font-medium">Admin pilih grup host di Zabbix</p>
                  <p className="text-muted-foreground">Misalnya &quot;Switch Factory&quot; atau &quot;Switch HQ&quot;. Daftar grup ini diambil langsung dari Zabbix secara real-time, bukan daftar tetap yang ditulis di kode ABS - kalau nanti ada grup baru di Zabbix, otomatis ikut muncul di sini juga.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="shrink-0 w-7 h-7 rounded-full bg-muted flex items-center justify-center">
                  <Search className="w-3.5 h-3.5" />
                </div>
                <div>
                  <p className="font-medium">ABS membandingkan &amp; menyaring otomatis</p>
                  <p className="text-muted-foreground">
                    Dari semua device di grup yang dipilih: (a) yang IP-nya <b>sudah tercatat</b> di ABS langsung disembunyikan
                    (tidak perlu ditambah lagi), dan (b) dari sisanya, ABS coba &quot;mengetuk pintu&quot; tiap device di port SSH (22)
                    dan Telnet (23) untuk memastikan device-nya benar-benar hidup dan bisa dihubungi. Device yang mati atau
                    tidak bisa diakses tidak akan ditampilkan - jadi daftar yang muncul dijamin berisi device baru yang siap ditambahkan.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="shrink-0 w-7 h-7 rounded-full bg-muted flex items-center justify-center">
                  <PlusCircle className="w-3.5 h-3.5" />
                </div>
                <div>
                  <p className="font-medium">Admin klik &quot;Add&quot; pada device yang mau ditambahkan</p>
                  <p className="text-muted-foreground">
                    Form Tambah Device langsung terbuka dengan hostname dan IP yang sudah terisi otomatis, jadi tidak perlu ketik ulang.
                    <b> Username dan password tetap harus diisi manual oleh admin</b> - Zabbix cuma tahu device-nya ada dan alamatnya,
                    bukan kredensial login untuk masuk ke device tersebut.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="shrink-0 w-7 h-7 rounded-full bg-muted flex items-center justify-center">
                  <ShieldCheck className="w-3.5 h-3.5" />
                </div>
                <div>
                  <p className="font-medium">Admin tes koneksi sebelum menyimpan</p>
                  <p className="text-muted-foreground">
                    Setelah kredensial diisi, tombol &quot;Test Connection&quot; bisa dipakai untuk memastikan username/password itu benar
                    dan ABS berhasil login ke device-nya (akan muncul cuplikan hasil asli dari device) - semua ini dicek
                    <b> sebelum</b> device benar-benar disimpan ke ABS, supaya tidak ada device dengan kredensial salah yang tersimpan.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Mengerti
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
