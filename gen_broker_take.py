import json, os, datetime, requests

api_key = os.environ.get("ANTHROPIC_API_KEY", "")

if not api_key or not api_key.strip():
    print("[SKIP] Chua co ANTHROPIC_API_KEY — bo qua auto-generate")
    print("[INFO] De bat tu dong: them ANTHROPIC_API_KEY vao GitHub Secrets")
    exit(0)

print("[AUTO] Generating Broker Take voi Claude API...")

try:
    with open("_snapshot.json","r",encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"[ERROR] Khong doc duoc snapshot: {e}")
    exit(0)

tz7 = datetime.timezone(datetime.timedelta(hours=7))
today = datetime.datetime.now(tz7).strftime("%d/%m/%Y")

data_str = json.dumps(data, ensure_ascii=False)

prompt = (
    "Ban la broker chung khoan Viet Nam 3 nam kinh nghiem. "
    "Viet nhan dinh cuoi ngay cho web dashboard. "
    "Nguoi doc can thong tin nhanh, gon, du de ra quyet dinh ngay.\n\n"
    "NGUYEN TAC:\n"
    "- Cau dau PHAI la ket luan, khong mo ta\n"
    "- Quan diem ro rang, khong nuoc doi\n"
    "- Khong dung tin don/noi gian lam can cu\n"
    "- Uu tien: Vi mo > Nganh > Ky thuat > Tam ly\n"
    "- Breadth quan trong hon diem so\n"
    "- Thang BCTC (4/7/10): can trong, nhieu nhieu\n\n"
    "DU LIEU NGAY " + today + ":\n"
    + data_str + "\n\n"
    "Tra ve JSON (CHI JSON, khong viet gi them):\n"
    '{"date":"' + today + '",'
    '"verdict":{"signal":"TICH CUC|THAN TRONG|TIEU CUC","emoji":"|","headline":"<=15 chu","summary":"<=40 chu"},'
    '"market_pulse":{"vnindex":"<=20 chu","breadth":"<=20 chu","foreign":"<=20 chu","liquidity":"<=20 chu"},'
    '"sector_highlight":{"leader":"nganh dan dat","laggard":"nganh yeu nhat","rotation":"<=25 chu"},'
    '"world_impact":"<=40 chu",'
    '"key_risk":"<=25 chu",'
    '"action":{"for_holder":"<=20 chu","for_watcher":"<=20 chu"},'
    '"brokers_take":["gach 1","gach 2","gach 3","gach 4","gach 5"],'
    '"generated_by":"auto","model":"claude-haiku-4-5"}'
)

try:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 1200,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"].strip()

    # Strip markdown code block nếu có
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    result = json.loads(raw)

    with open("broker-take.json","w",encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[AUTO] OK: {result.get('verdict',{}).get('emoji','')} {result.get('verdict',{}).get('headline','')}")

except Exception as e:
    print(f"[ERROR] API call failed: {e}")
    print("[INFO] broker-take.json giu nguyen noi dung cu")
