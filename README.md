# Questionnaire — Collectif Hack, IA & Électro

Formulaire Streamlit de candidature. Les réponses sont **chiffrées avec une clé publique** avant
d'être stockées ou envoyées : le serveur (et son hébergeur) ne peut pas les lire, seul toi, avec la clé privée.
Chaque candidature peut arriver sur Telegram avec une étiquette de tri : 🟢 à regarder en priorité, 🟡 à discuter, 🔴 profil fragile.

## Lancer en local

```bash
pip install -r requirements.txt
python admin_decrypt.py keygen          # crée private.key, affiche la clé publique
export PUBLIC_KEY="<clé publique affichée>"
streamlit run app.py
```

Les réponses s'écrivent dans `responses.jsonl` (chiffrées). Garde `private.key` **hors ligne** : sans elle, rien n'est lisible.

## Recevoir les candidatures sur Telegram

Un bot ne peut pas écrire à un `@pseudo` : il faut créer ton propre bot et lui parler une fois.

1. Dans Telegram, ouvre **@BotFather**, envoie `/newbot`, choisis un nom : tu reçois un **jeton** (`123456:ABC…`). Ne le publie jamais.
2. Ouvre ton nouveau bot et appuie sur **Démarrer** (`/start`).
3. Récupère ton identifiant de chat :
   ```bash
   python admin_decrypt.py telegram-setup --token <jeton>
   ```
   Il affiche `TELEGRAM_CHAT_ID = <nombre>`.
4. Ajoute dans les secrets de l'app : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.

À chaque candidature, le bot t'envoie deux choses :

- un **message de tri** : étiquette, pseudo, couleur de chapeau, niveau moyen déclaré, réponses pratiques remplies, thèmes, disponibilité, points à discuter ;
- un **fichier `candidature_<code>.enc`** : le dossier complet, chiffré, avec le canal de contact.

Pour lire un dossier, télécharge le fichier sur ton ordinateur :

```bash
python admin_decrypt.py read candidature_AB12CD34EF.enc --key private.key
```

Les messages de bot ne sont pas chiffrés de bout en bout : par défaut, le canal de contact reste donc dans le fichier chiffré.
Pour le recevoir directement dans le message, mets `TELEGRAM_INCLURE_CONTACT=1` ; le consentement affiché aux candidats s'adapte.

**Telegram comme seul stockage.** Avec `STORAGE=telegram`, l'app n'écrit rien sur le disque : les fichiers `.enc` restent dans ta conversation
avec le bot, ce qui évite Supabase sur un hébergement gratuit. Si l'envoi échoue, le candidat voit une erreur et peut réessayer.
Pour exporter plusieurs dossiers d'un coup, mets les `.enc` téléchargés dans un dossier :

```bash
python admin_decrypt.py export --dir telegram/ --key private.key
```

Si le jeton fuite, révoque-le avec `/revoke` dans @BotFather.

## Réglages (secrets Streamlit ou variables d'environnement)

| Nom | Rôle |
| --- | --- |
| `PUBLIC_KEY` | clé publique (obligatoire) |
| `STORAGE` | `file` (défaut), `supabase` ou `telegram` |
| `DATA_FILE` | chemin du fichier si `STORAGE=file` (défaut `responses.jsonl`) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | si `STORAGE=supabase` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | active les notifications Telegram |
| `TELEGRAM_INCLURE_CONTACT` | `1` pour mettre le canal de contact dans le message (défaut : non) |

En local, mets les secrets dans `.streamlit/secrets.toml` (ne le publie jamais sur Git) :

```toml
PUBLIC_KEY = "..."
STORAGE = "file"
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHAT_ID = "..."
```

## Où l'héberger

| Option | Coût | Stockage | À savoir |
| --- | --- | --- | --- |
| Raspberry Pi / petit VPS + Cloudflare Tunnel | 0 € avec un Pi | fichier local | tu gardes la main ; pas de port à ouvrir |
| Streamlit Community Cloud | gratuit | **éphémère** : `telegram` ou Supabase | déploiement depuis un dépôt GitHub (privé possible) |
| Hugging Face Spaces (SDK Streamlit) | gratuit | **éphémère** : `telegram` ou Supabase | pareil |
| Framaforms ou CryptPad Form | gratuit | chez eux | sans code, mais sans le tri ni Telegram |

Sur Streamlit Cloud ou Hugging Face, le disque est effacé à chaque redémarrage : utilise `STORAGE=telegram` ou Supabase.

### Supabase (stockage gratuit)

Dans l'éditeur SQL de ton projet :

```sql
create table responses (
  id text primary key,
  created_at timestamptz default now(),
  payload text not null
);
alter table responses enable row level security;
create policy "insertion seule" on responses for insert to anon with check (true);
```

La clé `anon` peut seulement **ajouter** des lignes, jamais les lire. Pour lire, utilise la clé
`service_role` en local uniquement :

```bash
export SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
python admin_decrypt.py export --supabase --key private.key
```

## Lire les candidatures

```bash
python admin_decrypt.py export --file responses.jsonl --key private.key
```

Produit `candidats.csv` (vue d'ensemble : étiquette de tri, moyenne déclarée, questions pratiques
remplies, points « à discuter ») et `dossiers/<code>.md` (un dossier lisible par candidat).
Les indicateurs aident au tri ; la notation finale suit la grille de lecture du document.

## À savoir

- L'hébergeur voit l'adresse IP des visiteurs ; l'app, elle, n'enregistre ni IP ni cookie de suivi.
- Aucun anti-spam : si le lien circule beaucoup, ajoute un mot de passe d'accès ou un captcha.
- Supprime les candidatures refusées sous 30 jours, comme annoncé dans le consentement (y compris dans la conversation Telegram).
- Le questionnaire est dans `app.py` : modifie les listes en haut du fichier pour changer les questions.
- Les règles de tri sont dans `triage.py`.
