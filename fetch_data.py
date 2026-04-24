import json, datetime, time, requests, math

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

# ================================================================
# OHLCV — lay 120 phien lich su tu vnstock VCI
# ================================================================
def fetch_ohlcv(ticker, n=120):
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        end   = TODAY
        start = (NOW - datetime.timedelta(days=n*2)).strftime("%Y-%m-%d")
        df = stock.stock(symbol=ticker, source='VCI').quote.history(
            start=start, end=end, interval='1D'
        )
        if df is None or len(df) == 0:
            print(f"  [WARN] {ticker} OHLCV: no data")
            return None

        # Chuan hoa columns
        col_map = {
            'open':'o','high':'h','low':'l','close':'c','volume':'v','value':'val'
        }
        df = df.rename(columns={k:v for k,v in col_map.items() if k in df.columns})

        # Fix decimal issue (VCI tra decimal cho index)
        if df['c'].mean() < 100 and df['c'].mean() > 0:
            for col in ['o','h','l','c']:
                if col in df.columns:
                    df[col] = df[col] * 1000

        # Lay n phien gan nhat
        df = df.tail(n)
        closes  = list(df['c'].astype(float))
        opens   = list(df['o'].astype(float)) if 'o' in df.columns else closes
        highs   = list(df['h'].astype(float)) if 'h' in df.columns else closes
        lows    = list(df['l'].astype(float)) if 'l' in df.columns else closes
        volumes = list(df['v'].astype(float)) if 'v' in df.columns else [0]*len(closes)
        dates   = [str(d)[:10] for d in df.index]

        print(f"  {ticker} OHLCV: {len(closes)} phien, close[-1]={closes[-1]:.2f}")
        return {"dates":dates, "opens":opens, "highs":highs, "lows":lows,
                "closes":closes, "volumes":volumes}

    except Exception as e:
        print(f"  [ERROR] {ticker} OHLCV: {e}")
        return None

# ================================================================
# INDICATORS — tinh toan thuan Python, khong can thu vien ngoai
# ================================================================
def calc_ma(closes, n):
    if len(closes) < n: return None
    return round(sum(closes[-n:]) / n, 2)

def calc_ema(closes, n):
    if len(closes) < n: return None
    k = 2 / (n + 1)
    ema = sum(closes[:n]) / n
    for c in closes[n:]:
        ema = c * k + ema * (1 - k)
    return round(ema, 2)

def calc_rsi(closes, n=14):
    if len(closes) < n + 1: return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n-1) + gains[i]) / n
        avg_loss = (avg_loss * (n-1) + losses[i]) / n
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def calc_bb(closes, n=20, k=2):
    if len(closes) < n: return None
    window = closes[-n:]
    mean   = sum(window) / n
    std    = math.sqrt(sum((c - mean)**2 for c in window) / n)
    return {
        "upper": round(mean + k * std, 2),
        "mid":   round(mean, 2),
        "lower": round(mean - k * std, 2),
        "width": round((4 * k * std) / mean * 100, 2),  # % of price
    }

def calc_atr(highs, lows, closes, n=14):
    if len(closes) < n + 1: return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i]  - closes[i-1])
        )
        trs.append(tr)
    if len(trs) < n: return None
    atr = sum(trs[:n]) / n
    for tr in trs[n:]:
        atr = (atr * (n-1) + tr) / n
    return round(atr, 2)

def calc_vma(volumes, n):
    if len(volumes) < n: return None
    return round(sum(volumes[-n:]) / n / 1e6, 2)  # trieu cp

def trend_label(close, ma):
    if ma is None: return "N/A"
    diff_pct = (close - ma) / ma * 100
    if diff_pct > 1.5: return "TANG"
    if diff_pct < -1.5: return "GIAM"
    return "NGANG"

def sr_levels(highs, lows, closes, n=50):
    """Tim vung ho tro / khang cu tu local min/max"""
    if len(closes) < 10: return [], []
    window = min(n, len(closes))
    h = highs[-window:]
    l = lows[-window:]
    c = closes[-window:]
    curr = closes[-1]

    # Tim local max (khang cu)
    resistance = []
    for i in range(2, len(h)-2):
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            if h[i] > curr * 1.002:  # chi lay muc tren gia hien tai
                resistance.append(round(h[i], 2))

    # Tim local min (ho tro)
    support = []
    for i in range(2, len(l)-2):
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            if l[i] < curr * 0.998:  # chi lay muc duoi gia hien tai
                support.append(round(l[i], 2))

    # Sort va lay gan nhat
    resistance.sort()
    support.sort(reverse=True)
    return support[:3], resistance[:3]

# ================================================================
# TECHNICAL ANALYSIS — tong hop
# ================================================================
def calc_technical(ohlcv):
    if not ohlcv: return {}
    closes  = ohlcv["closes"]
    highs   = ohlcv["highs"]
    lows    = ohlcv["lows"]
    volumes = ohlcv["volumes"]
    curr    = closes[-1]

    # MAs
    ma5   = calc_ma(closes, 5)
    ma10  = calc_ma(closes, 10)
    ma20  = calc_ma(closes, 20)
    ma50  = calc_ma(closes, 50)
    ma100 = calc_ma(closes, 100)
    ema20 = calc_ema(closes, 20)

    # RSI
    rsi14 = calc_rsi(closes, 14)

    # Bollinger Bands (20,2)
    bb = calc_bb(closes, 20, 2)

    # ATR
    atr14 = calc_atr(highs, lows, closes, 14)

    # Volume MAs
    vma10 = calc_vma(volumes, 10)
    vma20 = calc_vma(volumes, 20)
    vol_today = round(volumes[-1] / 1e6, 2) if volumes else 0

    # Volume divergence: gia tang nhung KL giam = phan ky am
    price_chg_5d = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0
    vol_chg_5d   = (volumes[-1] - volumes[-6]) / volumes[-6] * 100 if len(volumes) > 5 and volumes[-6] > 0 else 0
    vol_div = "NEGATIVE" if price_chg_5d > 1 and vol_chg_5d < -10 else \
              "POSITIVE" if price_chg_5d > 1 and vol_chg_5d > 10  else "NEUTRAL"

    # Xu huong
    trend_short = trend_label(curr, ma10)
    trend_mid   = trend_label(curr, ma50)
    trend_long  = trend_label(curr, ma100) if ma100 else "N/A"

    # Ho tro / Khang cu
    support_dyn, resist_dyn = sr_levels(highs, lows, closes, 60)

    # Them MA lam muc S/R
    sr_from_ma = {}
    if ma20:  sr_from_ma[f"MA20={ma20}"] = ma20
    if ma50:  sr_from_ma[f"MA50={ma50}"] = ma50
    if ma100: sr_from_ma[f"MA100={ma100}"] = ma100

    # Bollinger S/R
    if bb:
        if bb["upper"] > curr: resist_dyn.insert(0, bb["upper"])
        if bb["lower"] < curr: support_dyn.insert(0, bb["lower"])

    # Dedup va sort
    resist_dyn = sorted(list(set([r for r in resist_dyn if r > curr]))[:3])
    support_dyn = sorted(list(set([s for s in support_dyn if s < curr])), reverse=True)[:3]

    # % tu gia den muc S/R gan nhat
    nearest_r = resist_dyn[0] if resist_dyn else None
    nearest_s = support_dyn[0] if support_dyn else None
    to_resist = round((nearest_r - curr) / curr * 100, 2) if nearest_r else None
    to_support= round((curr - nearest_s) / curr * 100, 2) if nearest_s else None

    # RSI signal
    rsi_signal = "QUA_MUA" if rsi14 and rsi14 > 70 else \
                 "QUA_BAN" if rsi14 and rsi14 < 30 else "TRUNG_TINH"

    # BB position (% trong BB)
    bb_pos = None
    if bb and bb["upper"] != bb["lower"]:
        bb_pos = round((curr - bb["lower"]) / (bb["upper"] - bb["lower"]) * 100, 1)

    return {
        "close":  curr,
        "ma5":    ma5,
        "ma10":   ma10,
        "ma20":   ma20,
        "ma50":   ma50,
        "ma100":  ma100,
        "ema20":  ema20,
        "rsi14":  rsi14,
        "rsi_signal": rsi_signal,
        "bb":     bb,
        "bb_pos": bb_pos,
        "atr14":  atr14,
        "vol_today": vol_today,
        "vma10":  vma10,
        "vma20":  vma20,
        "vol_div": vol_div,
        "trend":  {"short": trend_short, "mid": trend_mid, "long": trend_long},
        "support":    support_dyn,
        "resistance": resist_dyn,
        "to_resist":  to_resist,
        "to_support": to_support,
    }

# ================================================================
# VN INDICES — vnstock VCI (da hoat dong tot)
# ================================================================
def fetch_vn_today():
    result = {}
    yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    two_days  = (NOW - datetime.timedelta(days=4)).strftime("%Y-%m-%d")  # lay du lich su
    try:
        from vnstock import Vnstock
        stock = Vnstock()
        for ticker in ["VNINDEX", "VN30", "VNMIDCAP"]:
            try:
                # Lay 3 phien gan nhat de co prev_close chinh xac
                df = stock.stock(symbol=ticker, source='VCI').quote.history(
                    start=two_days, end=TODAY, interval='1D'
                )
                if df is None or len(df) == 0:
                    df = stock.stock(symbol=ticker, source='VCI').quote.history(
                        start=yesterday, end=TODAY, interval='1D'
                    )
                if df is None or len(df) == 0: continue

                row    = df.iloc[-1]
                close  = sf(row.get('close', 0))
                open_p = sf(row.get('open', close))
                if close < 100 and close > 0: close*=1000; open_p*=1000
                if close < 100: continue

                # Neu open == close (VCI tra sai cho VNMIDCAP)
                # thi dung prev_close tu phien truoc
                if abs(open_p - close) < 0.001 and len(df) >= 2:
                    prev_close = sf(df.iloc[-2].get('close', 0))
                    if prev_close < 100 and prev_close > 0:
                        prev_close *= 1000
                    if prev_close > 100:
                        open_p = prev_close
                        print(f"  {ticker}: dung prev_close={prev_close:.2f} thay open")

                vol    = sf(row.get('volume', 0))
                change = round(close - open_p, 2)
                pct    = round(change / open_p * 100, 2) if open_p else 0
                result[ticker] = {
                    "value": round(close,2), "change": change, "pct": pct,
                    "vol": round(vol/1e6,2), "val": 0,
                    "date": str(df.index[-1])[:10],
                }
                print(f"  {ticker}: {close:.2f} ({pct:+.2f}%)")
                time.sleep(0.5)
            except Exception as e:
                print(f"  [WARN] {ticker}: {e}")
    except Exception as e:
        print(f"  [ERROR] fetch_vn: {e}")
    return result

# ================================================================
# MAIN
# ================================================================
try:
    with open("data.json","r",encoding="utf-8") as f: old = json.load(f)
except: old = {}

print("\n--- VN Indices hom nay ---")
vn = fetch_vn_today()
time.sleep(1)

print("\n--- OHLCV 120 phien: VNINDEX, VN30, VNMIDCAP ---")
technical = {}
for _ticker, _key in [("VNINDEX","vni"), ("VN30","vn30"), ("VNMIDCAP","vnmid")]:
    print(f"\n  {_ticker}...")
    ohlcv = fetch_ohlcv(_ticker, 120)
    time.sleep(0.5)
    if ohlcv:
        t = calc_technical(ohlcv)
        technical[_key] = t
        print(f"  {_ticker}: MA20={t.get('ma20')} RSI={t.get('rsi14')} trend={t.get('trend',{}).get('short')}")
        print(f"  Support={t.get('support')} Resist={t.get('resistance')}")
    else:
        print(f"  [WARN] {_ticker}: khong co OHLCV")
        technical[_key] = {}

tech = technical.get("vni", {})

# Merge VN data
vni  = vn.get("VNINDEX")  or old.get("vni",  {})
vn30 = vn.get("VN30")     or old.get("vn30", {})
vnm  = vn.get("VNMIDCAP") or old.get("vnmid",{})

# Gan breadth placeholder
if isinstance(vni, dict):
    vni.update({"up":0,"nt":0,"dn":0,"ceil":0,"floor":0})

# Foreign + industry: giu cu neu co, khong thi null
old_fgn = old.get("foreign", {})
fgn_final = old_fgn if old_fgn.get("net") not in [None,0,-240,1480] else {"net":None,"buy":None,"sell":None}
industry_final = old.get("industry", [])

data = {
    "updated":   UPDATED,
    "vni":       vni,
    "vn30":      vn30,
    "vnmid":     vnm,
    "foreign":   fgn_final,
    "industry":  industry_final,
    "technical": technical,  # indicators cho ca 3: vni, vn30, vnmid
}

with open("data.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open("_snapshot.json","w",encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

vni_v = vni.get('value','?') if isinstance(vni,dict) else '?'
vni_p = vni.get('pct',0)    if isinstance(vni,dict) else 0
print(f"\n=== XONG! {UPDATED} ===")
print(f"VNINDEX:  {vni_v} ({vni_p:+.2f}%)")
print(f"VN30:     {vn30.get('value','?') if isinstance(vn30,dict) else '?'}")
print(f"VNMIDCAP: {vnm.get('value','?') if isinstance(vnm,dict) else '?'}")
print(f"Technical: {len(technical)} indices ({', '.join(technical.keys())})")
