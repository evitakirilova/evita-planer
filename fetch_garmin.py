"""
Garmin Connect datu ielāde — miegs, soļi, stress
Atbalsta gan tokenu autorizāciju (ieteicams), gan paroli (rezerves variants).
"""

import os
import json
import base64
import tempfile
import traceback
from datetime import date, timedelta, datetime

EMAIL    = os.environ.get("GARMIN_EMAIL", "")
PASSWORD = os.environ.get("GARMIN_PASSWORD", "")
TOKENS_B64 = os.environ.get("GARMIN_TOKENS", "")

today     = date.today()
today_str = today.isoformat()
yest_str  = (today - timedelta(days=1)).isoformat()

result = {
    "date":         today_str,
    "updated":      datetime.utcnow().isoformat() + "Z",
    "steps":        None,
    "steps_goal":   10000,
    "sleep_hours":  None,
    "sleep_score":  None,
    "stress_avg":   None,
    "stress_level": None,
    "error":        None
}

try:
    import garth
    from garminconnect import Garmin

    if TOKENS_B64:
        # ── Tokenu autorizācija (ieteicamais veids) ──────────────
        print("Izmantoju saglabātos tokenus...")
        tokens = json.loads(base64.b64decode(TOKENS_B64).decode())
        token_dir = tempfile.mkdtemp()
        for filename, content in tokens.items():
            with open(os.path.join(token_dir, filename), "w") as f:
                f.write(content)
        api = Garmin()
        api.garth.load(token_dir)
        print("Tokenu autorizācija veiksmīga.")

    elif EMAIL and PASSWORD:
        # ── Paroles autorizācija (rezerves variants) ─────────────
        print(f"Pieslēdzos ar e-pastu {EMAIL}...")
        api = Garmin(email=EMAIL, password=PASSWORD)
        api.login()
        print("Pieslēgšanās veiksmīga.")

    else:
        raise ValueError("Nav ne GARMIN_TOKENS, ne GARMIN_EMAIL/GARMIN_PASSWORD.")

    # ── SOĻI ─────────────────────────────────────────────────────
    try:
        steps_data = api.get_steps_data(today_str)
        if steps_data:
            total = sum(s.get("steps", 0) for s in steps_data)
            result["steps"] = total
            print(f"Soļi: {total}")
        else:
            print("Soļu dati nav pieejami šodienai.")
    except Exception as e:
        print(f"Soļu kļūda: {e}")

    # ── MIEGS (vakardienas nakts) ─────────────────────────────────
    try:
        sleep_data = api.get_sleep_data(yest_str)
        dto = sleep_data.get("dailySleepDTO", {})
        sleep_sec = dto.get("sleepTimeSeconds")
        if sleep_sec:
            result["sleep_hours"] = round(sleep_sec / 3600, 1)
        score = dto.get("sleepScores", {}).get("overall", {}).get("value")
        if score:
            result["sleep_score"] = score
        print(f"Miegs: {result['sleep_hours']}h, skors: {result['sleep_score']}")
    except Exception as e:
        print(f"Miega kļūda: {e}")

    # ── STRESS ───────────────────────────────────────────────────
    try:
        stress_data = api.get_stress_data(today_str)
        avg = stress_data.get("avgStressLevel")
        if avg and avg > 0:
            result["stress_avg"] = avg
            result["stress_level"] = (
                "zems"      if avg < 26 else
                "vidējs"    if avg < 51 else
                "augsts"    if avg < 76 else
                "ļoti augsts"
            )
        print(f"Stress: {avg} ({result['stress_level']})")
    except Exception as e:
        print(f"Stresa kļūda: {e}")

except Exception as e:
    result["error"] = str(e)
    traceback.print_exc()

# ── Saglabā rezultātu ────────────────────────────────────────────
with open("garmin_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("\ngarmin_data.json saglabāts:")
print(json.dumps(result, ensure_ascii=False, indent=2))
