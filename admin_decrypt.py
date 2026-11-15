#!/usr/bin/env python3
"""Outils organisateur : clés, déchiffrement, export des candidatures, aide Telegram.

    python admin_decrypt.py keygen                         # crée private.key + affiche la clé publique
    python admin_decrypt.py telegram-setup --token TOKEN   # trouve ton chat_id après /start sur le bot
    python admin_decrypt.py read candidature_XXXX.enc      # lit un dossier reçu sur Telegram
    python admin_decrypt.py export --dir telegram/         # tous les .enc d'un dossier
    python admin_decrypt.py export --file responses.jsonl  # fichier local
    python admin_decrypt.py export --supabase              # table Supabase

Sortie de export : candidats.csv (vue d'ensemble) et dossiers/<code>.md (un dossier lisible par candidat).
Les indicateurs sont une aide au tri, pas un score : la notation finale suit la grille de lecture.
"""

import argparse
import base64
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

from nacl.public import PrivateKey, SealedBox

sys.path.insert(0, str(Path(__file__).resolve().parent))
from triage import etiquette, indicateurs  # noqa: E402


def keygen(args):
    chemin = Path(args.out)
    if chemin.exists():
        sys.exit(f"{chemin} existe déjà : je n'écrase pas une clé privée.")
    sk = PrivateKey.generate()
    chemin.write_text(base64.b64encode(bytes(sk)).decode())
    os.chmod(chemin, 0o600)
    print(f"Clé privée écrite dans {chemin}. Garde-la HORS LIGNE (sauvegarde chiffrée) : sans elle, rien n'est lisible.")
    print("Clé publique, à mettre dans PUBLIC_KEY (secrets de l'app) :")
    print(base64.b64encode(bytes(sk.public_key)).decode())


def telegram_setup(args):
    """Affiche le chat_id des personnes qui ont écrit au bot (envoie /start à ton bot d'abord)."""
    url = f"https://api.telegram.org/bot{args.token}/getUpdates"
    with urllib.request.urlopen(url, timeout=20) as r:
        donnees = json.load(r)
    vus = {}
    for u in donnees.get("result", []):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat:
            vus[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name") or "?"
    if not vus:
        sys.exit("Aucun message reçu : ouvre ton bot dans Telegram, appuie sur Démarrer (/start), puis relance.")
    for cid, nom in vus.items():
        print(f"TELEGRAM_CHAT_ID = {cid}   ({nom})")


def charger(args):
    if getattr(args, "dir", None):
        return [
            {"id": f.stem.replace("candidature_", ""), "payload": f.read_text().strip()}
            for f in sorted(Path(args.dir).glob("*.enc"))
        ]
    if args.supabase:
        url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/responses?select=id,payload&order=created_at"
        cle = os.environ["SUPABASE_SERVICE_KEY"]
        req = urllib.request.Request(url, headers={"apikey": cle, "Authorization": f"Bearer {cle}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    with open(args.file, encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f if ligne.strip()]


def formater(v):
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, list):
        return ", ".join(map(str, v)) if v else "—"
    return str(v) if str(v).strip() else "—"


def en_markdown(obj, niveau=0):
    marge = "  " * niveau
    lignes = []
    if isinstance(obj, dict):
        for cle, val in obj.items():
            if isinstance(val, dict) or (isinstance(val, list) and any(isinstance(x, (dict, list)) for x in val)):
                lignes.append(f"{marge}- **{cle}**")
                lignes += en_markdown(val, niveau + 1)
            else:
                lignes.append(f"{marge}- **{cle}** : {formater(val)}")
    elif isinstance(obj, list):
        for i, val in enumerate(obj, 1):
            lignes.append(f"{marge}{i}. {formater(val)}")
    return lignes


def boite(chemin_cle):
    cle = base64.b64decode(Path(chemin_cle).read_text().strip())
    return SealedBox(PrivateKey(cle))


def dechiffrer(b, payload):
    return json.loads(b.decrypt(base64.b64decode(payload)))


def dossier_md(code, p):
    _, _, drapeaux = indicateurs(p)
    tete = f"# Candidature {code} — {p['profil']['pseudo']}\n\n**Tri** : {etiquette(drapeaux)}\n\n"
    return tete + "\n".join(en_markdown(p)) + "\n"


def lire(args):
    code = Path(args.fichier).stem.replace("candidature_", "")
    p = dechiffrer(boite(args.key), Path(args.fichier).read_text().strip())
    print(dossier_md(code, p))


def export(args):
    b = boite(args.key)
    lignes_csv, dossiers = [], Path("dossiers")
    dossiers.mkdir(exist_ok=True)
    for rec in charger(args):
        try:
            p = dechiffrer(b, rec["payload"])
        except Exception:
            print(f"[!] {rec.get('id')} : déchiffrement impossible (mauvaise clé ou donnée altérée)", file=sys.stderr)
            continue
        moyenne, pratiques, drapeaux = indicateurs(p)
        lignes_csv.append({
            "code": rec["id"], "date": p["submitted_at"], "tri": etiquette(drapeaux), "pseudo": p["profil"]["pseudo"],
            "contact": p["profil"]["contact"], "chapeau": " / ".join(p["profil"]["chapeau"]),
            "anciennete": p["profil"]["anciennete"] or "", "competences_moyenne": moyenne,
            "questions_pratiques_ok": pratiques, "temps": p["dispo"]["temps"], "anonymat": p["dispo"]["anonymat"],
            "trente_jours": p["dispo"]["trente_jours"], "engagement": p["motivations"]["engagement"]["choix"],
            "a_discuter": " | ".join(drapeaux),
        })
        (dossiers / f"{rec['id']}.md").write_text(dossier_md(rec["id"], p), encoding="utf-8")
    if not lignes_csv:
        sys.exit("Aucune candidature lisible.")
    with open("candidats.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_csv[0]))
        w.writeheader()
        w.writerows(lignes_csv)
    print(f"{len(lignes_csv)} candidature(s) → candidats.csv et dossiers/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen", help="génère la paire de clés")
    k.add_argument("--out", default="private.key")
    k.set_defaults(func=keygen)

    t = sub.add_parser("telegram-setup", help="trouve ton chat_id Telegram")
    t.add_argument("--token", required=True)
    t.set_defaults(func=telegram_setup)

    r = sub.add_parser("read", help="lit un dossier .enc reçu sur Telegram")
    r.add_argument("fichier")
    r.add_argument("--key", default="private.key")
    r.set_defaults(func=lire)

    e = sub.add_parser("export", help="déchiffre et exporte les candidatures")
    e.add_argument("--key", default="private.key")
    src = e.add_mutually_exclusive_group()
    src.add_argument("--file", default="responses.jsonl")
    src.add_argument("--dir", help="dossier contenant des fichiers candidature_*.enc (reçus par Telegram)")
    src.add_argument("--supabase", action="store_true")
    e.set_defaults(func=export)

    a = ap.parse_args()
    a.func(a)
