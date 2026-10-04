#!/usr/bin/env python3
"""Collecte des sorties du club Strava ASCCAL -> data/activities.json
Le flux club ne fournit ni date ni identifiant : chaque sortie nouvelle est
datee du jour de collecte et reconnue par une empreinte anonyme."""
import hashlib, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

CLUB_ID = os.environ.get("STRAVA_CLUB_ID", "241399")
CID = os.environ["STRAVA_CLIENT_ID"]
SECRET = os.environ["STRAVA_CLIENT_SECRET"]
REFRESH = os.environ["STRAVA_REFRESH_TOKEN"]
PSEUDOS = json.loads(os.environ.get("PSEUDOS") or "{}")
DATA = Path("data/activities.json")
VELOTAF = re.compile(r"v[ée]lo\s*-?taf|commute|trajet|boulot|domicile", re.I)


def call(url, data=None, token=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def h(text, n):
    return hashlib.sha256((SECRET + "|" + text).encode()).hexdigest()[:n]


def main():
    tok = call("https://www.strava.com/oauth/token", {
        "client_id": CID, "client_secret": SECRET,
        "grant_type": "refresh_token", "refresh_token": REFRESH})
    if tok.get("refresh_token") and tok["refresh_token"] != REFRESH:
        print("ATTENTION : Strava a emis un nouveau jeton d'actualisation ; "
              "mettre a jour le secret STRAVA_REFRESH_TOKEN.")
    feed = call("https://www.strava.com/api/v3/clubs/%s/activities?per_page=200" % CLUB_ID,
                token=tok["access_token"])
    old = json.loads(DATA.read_text()) if DATA.exists() else {"activites": []}
    acts = old["activites"]
    seen = {a["s"] for a in acts}
    first = not acts
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    added = 0
    for a in reversed(feed):  # du plus ancien au plus recent
        ath = a.get("athlete") or {}
        name = ("%s %s" % (ath.get("firstname", ""), ath.get("lastname", ""))).strip()
        dist, mov = a.get("distance") or 0, a.get("moving_time") or 0
        sig = h("%s|%s|%s|%s|%s" % (name, dist, mov, a.get("elapsed_time"),
                                    a.get("total_elevation_gain")), 16)
        if sig in seen:
            continue
        seen.add(sig)
        added += 1
        acts.append({
            "s": sig,
            "p": PSEUDOS.get(name) or "Cycliste-" + h(name, 4),
            "t": a.get("sport_type") or a.get("type") or "?",
            "d": round(dist / 1000, 2),
            "m": int(mov),
            "e": int(a.get("total_elevation_gain") or 0),
            "c": today,
            "v": bool(VELOTAF.search(a.get("name") or "")),
            "i": first,
        })
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps({"maj": today, "activites": acts},
                               ensure_ascii=False, separators=(",", ":")))
    print("%d sorties dans le flux, %d nouvelles, %d au total" % (len(feed), added, len(acts)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # ne jamais afficher de secret
        print("Echec de la collecte :", type(exc).__name__, getattr(exc, "code", ""))
        sys.exit(1)
