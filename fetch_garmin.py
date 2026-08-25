"""
Garmin Connect datu ielade planotajam.

Raksta garmin_data.json TIESI TADA forma, kadu lasa planer_2026.html
(funkcija fetchGarminJson): yesterday_steps, sleep_hours, sleep_score,
stress_avg, stress_level, body_battery, weekly_walk_km, weekly_bike_km,
weekly_total_km, week_start.

Autorizacija: GARMIN_TOKENS (ieteicams) vai GARMIN_EMAIL + GARMIN_PASSWORD.

Drosibas princips: ja pieslegsanas neizdodas vai neviens raditajs netiek
iegūts, fails NETIEK parrakstits — labak veci dati neka tuksi.
"""

import os
import json
import base64
import tempfile
import traceback
from datetime import date, timedelta, datetime, timezone

EMAIL      = os.environ.get("GARMIN_EMAIL", "")
PASSWORD   = os.environ.get("GARMIN_PASSWORD", "")
TOKENS_B64 = os.environ.get("GARMIN_TOKENS", "")

today      = date.today()
yesterday  = today - timedelta(days=1)
week_start = today - timedelta(days=today.weekday())   # pirmdiena

result = {
    "date":            today.isoformat(),
    "updated":         datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "yesterday_steps": None,
    "steps_goal":      10000,
    "sleep_hours":     None,
    "sleep_score":     None,
    "stress_avg":      None,
    "stress_level":    None,
    "body_battery":    None,
    "weekly_walk_km":  None,
    "weekly_bike_km":  None,
    "weekly_total_km": None,
    "week_start":      week_start.isoformat(),
    "error":           None,
}

got = 0   # cik raditaju reali izdevas iegut


def stress_label(avg):
    return ("zems"        if avg < 26 else
            "vidējs"      if avg < 51 else
            "augsts"      if avg < 76 else
            "ļoti augsts")


try:
    from garminconnect import Garmin

    if TOKENS_B64:
        print("Autorizacija ar saglabatajiem tokeniem...")
        tokens = json.loads(base64.b64decode(TOKENS_B64).decode())
        token_dir = tempfile.mkdtemp()
        for filename, content in tokens.items():
            with open(os.path.join(token_dir, filename), "w") as f:
                f.write(content)
        api = Garmin()
        api.garth.load(token_dir)
        print("Tokenu autorizacija veiksmiga.")

    elif EMAIL and PASSWORD:
        print("Autorizacija ar e-pastu un paroli...")
        api = Garmin(email=EMAIL, password=PASSWORD)
        api.login()
        print("Pieslegsanas veiksmiga.")

    else:
        raise ValueError("Nav ne GARMIN_TOKENS, ne GARMIN_EMAIL/GARMIN_PASSWORD.")

    # ── VAKARDIENAS SOLI ─────────────────────────────────────────────
    # Planotajs to rada ka "vakar soli", tapec nemam VAKARDIENAS pilno dienu.
    try:
        total = 0
        try:
            sd = api.get_steps_data(yesterday.isoformat())
            if sd:
                total = sum((s.get("steps") or 0) for s in sd)
        except Exception:
            pass
        if not total:
            us = api.get_user_summary(yesterday.isoformat()) or {}
            total = us.get("totalSteps") or 0
        if total:
            result["yesterday_steps"] = int(total)
            got += 1
        print(f"Vakardienas soli: {result['yesterday_steps']}")
    except Exception as e:
        print(f"Solu kluda: {e}")

    # ── MIEGS ────────────────────────────────────────────────────────
    # Nakts, kas beidzas SODIEN. Ja vel nav sinhronizeta, nemam vakardienu.
    try:
        for d in (today, yesterday):
            sleep_data = api.get_sleep_data(d.isoformat()) or {}
            dto = sleep_data.get("dailySleepDTO") or {}
            sec = dto.get("sleepTimeSeconds")
            if sec:
                result["sleep_hours"] = round(sec / 3600, 2)
                score = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
                if score:
                    result["sleep_score"] = score
                got += 1
                break
        print(f"Miegs: {result['sleep_hours']}h, skors: {result['sleep_score']}")
    except Exception as e:
        print(f"Miega kluda: {e}")

    # ── STRESS ───────────────────────────────────────────────────────
    try:
        for d in (today, yesterday):
            stress_data = api.get_stress_data(d.isoformat()) or {}
            avg = stress_data.get("avgStressLevel")
            if avg and avg > 0:
                result["stress_avg"]   = avg
                result["stress_level"] = stress_label(avg)
                got += 1
                break
        print(f"Stress: {result['stress_avg']} ({result['stress_level']})")
    except Exception as e:
        print(f"Stresa kluda: {e}")

    # ── BODY BATTERY ─────────────────────────────────────────────────
    try:
        level = None
        try:
            bb = api.get_body_battery(today.isoformat(), today.isoformat()) or []
            for blok in bb:
                for v in (blok.get("bodyBatteryValuesArray") or []):
                    # forma: [laiks, statuss, limenis, versija]
                    if len(v) >= 3 and v[2] is not None:
                        level = v[2]
        except Exception:
            pass
        if level is None:
            us = api.get_user_summary(today.isoformat()) or {}
            level = us.get("bodyBatteryMostRecentValue")
        if level:
            result["body_battery"] = int(level)
            got += 1
        print(f"Body battery: {result['body_battery']}")
    except Exception as e:
        print(f"Body battery kluda: {e}")

    # ── NEDELAS KILOMETRI (no pirmdienas) ────────────────────────────
    try:
        walk_keys = {"walking", "casual_walking", "speed_walking", "hiking", "trail_running", "running", "treadmill_running", "indoor_walking"}
        bike_keys = {"cycling", "road_biking", "mountain_biking", "gravel_cycling", "virtual_ride", "indoor_cycling", "e_bike_fitness"}
        walk_m = 0.0
        bike_m = 0.0
        acts = api.get_activities_by_date(week_start.isoformat(), today.isoformat()) or []
        for a in acts:
            key  = ((a.get("activityType") or {}).get("typeKey") or "").lower()
            dist = a.get("distance") or 0
            if key in bike_keys:
                bike_m += dist
            elif key in walk_keys:
                walk_m += dist
        result["weekly_walk_km"]  = round(walk_m / 1000, 2)
        result["weekly_bike_km"]  = round(bike_m / 1000, 2)
        result["weekly_total_km"] = round((walk_m + bike_m) / 1000, 2)
        got += 1
        print(f"Nedelas km: kajam {result['weekly_walk_km']}, ritenis {result['weekly_bike_km']}, kopa {result['weekly_total_km']} ({len(acts)} aktivitates)")
    except Exception as e:
        print(f"Aktivitasu kluda: {e}")

except Exception as e:
    result["error"] = str(e)
    traceback.print_exc()

# ── Saglaba TIKAI tad, ja kaut kas reali tika iegūts ─────────────────
if got == 0:
    print("\nNeviens raditajs netika iegūts — garmin_data.json NETIEK parrakstits.")
    print(f"Kluda: {result['error']}")
    raise SystemExit(1)

with open("garmin_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\ngarmin_data.json saglabats ({got} raditaju grupas):")
print(json.dumps(result, ensure_ascii=False, indent=2))
