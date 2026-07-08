# French Vocabulary Engine

A simple Streamlit + SQLite app for learning French vocabulary with spaced repetition.

## What it does

- Add French words manually
- Save English and Russian translations
- Save explanations in French and English
- Save French and English examples
- Review words due today
- See words due this week
- Mark words as Again, Hard, Good, or Easy
- Automatically schedule the next review date

## How to run it

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Install the requirements:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
streamlit run app.py
```

The app will open in your browser.

## Review system

- Again: review in 1 day
- Hard: review in 3 days
- Good: review in 7 days
- Easy: review in 14 days

## Next improvement ideas

- Add AI generation for translations and examples
- Add audio pronunciation
- Add tags, levels, and grammar categories
- Export vocabulary to CSV
- Add quizzes
