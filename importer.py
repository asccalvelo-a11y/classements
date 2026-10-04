#!/usr/bin/env python3
"""Integre dans data/activities.json le flux « activites recentes » du groupe Strava, copie-colle a la main.
Seules les sorties nouvelles sont ajoutees. Les commentaires et les titres ne sont pas conserves.
Usage : python3 importer.py collage.txt AAAA-MM-JJ(date du collage) [prenom-initiale|complet]"""
import hashlib, json, re, sys, unicodedata
from datetime import date, timedelta
from pathlib import Path

DATA = Path("data/activities.json")
MOIS = {m: i + 1 for i, m in enumerate(
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split())}
MOIS.update({m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())})
DATE = re.compile(r"^(Aujourd'hui|Aujourd’hui|Today|Hier|Yesterday|(\d{1,2}) (\S+) (\d{4})|([A-Za-z]+) (\d{1,2}), (\d{4}))\b")


def quand(ligne, ref):
    """Date d'une ligne du type « Hier à 09:57 · Garmin » ; None si ce n'est pas une ligne de date d'activite."""
    if "·" not in ligne:
        return None
    m = DATE.match(ligne.strip())
    if not m:
        return None
    mot = m.group(1).lower()
    if mot.startswith(("aujourd", "today")):
        return ref
    if mot in ("hier", "yesterday"):
        return ref - timedelta(days=1)
    try:
        if m.group(2):
            return date(int(m.group(4)), MOIS[m.group(3).lower()], int(m.group(2)))
        return date(int(m.group(7)), MOIS[m.group(5).lower()], int(m.group(6)))
    except (KeyError, ValueError):
        return None


def km(s):
    s = re.sub(r"[^\d.,]", "", s)
    return float(s.replace(",", ".")) if "." not in s else float(s.replace(",", ""))


def metres(s):
    return int(re.sub(r"\D", "", s) or 0)


def secondes(s):
    h = re.search(r"(\d+)\s*h", s); m = re.search(r"(\d+)\s*m(?:in)?\b", s); sec = re.search(r"(\d+)\s*s\b", s)
    return (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0) + (int(sec.group(1)) if sec else 0)


def discipline(titre, virtuel):
    t = titre.lower()
    if virtuel:
        return "Home trainer"
    if re.search(r"v[ée]lo\s*-?\s*taf", t):
        return "Vélotaf"
    if re.search(r"\bvtt\b|mountain bike|\bmtb\b", t):
        return "VTT"
    if "gravel" in t:
        return "Gravel"
    if re.search(r"électrique|electrique|e-bike|ebike", t):
        return "VAE"
    return "Route"


def cle(nom):
    n = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z ]", " ", n.lower()).split())


def affichage(nom, mode):
    mots = [m for m in nom.split() if re.search(r"[A-Za-zÀ-ÿ]", m)]
    if mode == "complet" or len(mots) < 2:
        return nom
    return "%s %s." % (mots[0].capitalize(), mots[1][0].upper())


def lire(texte, ref):
    L = [l.strip() for l in texte.splitlines()]
    debuts = [i for i, l in enumerate(L) if i > 0 and quand(l, ref) and L[i - 1]]
    acts = []
    for n, i in enumerate(debuts):
        fin = debuts[n + 1] - 1 if n + 1 < len(debuts) else len(L)
        bloc = L[i + 1:fin]
        if "Distance" not in bloc:
            continue
        d = bloc.index("Distance")
        val = {}
        for j in range(d, min(d + 6, len(bloc) - 1), 2):
            val[bloc[j]] = bloc[j + 1]
        dist = km(val.get("Distance", "0"))
        duree = secondes(val.get("Temps") or val.get("Time") or "")
        if dist <= 0 or duree <= 0:
            continue
        avant = [l for l in bloc[:d] if l and l != "·"]
        if "·" in bloc[:d] and avant:   # la ligne qui suit le point median est le lieu
            avant = avant[1:]
        titre = " ".join(avant)
        acts.append({"nom": L[i - 1], "date": quand(L[i], ref).isoformat(), "km": dist,
                     "deniv": metres(val.get("Dénivelé") or val.get("Elev Gain") or "0"), "sec": duree,
                     "disc": discipline(titre, any("Sortie virtuelle" in l for l in bloc))})
    return acts


def main():
    texte, ref = Path(sys.argv[1]).read_text(encoding="utf-8"), date.fromisoformat(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else "prenom-initiale"
    lues = lire(texte, ref)
    if not lues:
        sys.exit("Aucune sortie reconnue dans le collage.")
    data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"activites": [], "adherents": []}
    vues = {a["s"] for a in data["activites"]}
    ajout = 0
    for a in lues:
        k = hashlib.sha256(cle(a["nom"]).encode()).hexdigest()[:10]
        s = hashlib.sha256(("%s|%s|%.2f|%d" % (k, a["date"], a["km"], a["sec"])).encode()).hexdigest()[:16]
        if s in vues:
            continue
        vues.add(s); ajout += 1
        data["activites"].append({"s": s, "k": k, "p": affichage(a["nom"], mode), "disc": a["disc"],
                                  "d": a["km"], "m": a["sec"], "e": a["deniv"], "c": a["date"]})
    data["activites"].sort(key=lambda a: a["c"])
    data["maj"] = ref.isoformat()
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("%d sorties lues, %d nouvelles, %d au total" % (len(lues), ajout, len(data["activites"])))


if __name__ == "__main__":
    main()
