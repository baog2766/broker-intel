import json, datetime, time, requests

TZ7     = datetime.timezone(datetime.timedelta(hours=7))
NOW     = datetime.datetime.now(TZ7)
TODAY   = NOW.strftime("%Y-%m-%d")
UPDATED = NOW.strftime("%d/%m/%Y %H:%M")

print(f"=== Bat dau: {UPDATED} (ngay {TODAY}) ===")

def sf(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d
def si(v, d=0):
    try: return int(v) if v is not None else d
    except: return d

NAME_MAP = {
    "Ngan hang":"Ngan hang","Tai chinh":"Tai chinh",
    "Bat dong san":"Bat dong san","Nguyen vat lieu":"Nguyen vat lieu",
    "Cong nghiep":"Cong nghiep","Tieu dung":"Tieu dung",
    "Cong nghe":"Cong nghe","Nang luong":"Nang luong",
    "Tien ich":"Tien ich","Y te":"Y te","Vien thong":"Vien thong",
    "Bao hiem":"Bao hiem","Chung khoan":"Chung khoan",
    # English
    "Banks":"Ngan hang","Financial Services":"Tai chinh",
    "Real Estate":"Bat dong san","Materials":"Nguyen vat lieu",
    "Industrials":"Cong nghiep","Consumer Discretionary":"Tieu dung tuy y",
    "Consumer Staples":"Tieu dung thiet yeu","Technology":"Cong nghe",
    "Energy":"Nang luong","Utilities":"Tien ich",
    "Health Care":"Y te","Telecommunication":"Vien thong",
    "Insurance":"Bao hiem","Securities":"Chung khoan",
}

# ================================================================
# VN INDICES — vnstock KBS source (ho tro VNMIDCAP)
# ================================================================
def fetch_vn_indices():
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        result = {}
        yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        for ticker in ["VNINDEX", "VN30", "VNMIDCAP"]:
            try:
                # KBS ho tro tat ca cac index VN
                df = stock.stock(symbol=ticker, source='KBS').quote.history(
                    start=TODAY, end=TODAY, interval='1D'
                )
                if df is None or len(df) == 0:
                    df = stock.stock(symbol=ticker, source='KBS').quote.history(
                        start=yesterday, end=TODAY, interval='1D'
                    )
                if df is None or len(df) == 0:
                    # Fallback VCI cho VNINDEX/VN30
                    if ticker != 'VNMIDCAP':
                        df = stock.stock(symbol=ticker, source='VCI').quote.history(
                            start=TODAY, end=TODAY, interval='1D'
                        )
                        if df is None or len(df) == 0:
                            df = stock.stock(symbol=ticker, source='VCI').quote.history(
                                start=yesterday, end=TODAY, interval='1D'
                            )

                if df is None or len(df) == 0:
                    print(f"  [WARN] {ticker}: no data")
                    continue

                row    = df.iloc[-1]
                close  = sf(row.get('close', 0))
                open_p = sf(row.get('open', close))
                vol    = sf(row.get('volume', 0))
                val    = sf(row.get('value', 0))

                if close < 100:
                    print(f"  [WARN] {ticker} close={close}<100, skip")
                    continue

                change = round(close - open_p, 2)
                pct    = round(change / open_p * 100, 2) if open_p else 0
                vol_m  = round(vol / 1e6, 2)
                val_b  = int(val / 1e9) if val > 1e6 else int(val)
                row_date = str(df.index[-1])[:10]

                result[ticker] = {
                    "value": round(close, 2), "change": change, "pct": pct,
                    "vol": vol_m, "val": val_b, "date": row_date,
                }
                print(f"  {ticker}: {close:.2f} ({pct:+.2f}%) date={row_date}")
                time.sleep(0.5)

            except Exception as e:
                print(f"  [WARN] {ticker}: {e}")
                continue

        return result
    except Exception as e:
        print(f"  [ERROR] fetch_vn: {e}")
        return {}

# ================================================================
# SECTOR INDICES — dung KBS sector index (VNFIN, VNREAL, etc.)
# Lay % thay doi hom nay cua tung nganh tu HOSE sector indices
# ================================================================
def fetch_industry_sector_indices():
    """
    HOSE co cac chi so nganh chinh thuc:
    VNFIN=Tai chinh, VNREAL=BDS, VNIND=CN, VNIT=CNTT
    VNCONS=Tieu dung, VNMAT=NVL, VNENE=NL, VNHEAL=Yte, VNUTI=Tien ich
    """
    SECTOR_INDICES = {
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
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        result = []

        for idx_code, sector_name in SECTOR_INDICES.items():
            try:
                df = stock.stock(symbol=idx_code, source='KBS').quote.history(
                    start=yesterday, end=TODAY, interval='1D'
                )
                if df is None or len(df) < 1:
                    continue

                # Lay 2 phien cuoi de tinh % thay doi
                if len(df) >= 2:
                    curr  = df.iloc[-1]
                    prev  = df.iloc[-2]
                    close = sf(curr.get('close', 0))
                    prev_c= sf(prev.get('close', close))
                    if close > 0 and prev_c > 0:
                        pct = round((close - prev_c) / prev_c * 100, 2)
                    else:
                        pct = 0
                else:
                    curr  = df.iloc[-1]
                    close = sf(curr.get('close', 0))
                    open_p= sf(curr.get('open', close))
                    pct   = round((close - open_p) / open_p * 100, 2) if open_p else 0

                result.append({"name": sector_name, "pct": pct, "up": 0, "dn": 0})
                print(f"  {idx_code} ({sector_name}): {pct:+.2f}%")
                time.sleep(0.3)

            except Exception as e:
                print(f"  [WARN] {idx_code}: {e}")
                continue

        result.sort(key=lambda x: x["pct"], reverse=True)
        if result:
            print(f"  Industry (sector indices): {len(result)} nganh")
            return result

    except Exception as e:
        print(f"  [ERROR] fetch_industry: {e}")

    return None

# ================================================================
# KHOI NGOAI — KBS API truc tiep
# ================================================================
def fetch_foreign():
    # Thu KBS API truc tiep (khong qua proxy)
    KBS_BASE = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"
    try:
        r = requests.get(
            f"{KBS_BASE}/foreign-trading?exchange=HOSE",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=15
        )
        if r.status_code == 200:
            d = r.json()
            items = d if isinstance(d, list) else d.get('data', [])
            if items:
                item = items[0] if isinstance(items, list) else items
                buy  = sf(item.get('buyVal', item.get('buyValue', 0)))
                sell = sf(item.get('sellVal', item.get('sellValue', 0)))
                net  = sf(item.get('netVal', item.get('netValue', 0))) or (buy-sell)
                if abs(buy) > 1e9: buy/=1e9; sell/=1e9; net/=1e9
                elif abs(buy) > 1e6: buy/=1e3; sell/=1e3; net/=1e3
                if abs(net) > 0.001:
                    print(f"  Foreign (KBS): net={net:.0f} ty")
                    return {"net":round(net),"buy":round(buy),"sell":round(sell)}
    except Exception as e:
        print(f"  [WARN] KBS foreign: {e}")

    # Thu vnstock market module
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        # vnstock 3.4+ co market module
        if hasattr(stock, 'market'):
            mkt = stock.market
            for method_name in ['foreign_trading', 'foreign_flow', 'foreign']:
                try:
                    method = getattr(mkt, method_name, None)
                    if method is None: continue
                    df = method()
                    if df is None or len(df) == 0: continue
                    row  = df.iloc[0]
                    buy  = sf(row.get('buyValue', row.get('buy_value', row.get('buyVal', 0))))
                    sell = sf(row.get('sellValue', row.get('sell_value', row.get('sellVal', 0))))
                    net  = sf(row.get('netValue', row.get('net_value', 0))) or (buy-sell)
                    if abs(buy) > 1e9: buy/=1e9; sell/=1e9; net/=1e9
                    if abs(net) > 0.001:
                        print(f"  Foreign (market.{method_name}): net={net:.0f} ty")
                        return {"net":round(net),"buy":round(buy),"sell":round(sell)}
                except: continue
    except Exception as e:
        print(f"  [WARN] vnstock market foreign: {e}")

    print("  [INFO] Foreign: khong co data")
    return None

# ================================================================
# BREADTH — skip, khong co trong vnstock free
# ================================================================
def fetch_breadth():
    print("  Breadth: skip")
    return {"up":0,"nt":0,"dn":0,"ceil":0,"floor":0}

# ================================================================
# MAIN
# ================================================================
try:
    with open("data.json","r",encoding="utf-8") as f: old = json.load(f)
except: old = {}

print("\n--- VN Indices ---")
vn = fetch_vn_indices()
time.sleep(1)

print("\n--- Industry (sector indices) ---")
industry = fetch_industry_sector_indices()
time.sleep(1)

print("\n--- Foreign ---")
fgn = fetch_foreign()
time.sleep(1)

print("\n--- Breadth ---")
breadth = fetch_breadth()

# Merge
vni  = vn.get("VNINDEX")  or old.get("vni",  {})
vn30 = vn.get("VN30")     or old.get("vn30", {})
vnm  = vn.get("VNMIDCAP") or old.get("vnmid",{})
if isinstance(vni, dict) and breadth:
    vni.update(breadth)

old_fgn = old.get("foreign", {})
if fgn and fgn.get("net") not in [None, 0]:
    fgn_final = fgn
elif old_fgn.get("net") not in [None, 0, -240, 1480]:
    fgn_final = old_fgn
else:
    fgn_final = {"net": None, "buy": None, "sell": None}

industry_final = industry if industry else old.get("industry", [])

data = {
    "updated":  UPDATED,
    "vni":      vni, "vn30": vn30, "vnmid": vnm,
    "foreign":  fgn_final,
    "industry": industry_final,
}
with open("data.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open("_snapshot.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

vni_v = vni.get('value','?') if isinstance(vni,dict) else '?'
vni_p = vni.get('pct', 0)   if isinstance(vni,dict) else 0
vni_d = vni.get('date','?')  if isinstance(vni,dict) else '?'
print(f"\n=== XONG! {UPDATED} ===")
print(f"VNINDEX:  {vni_v} ({vni_p:+.2f}%) date={vni_d}")
print(f"VN30:     {vn30.get('value','?') if isinstance(vn30,dict) else '?'}")
print(f"VNMIDCAP: {vnm.get('value','?') if isinstance(vnm,dict) else '?'}")
print(f"Foreign:  {fgn_final}")
print(f"Industry: {len(industry_final)} nganh")
