<div align="center">

# 🎯 MultiSpray

**One command. Many protocols. Every credential.**

A fast, colour‑coded credential sprayer that wraps [NetExec (nxc)](https://github.com/Pennyw0rth/NetExec)
to try one credential set against **SMB, SSH, WinRM, MSSQL, RDP, LDAP, FTP, VNC, WMI and NFS**
across many hosts — and tells you *exactly* which credential works on which service, on which host,
with a ready‑to‑paste connect command.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![NetExec](https://img.shields.io/badge/Powered%20by-NetExec-red)](https://github.com/Pennyw0rth/NetExec)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)]()

</div>

---

## 📸 What It Looks Like

```text
═══════════════════════════════════════════════════════════════
  MultiSpray v1.2.1  ·  multi-protocol credential sprayer
  Developed by Vikas :)
═══════════════════════════════════════════════════════════════

[*] Targets : 3 host(s), 5 user(s), 2 password(s), 10 service(s)
[*] Attempts: 300
[*] Starting 5 worker(s)…
[*] Press ANY key at any time to show live progress (Ctrl+C to abort).

[+] 10.0.0.5 SMB      administrator:Spring2025! (ADMIN)
[+] 10.0.0.5 WINRM    administrator:Spring2025! (ADMIN)
[+] 10.0.0.7 SSH      root:toor
[+] 10.0.0.9 MSSQL    sa:Spring2025!

[STATUS] ████████░░░░░░░░░░░░ 82/300 ( 27.3%) | Remaining: 218 | Elapsed: 47.3s | Rate: 1.73/s | ETA: 2m06s

============================================================
  SPRAY SUMMARY
============================================================

Host: 10.0.0.5
  SMB      administrator:Spring2025! (ADMIN)
           → smbclient //10.0.0.5/C$ -U 'administrator%Spring2025!'
  WINRM    administrator:Spring2025! (ADMIN)
           → evil-winrm -i 10.0.0.5 -u 'administrator' -p 'Spring2025!'

Host: 10.0.0.7
  SSH      root:toor
           → sshpass -p 'toor' ssh root@10.0.0.7

Host: 10.0.0.9
  MSSQL    sa:Spring2025!
           → impacket-mssqlclient 'sa':'Spring2025!'@10.0.0.9 -windows-auth

[*] Finished – 4 successful credential(s), 2 with admin rights.
```

---

## ✨ Features

- **One credential set, every protocol** — tests the same user/password combinations across up to **10 Windows & Linux services** in a single run.
- **Flexible inputs** — pass a single value or a file for each of hosts, usernames and passwords (mix & match freely).
- **Service selection** — spray everything by default, or restrict to the protocols you care about (`smb,ssh,winrm,…`).
- **Concurrent & rate‑limited** — configurable worker threads plus `--jitter` / `--delay` to avoid account lockouts.
- **Beautiful, always‑on colour** — green for hits, magenta for `(Pwn3d!)` admin access — colours survive piping and redirects.
- **Live progress on demand** — press **any key** during a run to see completed / remaining / rate / ETA — one line per keypress.
- **Copy‑paste ready connect commands** — every valid credential is followed by a ready‑to‑run command for that service (smbclient, evil‑winrm, xfreerdp, impacket‑mssqlclient, sshpass, ldapsearch, lftp, nxc, showmount). Domain is auto‑prepended when `--domain` is used, and admin SMB hits get the `C$` variant automatically.
- **Grouped summary** — final report is organised per host, then per service, so it’s easy to read at a glance.
- **Verbose or quiet** — by default only successes print. Add `--verbose` to see every failed attempt too.
- **TSV export** — dump all successful hits (including connect commands) to a spreadsheet‑friendly file with `--output`.
- **Dry‑run** — preview every task combination without touching the network.
- **Battery‑tested protocol layer** — authentication is handled by NetExec, so it inherits years of protocol‑specific improvements.

---

## 🎯 Supported Services

| Service | Port (default) | Authentication via |
|---------|:--------------:|--------------------|
| SMB     | 445            | NetExec `smb`      |
| SSH     | 22             | NetExec `ssh`      |
| WinRM   | 5985           | NetExec `winrm`    |
| MSSQL   | 1433           | NetExec `mssql`    |
| RDP     | 3389           | NetExec `rdp`      |
| LDAP    | 389            | NetExec `ldap`     |
| FTP     | 21             | NetExec `ftp`      |
| VNC     | 5900           | NetExec `vnc`      |
| WMI     | 135            | NetExec `wmi`      |
| NFS     | 2049           | NetExec `nfs`      |

---

## 📦 Installation

### 1. Install NetExec (required — MultiSpray is a wrapper around it)

```bash
pipx install netexec
```

*(Alternatively: `pip install netexec` — but `pipx` is recommended.)*

### 2. Install MultiSpray

```bash
git clone https://github.com/vikasrai11/multispray.git
cd multispray
pip install -r requirements.txt
```

Or install as a proper console command:

```bash
pip install .
multispray --help
```

---

## 🚀 Quick Start

```bash
# Single host, single user, single password → all services
python multispray.py -h 10.0.0.5 -u administrator -p 'P@ssw0rd'

# Full lists, SMB + WinRM only
python multispray.py -H hosts.txt -U users.txt -P passwords.txt --services smb,winrm

# Mix: single host with a user list, add jitter
python multispray.py -h 10.0.0.5 -U users.txt -p 'Summer2025!' --jitter 2
```

---

## 📖 Usage

```
multispray.py [-h HOST] [-H FILE] [-u USER] [-U FILE]
              [-p PASS] [-P FILE] [--services LIST]
              [--domain DOMAIN] [--local-auth]
              [--threads N] [--timeout S]
              [--jitter S] [--delay S]
              [--verbose] [--output FILE] [--dry-run] [--help] [--version]
```

### Flag Reference

| Flag | Description |
|------|-------------|
| `-h`, `--host HOST`        | Single target host (IP or hostname). **Repeatable.** |
| `-H`, `--hosts FILE`       | File with one host per line. **Repeatable.** |
| `-u`, `--user USER`        | Single username. **Repeatable.** |
| `-U`, `--users FILE`       | File with one username per line. **Repeatable.** |
| `-p`, `--password PASS`    | Single password. **Repeatable.** |
| `-P`, `--passwords FILE`   | File with one password per line. **Repeatable.** |
| `--services LIST`          | Comma‑separated services (`smb,ssh,winrm,…`). Default: **all**. |
| `--domain DOMAIN`          | Domain for authentication. |
| `--local-auth`             | Use local authentication (SMB/WinRM/etc.). |
| `--threads N`              | Concurrent workers (default `5`). |
| `--timeout S`              | Timeout per attempt in seconds (default `60`). |
| `--jitter S`               | Random delay `0..S` seconds between attempts. |
| `--delay S`                | Fixed delay (seconds) between attempts. |
| `--verbose`                | Also print failed attempts. |
| `--output FILE`            | Write successful hits to a TSV file. |
| `--dry-run`                | Preview combinations without executing. |
| `--help`                   | Show help and exit. |
| `--version`                | Show version and exit. |

> ⚠️ **Heads up:** `-h` is reserved for **single host**, not help. Use `--help` for help.

### ⌨️ Live Progress

While the spray is running, **press any key** at any time to print a live status line:

```text
[STATUS] ████████░░░░░░░░░░░░ 82/300 ( 27.3%) | Remaining: 218 | Elapsed: 47.3s | Rate: 1.73/s | ETA: 2m06s
```

Includes a progress bar, percentage, remaining attempts, elapsed time, current rate, and **ETA in seconds** (switches to `m`/`h` for long runs). **Ctrl+C still aborts cleanly** — the terminal state is always restored.

---

## 🧪 Examples

**Spray a single domain account against many hosts (SMB only, local auth):**
```bash
python multispray.py -H hosts.txt -u 'CORP\jdoe' -p 'Autumn2025!' --services smb --local-auth
```

**Slow and safe — avoid lockouts:**
```bash
python multispray.py -H hosts.txt -U users.txt -P passwords.txt \
    --threads 2 --jitter 4 --delay 2
```

**Export hits for the report:**
```bash
python multispray.py -H hosts.txt -U users.txt -P passwords.txt --output findings.tsv
```

**Preview what would be sprayed:**
```bash
python multispray.py -H hosts.txt -U users.txt -P passwords.txt --dry-run
```

### 🚀 From Hit to Shell in One Copy‑Paste

Every successful credential in the summary comes with a working connect command:

```text
Host: 10.0.0.5
  SMB      administrator:Spring2025! (ADMIN)
           → smbclient //10.0.0.5/C$ -U 'administrator%Spring2025!'
  WINRM    administrator:Spring2025! (ADMIN)
           → evil-winrm -i 10.0.0.5 -u 'administrator' -p 'Spring2025!'

Host: 10.0.0.7
  SSH      root:toor
           → sshpass -p 'toor' ssh root@10.0.0.7

Host: 10.0.0.9
  MSSQL    sa:Spring2025!
           → impacket-mssqlclient 'sa':'Spring2025!'@10.0.0.9 -windows-auth
```

Export (`--output hits.tsv`) includes a `connect_cmd` column too, so reports are actionable.

### 🧰 Optional companion tools

Install the ones matching the services you actually hit:

| Service | Tool | Install |
|---------|------|---------|
| SMB     | `smbclient` | `apt install smbclient` |
| SSH     | `sshpass`   | `apt install sshpass` |
| WinRM   | `evil-winrm` | `gem install evil-winrm` |
| MSSQL   | `impacket-mssqlclient` | `pipx install impacket` |
| RDP     | `xfreerdp`  | `apt install freerdp2-x11` |
| LDAP    | `ldapsearch` | `apt install ldap-utils` |
| FTP     | `lftp`      | `apt install lftp` |
| VNC     | `vncviewer` | `apt install tigervnc-viewer` |
| NFS     | `showmount` | `apt install nfs-common` |

---

## 🔧 How It Works

1. **Expand inputs** — every value in the CLI is either a single item or a file; the tool loads and de‑duplicates them.
2. **Build the task matrix** — cross product of *hosts × services × users × passwords*.
3. **Distribute across workers** — a bounded thread pool pulls tasks from a queue (default 5 workers). Each task fires a single `nxc` invocation.
4. **Parse NetExec output** — `[+]` marks success, `(Pwn3d!)` marks administrative access.
5. **Aggregate & report** — live output during the run, a grouped summary with connect commands, and optional TSV export at the end.

Because NetExec handles the protocol layer, MultiSpray inherits its accuracy and stays future‑proof — new NetExec protocols can be added to the `SERVICES` map in one line.

---

## ⚖️ Legal Disclaimer

> **MultiSpray is provided for authorised security testing and educational purposes only.**
> Using it against systems you do not own — or for which you do not have explicit **written permission** — is illegal in most jurisdictions and may violate computer‑fraud laws. The author(s) assume no liability for misuse or damage caused by this tool. Always obtain written authorisation before running any credential spray.

---

## 🗺️ Roadmap

- [ ] Support for custom NetExec arguments (`--nxc-args`)
- [ ] Parallel‑per‑service batching to speed up common workflows
- [ ] JSON output format
- [ ] Auto‑resume from previous TSV
- [ ] Docker image

Suggestions welcome — open a [feature request](../../issues/new/choose).

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for the full text.

---

## 🙏 Acknowledgements

- [**NetExec / nxc**](https://github.com/Pennyw0rth/NetExec) — the protocol engine that does the hard part.
- [**Colorama**](https://github.com/tartley/colorama) — cross‑platform terminal colours.
- Everyone who reports bugs, opens PRs, and gives feedback. ❤️
