# cookie-scraper

Incremental browser cookie extractor for Windows — Chrome, Edge, Brave, Chromium, Firefox.

First run: full AES-256-GCM decrypt + cache. Subsequent runs: only decrypt changed cookies (SHA256 diff).

## Quick Start

```bash
# Install dependencies (Python 3.13 required for pycryptodome + pywin32)
pip install -r scripts/requirements.txt

# List detected browsers
python scripts/cookie_scraper.py --list-browsers

# Scrape all cookies (use --kill if browser is running)
python scripts/cookie_scraper.py --kill

# Filter by domain, output netscape for curl/wget
python scripts/cookie_scraper.py --browser chrome --domain github.com -o netscape -f github.cookies

# Incremental (cache hits skip decryption)
python scripts/cookie_scraper.py --browser chrome -o json

# Cache stats
python scripts/cookie_scraper.py --cache-stats
```

## How It Works

| Step | Description |
|------|-------------|
| Read | Copy Chrome's locked SQLite DB (subprocess / powershell / raw read fallback) |
| Hash | SHA256 each cookie's encrypted blob |
| Cache | Look up (browser, host, name, path) in `%LOCALAPPDATA%\cookie-scraper\cookies.db` |
| Skip | Hash match → reuse cached plaintext (0 AES-GCM) |
| Decrypt | Hash mismatch or new → DPAPI unlock key → AES-256-GCM decrypt → update cache |

## Output Formats

- `text` — one line per cookie
- `json` — full structured dump
- `csv` — spreadsheet-ready
- `netscape` — curl / wget compatible cookie jar

## Supported Browsers

| Browser | Key | Encryption |
|---------|-----|-----------|
| Google Chrome | `chrome` | AES-256-GCM + DPAPI |
| Microsoft Edge | `edge` | AES-256-GCM + DPAPI |
| Brave | `brave` | AES-256-GCM + DPAPI |
| Chromium | `chromium` | AES-256-GCM + DPAPI |
| Mozilla Firefox | `firefox` | Plaintext |

## Requirements

- Windows (DPAPI via pywin32)
- Python 3.13+ with `pycryptodome`, `pywin32`
- Browser data dirs at their default paths

## License

MIT
