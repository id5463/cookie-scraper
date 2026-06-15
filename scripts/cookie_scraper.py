#!/usr/bin/env python3
"""Cookie scraper with local cache — incremental decryption on subsequent runs.

First run: full decrypt + save cache.  Subsequent runs: only decrypt changed cookies.

Usage:
    python cookie_scraper.py [options]
"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import win32crypt
except ImportError:
    win32crypt = None

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

# ── paths ─────────────────────────────────────────────────────────────────────

CACHE_DIR = os.path.expandvars(r"%LOCALAPPDATA%\cookie-scraper")
CACHE_DB = os.path.join(CACHE_DIR, "cookies.db")

# ── browser definitions ──────────────────────────────────────────────────────

BROWSERS = {
    "chrome": {
        "name": "Google Chrome",
        "process": "chrome.exe",
        "data_dir": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        "cookie_db": "Default\\Network\\Cookies",
        "cookie_db_fallback": "Default\\Cookies",
        "local_state": "Local State",
    },
    "edge": {
        "name": "Microsoft Edge",
        "process": "msedge.exe",
        "data_dir": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
        "cookie_db": "Default\\Network\\Cookies",
        "cookie_db_fallback": "Default\\Cookies",
        "local_state": "Local State",
    },
    "brave": {
        "name": "Brave",
        "process": "brave.exe",
        "data_dir": os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"),
        "cookie_db": "Default\\Network\\Cookies",
        "cookie_db_fallback": "Default\\Cookies",
        "local_state": "Local State",
    },
    "chromium": {
        "name": "Chromium",
        "process": "chrome.exe",
        "data_dir": os.path.expandvars(r"%LOCALAPPDATA%\Chromium\User Data"),
        "cookie_db": "Default\\Network\\Cookies",
        "cookie_db_fallback": "Default\\Cookies",
        "local_state": "Local State",
    },
    "firefox": {
        "name": "Mozilla Firefox",
        "process": "firefox.exe",
        "profile_dir": os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles"),
        "cookie_db": "cookies.sqlite",
    },
}


# ── cache layer ───────────────────────────────────────────────────────────────

def init_cache():
    """Create the local cache database if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cookies (
            browser     TEXT NOT NULL,
            host        TEXT NOT NULL,
            name        TEXT NOT NULL,
            path        TEXT NOT NULL DEFAULT '/',
            enc_hash    TEXT,
            value       TEXT,
            secure      INTEGER DEFAULT 0,
            httpOnly    INTEGER DEFAULT 0,
            persistent  INTEGER DEFAULT 0,
            created     TEXT,
            expires     TEXT,
            last_seen   TEXT,
            PRIMARY KEY (browser, host, name, path)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def cache_lookup(browser, host, name, path):
    """Return cached (value, enc_hash) or (None, None)."""
    conn = sqlite3.connect(CACHE_DB)
    row = conn.execute(
        "SELECT value, enc_hash FROM cookies WHERE browser=? AND host=? AND name=? AND path=?",
        (browser, host, name, path)
    ).fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)


def cache_upsert(browser, host, name, path, enc_hash, value, secure, httpOnly, persistent, created, expires):
    """Insert or update a cached cookie."""
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("""
        INSERT INTO cookies (browser, host, name, path, enc_hash, value, secure, httpOnly, persistent, created, expires, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (browser, host, name, path) DO UPDATE SET
            enc_hash = excluded.enc_hash,
            value    = excluded.value,
            secure   = excluded.secure,
            httpOnly = excluded.httpOnly,
            persistent = excluded.persistent,
            created  = excluded.created,
            expires  = excluded.expires,
            last_seen = excluded.last_seen
    """, (browser, host, name, path, enc_hash, value,
          int(secure), int(httpOnly), int(persistent), created, expires,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def cache_mark_seen(browser, host, name, path):
    """Update last_seen timestamp for an existing cookie."""
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        "UPDATE cookies SET last_seen=? WHERE browser=? AND host=? AND name=? AND path=?",
        (datetime.now(timezone.utc).isoformat(), browser, host, name, path)
    )
    conn.commit()
    conn.close()


def get_cache_stats():
    """Return (total_cookies, last_full_scrape) from cache."""
    if not os.path.isfile(CACHE_DB):
        return (0, None)
    conn = sqlite3.connect(CACHE_DB)
    total = conn.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    row = conn.execute("SELECT value FROM meta WHERE key='last_full_scrape'").fetchone()
    conn.close()
    return (total, row[0] if row else None)


# ── detection / browser utils ─────────────────────────────────────────────────

def list_detected_browsers():
    detected = []
    for key, cfg in BROWSERS.items():
        if key == "firefox":
            profile_dir = Path(cfg["profile_dir"])
            if profile_dir.is_dir() and any(profile_dir.glob("*.default*")):
                detected.append(key)
        else:
            data_dir = Path(cfg["data_dir"])
            if data_dir.is_dir() and (data_dir / "Local State").is_file():
                detected.append(key)
    return detected


def is_browser_running(browser_key):
    proc = BROWSERS[browser_key].get("process", "")
    if not proc:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {proc}"],
            capture_output=True, text=True, timeout=5
        )
        return proc.lower() in result.stdout.lower()
    except Exception:
        return False


def kill_browser(browser_key):
    proc = BROWSERS[browser_key].get("process", "")
    if not proc:
        return
    print(f"[!] Killing {proc} ...", file=sys.stderr)
    try:
        subprocess.run(["taskkill", "/F", "/IM", proc], capture_output=True, timeout=10)
        time.sleep(1.5)
    except Exception as e:
        print(f"[!] Kill failed: {e}", file=sys.stderr)


def find_firefox_profile(profile_dir):
    base = Path(profile_dir)
    if not base.is_dir():
        return None
    profiles = sorted(base.glob("*.default-release"), reverse=True)
    if not profiles:
        profiles = sorted(base.glob("*.default*"), reverse=True)
    return profiles[0] if profiles else None


# ── crypto ────────────────────────────────────────────────────────────────────

def get_chromium_encryption_key(local_state_path):
    if win32crypt is None:
        print("[!] pywin32 not installed — cannot decrypt Chromium cookies", file=sys.stderr)
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        encrypted_key = base64.b64decode(state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]  # strip "DPAPI"
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except Exception as e:
        print(f"[!] Failed to get key from {local_state_path}: {e}", file=sys.stderr)
        return None


def hash_encrypted(enc_val):
    """SHA256 of encrypted value blob — used to detect changes without decrypting."""
    if enc_val is None:
        return "none"
    return hashlib.sha256(enc_val).hexdigest()


def decrypt_chromium_value(encrypted_value, key):
    if AES is None:
        return "[encrypted — pycryptodome not installed]"
    try:
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        raw = cipher.decrypt(ciphertext)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.hex()
    except Exception:
        return "[decryption failed]"


# ── db file access ────────────────────────────────────────────────────────────

def _open_db(db_path, tmp_db, browser_name):
    conn = None
    # 1. immutable mode
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        conn.cursor().execute("SELECT 1")
        return conn
    except Exception:
        pass
    # 2. subprocess copy
    try:
        subprocess.run(
            ["cmd", "/c", "copy", "/b", str(db_path), str(tmp_db)],
            capture_output=True, timeout=5, check=True
        )
        if os.path.getsize(tmp_db) > 0:
            conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
            conn.cursor().execute("SELECT 1")
            return conn
    except Exception:
        pass
    # 3. powershell copy
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Copy-Item -LiteralPath '{db_path}' -Destination '{tmp_db}' -Force"],
            capture_output=True, timeout=10,
        )
        if os.path.getsize(tmp_db) > 0:
            conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
            conn.cursor().execute("SELECT 1")
            return conn
    except Exception:
        pass
    # 4. raw read
    try:
        with open(str(db_path), "rb") as src:
            data = src.read()
        with open(tmp_db, "wb") as dst:
            dst.write(data)
        if os.path.getsize(tmp_db) > 0:
            conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
            return conn
    except Exception:
        pass

    print(f"[-] {browser_name}: cookie db is locked. Please close the browser and retry.", file=sys.stderr)
    return None


# ── time conversion ───────────────────────────────────────────────────────────

def chrometime_to_iso(chrometime):
    if chrometime is None or chrometime == 0:
        return None
    ts = chrometime / 1_000_000 - 11644473600
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def unix_to_iso(ts):
    if ts is None or ts == 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── scrapers ──────────────────────────────────────────────────────────────────

def scrape_chromium(browser_key, cfg, use_cache):
    data_dir = Path(cfg["data_dir"])
    local_state = data_dir / cfg["local_state"]
    if not local_state.is_file():
        print(f"[-] {cfg['name']}: Local State not found", file=sys.stderr)
        return [], 0

    key = get_chromium_encryption_key(str(local_state))
    if key is None:
        return [], 0

    db_path = data_dir / cfg["cookie_db"]
    if not db_path.is_file():
        db_path = data_dir / cfg["cookie_db_fallback"]
    if not db_path.is_file():
        print(f"[-] {cfg['name']}: cookies db not found", file=sys.stderr)
        return [], 0

    tmp_dir = tempfile.mkdtemp(prefix="cookie_scraper_")
    tmp_db = os.path.join(tmp_dir, "Cookies.tmp")
    conn = _open_db(db_path, tmp_db, cfg['name'])
    if conn is None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return [], 0

    browser_name = cfg["name"]
    results = []
    cache_hits = 0
    cache_misses = 0

    try:
        rows = conn.execute("""
            SELECT host_key, name, value, encrypted_value,
                   path, expires_utc, is_secure, is_httponly,
                   creation_utc, has_expires, is_persistent
            FROM cookies
        """).fetchall()

        total = len(rows)
        for row in rows:
            host, name, plain_val, enc_val, path, expires, secure, httponly, created, has_exp, persistent = row

            created_iso = chrometime_to_iso(created) if created else None
            expires_iso = chrometime_to_iso(expires) if expires and has_exp else None
            enc_hash = hash_encrypted(enc_val)

            value = None
            if use_cache and enc_hash:
                cached_val, cached_hash = cache_lookup(browser_name, host, name, path)
                if cached_hash == enc_hash:
                    value = cached_val
                    cache_hits += 1
                    cache_mark_seen(browser_name, host, name, path)

            if value is None:
                # cache miss — must decrypt
                if plain_val:
                    value = plain_val
                else:
                    value = decrypt_chromium_value(enc_val, key)
                cache_misses += 1
                if use_cache:
                    cache_upsert(browser_name, host, name, path, enc_hash, value,
                                 secure, httponly, persistent, created_iso, expires_iso)

            results.append({
                "browser": browser_name,
                "host": host,
                "name": name,
                "value": value,
                "path": path,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
                "persistent": bool(persistent),
                "created": created_iso,
                "expires": expires_iso,
            })

        conn.close()
    except Exception as e:
        print(f"[!] {browser_name} sqlite error: {e}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if use_cache and total > 0:
        print(f"    cache: {cache_hits} hits / {cache_misses} decrypted ({total} total)", file=sys.stderr)

    return results, cache_misses


def scrape_firefox(browser_key, cfg, use_cache):
    profile = find_firefox_profile(cfg["profile_dir"])
    if profile is None:
        print(f"[-] {cfg['name']}: profile not found", file=sys.stderr)
        return [], 0

    db_path = profile / cfg["cookie_db"]
    if not db_path.is_file():
        print(f"[-] {cfg['name']}: cookies.sqlite not found", file=sys.stderr)
        return [], 0

    tmp_dir = tempfile.mkdtemp(prefix="cookie_scraper_")
    tmp_db = os.path.join(tmp_dir, "Cookies.tmp")
    conn = _open_db(str(db_path), tmp_db, cfg['name'])
    if conn is None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return [], 0

    browser_name = cfg["name"]
    results = []
    cache_hits = 0
    cache_misses = 0

    try:
        rows = conn.execute("""
            SELECT host, name, value, path,
                   expiry, isSecure, isHttpOnly,
                   creationTime, sameSite
            FROM moz_cookies
        """).fetchall()

        total = len(rows)
        for row in rows:
            host, name, value, path, expiry, secure, httponly, created, samesite = row
            created_iso = unix_to_iso(created / 1_000_000) if created else None
            expires_iso = unix_to_iso(expiry) if expiry else None
            enc_hash = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

            if use_cache:
                cached_val, cached_hash = cache_lookup(browser_name, host, name, path)
                if cached_hash == enc_hash:
                    cache_hits += 1
                    cache_mark_seen(browser_name, host, name, path)
                    results.append({
                        "browser": browser_name, "host": host, "name": name,
                        "value": cached_val, "path": path, "secure": bool(secure),
                        "httpOnly": bool(httponly), "sameSite": samesite,
                        "created": created_iso, "expires": expires_iso,
                    })
                    continue

            cache_misses += 1
            if use_cache:
                cache_upsert(browser_name, host, name, path, enc_hash, value,
                             secure, httponly, True, created_iso, expires_iso)

            results.append({
                "browser": browser_name, "host": host, "name": name,
                "value": value, "path": path, "secure": bool(secure),
                "httpOnly": bool(httponly), "sameSite": samesite,
                "created": created_iso, "expires": expires_iso,
            })

        conn.close()
    except Exception as e:
        print(f"[!] {browser_name} sqlite error: {e}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if use_cache and total > 0:
        print(f"    cache: {cache_hits} hits / {cache_misses} new ({total} total)", file=sys.stderr)

    return results, cache_misses


# ── output ────────────────────────────────────────────────────────────────────

def format_netscape(cookies):
    lines = ["# Netscape HTTP Cookie File", "# Generated by cookie_scraper.py", ""]
    for c in cookies:
        domain = c["host"]
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = str(int(datetime.fromisoformat(c["expires"]).timestamp())) if c.get("expires") else "0"
        path = c.get("path", "/")
        lines.append(f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{c['name']}\t{c['value']}")
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Incremental browser cookie scraper with local cache")
    parser.add_argument("--browser", "-b",
                       help="Comma-separated browser keys (chrome,edge,brave,chromium,firefox) or 'all'")
    parser.add_argument("--domain", "-d", help="Filter by domain (e.g. example.com)")
    parser.add_argument("--search", "-s", help="Search cookie name or value")
    parser.add_argument("--output", "-o", default="text",
                       choices=["text", "json", "csv", "netscape"])
    parser.add_argument("--outfile", "-f", help="Save to file instead of stdout")
    parser.add_argument("--list-browsers", action="store_true",
                       help="List detected browsers and exit")
    parser.add_argument("--kill", action="store_true",
                       help="Force-close browser before scraping to unlock cookie db")
    parser.add_argument("--no-cache", action="store_true",
                       help="Skip cache — force full decrypt on every run")
    parser.add_argument("--cache-stats", action="store_true",
                       help="Show cache statistics and exit")
    args = parser.parse_args()

    # ── cache stats ──
    if args.cache_stats:
        total, last = get_cache_stats()
        print(f"Cache DB: {CACHE_DB}")
        print(f"Cached cookies: {total}")
        print(f"Last full scrape: {last or 'never'}")
        return

    # ── list browsers ──
    if args.list_browsers:
        detected = list_detected_browsers()
        print("Detected browsers:")
        for k in detected:
            print(f"  {k}: {BROWSERS[k]['name']}")
        if not detected:
            print("  (none — no supported browser profiles found)")
        return

    # ── init cache ──
    use_cache = not args.no_cache
    if use_cache:
        init_cache()

    # ── determine browsers ──
    if args.browser and args.browser.lower() != "all":
        keys = [k.strip().lower() for k in args.browser.split(",")]
    else:
        keys = list_detected_browsers()

    if not keys:
        print("[!] No browsers to scrape. Use --browser or ensure profiles exist.", file=sys.stderr)
        sys.exit(1)

    all_cookies = []
    total_decrypted = 0
    any_killed = False

    for key in keys:
        if key not in BROWSERS:
            print(f"[!] Unknown browser: {key}", file=sys.stderr)
            continue
        cfg = BROWSERS[key]
        print(f"[*] Scraping {cfg['name']} ...", file=sys.stderr)

        forced = args.kill and is_browser_running(key)
        if forced:
            kill_browser(key)
            any_killed = True

        if key == "firefox":
            cookies, decrypted = scrape_firefox(key, cfg, use_cache)
        else:
            cookies, decrypted = scrape_chromium(key, cfg, use_cache)

        print(f"[+] {cfg['name']}: {len(cookies)} cookies", file=sys.stderr)
        all_cookies.extend(cookies)
        total_decrypted += decrypted

    if any_killed:
        print("[!] Browser was killed. You may want to reopen it.", file=sys.stderr)

    if use_cache:
        print(f"[*] Cache size: {get_cache_stats()[0]} cookies", file=sys.stderr)

    # ── filters ──
    if args.domain:
        domain = args.domain.lower().lstrip(".")
        all_cookies = [c for c in all_cookies if domain in c["host"]]

    if args.search:
        term = args.search.lower()
        all_cookies = [c for c in all_cookies
                       if term in c["name"].lower() or term in c["value"].lower()]

    # ── output ──
    if args.outfile:
        out = open(args.outfile, "w", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        out = sys.stdout

    try:
        if args.output == "json":
            json.dump(all_cookies, out, indent=2, ensure_ascii=False)
        elif args.output == "csv":
            import csv
            if all_cookies:
                writer = csv.DictWriter(out, fieldnames=all_cookies[0].keys())
                writer.writeheader()
                writer.writerows(all_cookies)
        elif args.output == "netscape":
            out.write(format_netscape(all_cookies))
        else:
            for c in all_cookies:
                out.write(f"[{c['browser']}] {c['host']} — {c['name']} = {c['value'][:120]}\n")
    finally:
        if args.outfile:
            out.close()
            print(f"\n[+] Saved {len(all_cookies)} cookies to {args.outfile}", file=sys.stderr)


if __name__ == "__main__":
    main()
