"""Questionnaire de recrutement — Collectif Hack, IA & Électro.

Les réponses sont chiffrées côté serveur avec une clé PUBLIQUE avant d'être stockées.
Seule la clé privée, gardée hors ligne par l'organisateur, permet de les relire
(voir admin_decrypt.py).
"""

import base64
import json
import os
import threading
import urllib.request
import uuid
from datetime import datetime, timezone

import requests
import streamlit as st
from nacl.public import PublicKey, SealedBox

from triage import etiquette, indicateurs

st.set_page_config(page_title="Collectif Hack, IA & Électro", page_icon="🕶️", layout="centered")
st.markdown(
    "<style>#MainMenu{visibility:hidden}footer{visibility:hidden}"
    "h1,h2,h3{font-family:'Courier New',monospace}</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- configuration


def cfg(name, default=None):
    """Lit un réglage dans st.secrets, puis dans les variables d'environnement."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


# ---------------------------------------------------------------- contenu

HATS = ["white hat", "grey hat", "black hat", "red hat", "blue hat", "green hat", "je ne me range pas"]
LANGUES = ["Français", "Anglais", "Autre"]
ANCIENNETE = ["Moins d'un an", "1 à 3 ans", "3 à 10 ans", "Plus de 10 ans"]
PARCOURS = ["Autodidacte", "Études", "Métier", "Hackerspace / fablab", "CTF", "Forums / Discord", "Dépôts Git / open source"]

DOMAINES = [
    ("IA / machine learning", "LLM locaux, RAG, fine-tuning, vision, agents"),
    ("Électronique et embarqué", "ESP32, Raspberry Pi, STM32, Arduino, PCB"),
    ("Radio et SDR", "RTL-SDR, HackRF, LoRa, ADS-B, antennes"),
    ("Sécurité défensive", "durcissement, chiffrement, détection, forensics"),
    ("Sécurité offensive en cadre légal", "CTF, labo personnel, pentest autorisé"),
    ("Développement", "Python, C/C++, Rust, JavaScript, Lua"),
    ("Réseaux et systèmes", "Linux, TCP/IP, VPN, Tor, virtualisation"),
    ("OSINT", "recherche en sources ouvertes, vérification"),
    ("Rétro-ingénierie", "firmware, protocoles, consoles"),
    ("Impression 3D et fabrication", "modélisation, boîtiers, supports"),
    ("Vie privée et anonymat", "chiffrement, hygiène numérique, outils"),
]
NIVEAUX = {0: "0 · jamais touché", 1: "1 · notions", 2: "2 · petits projets", 3: "3 · autonome", 4: "4 · je forme les autres"}

PRATIQUE = [
    "Comment ferais-tu tourner un modèle de langage en local sur du matériel modeste ?",
    "Un ESP32 redémarre en boucle dès que le WiFi s'active. Quelles pistes explores-tu, et dans quel ordre ?",
    "Quelle différence entre un récepteur SDR et une radio classique, et que peut-on écouter légalement ?",
    "Tu possèdes un objet connecté dont tu veux comprendre le firmware. Par où commences-tu ?",
    "Décris le dernier problème technique que tu as résolu : le blocage, ta démarche, le résultat.",
]

APPORTS = ["Compétences", "Matériel", "Temps", "Réseau", "Contenus (tutos, vidéos)", "Mentorat"]
ATTENTES = ["Apprendre", "Projets communs", "Entraide", "Matériel partagé", "Défis", "Réseau", "Autre"]
ENGAGEMENT = {
    "info": "Informer et sensibiliser (articles, ateliers, vulgarisation)",
    "outils": "Construire des outils pour la vie privée et la liberté d'expression",
    "legal": "Mener des campagnes publiques dans un cadre légal (pétitions, relais auprès de journalistes ou d'ONG)",
    "direct": "Agir techniquement sur des systèmes tiers sans autorisation",
    "tech": "Aucune : je suis là pour la technique",
}

THEMES = [
    "IA locale et agents", "TinyML et vision embarquée", "IoT et domotique", "SDR, RF, LoRa, Meshtastic",
    "Drones et FPV", "Impression 3D", "Vie privée et anonymat", "OSINT", "Sécurité défensive",
    "Rétro-ingénierie matérielle", "Modding et jeux", "Outils pour associations", "Autre",
]
CONTRIB = [
    "Prototyper", "Coder des outils", "Tester du matériel", "Documenter et écrire des tutoriels",
    "Veille et recherche", "Design et interface", "Animer la communauté", "Organiser",
]
MATERIEL = [
    "PC ou serveur", "Carte graphique pour l'IA", "Raspberry Pi", "ESP32", "Arduino", "Flipper Zero",
    "HackRF ou PortaPack", "RTL-SDR", "LoRa ou Meshtastic", "Imprimante 3D", "Drone",
    "Oscilloscope ou analyseur logique", "Autre",
]
FORMATS = ["Sessions de build en vocal", "Ateliers en ligne", "Hackathons mensuels", "Projets en binôme", "Veille partagée par écrit"]

CHARTE = [
    "On travaille sur notre matériel, nos réseaux, ou avec une autorisation explicite.",
    "On n'agit jamais contre des innocents ni pour de mauvaises raisons (vengeance, profit personnel, jeu), "
    "et on ne publie aucune donnée personnelle.",
    "On ne manipule pas de données volées ou issues d'une fuite.",
    "On signale les failles de façon responsable, avant toute publication.",
    "On partage ce qu'on apprend, et on décide ensemble de ce qu'on publie.",
]

SCENARIOS = {
    "s1": (
        "Tu découvres une faille sur le site d'une association locale en l'utilisant normalement. Tu :",
        {"a": "préviens discrètement le responsable", "b": "testes jusqu'où tu peux aller",
         "c": "publies pour faire pression", "d": "ignores"},
    ),
    "s2": (
        "Un membre propose de tester le WiFi de son voisin « pour voir s'il est sécurisé ». Tu :",
        {"a": "refuses et proposes de tester ton propre routeur", "b": "participes si le voisin ne le saura pas",
         "c": "regardes sans rien dire"},
    ),
    "s3": (
        "Quelqu'un partage dans le groupe une base de données fuitée contenant des données personnelles. Tu :",
        {"a": "demandes de la supprimer et expliques pourquoi", "b": "la télécharges pour l'étudier",
         "c": "l'utilises pour chercher des infos sur quelqu'un"},
    ),
}

TEMPS = ["Moins de 2 h", "2 à 5 h", "5 à 10 h", "Plus de 10 h"]
ANONYMAT = ["Pseudo seul", "Pseudo avec vocal", "Visio caméra coupée", "À visage découvert pour des rencontres en personne"]
PHYSIQUE = ["Oui", "Non", "Selon le lieu"]
TRENTE_JOURS = ["Oui", "Peut-être", "Non"]

# ---------------------------------------------------------------- chiffrement et stockage

_lock = threading.Lock()


def chiffrer(payload: dict) -> str:
    """Chiffre le dossier avec la clé publique (SealedBox) : le serveur ne peut pas le relire."""
    pub = PublicKey(base64.b64decode(cfg("PUBLIC_KEY")))
    brut = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(SealedBox(pub).encrypt(brut)).decode()


def stocker(ref: str, chiffre: str) -> None:
    if cfg("STORAGE", "file") == "supabase":
        url = cfg("SUPABASE_URL").rstrip("/") + "/rest/v1/responses"
        cle = cfg("SUPABASE_ANON_KEY")
        req = urllib.request.Request(
            url,
            data=json.dumps({"id": ref, "payload": chiffre}).encode(),
            method="POST",
            headers={
                "apikey": cle,
                "Authorization": f"Bearer {cle}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        urllib.request.urlopen(req, timeout=15).close()
    else:
        chemin = cfg("DATA_FILE", "responses.jsonl")
        with _lock, open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": ref, "payload": chiffre}) + "\n")


def telegram_actif() -> bool:
    return bool(cfg("TELEGRAM_BOT_TOKEN") and cfg("TELEGRAM_CHAT_ID"))


def contact_dans_telegram() -> bool:
    return str(cfg("TELEGRAM_INCLURE_CONTACT", "")).strip().lower() in ("1", "true", "oui", "yes")


def notifier_telegram(ref: str, chiffre: str, p: dict) -> None:
    """Envoie au bot un résumé de tri (sans le canal de contact, sauf réglage) + le dossier chiffré en fichier."""
    token, chat = cfg("TELEGRAM_BOT_TOKEN"), cfg("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError("Telegram non configuré")
    moyenne, pratiques, drapeaux = indicateurs(p)
    lignes = [
        f"🕶️ Nouvelle candidature {ref}",
        etiquette(drapeaux),
        f"Pseudo : {p['profil']['pseudo']}",
        f"Chapeau : {', '.join(p['profil']['chapeau']) or '—'}",
        f"Ancienneté : {p['profil']['anciennete'] or '—'}",
        f"Niveau moyen déclaré : {moyenne}/4 · réponses pratiques : {pratiques}/5",
        f"Thèmes : {', '.join(p['appetences']['themes'])}",
        f"Dispo : {p['dispo']['temps']} · anonymat : {p['dispo']['anonymat']}",
        f"Engagement : {p['motivations']['engagement']['texte']}",
    ]
    if drapeaux:
        lignes.append("À discuter : " + " ; ".join(drapeaux))
    if contact_dans_telegram():
        lignes.append(f"Contact : {p['profil']['contact']}")
    else:
        lignes.append("Contact : dans le dossier chiffré ci-dessous")
    base = f"https://api.telegram.org/bot{token}"
    requests.post(f"{base}/sendMessage", data={"chat_id": chat, "text": "\n".join(lignes)[:4000]},
                  timeout=15).raise_for_status()
    requests.post(
        f"{base}/sendDocument",
        data={"chat_id": chat, "caption": f"Dossier chiffré {ref} : python admin_decrypt.py read candidature_{ref}.enc"},
        files={"document": (f"candidature_{ref}.enc", chiffre.encode())},
        timeout=30,
    ).raise_for_status()


# ---------------------------------------------------------------- page


def accueil():
    st.title("🕶️ Collectif Hack, IA & Électro")
    st.markdown(
        """
Je Suis Trhacknon un Hacker Et Developpeur, Je me suis formé de maniere autodidacte.
Ce questionnaire sert à composer un petit collectif de hackers, makers et développeurs qui explorent
l'IA, l'électronique et les usages des équipements accessibles à tous. Compte 10 à 15 minutes ;
les champs marqués * sont obligatoires.

- **Ce qu'on fait** : veille, prototypes, expérimentations sur notre propre matériel, partage de méthodes et de documentation.
- **Ce qu'on ne fait pas** : attaquer un système sans autorisation, cibler des innocents ou agir par vengeance ou profit, exploiter des données volées.
- **Anonymat** : un pseudo suffit. Ne donne ni nom, ni adresse, ni photo.
- **Il n'y a pas de bonne réponse** : on cherche des gens curieux et honnêtes sur leur niveau, pas des experts autoproclamés.

**Toutes les couleurs de chapeau sont bienvenues** : white, grey, black, red, blue ou green hat.
On regarde ce que tu sais et comment tu raisonnes, pas l'étiquette.
"""
    )


def main():
    if not cfg("PUBLIC_KEY"):
        st.error("Configuration incomplète : la clé publique PUBLIC_KEY est absente (voir README).")
        st.stop()

    if st.session_state.get("done"):
        st.title("🕶️ Merci !")
        st.success("Tes réponses sont enregistrées, chiffrées. On te répond sur le canal que tu as indiqué.")
        st.caption("Ton code de suivi (à garder si tu veux écrire au sujet de ta candidature) :")
        st.code(st.session_state["ref"])
        st.stop()

    accueil()

    with st.form("questionnaire"):
        # ---- 1. Profil
        st.header("1 · Profil")
        pseudo = st.text_input("Pseudo *", key="pseudo", max_chars=40)
        contact = st.text_input(
            "Canal de contact sécurisé *", key="contact", max_chars=200,
            help="Signal, Matrix, SimpleX, Session ou e-mail chiffré. Pas de numéro ni d'adresse personnels si tu peux l'éviter.",
        )
        langues = st.multiselect("Langues", LANGUES, key="langues")
        anciennete = st.radio("Depuis quand bidouilles-tu ?", ANCIENNETE, index=None, key="anciennete")
        chapeau = st.multiselect(
            "Ta couleur de chapeau (facultatif)", HATS, key="chapeau",
            help="Une couleur suffit, inutile de détailler tes actes passés.",
        )
        parcours = st.multiselect("Ton parcours", PARCOURS, key="parcours")
        projet_fier = st.text_area(
            "Un projet dont tu es fier *", key="projet_fier", height=140, max_chars=3000,
            help="Ce que tu as construit, cassé ou compris, avec un lien si tu en as un.",
        )
        origine = st.text_input("Comment as-tu entendu parler de nous ?", key="origine", max_chars=200)

        # ---- 2. Compétences
        st.header("2 · Compétences techniques")
        st.caption("Auto-évaluation : 0 = jamais touché · 1 = notions · 2 = petits projets · 3 = autonome · 4 = je forme les autres.")
        niveaux = {}
        for i, (domaine, exemples) in enumerate(DOMAINES):
            niveaux[domaine] = st.select_slider(
                domaine, options=list(NIVEAUX), value=0, format_func=NIVEAUX.get, key=f"niv_{i}", help=exemples,
            )
        st.subheader("Questions pratiques")
        st.caption("Réponds à au moins 3 questions sur 5, en 3 à 6 lignes. L'honnêteté sur tes limites compte autant que la réponse.")
        pratique = [
            st.text_area(q, key=f"pratique_{i}", height=110, max_chars=2500) for i, q in enumerate(PRATIQUE)
        ]
        outils = st.text_input("Outils au quotidien", key="outils", max_chars=300,
                               help="Langages, systèmes, logiciels que tu utilises vraiment.")

        # ---- 3. Motivations
        st.header("3 · Motivations")
        pourquoi = st.text_area("Pourquoi veux-tu rejoindre ce collectif ? *", key="pourquoi", height=160, max_chars=3000,
                                help="5 lignes minimum.")
        apport = st.multiselect("Qu'apportes-tu concrètement ? *", APPORTS, key="apport")
        apport_detail = st.text_input("Précision sur ton apport (facultatif)", key="apport_detail", max_chars=300)
        attentes = st.multiselect("Qu'attends-tu de nous ? (3 maximum)", ATTENTES, key="attentes", max_selections=3)
        engagement = st.radio("Quelle forme d'engagement te correspond ? *", list(ENGAGEMENT), index=None,
                              format_func=ENGAGEMENT.get, key="engagement")
        quitter = st.text_input("Qu'est-ce qui te ferait quitter un collectif ?", key="quitter", max_chars=300)
        un_an = st.text_area("Ce que tu veux voir naître d'ici un an grâce à ce groupe", key="un_an", height=110, max_chars=2000)

        # ---- 4. Appétences
        st.header("4 · Appétences")
        themes = st.multiselect("Thèmes qui t'attirent * (5 maximum)", THEMES, key="themes", max_selections=5)
        contrib = st.multiselect("Façon de contribuer * (3 maximum)", CONTRIB, key="contrib", max_selections=3)
        materiel = st.multiselect("Matériel que tu possèdes", MATERIEL, key="materiel")
        projet_3m = st.text_area("Le projet dont tu rêves en 3 mois", key="projet_3m", height=130, max_chars=2500,
                                 help="L'idée, le matériel nécessaire, ce qui te bloque.")
        formats = st.multiselect("Format préféré (2 maximum)", FORMATS, key="formats", max_selections=2)

        # ---- 5. Éthique
        st.header("5 · Éthique et lignes rouges")
        st.caption("Cette section ne juge ni ton passé ni ta couleur de chapeau : elle évalue ton raisonnement.")
        st.markdown("**Charte du collectif**")
        st.markdown("\n".join(f"{i}. {c}" for i, c in enumerate(CHARTE, 1)))
        charte = st.checkbox("J'ai lu la charte et je l'accepte *", key="charte")
        st.subheader("Mises en situation")
        scenarios = {}
        for sid, (question, options) in SCENARIOS.items():
            choix = st.radio(question, list(options), index=None, format_func=lambda k, o=options: o[k], key=f"sc_{sid}")
            justif = st.text_input("Une phrase pour justifier", key=f"sc_{sid}_j", max_chars=400)
            scenarios[sid] = (choix, justif)
        criteres = st.text_area(
            "Un membre veut s'en prendre à une personne ou une organisation qu'il juge coupable. Quels critères exiges-tu "
            "avant d'accepter : quelles preuves, qui les vérifie, quelle proportion, quel risque pour des innocents, "
            "et que fais-tu si c'était une erreur ? *",
            key="criteres", height=180, max_chars=3000,
        )
        dual_use = st.text_area(
            "Tu as créé un outil qui pourrait servir à surveiller quelqu'un. Comment décides-tu de le publier ou non ?",
            key="dual_use", height=130, max_chars=2500,
        )
        lignes_rouges = st.text_area(
            "Y a-t-il des choses que tu refuserais de faire même si tout le groupe votait pour ? Lesquelles ?",
            key="lignes_rouges", height=110, max_chars=2000,
        )

        # ---- 6. Disponibilité
        st.header("6 · Disponibilité et fonctionnement")
        temps = st.radio("Temps par semaine *", TEMPS, index=None, key="temps")
        fuseau = st.text_input("Fuseau horaire et créneaux habituels", key="fuseau", max_chars=200)
        outils_com = st.text_input("Outils que tu utilises ou refuses (Signal, Matrix, SimpleX, Mumble, Discord, Git…)",
                                   key="outils_com", max_chars=300)
        anonymat = st.radio("Niveau d'anonymat souhaité *", ANONYMAT, index=None, key="anonymat")
        physique = st.radio("Rencontres physiques occasionnelles", PHYSIQUE, index=None, key="physique")
        trente_jours = st.radio("Peux-tu contribuer à un petit projet concret dans les 30 jours ? *", TRENTE_JOURS,
                                index=None, key="trente_jours")
        libre = st.text_area("Autre chose à nous dire ? Connais tu des collectifs de hackers ? Si Oui Que penses tu de leurs actions; Et de la maniere dont ils ciblent leurs 'victimes'", key="libre", height=100, max_chars=2000)

        st.divider()
        texte_consent = (
            "J'accepte que mes réponses soient stockées chiffrées et lues uniquement par l'organisateur, pour évaluer "
            "ma candidature. Elles seront supprimées sous 30 jours si je ne suis pas retenu(e)."
        )
        if telegram_actif():
            texte_consent += (
                " Un résumé (" + ("y compris mon canal de contact" if contact_dans_telegram() else "sans mon canal de contact")
                + ") est envoyé à l'organisateur par messagerie Telegram ; mon dossier complet y reste chiffré."
            )
        consent = st.checkbox(texte_consent + " *", key="consent")
        envoye = st.form_submit_button("Envoyer", type="primary")

    if not envoye:
        return

    # ---- validation
    erreurs = []
    if not pseudo.strip():
        erreurs.append("Pseudo obligatoire.")
    if not contact.strip():
        erreurs.append("Canal de contact obligatoire.")
    if len(projet_fier.strip()) < 30:
        erreurs.append("Décris ton projet en quelques phrases (30 caractères minimum).")
    if sum(len(t.strip()) >= 30 for t in pratique) < 3:
        erreurs.append("Réponds à au moins 3 questions pratiques (30 caractères minimum chacune).")
    if len(pourquoi.strip()) < 100:
        erreurs.append("Explique ta motivation un peu plus (100 caractères minimum).")
    if not apport:
        erreurs.append("Indique au moins un apport.")
    if engagement is None:
        erreurs.append("Choisis une forme d'engagement.")
    if not themes:
        erreurs.append("Choisis au moins un thème.")
    if not contrib:
        erreurs.append("Choisis au moins une façon de contribuer.")
    if not charte:
        erreurs.append("Tu dois accepter la charte.")
    if any(choix is None for choix, _ in scenarios.values()):
        erreurs.append("Réponds aux trois mises en situation.")
    if len(criteres.strip()) < 60:
        erreurs.append("Détaille tes critères de ciblage (60 caractères minimum).")
    if temps is None or anonymat is None or trente_jours is None:
        erreurs.append("Réponds aux questions de disponibilité marquées *.")
    if not consent:
        erreurs.append("Le consentement au stockage est obligatoire.")
    if erreurs:
        st.error("Il manque quelques éléments :\n\n" + "\n".join(f"- {e}" for e in erreurs))
        return

    # ---- enregistrement
    payload = {
        "version": 1,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "profil": {
            "pseudo": pseudo.strip(), "contact": contact.strip(), "langues": langues, "anciennete": anciennete,
            "chapeau": chapeau, "parcours": parcours, "projet_fier": projet_fier.strip(), "origine": origine.strip(),
        },
        "competences": {"niveaux": niveaux, "pratique": [t.strip() for t in pratique], "outils": outils.strip()},
        "motivations": {
            "pourquoi": pourquoi.strip(), "apport": apport, "apport_detail": apport_detail.strip(),
            "attentes": attentes, "engagement": {"choix": engagement, "texte": ENGAGEMENT[engagement]},
            "quitter": quitter.strip(), "un_an": un_an.strip(),
        },
        "appetences": {
            "themes": themes, "contribution": contrib, "materiel": materiel,
            "projet_3_mois": projet_3m.strip(), "formats": formats,
        },
        "ethique": {
            "charte_acceptee": True,
            "scenarios": {
                sid: {"choix": choix, "texte": SCENARIOS[sid][1][choix], "justification": justif.strip()}
                for sid, (choix, justif) in scenarios.items()
            },
            "criteres_ciblage": criteres.strip(), "dual_use": dual_use.strip(), "lignes_rouges": lignes_rouges.strip(),
        },
        "dispo": {
            "temps": temps, "fuseau": fuseau.strip(), "outils_com": outils_com.strip(), "anonymat": anonymat,
            "physique": physique, "trente_jours": trente_jours, "libre": libre.strip(),
        },
    }
    ref = uuid.uuid4().hex[:10].upper()
    solo_telegram = cfg("STORAGE", "file") == "telegram"  # Telegram sert alors de seul stockage
    try:
        chiffre = chiffrer(payload)
        if solo_telegram:
            notifier_telegram(ref, chiffre, payload)
        else:
            stocker(ref, chiffre)
    except Exception:
        st.error("L'enregistrement a échoué. Réessaie dans quelques minutes.")
        return
    if not solo_telegram and telegram_actif():
        try:
            notifier_telegram(ref, chiffre, payload)
        except Exception:
            print("Notification Telegram : échec d'envoi")  # sans détail : l'URL contient le jeton
    st.session_state["done"] = True
    st.session_state["ref"] = ref
    st.rerun()


main()
