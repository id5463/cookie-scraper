---
name: cookie-scraper
description: "浠庢湰鍦版祻瑙堝櫒涓閲忔彁鍙?Cookie锛圕hrome/Edge/Brave/Firefox锛夛紝鏈湴缂撳瓨 + 澧為噺瑙ｅ瘑锛岄娆″叏閲忓悗缁绾э紝杈撳嚭 text/json/csv/netscape 鏍煎紡銆?
version: "2.0.0"
---

# cookie-scraper

浠庢湰鏈烘祻瑙堝櫒鎶撳彇 Cookie锛?*棣栨鍏ㄩ噺瑙ｅ瘑 + 鏈湴缂撳瓨锛屽悗缁繍琛屽彧瑙ｅ瘑鍙樻洿鐨?Cookie**銆?
## 浣曟椂浣跨敤

- 闇€瑕?*鎻愬彇鏌愪釜鍩熷悕鐨?Cookie** 鐢ㄤ簬 curl/wget 璇锋眰
- 闇€瑕?*鏌ユ壘鍖呭惈鐗瑰畾鍏抽敭瀛楃殑 Cookie**锛堝 token銆乻ession銆乤uth锛?- 闇€瑕?*澶囦唤娴忚鍣?Cookie** 鍒?netscape 鏍煎紡
- 闇€瑕?*鍒嗘瀽娴忚鍣ㄤ腑瀛樹簡鍝簺缃戠珯鐨?Cookie**

## 宸ュ叿

### cookie_scraper.py 鈥?澧為噺 Cookie 鎻愬彇鍣?
```bash
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py [options]
```

**甯哥敤鍙傛暟:**

| 鍙傛暟 | 璇存槑 |
|------|------|
| `--browser chrome` | 鍙姄鍙?Chrome |
| `--browser chrome,edge,firefox` | 鎶撳彇澶氫釜娴忚鍣?|
| `--browser all` | 鎵€鏈夋娴嬪埌鐨勬祻瑙堝櫒锛堥粯璁わ級 |
| `--domain example.com` | 鎸夊煙鍚嶈繃婊?|
| `--search token` | 鎼滅储 Cookie 鍚嶆垨鍊?|
| `-o text` | 鏂囨湰鏍煎紡锛堥粯璁わ級 |
| `-o json` | JSON 鏍煎紡 |
| `-o csv` | CSV 鏍煎紡 |
| `-o netscape` | Netscape 鏍煎紡锛坈url/wget 鍏煎锛?|
| `-f cookies.txt` | 杈撳嚭鍒版枃浠?|
| `--list-browsers` | 鍒楀嚭鏈満鍙姄鍙栫殑娴忚鍣?|
| `--kill` | 寮哄埗鍏抽棴娴忚鍣ㄤ互瑙ｉ攣鏁版嵁搴?|
| `--no-cache` | 璺宠繃缂撳瓨锛屽己鍒跺叏閮ㄩ噸鏂拌В瀵?|
| `--cache-stats` | 鏌ョ湅缂撳瓨缁熻 |

**绀轰緥:**

```bash
# 鍒楀嚭鎵€鏈夋祻瑙堝櫒
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py --list-browsers

# 鎶撳彇鎵€鏈夋祻瑙堝櫒鐨勬墍鏈?Cookie锛堥娆″叏閲忥紝鍚庣画澧為噺锛?C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py

# 鍙姄鍙?Chrome 涓?github.com 鐨?Cookie锛岃緭鍑?netscape 鏍煎紡
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py --browser chrome --domain github.com -o netscape -f github.cookies

# 鎼滅储鍖呭惈 "session" 鐨?Cookie
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py --search session -o json

# 鏌ョ湅缂撳瓨缁熻
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py --cache-stats

# 寮哄埗鍏ㄩ噺閲嶆柊瑙ｅ瘑锛堜笉浣跨敤缂撳瓨锛?C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe scripts/cookie_scraper.py --no-cache -o json
```

## 鍏稿瀷宸ヤ綔娴?
1. **棣栨**: `cookie_scraper.py --kill` 鈫?鍏ㄩ噺瑙ｅ瘑鎵€鏈?Cookie锛屽瓨鍏ユ湰鍦扮紦瀛?2. **鍚庣画**: `cookie_scraper.py` 鈫?绉掔骇瀹屾垚锛屽彧瑙ｅ瘑鏂板/鍙樻洿鐨?Cookie
3. `--browser chrome --domain example.com` 杩囨护鐩爣鍩熷悕
4. 杈撳嚭 netscape 鏍煎紡渚?curl/wget 浣跨敤

## 缂撳瓨鏈哄埗

- 缂撳瓨浣嶇疆: `%LOCALAPPDATA%\cookie-scraper\cookies.db`
- 姣忎釜 Cookie 鎸?`(browser, host, name, path)` 鍞竴鏍囪瘑
- 閫氳繃 SHA256 姣旇緝鍔犲瘑鍊硷紝鍙湁鍙樻洿鐨勬墠閲嶆柊瑙ｅ瘑
- 棣栨: ~2313 娆?AES-GCM 瑙ｅ瘑锛涘悗缁? 0~鍑犲崄娆?
## 鏀寔鐨勬祻瑙堝櫒

| 娴忚鍣?| Key | 鍔犲瘑 | 鐘舵€?|
|--------|-----|------|------|
| Google Chrome | `chrome` | AES-256-GCM + DPAPI | 鏀寔瑙ｅ瘑 |
| Microsoft Edge | `edge` | AES-256-GCM + DPAPI | 鏀寔瑙ｅ瘑 |
| Brave | `brave` | AES-256-GCM + DPAPI | 鏀寔瑙ｅ瘑 |
| Chromium | `chromium` | AES-256-GCM + DPAPI | 鏀寔瑙ｅ瘑 |
| Mozilla Firefox | `firefox` | 鏄庢枃瀛樺偍 | 鐩存帴璇诲彇 |

## 渚濊禆

```bash
C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe -m pip install -r scripts/requirements.txt
```

## 璁稿彲

MIT
