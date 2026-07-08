# French Vocabulary Engine

Personal French flashcards app: Streamlit + SQLite + spaced repetition. Auto-generates well-formatted cards using **Google Gemini's free API tier** — no billing required.

## Card format

Each generated card looks like:

```
1. encombrant / encombrante
Meaning / English: bulky, cumbersome, takes up too much space
Русский: громоздкий, неудобный, занимающий много места
Use / Français : On utilise encombrant pour parler d'un objet qui prend beaucoup de place ou qui gêne.

Exemple : Ce fauteuil est trop encombrant pour mon petit appartement.
   English: This armchair is too bulky for my small apartment.
   Русский: Это кресло слишком громоздкое для моей маленькой квартиры.

Exemple : ... (two more)

Prononciation : [ɑ̃.kɔ̃.bʁɑ̃] / [ɑ̃.kɔ̃.bʁɑ̃t]
```

When a word can be both a noun and a verb, Gemini picks example sentences that cover both senses.

## Setup

1. Install Python 3.10+.
2. Install requirements:

```bash
pip install -r requirements.txt
```

3. Get a **free** Gemini API key at https://aistudio.google.com/apikey (Google login, no credit card needed).
4. Provide the key one of three ways:

**Sidebar (easiest):** paste it into the "Gemini API key" field in the app sidebar.

**Env variable:**
```bash
export GEMINI_API_KEY="AIza..."
streamlit run app.py
```

**Streamlit Cloud secrets** (for deployment) — in `.streamlit/secrets.toml`:
```toml
GEMINI_API_KEY = "AIza..."
```

5. Run:

```bash
streamlit run app.py
```

## Free tier limits

Gemini 2.0 Flash free tier: 15 requests per minute, 1,500 per day. Plenty for personal vocab building.

## Review system

- Again: 1 day
- Hard: 3 days
- Good: 7 days
- Easy: 14 days

## Notes

- The database file `vocabulary.db` is created next to `app.py` on first run.
- When deploying on Streamlit Cloud, the DB is ephemeral — export important data or move to Postgres for persistence.

## Ideas

- CSV / Anki export
- Audio pronunciation (gTTS, free)
- Tags and CEFR levels
- Quiz mode
