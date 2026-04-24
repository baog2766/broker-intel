import json, datetime, time, requests

TZ7     = datetime.timezone(datetime.timedelta(hours=7))
NOW     = datetime.datetime.now(TZ7)
TODAY   = NOW.strftime("%Y-%m-%d")
UPDATED = NOW.strftime("%d/%m/%Y %H:%M")

print(f"=== Bat dau: {UPDATED} (ngay {TODAY}) ===")

H_KBS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Origin": "https://kbsec.com.vn",
    "Referer": "https://kbsec.com.vn/",
}
KBS = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"

def sf(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d
def si(v, d=0):
    try: return int(v) if v is not None else d
    except: return d

# ================================================================
# VN INDICES — KBS API truc tiep
# Endpoint: /index/{symbol}/data_D (lich su ngay)
# ================================================================
def fetch_vn_indices():
    result = {}
    # Map ticker → KBS index code
    TICKERS = {
        "VNINDEX": "VNIndex",
        "VN30":    "VN30",
        "VNMIDCAP":"VNMID",   # KBS dung VNMID
    }
    yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    for ticker, kbs_code in TICKERS.items():
        try:
            url = f"{KBS}/index/{kbs_code}/data_D"
            r = requests.get(url, headers=H_KBS, timeout=15)
            if r.status_code != 200:
                print(f"  [WARN] {ticker} KBS status={r.status_code}")
                continue
            d = r.json()
            rows = d.get("data_day", d.get("data", d if isinstance(d, list) else []))
            if not rows:
                print(f"  [WARN] {ticker} KBS empty")
                continue

            # Lay row moi nhat
            rows_sorted = sorted(rows, key=lambda x: x.get("t",""), reverse=True)
            curr = rows_sorted[0]
            prev = rows_sorted[1] if len(rows_sorted) > 1 else curr

            close  = sf(curr.get("c", curr.get("close", 0)))
            open_p = sf(curr.get("o", curr.get("open", close)))
            vol    = sf(curr.get("v", curr.get("volume", 0)))
            row_date = str(curr.get("t",""))[:10]

            # KBS co the tra decimal (1.87 = 1870) → nhan 1000
            if close < 100 and close > 0:
                close  *= 1000
                open_p *= 1000

            if close < 100:
                print(f"  [WARN] {ticker} close={close}<100 sau xu ly")
                continue

            # Lay prev close de tinh change
            prev_close = sf(prev.get("c", prev.get("close", open_p)))
            if prev_close < 100 and prev_close > 0:
                prev_close *= 1000

            change = round(close - prev_close, 2)
            pct    = round(change / prev_close * 100, 2) if prev_close else 0
            vol_m  = round(vol / 1e6, 2)

            result[ticker] = {
                "value": round(close, 2), "change": change, "pct": pct,
                "vol": vol_m, "val": 0, "date": row_date,
            }
            print(f"  {ticker}: {close:.2f} ({pct:+.2f}%) date={row_date}")

        except Exception as e:
            print(f"  [WARN] {ticker} KBS direct: {e}")

    # Fallback vnstock VCI cho bat ky ticker nao con thieu
    missing = [t for t in ["VNINDEX","VN30","VNMIDCAP"] if t not in result]
    if missing:
        print(f"  Fallback vnstock VCI cho: {missing}")
        try:
            from vnstock import Vnstock
            stock = Vnstock()
            for ticker in missing:
                try:
                    df = stock.stock(symbol=ticker, source='VCI').quote.history(
                        start=TODAY, end=TODAY, interval='1D'
                    )
                    if df is None or len(df) == 0:
                        yesterday2 = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                        df = stock.stock(symbol=ticker, source='VCI').quote.history(
                            start=yesterday2, end=TODAY, interval='1D'
                        )
                    if df is None or len(df) == 0: continue
                    row    = df.iloc[-1]
                    close  = sf(row.get('close', 0))
                    open_p = sf(row.get('open', close))
                    # VCI tra decimal → nhan 1000
                    if close < 100 and close > 0:
                        close  *= 1000
                        open_p *= 1000
                    if close < 100: continue
                    vol   = sf(row.get('volume', 0))
                    change = round(close - open_p, 2)
                    pct    = round(change / open_p * 100, 2) if open_p else 0
                    result[ticker] = {
                        "value": round(close,2), "change": change, "pct": pct,
                        "vol": round(vol/1e6,2), "val": 0,
                        "date": str(df.index[-1])[:10],
                    }
                    print(f"  {ticker} (VCI fallback): {close:.2f} ({pct:+.2f}%)")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  [WARN] {ticker} VCI: {e}")
        except Exception as e:
            print(f"  [WARN] vnstock fallback: {e}")

    return result

# ================================================================
# INDUSTRY — KBS sector index API truc tiep
# Endpoint: /index/{sector_code}/data_D
# ================================================================
def fetch_industry():
    SECTOR_MAP = {
        "VNFIN":  "Tai chinh",
        "VNREAL": "Bat dong san",
        "VNIND":  "Cong nghiep",
        "VNIT":   "Cong nghe",
        "VNCONS": "Tieu dung",
        "VNMAT":  "Nguyen vat lieu",
        "VNENE":  "Nang luong",
        "VNHEAL": "Y te",
        "VNUTI":  "Tien ich",
    }
    result = []
    for code, name in SECTOR_MAP.items():
        try:
            url = f"{KBS}/index/{code}/data_D"
            r = requests.get(url, headers=H_KBS, timeout=10)
            if r.status_code != 200:
                print(f"  [WARN] {code} status={r.status_code}")
                continue
            d = r.json()
            rows = d.get("data_day", d.get("data", d if isinstance(d, list) else []))
            if not rows or len(rows) < 2:
                print(f"  [WARN] {code} insufficient data ({len(rows) if rows else 0} rows)")
                continue

            rows_sorted = sorted(rows, key=lambda x: x.get("t",""), reverse=True)
            curr = rows_sorted[0]
            prev = rows_sorted[1]
            c = sf(curr.get("c", curr.get("close", 0)))
            p = sf(prev.get("c", prev.get("close", c)))
            if c < 1 and c > 0: c *= 1000
            if p < 1 and p > 0: p *= 1000
            pct = round((c - p) / p * 100, 2) if p > 0 else 0
            result.append({"name": name, "pct": pct, "up": 0, "dn": 0})
            print(f"  {code} ({name}): {pct:+.2f}%")
            time.sleep(0.2)
        except Exception as e:
            print(f"  [WARN] {code}: {e}")

    result.sort(key=lambda x: x["pct"], reverse=True)
    return result if result else None

# ================================================================
# KHOI NGOAI — KBS foreign trading API
# ================================================================
def fetch_foreign():
    endpoints = [
        f"{KBS}/foreign-trading?exchange=HOSE",
        f"{KBS}/foreign-trading/HOSE",
        f"{KBS}/market/foreign-trading",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=H_KBS, timeout=10)
            if r.status_code != 200: continue
            d = r.json()
            items = d if isinstance(d, list) else d.get('data', [d])
            if not items: continue
            item = items[0] if isinstance(items, list) else items
            buy  = sf(item.get('buyVal', item.get('buyValue', item.get('totalBuy', 0))))
            sell = sf(item.get('sellVal', item.get('sellValue', item.get('totalSell', 0))))
            net  = sf(item.get('netVal', item.get('netValue', item.get('net', 0)))) or (buy-sell)
            if abs(buy) > 1e9: buy/=1e9; sell/=1e9; net/=1e9
            elif abs(buy) > 1e6: buy/=1e3; sell/=1e3; net/=1e3
            if abs(net) > 0.001:
                print(f"  Foreign (KBS): net={net:.0f} ty")
                return {"net":round(net),"buy":round(buy),"sell":round(sell)}
        except Exception as e:
            print(f"  [WARN] {url[:50]}: {e}")

    # Fallback SSI qua requests truc tiep (khong proxy)
    try:
        r = requests.get(
            "https://iboard-query.ssi.com.vn/v2/stock/foreignTrading/all?exchangeCode=HOSE",
            headers={**H_KBS, "Referer":"https://iboard.ssi.com.vn/"},
            timeout=10
        )
        if r.status_code == 200:
            d = r.json()
            raw = d.get("data")
            item = raw if isinstance(raw, dict) else (raw[0] if isinstance(raw,list) and raw else None)
            if item:
                buy  = sf(item.get("buyVal", item.get("buyValue", 0)))
                sell = sf(item.get("sellVal", item.get("sellValue", 0)))
                net  = sf(item.get("netVal", item.get("netValue", 0))) or (buy-sell)
                if abs(buy) > 1e9: buy/=1e9; sell/=1e9; net/=1e9
                elif abs(buy) > 1e6: buy/=1e3; sell/=1e3; net/=1e3
                if abs(net) > 0.001:
                    print(f"  Foreign (SSI direct): net={net:.0f} ty")
                    return {"net":round(net),"buy":round(buy),"sell":round(sell)}
    except Exception as e:
        print(f"  [WARN] SSI direct: {e}")

    print("  [INFO] Foreign: khong co data")
    return None

# ================================================================
# MAIN
# ================================================================
try:
    with open("data.json","r",encoding="utf-8") as f: old = json.load(f)
except: old = {}

print("\n--- VN Indices ---")
vn = fetch_vn_indices()
time.sleep(1)

print("\n--- Industry ---")
industry = fetch_industry()
time.sleep(1)

print("\n--- Foreign ---")
fgn = fetch_foreign()

# Merge
vni  = vn.get("VNINDEX")  or old.get("vni",  {})
vn30 = vn.get("VN30")     or old.get("vn30", {})
vnm  = vn.get("VNMIDCAP") or old.get("vnmid",{})
breadth = {"up":0,"nt":0,"dn":0,"ceil":0,"floor":0}
if isinstance(vni, dict): vni.update(breadth)

old_fgn = old.get("foreign", {})
if fgn and fgn.get("net") not in [None, 0]:
    fgn_final = fgn
elif old_fgn.get("net") not in [None, 0, -240, 1480]:
    fgn_final = old_fgn
else:
    fgn_final = {"net": None, "buy": None, "sell": None}

industry_final = industry if industry else old.get("industry", [])

data = {
    "updated": UPDATED,
    "vni": vni, "vn30": vn30, "vnmid": vnm,
    "foreign": fgn_final, "industry": industry_final,
}
with open("data.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open("_snapshot.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

vni_v = vni.get('value','?') if isinstance(vni,dict) else '?'
vni_p = vni.get('pct',0)    if isinstance(vni,dict) else 0
vni_d = vni.get('date','?') if isinstance(vni,dict) else '?'
print(f"\n=== XONG! {UPDATED} ===")
print(f"VNINDEX:  {vni_v} ({vni_p:+.2f}%) date={vni_d}")
print(f"VN30:     {vn30.get('value','?') if isinstance(vn30,dict) else '?'}")
print(f"VNMIDCAP: {vnm.get('value','?') if isinstance(vnm,dict) else '?'}")
print(f"Foreign:  {fgn_final}")
print(f"Industry: {len(industry_final)} nganh")
