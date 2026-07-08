# French Vocabulary Engine

A simple Streamlit + SQLite app for learning French vocabulary with spaced repetition and AI-generated word cards.

## What it does

- Type a French word and let Claude fill in translation, IPA, explanations, and example sentences
- Save English and Russian translations
- Explanations in French and English
- French and English example sentences
- Review words due today
- Weekly review view
- Rate as Again / Hard / Good / Easy; next review date is scheduled automatically

## Setup

1. Install Python 3.10+.
2. Install the requirements:

```bash
pip install -r requirements.txt
```

3. Get an Anthropic API key from https://console.anthropic.com/settings/keys.

4. Provide the key in one of three ways:

**Environment variable (recommended for local dev):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Streamlit secrets (recommended for Streamlit Cloud):**
Create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

**Sidebar input:** paste the key into the "Anthropic API key" field in the sidebar.

5. Run the app:

```bash
streamlit run app.py
```

## Using AI generation

On the "Add Word" page, type a French word in the "Generate with Claude" box and click **Generate**. Claude fills in all fields; edit them if you want, then click **Save word**.

Model used: `claude-haiku-4-5-20251001` (fast and cheap; ~fractions of a cent per word).

## Review system

- Again: review in 1 day
- Hard: review in 3 days
- Good: review in 7 days
- Easy: review in 14 days

## Deploying on Streamlit Cloud

Add `ANTHROPIC_API_KEY` under **App settings → Secrets** on Streamlit Cloud. The app will pick it up via `st.secrets`.

## Ideas for next steps

- Audio pronunciation (ElevenLabs / Google TTS)
- Tags, CEFR levels, grammar categories
- Export to CSV / Anki
- Quiz mode
