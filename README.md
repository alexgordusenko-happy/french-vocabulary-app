# French Vocabulary Engine

Personal French vocabulary app: Streamlit + SQLite + spaced repetition. Auto-fills word cards from **free public sources** — no API key or subscription required.

## What it does

- Type a French word and it fills in:
  - IPA pronunciation (from French Wiktionary)
  - Short French definition (from Wiktionary)
  - English and Russian translations (from MyMemory Translation)
  - A French example sentence when available, translated to English
- Save your own notes
- Spaced-repetition review (Again / Hard / Good / Easy)
- Search your vocabulary
- Statistics

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

That's it. No account, no billing, no keys.

## Data sources

- **fr.wiktionary.org** via the MediaWiki API — for IPA and the French definition
- **api.mymemory.translated.net** — free translation, ~5000 words/day anonymous per IP

## Limitations vs a paid AI

- Wiktionary won't have every conjugated form; search for the base form (e.g. `préserver`, not `préservais`)
- MyMemory translations are decent but not as smooth as Claude / GPT
- If auto-fill returns nothing, just edit the fields manually and save

If you later want higher-quality generation, you can swap in the Anthropic API (previous version of this app is available on request).

## Review system

- Again: 1 day
- Hard: 3 days
- Good: 7 days
- Easy: 14 days

## Ideas

- Audio pronunciation via `gTTS` (also free, no key)
- CSV / Anki export
- Quiz mode
- Fallback lookup on en.wiktionary.org when fr.wiktionary has no page
