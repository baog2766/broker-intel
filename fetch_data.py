import json, datetime, requests, time

TZ7 = datetime.timezone(datetime.timedelta(hours=7))
NOW  = datetime.datetime.now(TZ7)
TODAY = NOW.strftime("%Y-%m-%d")          # filter API theo ngày hôm nay
UPDATED = NOW.strftime("%d/%m/%Y %H:%M")

print(f"=== Bat dau fetch: {UPDATED} (ngay {TODAY}) ===")

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://tcinvest.tcbs.com.vn/",
}

def sf(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d

def si(v, d=0):
    try: return int(v) if v is not None else d
    except: return d

NAME_MAP = {
    "Banks":"Ngan hang","Financial Services":"Tai chinh",
    "Real Estate":"Bat dong san","Materials":"Nguyen vat lieu",
    "Industrials":"Cong nghiep","Consumer Discretionary":"Tieu dung tuy y",
    "Consumer Staples":"Tieu dung thiet yeu","Technology":"Cong nghe",
    "Energy":"Nang luong","Utilities":"Tien ich",
    "Health Care":"Y te","Telecommunication":"Vien thong",
    "Insurance":"Bao hiem","Securities":"Chung khoan",
    "BANK":"Ngan hang","FINANCIAL":"Tai chinh",
    "REALESTATE":"Bat dong san","MATERIAL":"Nguyen vat lieu",
    "INDUSTRIAL":"Cong nghiep","CONSUMER":"Tieu dung",
    "TECH":"Cong nghe","ENERGY":"Nang luong",
    "UTILITY":"Tien ich","HEALTH":"Y te",
}

# ================================================================
# VN INDICES — VNDirect finfo-api
# Filter theo ngày hôm nay để không bao giờ lấy data ngày cũ.
# Thử 3 nguồn theo thứ tự ưu tiên.
# ================================================================
def fetch_vn():
    # Nguon 1: VNDirect filter theo fromDate/toDate hôm nay
    urls = [
        # Co filter ngay hom nay — chinh xac nhat
        "https://finfo-api.vndirect.com.vn/v4/stock-prices"
        "?code=VNINDEX,VN30,VNMIDCAP"
        "&sort=date:desc&size=3"
        "&fromDate=" + TODAY + "&toDate=" + TODAY,
        # Fallback khong filter ngay — lay moi nhat
        "https://finfo-api.vndirect.com.vn/v4/stock-prices"
        "?code=VNINDEX,VN30,VNMIDCAP"
        "&sort=date:desc&size=3",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=H, timeout=15)
            r.raise_for_status()
            rows = r.json().get("data", [])
            if not rows:
                print(f"  [WARN] VNDirect tra ve empty, thu URL tiep theo...")
                continue

            result = {}
            for row in rows:
                code = (row.get("code") or "").strip().upper()
                if code not in ["VNINDEX","VN30","VNMIDCAP"]: continue

                row_date = row.get("date","?")

                # --- Parse close ---
                # VNDirect co the tra close=pctChange cho VNMIDCAP
                # Logic: thu tung field, lay cai dau tien > 100
                close = 0
                for field in ["close","adClose","referencePrice","basicPrice","matchPrice"]:
                    v = sf(row.get(field))
                    if v > 100:
                        close = v
                        break

                if close == 0:
                    print(f"  [WARN] {code} khong tim duoc close > 100, skip. row={row}")
                    continue

                # --- Parse pctChange ---
                raw_pct = sf(row.get("pctChange"))
                # Neu |pct| < 0.1 va != 0 → dang decimal (0.0088) → nhan 100
                pct = raw_pct * 100 if (raw_pct != 0 and abs(raw_pct) < 0.1) else raw_pct

                # --- Sanity check pct ---
                # Neu pct bat thuong (vi du >20% hoac <-20%) → tinh lai tu change/close
                change_raw = sf(row.get("change"))
                if abs(pct) > 15 and close > 0:
                    pct = round(change_raw / close * 100, 2)
                    print(f"  [WARN] {code} pct bat thuong {pct:.2f}%, tinh lai tu change")

                result[code] = {
                    "value":  round(close, 2),
                    "change": round(change_raw, 2),
                    "pct":    round(pct, 2),
                    "vol":    round(sf(row.get("nmVolume")) / 1e6, 2),
                    "val":    int(sf(row.get("nmValue")) / 1e9),
                    "date":   row_date,
                }
                print(f"  {code}: {close:.2f} ({pct:+.2f}%) — ngay={row_date}")

            if result:
                # Kiem tra xem co phai data hom nay khong
                for code, v in result.items():
                    if v.get("date","") != TODAY:
                        print(f"  [WARN] {code} date={v['date']} != today={TODAY} — co the la data cu!")
                return result

        except Exception as e:
            print(f"  [ERROR] VNDirect {url[:60]}: {e}")
            continue

    # Nguon 2: TCBS index history (fallback cuoi)
    print("  [FALLBACK] Thu TCBS index history...")
    result = {}
    for ticker in ["VNINDEX","VN30","VNMIDCAP"]:
        try:
            url = (f"https://apipubaws.tcbs.com.vn/stock-insight/v1/index/history"
                   f"?ticker={ticker}&type=index&count=2")
            r = requests.get(url, headers=H, timeout=15)
            r.raise_for_status()
            rows = r.json().get("data",[])
            if not rows: continue
            rows.sort(key=lambda x: x.get("t",0), reverse=True)
            curr = rows[0]
            prev = rows[1] if len(rows) > 1 else rows[0]
            close = sf(curr.get("c") or curr.get("close"))
            if close < 100: continue
            prev_c = sf(prev.get("c") or prev.get("close") or close)
            change = round(close - prev_c, 2)
            pct    = round(change / prev_c * 100, 2) if prev_c else 0
            vol    = round(sf(curr.get("v")) / 1e6, 2)
            # Kiem tra ngay
            ts = curr.get("t",0)
            row_date = datetime.datetime.fromtimestamp(ts, TZ7).strftime("%Y-%m-%d") if ts else "?"
            result[ticker] = {
                "value": round(close,2), "change": change, "pct": pct,
                "vol": vol, "val": 0, "date": row_date,
            }
            print(f"  TCBS {ticker}: {close:.2f} ({pct:+.2f}%) — ngay={row_date}")
        except Exception as e:
            print(f"  [WARN] TCBS {ticker}: {e}")

    return result if result else {}

# ================================================================
# KHOI NGOAI — SSI iBoard -> VNDirect fallback
# ================================================================
def fetch_foreign():
    sources = [
        ("https://iboard-query.ssi.com.vn/v2/stock/foreignTrading/all?exchangeCode=HOSE",
         {**H, "Referer": "https://iboard.ssi.com.vn/"}),
        ("https://finfo-api.vndirect.com.vn/v4/vnmarket/foreign?sort=date:desc&size=1", H),
    ]
    for url, h in sources:
        try:
            r = requests.get(url, headers=h, timeout=15)
            r.raise_for_status()
            d = r.json()
            raw = d.get("data")
            item = raw if isinstance(raw, dict) else (raw[0] if isinstance(raw, list) and raw else None)
            if not item: continue
            buy  = sf(item.get("buyVal") or item.get("buyValue") or item.get("totalBuyValue"))
            sell = sf(item.get("sellVal") or item.get("sellValue") or item.get("totalSellValue"))
            net  = sf(item.get("netVal") or item.get("netValue")) or (buy - sell)
            if abs(buy) > 1e9:   buy/=1e9; sell/=1e9; net/=1e9
            elif abs(buy) > 1e6: buy/=1e3; sell/=1e3; net/=1e3
            if abs(net) < 0.001: continue  # so nho qua → likely loi
            print(f"  Foreign net: {net:.0f} ty (buy={buy:.0f} sell={sell:.0f})")
            return {"net": round(net), "buy": round(buy), "sell": round(sell)}
        except Exception as e:
            print(f"  [WARN] Foreign {url[:50]}: {e}")
    print("  [ERROR] Foreign: all sources fail")
    return None

# ================================================================
# BREADTH — TCBS snapshot
# ================================================================
def fetch_breadth():
    try:
        r = requests.get(
            "https://apipubaws.tcbs.com.vn/stock-insight/v1/index/snapshot",
            headers=H, timeout=15)
        r.raise_for_status()
        items = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        for item in items:
            if (item.get("indexId") or item.get("comGroupCode") or "").upper() == "VNINDEX":
                b = {
                    "up":    si(item.get("advances")),
                    "nt":    si(item.get("noChange")),
                    "dn":    si(item.get("declines")),
                    "ceil":  si(item.get("ceiling")),
                    "floor": si(item.get("floor")),
                }
                print(f"  Breadth: up={b['up']} dn={b['dn']} ceil={b['ceil']} floor={b['floor']}")
                return b
    except Exception as e:
        print(f"  [WARN] Breadth: {e}")
    return {"up":0,"nt":0,"dn":0,"ceil":0,"floor":0}

# ================================================================
# INDUSTRY — TCBS -> VNDirect fallback
# ================================================================
def fetch_industry():
    def normalize(items_raw, name_key, pct_key, up_key=None, dn_key=None):
        result = []
        for item in items_raw:
            name_raw = item.get(name_key) or ""
            name_vn  = NAME_MAP.get(name_raw, name_raw)
            pct = sf(item.get(pct_key) or 0)
            if abs(pct) < 0.1 and pct != 0: pct = pct * 100
            if name_vn:
                result.append({
                    "name": name_vn, "pct": round(pct, 2),
                    "up": si(item.get(up_key) if up_key else 0),
                    "dn": si(item.get(dn_key) if dn_key else 0),
                })
        return sorted(result, key=lambda x: x["pct"], reverse=True)

    # TCBS snapshot
    try:
        r = requests.get(
            "https://apipubaws.tcbs.com.vn/stock-insight/v1/industry/snapshot",
            headers=H, timeout=15)
        r.raise_for_status()
        raw   = r.json()
        items = raw if isinstance(raw, list) else raw.get("data", [])
        for key in ["dayChangePercent","changePercent","pctChange","change","performance"]:
            if items and items[0].get(key) is not None:
                for nk in ["industry","industryName","name"]:
                    result = normalize(items, nk, key, "advances", "declines")
                    if result:
                        print(f"  Industry (TCBS snapshot/{key}): {len(result)} nganh")
                        return result
    except Exception as e:
        print(f"  [WARN] TCBS industry snapshot: {e}")

    # TCBS performance
    for period in ["D","1D","day"]:
        try:
            r = requests.get(
                f"https://apipubaws.tcbs.com.vn/stock-insight/v1/industry/performance?period={period}",
                headers=H, timeout=15)
            r.raise_for_status()
            raw   = r.json()
            items = raw if isinstance(raw, list) else raw.get("data", [])
            if not items: continue
            for key in ["performance","pct","change","dayChangePercent"]:
                for nk in ["industry","name"]:
                    result = normalize(items, nk, key)
                    if result:
                        print(f"  Industry (TCBS perf/{period}): {len(result)} nganh")
                        return result
        except: pass

    # VNDirect fallback
    try:
        r = requests.get(
            "https://finfo-api.vndirect.com.vn/v4/industryStatistics?sort=date:desc&size=20",
            headers=H, timeout=15)
        r.raise_for_status()
        rows = r.json().get("data", [])
        seen, result = set(), []
        for row in rows:
            name_vn = NAME_MAP.get(row.get("industry") or row.get("industryCode") or "","")
            if not name_vn or name_vn in seen: continue
            seen.add(name_vn)
            pct = sf(row.get("pctChange") or row.get("change") or 0)
            if abs(pct) < 0.1 and pct != 0: pct *= 100
            result.append({"name": name_vn, "pct": round(pct,2), "up":0, "dn":0})
        result.sort(key=lambda x: x["pct"], reverse=True)
        if result:
            print(f"  Industry (VNDirect): {len(result)} nganh")
            return result
    except Exception as e:
        print(f"  [WARN] VNDirect industry: {e}")

    print("  [ERROR] Industry: all sources fail")
    return None

# ================================================================
# MAIN
# ================================================================
try:
    with open("data.json","r",encoding="utf-8") as f: old = json.load(f)
except: old = {}

print("\n--- Fetching VN indices ---")
vn = fetch_vn()
time.sleep(1)

print("\n--- Fetching foreign ---")
fgn = fetch_foreign()
time.sleep(1)

print("\n--- Fetching breadth ---")
breadth = fetch_breadth()
time.sleep(1)

print("\n--- Fetching industry ---")
industry = fetch_industry()

# Merge — chi giu data hom nay, fallback sang cu neu loi
vni  = vn.get("VNINDEX")  or old.get("vni",  {})
vn30 = vn.get("VN30")     or old.get("vn30", {})
vnm  = vn.get("VNMIDCAP") or old.get("vnmid",{})

# Gan breadth vao VNINDEX
if isinstance(vni, dict) and breadth:
    vni.update(breadth)

# Foreign: chi dung so that, khong dung demo
old_fgn = old.get("foreign", {})
if fgn and fgn.get("net") not in [None, 0]:
    fgn_final = fgn
elif old_fgn.get("net") not in [None, 0, -240, 1480]:
    fgn_final = old_fgn  # giu ngay truoc neu co so that
else:
    fgn_final = {"net": None, "buy": None, "sell": None}

industry_final = industry if industry else old.get("industry", [])

data = {
    "updated":  UPDATED,
    "vni":      vni,
    "vn30":     vn30,
    "vnmid":    vnm,
    "foreign":  fgn_final,
    "industry": industry_final,
}

with open("data.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Snapshot cho gen_broker_take.py
with open("_snapshot.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n=== XONG! data.json cap nhat luc {UPDATED} ===")
print(f"VNINDEX:  {vni.get('value')} ({vni.get('pct'):+.2f}%) — ngay={vni.get('date','?')}")
print(f"VN30:     {vn30.get('value')} ({vn30.get('pct'):+.2f}%) — ngay={vn30.get('date','?')}")
print(f"VNMIDCAP: {vnm.get('value')} ({vnm.get('pct'):+.2f}%) — ngay={vnm.get('date','?')}")
print(f"Foreign:  {fgn_final}")
print(f"Industry: {len(industry_final)} nganh")
