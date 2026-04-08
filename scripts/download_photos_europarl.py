import json, urllib.request, time
from pathlib import Path

PHOTOS_EP = Path("data/photos/europarl")
PHOTOS_EP.mkdir(parents=True, exist_ok=True)
STATE = Path("data/europarl/state.json")

def download(url, dest):
    if dest.exists(): return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        if len(data) < 500: return False
        dest.write_bytes(data)
        return True
    except: return False

def main():
    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)
    print(f"Europarl — {len(state)} eurodéputé·e·s")
    ok = fail = 0
    for ep_id, info in state.items():
        url = f"https://www.europarl.europa.eu/mepphoto/{ep_id}.jpg"
        if download(url, PHOTOS_EP / f"{ep_id}.jpg"): ok += 1
        else: fail += 1
        time.sleep(0.05)
    print(f"✓ {ok} · ✗ {fail}")

if __name__ == "__main__":
    main()
