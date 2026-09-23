#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC Check - diagnostica gratuita e open source per Windows, macOS e Linux.

Controlla: sistema, CPU, RAM, scheda grafica, dischi e spazio, velocita'
(CPU / RAM / disco), batteria, temperature, rete, programmi in esecuzione,
programmi all'avvio e sicurezza di base. Alla fine crea un report HTML.

Tutto gira in locale: nessun dato viene inviato a nessuno.
Uso:  python3 pc_check.py [--fast] [--no-scan] [--no-browser] [--json FILE] [--out FILE]
"""
import argparse
import datetime as dt
import getpass
import glob
import hashlib
import html
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = "1.0.0"
SYSTEM = platform.system()
IS_WIN, IS_MAC, IS_LINUX = SYSTEM == "Windows", SYSTEM == "Darwin", SYSTEM == "Linux"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ------------------------------------------------------------------ psutil
def ensure_psutil():
    try:
        import psutil  # noqa
        return psutil
    except ImportError:
        pass
    print("Installo la libreria 'psutil' (una volta sola)...")
    for extra in ([], ["--user"]):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                                   "--disable-pip-version-check", "psutil"] + extra)
            import importlib
            import site
            importlib.invalidate_caches()
            try:
                sys.path.append(site.getusersitepackages())
            except Exception:
                pass
            import psutil  # noqa
            return psutil
        except Exception:
            continue
    print("Impossibile installare psutil. Esegui a mano:  python3 -m pip install psutil")
    sys.exit(1)


psutil = ensure_psutil()

# ------------------------------------------------------------------ utilità
USE_COLOR = sys.stdout.isatty()
if IS_WIN:
    os.system("")  # abilita i colori ANSI nella console di Windows


def col(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def run(cmd, timeout=40, encoding=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding=encoding, errors="replace",
                           creationflags=0x08000000 if IS_WIN else 0)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def ps(command, timeout=60):
    full = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command
    return run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", full], timeout, "utf-8")


def ps_json(command):
    out = ps(command + " | ConvertTo-Json -Depth 3 -Compress")
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return ""


def hb(n):
    """Byte in formato leggibile."""
    if n is None:
        return "n/d"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_td(td):
    s = int(td.total_seconds())
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    return (f"{d} g " if d else "") + f"{h} h {m} min"


def rx(pattern, text, flags=re.M):
    m = re.search(pattern, text or "", flags)
    return m.group(1).strip() if m else ""


def is_admin():
    try:
        if IS_WIN:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


_cache = {}


def mac_hw():
    if "hw" not in _cache:
        _cache["hw"] = run(["system_profiler", "SPHardwareDataType"])
    return _cache["hw"]


# ------------------------------------------------------------------ problemi
ISSUES = []
LEVELS = {"crit": "Critico", "warn": "Attenzione", "info": "Consiglio"}


def issue(level, area, msg, advice=""):
    ISSUES.append({"level": level, "area": area, "msg": msg, "advice": advice})


def section(sid, title, wide=False):
    return {"id": sid, "title": title, "wide": wide, "kv": [], "bars": [], "tables": [], "notes": []}


# ------------------------------------------------------------------ SISTEMA
def collect_system(args):
    s = section("sistema", "Sistema")
    model = os_name = ""
    if IS_WIN:
        build = sys.getwindowsversion().build
        cap = ps("(Get-CimInstance Win32_OperatingSystem).Caption")
        os_name = f"{cap or ('Windows 11' if build >= 22000 else 'Windows ' + platform.release())} (build {build})"
        cs = ps_json("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model")
        if cs:
            model = f"{cs[0].get('Manufacturer') or ''} {cs[0].get('Model') or ''}".strip()
    elif IS_MAC:
        os_name = f"macOS {platform.mac_ver()[0]}"
        hw = mac_hw()
        model = " ".join(x for x in (rx(r"Model Name:\s*(.+)", hw), rx(r"Model Identifier:\s*(.+)", hw)) if x)
    else:
        os_name = rx(r'^PRETTY_NAME="?([^"\n]+)', read("/etc/os-release")) or "Linux"
        model = f"{read('/sys/class/dmi/id/sys_vendor')} {read('/sys/class/dmi/id/product_name')}".strip()

    boot = dt.datetime.fromtimestamp(psutil.boot_time())
    up = dt.datetime.now() - boot
    try:
        user = getpass.getuser()
    except Exception:
        user = "n/d"
    s["kv"] += [
        ("Computer", socket.gethostname()),
        ("Modello", model or "n/d"),
        ("Sistema operativo", os_name),
        ("Versione kernel", platform.version() if IS_WIN else platform.release()),
        ("Architettura", platform.machine()),
        ("Utente", user + (" (amministratore)" if is_admin() else "")),
        ("Acceso da", f"{fmt_td(up)} (dal {boot:%d/%m/%Y %H:%M})"),
    ]
    if up.days >= 14:
        extra = " Su Windows usa 'Riavvia': lo spegnimento con 'Avvio rapido' non azzera il sistema." if IS_WIN else ""
        issue("info", "Sistema", f"Il computer non viene riavviato da {up.days} giorni.",
              "Un riavvio libera memoria e completa gli aggiornamenti." + extra)
    return s


# ------------------------------------------------------------------ CPU
def bench_cpu(seconds=2.0):
    data = os.urandom(1 << 20)  # 1 MB

    def worker(_):
        n, end = 0, time.perf_counter() + seconds
        while time.perf_counter() < end:
            hashlib.sha256(data).digest()
            n += 1
        return n

    single = worker(0) / seconds
    threads = psutil.cpu_count() or 1
    with ThreadPoolExecutor(threads) as ex:  # hashlib rilascia il GIL: usa tutti i core
        multi = sum(ex.map(worker, range(threads))) / seconds
    return single, multi


def collect_cpu(args):
    s = section("cpu", "Processore (CPU)")
    if IS_WIN:
        name = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name")
    elif IS_MAC:
        name = run(["sysctl", "-n", "machdep.cpu.brand_string"])
    else:
        name = rx(r"^model name\s*:\s*(.+)$", read("/proc/cpuinfo")) or rx(r"^Model name:\s*(.+)$", run(["lscpu"]))
    name = (name or platform.processor() or "n/d").strip()

    per = psutil.cpu_percent(interval=1, percpu=True)
    usage = sum(per) / len(per) if per else 0.0
    s["kv"] += [("Modello", name),
                ("Core fisici / thread", f"{psutil.cpu_count(logical=False) or '?'} / {psutil.cpu_count() or '?'}")]
    try:
        f = psutil.cpu_freq()
        if f and f.current:
            s["kv"].append(("Frequenza", f"{f.current:.0f} MHz" + (f" (max {f.max:.0f} MHz)" if f.max else "")))
    except Exception:
        pass
    if not IS_WIN:
        try:
            s["kv"].append(("Carico medio 1/5/15 min", " / ".join(f"{x:.2f}" for x in psutil.getloadavg())))
        except Exception:
            pass
    s["kv"].append(("Uso per core", "  ".join(f"{p:.0f}%" for p in per)))
    s["bars"].append(("Utilizzo CPU (misurato ora)", usage, f"{usage:.0f}%"))
    if usage > 80:
        issue("warn", "CPU", f"La CPU è occupata al {usage:.0f}% durante il controllo.",
              "Guarda la tabella 'Programmi che consumano più CPU' e chiudi quello che non serve.")
    if args.bench:
        print("    test velocità CPU (4 s)...")
        single, multi = bench_cpu()
        s["kv"] += [("Velocità single-core", f"{single:.0f} MB/s (calcolo SHA-256)"),
                    ("Velocità multi-core", f"{multi:.0f} MB/s (calcolo SHA-256)"),
                    ("Guadagno multi-core", f"{multi / single:.1f}×" if single else "n/d")]
        s["notes"].append("I test di velocità sono indicativi: servono a confrontare lo stesso computer nel tempo "
                          "(es. prima e dopo una pulizia) o computer simili.")
    return s


# ------------------------------------------------------------------ RAM
SMBIOS_MEM = {18: "DDR", 19: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2",
              29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}


def ram_modules():
    mods = []
    if IS_WIN:
        for m in ps_json("Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,BankLabel,Capacity,"
                         "Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,SMBIOSMemoryType"):
            speed = m.get("ConfiguredClockSpeed") or m.get("Speed")
            mods.append({"Slot": m.get("DeviceLocator") or m.get("BankLabel") or "",
                         "Capacità": hb(m.get("Capacity")),
                         "Tipo": SMBIOS_MEM.get(m.get("SMBIOSMemoryType"), ""),
                         "Velocità": f"{speed} MT/s" if speed else "",
                         "Produttore": (m.get("Manufacturer") or "").strip(),
                         "Codice": (m.get("PartNumber") or "").strip()})
    elif IS_MAC:
        try:
            data = json.loads(run(["system_profiler", "SPMemoryDataType", "-json"])).get("SPMemoryDataType", [])
        except Exception:
            data = []
        for d in data:
            if "_items" in d:  # Mac Intel con slot
                for it in d["_items"]:
                    if it.get("dimm_size", "").lower().startswith("empty"):
                        continue
                    mods.append({"Slot": it.get("_name", ""), "Capacità": it.get("dimm_size", ""),
                                 "Tipo": it.get("dimm_type", ""), "Velocità": it.get("dimm_speed", ""),
                                 "Produttore": it.get("dimm_manufacturer", ""), "Codice": it.get("dimm_part_number", "")})
            else:  # Apple Silicon: memoria unificata
                mods.append({"Slot": "Memoria unificata (saldata)", "Capacità": d.get("SPMemoryDataType", ""),
                             "Tipo": d.get("dimm_type", ""), "Velocità": "",
                             "Produttore": d.get("dimm_manufacturer", ""), "Codice": ""})
    elif is_admin() and shutil.which("dmidecode"):
        for block in run(["dmidecode", "-t", "17"]).split("\n\n"):
            size = rx(r"^\s*Size:\s*(.+)$", block)
            if "Memory Device" not in block or not size or "No Module" in size:
                continue
            mods.append({"Slot": rx(r"^\s*Locator:\s*(.+)$", block), "Capacità": size,
                         "Tipo": rx(r"^\s*Type:\s*(.+)$", block),
                         "Velocità": rx(r"^\s*Configured Memory Speed:\s*(.+)$", block) or rx(r"^\s*Speed:\s*(.+)$", block),
                         "Produttore": rx(r"^\s*Manufacturer:\s*(.+)$", block),
                         "Codice": rx(r"^\s*Part Number:\s*(.+)$", block)})
    return mods


def bench_ram(seconds=1.5):
    size = 64 << 20
    if psutil.virtual_memory().available < 6 * size:
        size = 16 << 20
    src, dst = bytearray(os.urandom(1 << 20)) * (size >> 20), bytearray(size)
    n, start = 0, time.perf_counter()
    while time.perf_counter() - start < seconds:
        dst[:] = src
        n += 1
    return size * n / (time.perf_counter() - start)


def collect_ram(args):
    s = section("ram", "Memoria (RAM)")
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    used = vm.total - vm.available
    pct = used / vm.total * 100
    s["kv"] += [("RAM totale", hb(vm.total)), ("In uso", hb(used)), ("Disponibile", hb(vm.available))]
    s["bars"].append(("RAM in uso", pct, f"{hb(used)} di {hb(vm.total)}"))
    if sw.total:
        s["bars"].append(("Memoria virtuale (swap / file di paging)", sw.percent, f"{hb(sw.used)} di {hb(sw.total)}"))
    mods = ram_modules()
    if mods:
        s["tables"].append(("Moduli installati", list(mods[0].keys()), [list(m.values()) for m in mods]))
    elif IS_LINUX:
        s["notes"].append("Per vedere i singoli moduli RAM su Linux esegui il programma con sudo.")
    if args.bench:
        print("    test velocità RAM...")
        s["kv"].append(("Velocità copia in memoria", f"{bench_ram() / 1024 ** 3:.1f} GB/s (indicativo)"))

    if pct >= 90:
        issue("crit", "RAM", f"La RAM è quasi piena ({pct:.0f}%): il computer rallenta molto.",
              "Chiudi schede del browser e programmi pesanti; se succede sempre valuta più RAM.")
    elif pct >= 80:
        issue("warn", "RAM", f"La RAM è molto occupata ({pct:.0f}%).",
              "Controlla i programmi che usano più memoria nella tabella dei programmi.")
    if vm.total < 7.5 * 1024 ** 3:
        issue("info", "RAM", f"RAM totale ridotta ({hb(vm.total)}).",
              "Per un uso moderno (browser + ufficio) sono consigliati almeno 8 GB, meglio 16 GB.")
    if sw.total and sw.percent > 60 and pct > 70:
        issue("warn", "RAM", f"Il sistema usa molta memoria virtuale su disco ({sw.percent:.0f}%).",
              "Segno che la RAM non basta: il disco lavora al posto della RAM ed è molto più lento.")
    return s


# ------------------------------------------------------------------ GPU
def collect_gpu(args):
    s = section("gpu", "Scheda grafica (GPU)")
    rows = []
    if IS_WIN:
        real_vram = {}
        for r in ps_json(r"Get-ItemProperty 'HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' "
                         r"-ErrorAction SilentlyContinue | Select-Object DriverDesc,'HardwareInformation.qwMemorySize'"):
            v = r.get("HardwareInformation.qwMemorySize")
            if r.get("DriverDesc") and isinstance(v, (int, float)) and v > 0:
                real_vram[r["DriverDesc"]] = v
        for g in ps_json("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,"
                         "CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,Status"):
            name = g.get("Name") or "n/d"
            vram = real_vram.get(name) or g.get("AdapterRAM")
            res = (f"{g.get('CurrentHorizontalResolution')}×{g.get('CurrentVerticalResolution')} "
                   f"@ {g.get('CurrentRefreshRate')} Hz") if g.get("CurrentHorizontalResolution") else ""
            rows.append([name, hb(vram) if vram else "condivisa", g.get("DriverVersion") or "", res, g.get("Status") or ""])
            if "basic display" in name.lower() or "vga standard" in name.lower():
                issue("warn", "GPU", "Manca il driver della scheda grafica (in uso il driver base di Microsoft).",
                      "Installa il driver dal sito del produttore del PC o di Intel / AMD / NVIDIA.")
            elif g.get("Status") and g.get("Status") != "OK":
                issue("warn", "GPU", f"La scheda grafica '{name}' riporta lo stato '{g.get('Status')}'.",
                      "Aggiorna o reinstalla il driver grafico.")
        headers = ["Nome", "Memoria video", "Driver", "Risoluzione", "Stato"]
    elif IS_MAC:
        try:
            data = json.loads(run(["system_profiler", "SPDisplaysDataType", "-json"])).get("SPDisplaysDataType", [])
        except Exception:
            data = []
        for g in data:
            screens = ", ".join(f"{d.get('_name', '')} {d.get('_spdisplays_resolution', '')}".strip()
                                for d in g.get("spdisplays_ndrvs", []))
            rows.append([g.get("sppci_model") or g.get("_name", "n/d"),
                         g.get("spdisplays_vram") or g.get("spdisplays_vram_shared") or "unificata (condivisa con la RAM)",
                         str(g.get("sppci_cores", "")), g.get("spdisplays_mtlgpufamilysupport", "").replace("spdisplays_", ""),
                         screens])
        headers = ["Nome", "Memoria video", "Core GPU", "Metal", "Schermi"]
    else:
        for line in run(["lspci"]).splitlines():
            if re.search(r"VGA|3D controller|Display controller", line):
                rows.append([line.split(": ", 1)[-1], "", ""])
        headers = ["Nome", "Memoria video", "Driver"]
        for r in rows:
            low = r[0].lower()
            drv = "nvidia" if "nvidia" in low else "amdgpu" if ("amd" in low or "ati" in low) else "i915" if "intel" in low else ""
            if drv and os.path.isdir(f"/sys/module/{drv}"):
                r[2] = drv
    if rows:
        s["tables"].append(("Schede video trovate", headers, rows))

    if shutil.which("nvidia-smi"):
        out = run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu,driver_version",
                   "--format=csv,noheader,nounits"])
        for line in out.splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) < 6:
                continue
            s["kv"] += [(f"{p[0]} - memoria", f"{p[2]} / {p[1]} MB"), (f"{p[0]} - temperatura", f"{p[3]} °C"),
                        (f"{p[0]} - utilizzo", f"{p[4]}%"), (f"{p[0]} - driver NVIDIA", p[5])]
            try:
                if float(p[3]) >= 85:
                    issue("warn", "GPU", f"La GPU NVIDIA è calda ({p[3]} °C).",
                          "Pulisci le prese d'aria e usa il portatile su una superficie rigida.")
            except ValueError:
                pass
    if not rows and not s["kv"]:
        s["notes"].append("Nessuna scheda grafica rilevata con gli strumenti disponibili.")
    return s


# ------------------------------------------------------------------ DISCHI
SKIP_FS = {"squashfs", "tmpfs", "devtmpfs", "overlay", "autofs", "devfs", "nullfs", "ramfs"}
MAC_SKIP = ("/System/Volumes/VM", "/System/Volumes/Preboot", "/System/Volumes/Update", "/System/Volumes/xarts",
            "/System/Volumes/iSCPreboot", "/System/Volumes/Hardware", "/private/var/vm", "/Library/Developer")
WIN_MEDIA = {0: "", 3: "HDD", 4: "SSD", 5: "SCM"}
WIN_BUS = {1: "SCSI", 3: "ATA", 7: "USB", 8: "RAID", 10: "SAS", 11: "SATA", 12: "SD", 17: "NVMe"}
WIN_HEALTH = {0: "Buona", 1: "Attenzione", 2: "Guasto", 5: "Sconosciuto"}


def physical_disks():
    rows = []
    if IS_WIN:
        for d in ps_json("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,HealthStatus,Size"):
            media, bus, health = d.get("MediaType"), d.get("BusType"), d.get("HealthStatus")
            media = WIN_MEDIA.get(media, media) if isinstance(media, int) else media
            bus = WIN_BUS.get(bus, bus) if isinstance(bus, int) else bus
            health = WIN_HEALTH.get(health, health) if isinstance(health, int) else {"Healthy": "Buona"}.get(health, health)
            rows.append([d.get("FriendlyName", ""), f"{media or ''} {bus or ''}".strip(), hb(d.get("Size")), str(health)])
    elif IS_MAC:
        for dev in re.findall(r"^(/dev/disk\d+) \((?:internal|external), physical\)", run(["diskutil", "list"]), re.M):
            info = run(["diskutil", "info", dev])
            kind = "SSD" if rx(r"Solid State:\s*(.+)", info) == "Yes" else "HDD"
            rows.append([rx(r"Device / Media Name:\s*(.+)", info), f"{kind} {rx(r'Protocol:\s*(.+)', info)}",
                         rx(r"Disk Size:\s*([\d.,]+ \w+)", info), rx(r"SMART Status:\s*(.+)", info) or "n/d"])
    else:
        try:
            devs = json.loads(run(["lsblk", "-d", "-J", "-b", "-o", "NAME,MODEL,SIZE,ROTA,TYPE,TRAN"])).get("blockdevices", [])
        except Exception:
            devs = []
        for d in devs:
            if d.get("type") != "disk" or str(d.get("name", "")).startswith(("loop", "zram", "ram")):
                continue
            health = "n/d (serve sudo + smartctl)"
            if is_admin() and shutil.which("smartctl"):
                out = run(["smartctl", "-H", f"/dev/{d['name']}"])
                health = rx(r"(?:overall-health.*?|SMART Health Status):\s*(.+)", out) or "n/d"
            rota = d.get("rota") in (True, "1", 1)
            rows.append([(d.get("model") or d.get("name") or "").strip(),
                         f"{'HDD' if rota else 'SSD'} {d.get('tran') or ''}".strip(), hb(d.get("size")), health])
    for r in rows:
        h = str(r[3]).lower()
        if h and not any(ok in h for ok in ("buona", "verified", "passed", "ok", "n/d", "sconosciuto", "not supported")):
            issue("crit", "Disco", f"Il disco '{r[0]}' riporta uno stato di salute: {r[3]}.",
                  "Fai SUBITO un backup dei tuoi file: il disco potrebbe guastarsi.")
        if "hdd" in str(r[1]).lower():
            issue("info", "Disco", f"Il disco '{r[0]}' è meccanico (HDD).",
                  "Sostituirlo con un SSD è l'aggiornamento che velocizza di più un computer datato.")
    return rows


def bench_disk(folder, size_mb=256):
    if shutil.disk_usage(folder).free < size_mb * 4 * 1024 ** 2:
        return None, None
    fn = os.path.join(folder, f"pccheck_{os.getpid()}.tmp")
    block = os.urandom(4 << 20)

    def nocache(fd):
        try:
            if IS_MAC:
                import fcntl
                fcntl.fcntl(fd, 48, 1)  # F_NOCACHE
        except Exception:
            pass

    try:
        fd = os.open(fn, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0))
        nocache(fd)
        t = time.perf_counter()
        for _ in range(size_mb // 4):
            os.write(fd, block)
        os.fsync(fd)
        w = size_mb / (time.perf_counter() - t)
        if IS_LINUX:
            try:
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            except Exception:
                pass
        os.close(fd)
        fd = os.open(fn, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        nocache(fd)
        t = time.perf_counter()
        while os.read(fd, 4 << 20):
            pass
        r = size_mb / (time.perf_counter() - t)
        os.close(fd)
        return w, r
    except Exception:
        return None, None
    finally:
        try:
            os.remove(fn)
        except Exception:
            pass


def collect_disks(args):
    s = section("dischi", "Dischi e spazio")
    system_mount = (os.environ.get("SystemDrive", "C:") + "\\") if IS_WIN else ("/System/Volumes/Data" if IS_MAC else "/")
    seen, rows = set(), []
    for p in psutil.disk_partitions(all=False):
        if p.fstype.lower() in SKIP_FS or (IS_WIN and "cdrom" in p.opts):
            continue
        if IS_LINUX and p.mountpoint.startswith(("/snap", "/var/snap", "/var/lib/docker", "/boot")):
            continue
        if IS_MAC and p.mountpoint.startswith(MAC_SKIP):
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        if not u.total or (p.mountpoint, u.total) in seen:
            continue
        seen.add((p.mountpoint, u.total))
        label = p.mountpoint + ("  (sistema)" if p.mountpoint == system_mount else "")
        s["bars"].append((f"{label}  [{p.fstype}]", u.percent, f"{hb(u.used)} usati di {hb(u.total)} - liberi {hb(u.free)}"))
        rows.append([p.mountpoint, p.device, p.fstype, hb(u.total), hb(u.used), hb(u.free), f"{u.percent:.0f}%"])
        if IS_MAC and p.mountpoint == "/":
            continue  # su macOS "/" e "Data" condividono lo stesso spazio: valuto solo "Data"
        if u.percent >= 95 or (p.mountpoint == system_mount and u.free < 5 * 1024 ** 3):
            issue("crit", "Disco", f"Il disco {p.mountpoint} è quasi pieno ({u.percent:.0f}%, liberi {hb(u.free)}).",
                  "Libera spazio subito: con il disco pieno il sistema rallenta e gli aggiornamenti falliscono.")
        elif u.percent >= 85 or (p.mountpoint == system_mount and u.free < 15 * 1024 ** 3):
            issue("warn", "Disco", f"Il disco {p.mountpoint} sta finendo lo spazio ({u.percent:.0f}%, liberi {hb(u.free)}).",
                  "Svuota Download e cestino, disinstalla i programmi che non usi, sposta foto e video su un disco esterno.")
    if rows:
        s["tables"].append(("Partizioni", ["Punto", "Dispositivo", "File system", "Totale", "Usato", "Libero", "%"], rows))
    phys = physical_disks()
    if phys:
        s["tables"].append(("Dischi fisici", ["Modello", "Tipo", "Capacità", "Salute"], phys))
    if IS_WIN and not is_admin():
        s["notes"].append("Per dati SMART più dettagliati su Windows apri PowerShell come amministratore.")

    if args.bench:
        print("    test velocità disco (scrive e cancella un file da 256 MB)...")
        w, r = bench_disk(tempfile.gettempdir())
        if w:
            s["kv"] += [("Velocità scrittura (disco di sistema)", f"{w:.0f} MB/s"),
                        ("Velocità lettura (disco di sistema)", f"{r:.0f} MB/s" + (" (può essere gonfiata dalla cache)" if IS_WIN else ""))]
            if w < 60:
                issue("warn", "Disco", f"Il disco di sistema è lento in scrittura ({w:.0f} MB/s).",
                      "Tipico di un HDD o di un SSD molto pieno o usurato. Un SSD moderno supera i 300 MB/s.")
        else:
            s["notes"].append("Test velocità disco saltato: spazio libero insufficiente.")
    try:
        io = psutil.disk_io_counters()
        if io:
            s["kv"] += [("Letti dall'accensione", hb(io.read_bytes)), ("Scritti dall'accensione", hb(io.write_bytes))]
    except Exception:
        pass
    return s


# ------------------------------------------------------------------ SPAZIO CARTELLE
def dir_size(path, deadline):
    total, stack = 0, [path]
    while stack:
        if time.time() > deadline:
            return total, False
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total, True


def collect_space(args):
    s = section("spazio", "Cosa occupa spazio nella tua cartella utente")
    home = str(Path.home())
    deadline = time.time() + args.scan_seconds
    rows, complete = [], True
    try:
        entries = list(os.scandir(home))
    except OSError:
        entries = []
    for e in entries:
        try:
            if e.is_symlink():
                continue
            if e.is_dir(follow_symlinks=False):
                size, done = dir_size(e.path, deadline)
                complete &= done
            else:
                size = e.stat(follow_symlinks=False).st_size
            rows.append((e.name, size))
        except OSError:
            pass
    rows.sort(key=lambda x: -x[1])
    total = sum(r[1] for r in rows) or 1
    s["tables"].append((f"Cartelle e file più grandi in {home}", ["Nome", "Dimensione", "% della cartella utente"],
                        [[n, hb(sz), f"{sz / total * 100:.0f}%"] for n, sz in rows[:15]]))
    if not complete:
        s["notes"].append(f"Scansione interrotta dopo {args.scan_seconds} s: i valori sono parziali (minimi).")
    if IS_WIN:
        s["notes"].append("Le cartelle OneDrive possono mostrare anche file che sono solo nel cloud.")

    tmp = tempfile.gettempdir()
    tsize, _ = dir_size(tmp, time.time() + 15)
    s["kv"].append(("File temporanei", f"{hb(tsize)}  ({tmp})"))
    if tsize > 3 * 1024 ** 3:
        tip = ("Usa 'Pulizia disco' o Impostazioni > Sistema > Archiviazione > File temporanei." if IS_WIN
               else "Riavvia il computer: molti file temporanei vengono cancellati all'avvio.")
        issue("info", "Disco", f"I file temporanei occupano {hb(tsize)}.", tip)
    return s


# ------------------------------------------------------------------ BATTERIA
def collect_battery(args):
    try:
        b = psutil.sensors_battery()
    except Exception:
        b = None
    if b is None:
        return None
    s = section("batteria", "Batteria")
    s["bars"].append(("Carica attuale", b.percent, f"{b.percent:.0f}%"))
    s["kv"].append(("Alimentazione", "Collegato alla corrente" if b.power_plugged else "A batteria"))
    if not b.power_plugged and b.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED) and b.secsleft > 0:
        s["kv"].append(("Autonomia stimata", fmt_td(dt.timedelta(seconds=b.secsleft))))

    design = full = cycles = health = None
    condition = ""
    if IS_WIN:
        fn = os.path.join(tempfile.gettempdir(), "pccheck_battery.xml")
        run(["powercfg", "/batteryreport", "/xml", "/output", fn], timeout=30)
        try:
            raw = open(fn, "rb").read()
            txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "ignore")
            design = int(rx(r"<DesignCapacity>(\d+)", txt) or 0) or None
            full = int(rx(r"<FullChargeCapacity>(\d+)", txt) or 0) or None
            cycles = rx(r"<CycleCount>(\d+)", txt) or None
            os.remove(fn)
        except Exception:
            pass
    elif IS_MAC:
        sp = run(["system_profiler", "SPPowerDataType"])
        cycles = rx(r"Cycle Count:\s*(\d+)", sp) or None
        condition = rx(r"Condition:\s*(.+)", sp)
        maxcap = rx(r"Maximum Capacity:\s*(\d+)\s*%", sp)
        if maxcap:
            health = float(maxcap)
        else:
            io = run(["ioreg", "-rn", "AppleSmartBattery"])
            design = int(rx(r'"DesignCapacity" = (\d+)', io) or 0) or None
            full = int(rx(r'"AppleRawMaxCapacity" = (\d+)', io) or rx(r'"MaxCapacity" = (\d+)', io) or 0) or None
    else:
        for bat in sorted(glob.glob("/sys/class/power_supply/BAT*")):
            full = int(read(f"{bat}/energy_full") or read(f"{bat}/charge_full") or 0) or None
            design = int(read(f"{bat}/energy_full_design") or read(f"{bat}/charge_full_design") or 0) or None
            cycles = read(f"{bat}/cycle_count") or None
            break
    if health is None and design and full:
        health = min(full / design * 100, 100)
    if health is not None:
        s["bars"].append(("Salute batteria (capacità rispetto a quando era nuova)", health, f"{health:.0f}%"))
    if design and full:
        s["kv"].append(("Capacità attuale / originale", f"{full} / {design} (mWh o mAh)"))
    if cycles and cycles != "0":
        s["kv"].append(("Cicli di carica", cycles))
    if condition:
        s["kv"].append(("Condizione (macOS)", condition))
    if health is not None and health < 60:
        issue("crit", "Batteria", f"La batteria è molto usurata ({health:.0f}% della capacità originale).",
              "Valuta la sostituzione: l'autonomia è ridotta e può spegnersi all'improvviso.")
    elif health is not None and health < 80:
        issue("warn", "Batteria", f"La batteria è usurata ({health:.0f}% della capacità originale).",
              "È normale dopo qualche anno. Evita di tenerla sempre al 100% e al caldo.")
    if condition and condition.lower() not in ("normal", "normale"):
        issue("warn", "Batteria", f"macOS segnala la batteria come: {condition}.", "Fai controllare la batteria.")
    return s


# ------------------------------------------------------------------ TEMPERATURE
def collect_sensors(args):
    s = section("sensori", "Temperature e ventole")
    rows = []
    try:
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    except Exception:
        temps = {}
    for chip, entries in (temps or {}).items():
        for e in entries:
            if not e.current or e.current <= 0:
                continue
            rows.append([chip, e.label or "-", f"{e.current:.0f} °C", f"{e.critical:.0f} °C" if e.critical else ""])
            if e.current >= 90:
                issue("crit", "Temperatura", f"Sensore {chip} {e.label}: {e.current:.0f} °C, molto alta.",
                      "Pulisci le ventole dalla polvere e controlla la pasta termica.")
            elif e.current >= 80:
                issue("warn", "Temperatura", f"Sensore {chip} {e.label}: {e.current:.0f} °C, alta.",
                      "Usa il portatile su un piano rigido e pulisci le prese d'aria.")
    if rows:
        s["tables"].append(("Sensori di temperatura", ["Chip", "Sensore", "Temperatura", "Critica a"], rows[:20]))
    try:
        fans = psutil.sensors_fans() if hasattr(psutil, "sensors_fans") else {}
        frows = [[chip, f.label or "-", f"{f.current} RPM"] for chip, fl in (fans or {}).items() for f in fl]
        if frows:
            s["tables"].append(("Ventole", ["Chip", "Ventola", "Giri"], frows))
    except Exception:
        pass
    if not s["tables"] and IS_LINUX:
        s["notes"].append("Nessun sensore letto. Installa gratis 'lm-sensors' (sudo apt install lm-sensors) e riprova.")
    elif not s["tables"]:
        s["notes"].append("Windows e macOS non permettono di leggere le temperature senza programmi aggiuntivi. "
                          "Gratis: HWiNFO o LibreHardwareMonitor (Windows), 'sudo powermetrics' (Mac).")
    return s


# ------------------------------------------------------------------ RETE
def collect_network(args):
    s = section("rete", "Rete e Internet")
    addrs, stats = psutil.net_if_addrs(), psutil.net_if_stats()
    rows = []
    for name, st in stats.items():
        ips = [a.address for a in addrs.get(name, []) if a.family == socket.AF_INET]
        if not st.isup or not ips or all(ip.startswith("127.") for ip in ips):
            continue
        rows.append([name, ", ".join(ips), f"{st.speed} Mbit/s" if st.speed else ""])
    if rows:
        s["tables"].append(("Connessioni attive", ["Interfaccia", "Indirizzo IP", "Velocità collegamento"], rows))
    try:
        t = time.perf_counter()
        socket.create_connection(("1.1.1.1", 443), timeout=4).close()
        s["kv"].append(("Internet", f"raggiungibile, latenza {(time.perf_counter() - t) * 1000:.0f} ms"))
        try:
            socket.gethostbyname("github.com")
            s["kv"].append(("DNS (risoluzione nomi)", "funziona"))
        except Exception:
            s["kv"].append(("DNS (risoluzione nomi)", "NON funziona"))
            issue("warn", "Rete", "Internet risponde ma la risoluzione dei nomi (DNS) non funziona.",
                  "Riavvia il router o imposta un DNS pubblico (es. 1.1.1.1).")
    except Exception:
        s["kv"].append(("Internet", "non raggiungibile"))
        issue("info", "Rete", "Internet non è raggiungibile in questo momento.", "Controlla Wi-Fi o cavo.")
    try:
        io = psutil.net_io_counters()
        s["kv"] += [("Ricevuti dall'accensione", hb(io.bytes_recv)), ("Inviati dall'accensione", hb(io.bytes_sent))]
    except Exception:
        pass
    return s


# ------------------------------------------------------------------ PROGRAMMI
def collect_processes(args):
    s = section("programmi", "Programmi in esecuzione", wide=True)
    ncpu = psutil.cpu_count() or 1
    total_ram = psutil.virtual_memory().total
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "memory_info"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except Exception:
            pass
    time.sleep(1.5)
    data = []
    for p in procs:
        try:
            if p.info["pid"] == 0:
                continue
            mem = p.info["memory_info"].rss if p.info["memory_info"] else 0
            user = (p.info.get("username") or "").split("\\")[-1]
            data.append({"pid": p.info["pid"], "name": p.info["name"] or "?", "user": user,
                         "cpu": p.cpu_percent(None) / ncpu, "mem": mem})
        except Exception:
            pass
    groups = {}
    for d in data:
        g = groups.setdefault(d["name"], {"n": 0, "cpu": 0.0, "mem": 0})
        g["n"] += 1
        g["cpu"] += d["cpu"]
        g["mem"] += d["mem"]
    s["kv"].append(("Processi attivi", str(len(data))))
    top_mem = [x for x in sorted(groups.items(), key=lambda x: -x[1]["mem"]) if x[1]["mem"] > 0][:15]
    s["tables"].append(("Programmi che usano più RAM (processi con lo stesso nome raggruppati)",
                        ["Programma", "Processi", "RAM", "% RAM", "CPU"],
                        [[n, str(g["n"]), hb(g["mem"]), f"{g['mem'] / total_ram * 100:.1f}%", f"{g['cpu']:.1f}%"]
                         for n, g in top_mem]))
    top_cpu = sorted(data, key=lambda x: -x["cpu"])[:12]
    s["tables"].append(("Programmi che consumano più CPU (ultimi 1,5 secondi)", ["Programma", "PID", "Utente", "CPU", "RAM"],
                        [[d["name"], str(d["pid"]), d["user"], f"{d['cpu']:.1f}%", hb(d["mem"])] for d in top_cpu]))
    s["notes"].append("La RAM dei processi raggruppati può essere sovrastimata perché parte della memoria è condivisa.")
    for n, g in top_mem[:3]:
        if g["mem"] / total_ram > 0.30:
            issue("warn", "Programmi", f"'{n}' usa {hb(g['mem'])} di RAM ({g['mem'] / total_ram * 100:.0f}%).",
                  "Se è il browser, chiudi le schede che non usi; altrimenti riavvia il programma.")
    for d in top_cpu[:3]:
        if d["cpu"] > 50:
            issue("warn", "Programmi", f"'{d['name']}' usa il {d['cpu']:.0f}% della CPU.",
                  "Se non lo stai usando attivamente potrebbe essere bloccato: chiudilo o riavvialo.")
    return s


def collect_startup(args):
    s = section("avvio", "Programmi che partono all'accensione", wide=True)
    rows = []
    if IS_WIN:
        for it in ps_json("Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location"):
            rows.append([it.get("Name") or "", (it.get("Command") or "")[:90], it.get("Location") or ""])
        tip = "Disattivali da Gestione attività (Ctrl+Maiusc+Esc) > App di avvio."
    elif IS_MAC:
        for d in ("~/Library/LaunchAgents", "/Library/LaunchAgents", "/Library/LaunchDaemons"):
            for f in sorted(glob.glob(os.path.join(os.path.expanduser(d), "*.plist"))):
                rows.append([Path(f).stem, "", d])
        tip = "Gestiscili da Impostazioni di Sistema > Generali > Elementi login."
        s["notes"].append("Mostra solo gli elementi di terze parti; gli 'Elementi login' sono in Impostazioni di Sistema.")
    else:
        for f in sorted(glob.glob(os.path.expanduser("~/.config/autostart/*.desktop"))):
            txt = read(f)
            rows.append([rx(r"^Name=(.+)$", txt) or Path(f).stem, rx(r"^Exec=(.+)$", txt)[:90], "~/.config/autostart"])
        enabled = run(["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-legend"])
        if enabled:
            s["kv"].append(("Servizi di sistema abilitati", str(len(enabled.splitlines()))))
        tip = "Gestiscili dalle 'Applicazioni d'avvio' del tuo ambiente desktop."
    s["kv"].insert(0, ("Programmi all'avvio", str(len(rows))))
    if rows:
        s["tables"].append(("Elenco", ["Nome", "Comando", "Posizione"], rows[:40]))
    if len(rows) > 12:
        issue("warn", "Avvio", f"Ci sono {len(rows)} programmi che partono all'accensione.",
              "Rallentano l'avvio e occupano RAM. " + tip)
    return s


# ------------------------------------------------------------------ SICUREZZA
def collect_security(args):
    s = section("sicurezza", "Sicurezza e aggiornamenti")
    if IS_WIN:
        mp = ps("$s=Get-MpComputerStatus -ErrorAction SilentlyContinue; "
                "if($s){\"$($s.AntivirusEnabled)|$($s.RealTimeProtectionEnabled)|$($s.AntivirusSignatureAge)\"}")
        if mp.count("|") == 2:
            av, rt, age = mp.split("|")
            s["kv"] += [("Microsoft Defender", "attivo" if av == "True" else "non attivo (forse c'è un altro antivirus)"),
                        ("Protezione in tempo reale", "attiva" if rt == "True" else "DISATTIVATA"),
                        ("Firme antivirus aggiornate", f"{age} giorni fa")]
            if av == "True" and rt != "True":
                issue("crit", "Sicurezza", "La protezione in tempo reale di Defender è disattivata.",
                      "Riattivala da Sicurezza di Windows > Protezione da virus e minacce.")
            if age.isdigit() and int(age) > 7:
                issue("warn", "Sicurezza", f"Le firme antivirus non si aggiornano da {age} giorni.",
                      "Avvia Windows Update e controlla la connessione.")
        last = ps("(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn.ToString('yyyy-MM-dd')")
        if re.match(r"\d{4}-\d{2}-\d{2}", last):
            days = (dt.date.today() - dt.date.fromisoformat(last)).days
            s["kv"].append(("Ultimo aggiornamento Windows installato", f"{last} ({days} giorni fa)"))
            if days > 60:
                issue("warn", "Sicurezza", f"L'ultimo aggiornamento di Windows risale a {days} giorni fa.",
                      "Apri Impostazioni > Windows Update e installa gli aggiornamenti.")
        fw = ps("(Get-NetFirewallProfile | Where-Object {$_.Enabled -eq $false}).Name -join ','")
        s["kv"].append(("Firewall", "attivo su tutti i profili" if not fw else f"disattivato su: {fw}"))
        if fw:
            issue("warn", "Sicurezza", f"Il firewall di Windows è disattivato ({fw}).", "Riattivalo da Sicurezza di Windows.")
    elif IS_MAC:
        fv = run(["fdesetup", "status"])
        gk = run(["spctl", "--status"])
        s["kv"] += [("FileVault (cifratura disco)", fv or "n/d"), ("Gatekeeper", gk or "n/d")]
        if "Off" in fv:
            issue("info", "Sicurezza", "FileVault è disattivato: se perdi il Mac i dati sono leggibili.",
                  "Attivalo da Impostazioni di Sistema > Privacy e sicurezza > FileVault.")
        if "disabled" in gk:
            issue("warn", "Sicurezza", "Gatekeeper è disattivato.", "Riattivalo con: sudo spctl --master-enable")
    else:
        if shutil.which("apt"):
            n = len([l for l in run(["apt", "list", "--upgradable"]).splitlines() if "/" in l])
            s["kv"].append(("Pacchetti da aggiornare (apt, cache locale)", str(n)))
            if n > 30:
                issue("info", "Sicurezza", f"Ci sono {n} pacchetti da aggiornare.", "Esegui: sudo apt update && sudo apt upgrade")
        ufw = run(["ufw", "status"]) if shutil.which("ufw") else ""
        if ufw:
            s["kv"].append(("Firewall (ufw)", ufw.splitlines()[0]))
    if not s["kv"]:
        s["notes"].append("Nessuna informazione di sicurezza disponibile su questo sistema.")
    return s


# ------------------------------------------------------------------ OUTPUT TERMINALE
def term_bar(pct, width=24):
    n = int(round(min(max(pct, 0), 100) / 100 * width))
    code = "31" if pct >= 90 else "33" if pct >= 80 else "32"
    return col("█" * n, code) + "░" * (width - n)


def print_section(s):
    print(col(f"\n■ {s['title']}", "1;36"))
    for label, pct, detail in s["bars"]:
        print(f"  {label}\n    {term_bar(pct)} {detail}")
    for k, v in s["kv"]:
        print(f"  {k}: {v}")
    for title, headers, rows in s["tables"]:
        print(col(f"  {title}", "1"))
        rows = rows[:10]
        widths = [min(max(len(str(x)) for x in [h] + [r[i] for r in rows]), 34) for i, h in enumerate(headers)]
        fmt = "    " + "  ".join(f"{{:<{w}}}" for w in widths)
        print(col(fmt.format(*[h[:w] for h, w in zip(headers, widths)]), "2"))
        for r in rows:
            print(fmt.format(*[str(x)[:w] for x, w in zip(r, widths)]))
    for n in s["notes"]:
        print(col(f"  i {n}", "2"))


def score_and_verdict():
    crit = sum(1 for i in ISSUES if i["level"] == "crit")
    warn = sum(1 for i in ISSUES if i["level"] == "warn")
    info = sum(1 for i in ISSUES if i["level"] == "info")
    score = max(0, 100 - crit * 20 - warn * 8 - info * 2)
    if crit:
        verdict = "Ci sono problemi da risolvere subito."
    elif warn:
        verdict = "Il computer funziona, ma alcune cose vanno sistemate."
    elif info:
        verdict = "Il computer è in buona salute. Qualche consiglio per migliorarlo."
    else:
        verdict = "Il computer è in ottima salute."
    return score, verdict


# ------------------------------------------------------------------ REPORT HTML
CSS = """
:root{--paper:#e9edf1;--sheet:#fbfcfd;--ink:#18222d;--steel:#5a6878;--rule:#cfd6de;--track:#dde3e9;
--ok:#2c7a4b;--warn:#c98a00;--crit:#b8322a;--signal:#f2b705;--info:#3d6f99;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--paper:#11161c;--sheet:#1a2129;--ink:#e6ebf0;--steel:#9aa8b6;
--rule:#2c3640;--track:#2a333d;--ok:#4cb87a;--warn:#e0a92a;--crit:#e25b52;--info:#6fa3cf;color-scheme:dark}}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.h{font-family:Bahnschrift,"DIN Alternate","DIN Condensed","Roboto Condensed","Arial Narrow",system-ui,sans-serif;letter-spacing:.01em}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header.top{display:grid;grid-template-columns:auto 1fr;gap:28px;align-items:center;background:var(--sheet);
border-left:10px solid var(--signal);padding:26px 28px;border-radius:4px}
.gauge{width:150px;height:150px}
.gauge .n{font-size:44px;font-weight:700;fill:var(--ink)}.gauge .l{font-size:11px;fill:var(--steel)}
h1{margin:0 0 4px;font-size:30px;line-height:1.15}
.meta{color:var(--steel);font-size:13.5px;margin:0}
.verdict{font-size:19px;margin:10px 0 0}
.issues{margin:22px 0 8px;background:var(--sheet);border-radius:4px;padding:6px 0}
.issues h2{padding:12px 24px 4px}
.iss{display:grid;grid-template-columns:110px 1fr;gap:16px;padding:12px 24px;border-top:1px solid var(--rule)}
.tag{font-size:12.5px;font-weight:700;padding:3px 8px;border-radius:3px;height:fit-content;text-align:center;color:#fff}
.tag.crit{background:var(--crit)}.tag.warn{background:var(--warn);color:#1b1400}.tag.info{background:var(--info)}
.iss b{font-weight:600}.iss .adv{color:var(--steel);font-size:14px}
.allgood{padding:14px 24px;color:var(--ok);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,470px),1fr));gap:18px;margin-top:18px;align-items:start}
.card{background:var(--sheet);border-radius:4px;padding:20px 22px;min-width:0}
.card.wide{grid-column:1/-1}
h2{font-size:21px;margin:0 0 14px;font-weight:700}
h3{font-size:14px;margin:18px 0 6px;color:var(--steel);font-weight:600}
.bar{margin:0 0 14px}.bar-top{display:flex;justify-content:space-between;gap:12px;font-size:14px;flex-wrap:wrap}
.bar-top span:last-child{color:var(--steel)}
.track{height:10px;background:var(--track);border-radius:2px;margin-top:5px;overflow:hidden}
.fill{height:100%}.fill.ok{background:var(--ok)}.fill.warn{background:var(--warn)}.fill.crit{background:var(--crit)}
dl.kv{display:grid;grid-template-columns:minmax(150px,38%) 1fr;margin:0;font-size:14px}
dl.kv dt,dl.kv dd{padding:6px 0;border-top:1px solid var(--rule);margin:0}
dl.kv dt{color:var(--steel);padding-right:12px}dl.kv dd{overflow-wrap:anywhere}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}
th{text-align:left;color:var(--steel);font-weight:600;border-bottom:2px solid var(--rule);padding:6px 10px 6px 0;white-space:nowrap}
td{border-bottom:1px solid var(--rule);padding:6px 10px 6px 0;overflow-wrap:anywhere}
.note{color:var(--steel);font-size:13px;margin:12px 0 0}
footer{color:var(--steel);font-size:12.5px;margin-top:28px}
@media (max-width:600px){header.top{grid-template-columns:1fr}.iss{grid-template-columns:1fr;gap:6px}.tag{width:fit-content}}
"""


def render_html(sections, meta):
    e = html.escape
    score, verdict = score_and_verdict()
    color = "var(--crit)" if score < 50 else "var(--warn)" if score < 80 else "var(--ok)"
    arc = 2 * 3.14159 * 62
    gauge = (f'<svg class="gauge" viewBox="0 0 150 150" role="img" aria-label="Punteggio {score} su 100">'
             f'<circle cx="75" cy="75" r="62" fill="none" stroke="var(--track)" stroke-width="12"/>'
             f'<circle cx="75" cy="75" r="62" fill="none" stroke="{color}" stroke-width="12" '
             f'stroke-dasharray="{arc * score / 100:.1f} {arc:.1f}" transform="rotate(-90 75 75)"/>'
             f'<text x="75" y="84" text-anchor="middle" class="n h">{score}</text>'
             f'<text x="75" y="104" text-anchor="middle" class="l">su 100</text></svg>')
    order = {"crit": 0, "warn": 1, "info": 2}
    iss = "".join(f'<div class="iss"><span class="tag {i["level"]}">{LEVELS[i["level"]]}</span>'
                  f'<div><b>{e(i["area"])}:</b> {e(i["msg"])}<div class="adv">{e(i["advice"])}</div></div></div>'
                  for i in sorted(ISSUES, key=lambda x: order[x["level"]]))
    iss = iss or '<div class="allgood">Nessun problema trovato.</div>'

    cards = []
    for s in sections:
        out = [f'<section class="card{" wide" if s["wide"] else ""}" id="{s["id"]}"><h2 class="h">{e(s["title"])}</h2>']
        for label, pct, detail in s["bars"]:
            lvl = "crit" if pct >= 90 else "warn" if pct >= 80 else "ok"
            if "Salute batteria" in label or "Carica" in label:
                lvl = "crit" if pct < 30 else "warn" if pct < 60 else "ok"
            out.append(f'<div class="bar"><div class="bar-top"><span>{e(label)}</span><span>{e(detail)}</span></div>'
                       f'<div class="track"><div class="fill {lvl}" style="width:{min(max(pct, 0), 100):.1f}%"></div></div></div>')
        if s["kv"]:
            out.append('<dl class="kv">' + "".join(f"<dt>{e(str(k))}</dt><dd>{e(str(v))}</dd>" for k, v in s["kv"]) + "</dl>")
        for title, headers, rows in s["tables"]:
            out.append(f"<h3>{e(title)}</h3><div class='tw'><table><thead><tr>"
                       + "".join(f"<th>{e(h)}</th>" for h in headers) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table></div>")
        for n in s["notes"]:
            out.append(f'<p class="note">{e(n)}</p>')
        out.append("</section>")
        cards.append("".join(out))

    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PC Check - {e(meta['host'])} - {e(meta['date'])}</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top">{gauge}<div><h1 class="h">Stato di salute di {e(meta['host'])}</h1>
<p class="meta">{e(meta['os'])} - controllo del {e(meta['date'])} - durata {e(meta['duration'])}</p>
<p class="verdict">{e(verdict)}</p></div></header>
<div class="issues"><h2 class="h">Cosa sistemare</h2>{iss}</div>
<div class="grid">{''.join(cards)}</div>
<footer>Creato da PC Check {VERSION}. Tutti i dati sono stati raccolti sul tuo computer e non sono stati inviati a nessuno.</footer>
</div></body></html>"""


# ------------------------------------------------------------------ MAIN
def main():
    ap = argparse.ArgumentParser(description="PC Check - diagnostica gratuita per Windows, macOS e Linux")
    ap.add_argument("--fast", action="store_true", help="salta test di velocità e scansione cartelle")
    ap.add_argument("--no-bench", action="store_true", help="salta i test di velocità")
    ap.add_argument("--no-scan", action="store_true", help="salta la scansione delle cartelle")
    ap.add_argument("--scan-seconds", type=int, default=40, help="tempo massimo scansione cartelle (default 40)")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il report nel browser")
    ap.add_argument("--out", help="percorso del report HTML")
    ap.add_argument("--json", help="salva anche i dati in JSON")
    args = ap.parse_args()
    args.bench = not (args.fast or args.no_bench)
    scan = not (args.fast or args.no_scan)

    start = time.time()
    print(col(f"\nPC Check {VERSION} - analisi del computer in corso (circa 1 minuto)...\n", "1"))
    steps = [("Sistema", collect_system), ("CPU", collect_cpu), ("RAM", collect_ram), ("Scheda grafica", collect_gpu),
             ("Dischi", collect_disks), ("Batteria", collect_battery), ("Temperature", collect_sensors),
             ("Rete", collect_network), ("Programmi in esecuzione", collect_processes),
             ("Programmi all'avvio", collect_startup), ("Sicurezza", collect_security)]
    if scan:
        steps.insert(5, ("Spazio occupato nelle cartelle", collect_space))
    sections = []
    for label, fn in steps:
        print(f"  • {label}...")
        try:
            s = fn(args)
            if s:
                sections.append(s)
        except Exception as ex:
            err = section(label.lower(), label)
            err["notes"].append(f"Errore durante il controllo: {ex}")
            sections.append(err)

    for s in sections:
        print_section(s)
    score, verdict = score_and_verdict()
    print(col(f"\n■ Risultato: {score}/100 - {verdict}", "1;33"))
    for i in ISSUES:
        code = {"crit": "31", "warn": "33", "info": "36"}[i["level"]]
        print(f"  {col('[' + LEVELS[i['level']] + ']', code)} {i['area']}: {i['msg']}\n      -> {i['advice']}")

    sysd = dict(sections[0]["kv"]) if sections else {}
    meta = {"host": socket.gethostname(), "os": sysd.get("Sistema operativo", SYSTEM),
            "date": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "duration": f"{time.time() - start:.0f} s"}
    out = Path(args.out) if args.out else Path.home() / f"pc-check-report-{dt.datetime.now():%Y%m%d-%H%M}.html"
    try:
        out.write_text(render_html(sections, meta), encoding="utf-8")
        print(col(f"\nReport salvato in: {out}", "1;32"))
        if not args.no_browser:
            webbrowser.open(out.resolve().as_uri())
    except Exception as ex:
        print(f"Impossibile salvare il report: {ex}")
    if args.json:
        Path(args.json).write_text(json.dumps({"meta": meta, "score": score, "issues": ISSUES, "sections": sections},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Dati JSON salvati in: {args.json}")
    if getattr(sys, "frozen", False):
        input("\nPremi Invio per chiudere...")


if __name__ == "__main__":
    main()
