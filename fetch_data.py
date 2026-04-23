import json, datetime, time

TZ7 = datetime.timezone(datetime.timedelta(hours=7))
NOW  = datetime.datetime.now(TZ7)
TODAY     = NOW.strftime("%Y-%m-%d")
UPDATED   = NOW.strftime("%d/%m/%Y %H:%M")

print(f"=== Bat dau: {UPDATED} (ngay {TODAY}) ===")

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
}

# ================================================================
# VN INDICES — dung vnstock (khong bi block)
# ================================================================
def fetch_vn_vnstock():
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        result = {}
        for ticker in ["VNINDEX", "VN30", "VNMIDCAP"]:
            try:
                df = stock.stock(symbol=ticker, source='VCI').quote.history(
                    start=TODAY, end=TODAY, interval='1D'
                )
                if df is None or len(df) == 0:
                    # Thu ngay hom qua neu chua co data (sau gio dong cua)
                    yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    df = stock.stock(symbol=ticker, source='VCI').quote.history(
                        start=yesterday, end=TODAY, interval='1D'
                    )
                if df is None or len(df) == 0:
                    print(f"  [WARN] vnstock {ticker}: no data")
                    continue

                row = df.iloc[-1]
                close  = sf(row.get('close', 0))
                open_p = sf(row.get('open', close))
                high   = sf(row.get('high', close))
                low    = sf(row.get('low', close))
                vol    = sf(row.get('volume', 0))
                val    = sf(row.get('value', 0))

                if close < 100:
                    print(f"  [WARN] {ticker} close={close} < 100, skip")
                    continue

                change = round(close - open_p, 2)
                pct    = round(change / open_p * 100, 2) if open_p else 0
                vol_m  = round(vol / 1e6, 2)
                val_b  = int(val / 1e9) if val > 1e6 else int(val)

                # Lay ngay tu index cua df
                row_date = str(df.index[-1])[:10] if hasattr(df.index[-1], '__str__') else TODAY

                result[ticker] = {
                    "value":  round(close, 2),
                    "change": change,
                    "pct":    pct,
                    "vol":    vol_m,
                    "val":    val_b,
                    "date":   row_date,
                }
                print(f"  {ticker}: {close:.2f} ({pct:+.2f}%) vol={vol_m}M date={row_date}")
                time.sleep(0.5)

            except Exception as e:
                print(f"  [WARN] vnstock {ticker}: {e}")
                continue

        return result

    except ImportError:
        print("  [ERROR] vnstock chua duoc cai dat")
        return {}
    except Exception as e:
        print(f"  [ERROR] vnstock: {e}")
        return {}

# ================================================================
# BREADTH — dung vnstock market breadth
# ================================================================
def fetch_breadth_vnstock():
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        # Thu lay breadth tu market overview
        try:
            df = stock.trading.price_board(['VNINDEX'])
            if df is not None and len(df) > 0:
                row = df.iloc[0]
                b = {
                    "up":    si(row.get('advances', row.get('adv', 0))),
                    "nt":    si(row.get('noChange', row.get('nc', 0))),
                    "dn":    si(row.get('declines', row.get('dec', 0))),
                    "ceil":  si(row.get('ceiling', 0)),
                    "floor": si(row.get('floor', 0)),
                }
                print(f"  Breadth: up={b['up']} dn={b['dn']}")
                return b
        except: pass

        # Fallback: dem so ma tang giam tu VN30
        try:
            symbols = stock.listing.symbols_by_group('VN30')
            if symbols and len(symbols) > 0:
                df2 = stock.trading.price_board(symbols[:30])
                if df2 is not None and len(df2) > 0:
                    # Tim cot pct change
                    for col in ['priceChange', 'pctChange', 'change_pct', 'matchedPrice']:
                        if col in df2.columns:
                            up = int((df2[col] > 0).sum())
                            dn = int((df2[col] < 0).sum())
                            nt = int((df2[col] == 0).sum())
                            print(f"  Breadth (VN30): up={up} dn={dn} nt={nt}")
                            return {"up":up,"nt":nt,"dn":dn,"ceil":0,"floor":0}
        except: pass

    except Exception as e:
        print(f"  [WARN] Breadth: {e}")

    return {"up":0,"nt":0,"dn":0,"ceil":0,"floor":0}

# ================================================================
# KHOI NGOAI — dung vnstock foreign trading
# ================================================================
def fetch_foreign_vnstock():
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        try:
            df = stock.trading.foreign_trading(exchange='HOSE')
            if df is not None and len(df) > 0:
                row = df.iloc[0] if hasattr(df, 'iloc') else df
                buy  = sf(row.get('buyVal', row.get('buy_value', row.get('foreignBuyValue', 0))))
                sell = sf(row.get('sellVal', row.get('sell_value', row.get('foreignSellValue', 0))))
                net  = sf(row.get('netVal', row.get('net_value', row.get('foreignNetValue', 0)))) or (buy - sell)
                # Chuan hoa don vi → ty dong
                if abs(buy) > 1e9:   buy/=1e9; sell/=1e9; net/=1e9
                elif abs(buy) > 1e6: buy/=1e3; sell/=1e3; net/=1e3
                if abs(net) > 0.001:
                    print(f"  Foreign net: {net:.0f} ty")
                    return {"net":round(net),"buy":round(buy),"sell":round(sell)}
        except Exception as e:
            print(f"  [WARN] vnstock foreign: {e}")
    except Exception as e:
        print(f"  [WARN] Foreign: {e}")
    return None

# ================================================================
# INDUSTRY — dung vnstock
# ================================================================
def fetch_industry_vnstock():
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        try:
            df = stock.trading.industry_performance()
            if df is not None and len(df) > 0:
                result = []
                for _, row in df.iterrows():
                    name_raw = str(row.get('industry', row.get('sector', row.get('name', ''))))
                    name_vn  = NAME_MAP.get(name_raw, name_raw)
                    pct = sf(row.get('pctChange', row.get('change', row.get('performance', 0))))
                    if abs(pct) < 0.1 and pct != 0: pct *= 100
                    if name_vn:
                        result.append({"name": name_vn, "pct": round(pct,2), "up":0, "dn":0})
                result.sort(key=lambda x: x["pct"], reverse=True)
                if result:
                    print(f"  Industry (vnstock): {len(result)} nganh")
                    return result
        except Exception as e:
            print(f"  [WARN] vnstock industry: {e}")
    except Exception as e:
        print(f"  [WARN] Industry: {e}")
    return None

# ================================================================
# MAIN
# ================================================================
try:
    with open("data.json","r",encoding="utf-8") as f: old = json.load(f)
except: old = {}

print("\n--- Fetching VN indices (vnstock) ---")
vn = fetch_vn_vnstock()
time.sleep(1)

print("\n--- Fetching breadth ---")
breadth = fetch_breadth_vnstock()
time.sleep(1)

print("\n--- Fetching foreign ---")
fgn = fetch_foreign_vnstock()
time.sleep(1)

print("\n--- Fetching industry ---")
industry = fetch_industry_vnstock()

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
    "vni":      vni,
    "vn30":     vn30,
    "vnmid":    vnm,
    "foreign":  fgn_final,
    "industry": industry_final,
}

with open("data.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open("_snapshot.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n=== XONG! {UPDATED} ===")
vni_val = vni.get('value','?') if isinstance(vni, dict) else '?'
vni_pct = vni.get('pct', 0) if isinstance(vni, dict) else 0
vni_date = vni.get('date','?') if isinstance(vni, dict) else '?'
vn30_val = vn30.get('value','?') if isinstance(vn30, dict) else '?'
vnm_val  = vnm.get('value','?') if isinstance(vnm, dict) else '?'
print(f"VNINDEX:  {vni_val} ({vni_pct:+.2f}%) ngay={vni_date}")
print(f"VN30:     {vn30_val}")
print(f"VNMIDCAP: {vnm_val}")
print(f"Foreign:  {fgn_final}")
print(f"Industry: {len(industry_final)} nganh")
