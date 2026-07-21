"""
Garmin Connect datu ielāde — miegs, soļi, stress
Palaiž GitHub Actions katru rītu un saglabā garmin_data.json
"""

import os
import json
import traceback
from datetime import date, timedelta, datetime

try:
    from garminconnect import Garmin
except ImportError:
    print("Kļūda: pip install garminconnect")
    raise

EMAIL = os.environ.get("GARMIN_EMAIL")
PASSWORD = os.environ.get("GARMIN_PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("Nav GARMIN_EMAIL vai GARMIN_PASSWORD vides mainīgajos")

today = date.today()
today_str = today.isoformat()
yesterday_str = (today - timedelta(days=1)).isoformat()

result = {
    "date": today_str,
    "updated": datetime.utcnow().isoformat() + "Z",
    "steps": None,
    "steps_goal": 10000,
    "sleep_hours": None,
    "sleep_score": None,
    "stress_avg": None,
    "stress_level": None,
    "error": None
}

try:
    print(f"Pieslēdzos Garmin Connect kā {EMAIL}...")
    api = Garmin(email=EMAIL, password=PASSWORD)
    api.login()
    print("Pieslēgšanās veiksmīga.")

    # --- SOĻI ---
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

    # --- MIEGS (vakardienas nakts) ---
    try:
        sleep_data = api.get_sleep_data(yesterday_str)
        dto = sleep_data.get("dailySleepDTO", {})
        sleep_sec = dto.get("sleepTimeSeconds")
        if sleep_sec:
            result["sleep_hours"] = round(sleep_sec / 3600, 1)
        result["sleep_score"] = dto.get("sleepScores", {}).get("overall", {}).get("value") \
                                 or sleep_data.get("sleepScores", {}).get("totalScore")
        print(f"Miegs: {result['sleep_hours']}h, skors: {result['sleep_score']}")
    except Exception as e:
        print(f"Miega kļūda: {e}")

    # --- STRESS ---
    try:
        stress_data = api.get_stress_data(today_str)
        avg = stress_data.get("avgStressLevel")
        if avg and avg > 0:
            result["stress_avg"] = avg
            if avg < 26:
                result["stress_level"] = "zems"
            elif avg < 51:
                result["stress_level"] = "vidējs"
            elif avg < 76:
                result["stress_level"] = "augsts"
            else:
                result["stress_level"] = "ļoti augsts"
        print(f"Stress: {avg} ({result['stress_level']})")
    except Exception as e:
        print(f"Stresa kļūda: {e}")

except Exception as e:
    result["error"] = str(e)
    traceback.print_exc()

# Saglabā rezultātu
output_path = "garmin_data.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nSaglabāts {output_path}:")
print(json.dumps(result, ensure_ascii=False, indent=2))
