"""
gen_conviction.py
Đọc Google Sheets → sinh 3 file JSON:
  - conviction.json   : conviction hôm nay + lịch sử
  - watchlist.json    : danh sách đang theo dõi
  - track-record.json : thống kê hiệu suất
"""

import json
import os
import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Cấu hình ──────────────────────────────────────────────
SHEET_ID   = os.environ.get('SHEET_ID', '')
SCOPES     = ['https://www.googleapis.com/auth/spreadsheets.readonly']
TZ7        = datetime.timezone(datetime.timedelta(hours=7))

# ── Kết nối Google Sheets API ─────────────────────────────
def get_sheet_service():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS', '')
    if not creds_json:
        raise ValueError("Chưa có GOOGLE_CREDENTIALS trong environment")
    
    import tempfile
    # Ghi credentials ra file tạm
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(creds_json)
        creds_file = f.name
    
    creds   = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    os.unlink(creds_file)  # Xóa file tạm
    return service.spreadsheets()

# ── Đọc toàn bộ tab convictions ───────────────────────────
def read_convictions(sheets):
    result = sheets.values().get(
        spreadsheetId=SHEET_ID,
        range='convictions!A:R'  # A đến R = 18 cột
    ).execute()
    
    rows   = result.get('values', [])
    if len(rows) < 2:
        return []
    
    # Dòng đầu là header, bỏ qua
    headers = rows[0]
    data    = []
    
    for row in rows[1:]:
        # Đảm bảo row đủ 18 cột
        while len(row) < 18:
            row.append('')
        
        conviction = {
            'id':         row[0],
            'date':       row[1],
            'createdAt':  row[2],
            'ticker':     row[3],
            'action':     row[4],
            'entryLow':   float(row[5]) if row[5] else None,
            'entryHigh':  float(row[6]) if row[6] else None,
            'target':     float(row[7]) if row[7] else None,
            'stopLoss':   float(row[8]) if row[8] else None,
            'thesis':     row[9],
            'tags':       row[10].split(',') if row[10] else [],
            'horizon':    row[11],
            'status':     row[12] or 'open',
            'closeDate':  row[13],
            'closePrice': float(row[14]) if row[14] else None,
            'returnPct':  float(row[15]) if row[15] else None,
            'tg_msg_id':  row[16],
            'tg_channel': row[17],
        }
        
        # Tính holding days nếu đã đóng
        if conviction['status'] == 'closed' and conviction['date'] and conviction['closeDate']:
            try:
                open_dt  = datetime.datetime.strptime(conviction['date'], '%Y-%m-%d')
                close_dt = datetime.datetime.strptime(conviction['closeDate'], '%Y-%m-%d')
                conviction['holdingDays'] = (close_dt - open_dt).days
            except:
                conviction['holdingDays'] = None
        else:
            conviction['holdingDays'] = None
        
        # Tạo link Telegram verify
        if conviction['tg_msg_id'] and conviction['tg_channel']:
            channel = conviction['tg_channel'].replace('@', '')
            conviction['tg_url'] = f"https://t.me/{channel}/{conviction['tg_msg_id']}"
        else:
            conviction['tg_url'] = None
        
        data.append(conviction)
    
    return data

# ── Tính thống kê track record ────────────────────────────
def calc_stats(convictions):
    closed = [c for c in convictions if c['status'] == 'closed' and c['returnPct'] is not None]
    
    if not closed:
        return {
            'totalTrades':  0,
            'winRate':      0,
            'avgReturn':    0,
            'totalReturn':  0,
            'avgHoldDays':  0,
            'bestTrade':    None,
            'worstTrade':   None,
        }
    
    wins      = [c for c in closed if c['returnPct'] > 0]
    losses    = [c for c in closed if c['returnPct'] <= 0]
    returns   = [c['returnPct'] for c in closed]
    hold_days = [c['holdingDays'] for c in closed if c['holdingDays'] is not None]
    
    best  = max(closed, key=lambda x: x['returnPct'])
    worst = min(closed, key=lambda x: x['returnPct'])
    
    return {
        'totalTrades': len(closed),
        'winCount':    len(wins),
        'lossCount':   len(losses),
        'winRate':     round(len(wins) / len(closed) * 100, 1),
        'avgReturn':   round(sum(returns) / len(returns), 2),
        'totalReturn': round(sum(returns), 2),
        'avgHoldDays': round(sum(hold_days) / len(hold_days), 1) if hold_days else 0,
        'bestTrade':   {
            'ticker':    best['ticker'],
            'returnPct': best['returnPct'],
            'date':      best['date'],
        },
        'worstTrade':  {
            'ticker':    worst['ticker'],
            'returnPct': worst['returnPct'],
            'date':      worst['date'],
        },
    }

# ── Main ──────────────────────────────────────────────────
def main():
    now_vn  = datetime.datetime.now(TZ7)
    today   = now_vn.strftime('%Y-%m-%d')
    updated = now_vn.strftime('%d/%m/%Y %H:%M')
    
    print(f"Bắt đầu: {updated}")
    print(f"Sheet ID: {SHEET_ID[:20]}...")
    
    # Kết nối Sheets
    sheets = get_sheet_service()
    print("Kết nối Sheets OK")
    
    # Đọc data
    convictions = read_convictions(sheets)
    print(f"Đọc được {len(convictions)} convictions")
    
    # Phân loại
    open_convictions   = [c for c in convictions if c['status'] == 'open']
    closed_convictions = [c for c in convictions if c['status'] == 'closed']
    today_conviction   = next((c for c in open_convictions if c['date'] == today), None)
    
    # Tính stats
    stats = calc_stats(convictions)
    print(f"Stats: {stats['totalTrades']} trades, win rate {stats['winRate']}%")
    
    # ── Sinh conviction.json ──
    conviction_data = {
        'updated':   updated,
        'today':     today_conviction,
        'open':      open_convictions,
        'closed':    closed_convictions[:20],  # 20 gần nhất
        'all':       convictions,
    }
    with open('conviction.json', 'w', encoding='utf-8') as f:
        json.dump(conviction_data, f, ensure_ascii=False, indent=2)
    print("Đã sinh conviction.json")
    
    # ── Sinh watchlist.json ──
    # Watchlist = các conviction đang open
    watchlist = []
    for c in open_convictions:
        watchlist.append({
            'ticker':    c['ticker'],
            'action':    c['action'],
            'entryLow':  c['entryLow'],
            'entryHigh': c['entryHigh'],
            'target':    c['target'],
            'stopLoss':  c['stopLoss'],
            'thesis':    c['thesis'],
            'horizon':   c['horizon'],
            'date':      c['date'],
            'id':        c['id'],
            'tg_url':    c['tg_url'],
        })
    
    watchlist_data = {
        'updated': updated,
        'items':   watchlist,
        'count':   len(watchlist),
    }
    with open('watchlist.json', 'w', encoding='utf-8') as f:
        json.dump(watchlist_data, f, ensure_ascii=False, indent=2)
    print("Đã sinh watchlist.json")
    
    # ── Sinh track-record.json ──
    track_record_data = {
        'updated':    updated,
        'stats':      stats,
        'closed':     closed_convictions,
        'open':       open_convictions,
    }
    with open('track-record.json', 'w', encoding='utf-8') as f:
        json.dump(track_record_data, f, ensure_ascii=False, indent=2)
    print("Đã sinh track-record.json")
    
    print(f"\nXong! Đã sinh 3 file JSON lúc {updated}")

if __name__ == '__main__':
    main()
