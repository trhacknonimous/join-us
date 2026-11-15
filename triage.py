"""Indicateurs de tri partagés par l'app (notification Telegram) et par admin_decrypt.py (export).

Ce sont des aides à la lecture, pas un score : la décision et la notation finale (grille de lecture)
restent celles de l'organisateur.
"""

import statistics


def indicateurs(p: dict):
    """Retourne (moyenne des niveaux déclarés, nombre de réponses pratiques étoffées, points à discuter)."""
    niveaux = list(p["competences"]["niveaux"].values())
    moyenne = round(statistics.mean(niveaux), 2) if niveaux else 0
    pratiques = sum(len(t.strip()) >= 30 for t in p["competences"]["pratique"])
    drapeaux = []
    for sid in ("s1", "s2", "s3"):
        if p["ethique"]["scenarios"][sid]["choix"] != "a":
            drapeaux.append(f"{sid} : réponse à discuter")
    if len(p["ethique"]["criteres_ciblage"]) < 150:
        drapeaux.append("critères de ciblage courts")
    if moyenne >= 3.5 and pratiques < 3:
        drapeaux.append("niveau déclaré élevé, peu de preuves")
    if p["motivations"]["engagement"]["choix"] == "direct":
        drapeaux.append("engagement : action sans autorisation (à creuser)")
    if p["dispo"]["temps"] == "Moins de 2 h":
        drapeaux.append("disponibilité faible")
    return moyenne, pratiques, drapeaux


def etiquette(drapeaux) -> str:
    """Étiquette de tri : aucune alerte, 1 à 2 alertes, 3 alertes ou plus."""
    if not drapeaux:
        return "🟢 à regarder en priorité"
    if len(drapeaux) <= 2:
        return "🟡 à discuter"
    return "🔴 profil fragile"
