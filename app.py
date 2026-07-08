import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import requests
import streamlit as st

DB_PATH = Path(__file__).with_name("vocabulary.db")

RATING_INTERVALS = {
    "Again": 1,
    "Hard": 3,
    "Good": 7,
    "Easy": 14,
}

AI_FIELDS = [
    "english_translation",
    "russian_translation",
    "pronunciation",
    "explanation_fr",
    "explanation_en",
    "example_fr",
    "example_en",
]


# ---------- Database ----------

def connect_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                french_word TEXT NOT NULL,
                english_translation TEXT,
                russian_translation TEXT,
                explanation_fr TEXT,
                explanation_en TEXT,
                example_fr TEXT,
                example_en TEXT,
                pronunciation TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                last_reviewed TEXT,
                next_review TEXT NOT NULL,
                review_count INTEGER NOT NULL DEFAULT 0,
                difficulty TEXT NOT NULL DEFAULT 'New'
            )
            """
        )
        conn.commit()


def add_word(data):
    today = date.today().isoformat()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO words (
                french_word, english_translation, russian_translation,
                explanation_fr, explanation_en, example_fr, example_en,
                pronunciation, notes, created_at, next_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["french_word"].strip(),
                data["english_translation"].strip(),
                data["russian_translation"].strip(),
                data["explanation_fr"].strip(),
                data["explanation_en"].strip(),
                data["example_fr"].strip(),
                data["example_en"].strip(),
                data["pronunciation"].strip(),
                data["notes"].strip(),
                today,
                today,
            ),
        )
        conn.commit()


def get_all_words(search_term=""):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        if search_term:
            rows = conn.execute(
                """
                SELECT * FROM words
                WHERE french_word LIKE ?
                   OR english_translation LIKE ?
                   OR russian_translation LIKE ?
                ORDER BY french_word COLLATE NOCASE
                """,
                (f"%{search_term}%",) * 3,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM words ORDER BY french_word COLLATE NOCASE"
            ).fetchall()
    return rows


def get_words_due_until(end_date):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT * FROM words
            WHERE next_review <= ?
            ORDER BY next_review ASC, french_word COLLATE NOCASE
            """,
            (end_date.isoformat(),),
        ).fetchall()


def update_review(word_id, rating):
    today = date.today()
    next_review = today + timedelta(days=RATING_INTERVALS[rating])
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE words
            SET last_reviewed = ?, next_review = ?,
                review_count = review_count + 1, difficulty = ?
            WHERE id = ?
            """,
            (today.isoformat(), next_review.isoformat(), rating, word_id),
        )
        conn.commit()


def delete_word(word_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()


# ---------- Free public data sources (no API key) ----------

WIKTIONARY_URL = "https://fr.wiktionary.org/w/api.php"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
HEADERS = {"User-Agent": "FrenchVocabApp/1.0 (personal learning tool)"}


def fetch_wiktionary(word: str) -> str:
    """Fetch raw wikitext of a French word page from fr.wiktionary.org."""
    params = {
        "action": "parse",
        "page": word,
        "format": "json",
        "prop": "wikitext",
        "redirects": 1,
    }
    r = requests.get(WIKTIONARY_URL, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        return ""
    return data.get("parse", {}).get("wikitext", {}).get("*", "")


def extract_ipa(wikitext: str) -> str:
    """Pull IPA out of {{pron|...|fr}} template."""
    m = re.search(r"\{\{pron\|([^|}]+)\|fr\}\}", wikitext)
    if m:
        ipa = m.group(1).strip()
        return f"/{ipa}/"
    return ""


def _clean_wiki(text: str) -> str:
    """Strip common wikitext markup for display."""
    # Remove templates {{...}}
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # [[link|display]] -> display, [[link]] -> link
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # ''italic'' and '''bold'''
    text = re.sub(r"'{2,}", "", text)
    return text.strip(" *#:;-").strip()


def extract_definition_fr(wikitext: str) -> str:
    """Pull the first numbered definition from the French section."""
    # Locate French section (== {{langue|fr}} ==)
    fr_match = re.search(r"==\s*\{\{langue\|fr\}\}\s*==", wikitext)
    section = wikitext[fr_match.end():] if fr_match else wikitext
    # Stop at next language
    next_lang = re.search(r"\n==\s*\{\{langue\|", section)
    if next_lang:
        section = section[: next_lang.start()]
    # First numbered line "# definition"
    for line in section.splitlines():
        line = line.rstrip()
        if line.startswith("#") and not line.startswith("#*") and not line.startswith("#:"):
            return _clean_wiki(line[1:])
    return ""


def extract_example_fr(wikitext: str) -> str:
    """Pull the first example from the French section (lines starting with #*)."""
    fr_match = re.search(r"==\s*\{\{langue\|fr\}\}\s*==", wikitext)
    section = wikitext[fr_match.end():] if fr_match else wikitext
    next_lang = re.search(r"\n==\s*\{\{langue\|", section)
    if next_lang:
        section = section[: next_lang.start()]
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("#*") and not stripped.startswith("#*:"):
            example = _clean_wiki(stripped[2:])
            if example:
                return example
    return ""


def mymemory_translate(text: str, lang_pair: str) -> str:
    """Free translation API — up to ~5000 words/day anonymous."""
    if not text:
        return ""
    try:
        r = requests.get(
            MYMEMORY_URL,
            params={"q": text, "langpair": lang_pair},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("responseData", {}).get("translatedText", "")
    except Exception:
        return ""


def generate_word_data(french_word: str) -> dict:
    """Use Wiktionary + MyMemory to fill in fields — no API key required."""
    result = {f: "" for f in AI_FIELDS}
    wikitext = fetch_wiktionary(french_word)

    if wikitext:
        result["pronunciation"] = extract_ipa(wikitext)
        result["explanation_fr"] = extract_definition_fr(wikitext)
        result["example_fr"] = extract_example_fr(wikitext)

    # Translations via MyMemory
    result["english_translation"] = mymemory_translate(french_word, "fr|en")
    result["russian_translation"] = mymemory_translate(french_word, "fr|ru")

    if result["explanation_fr"]:
        result["explanation_en"] = mymemory_translate(result["explanation_fr"], "fr|en")

    if result["example_fr"]:
        result["example_en"] = mymemory_translate(result["example_fr"], "fr|en")

    return result


# ---------- UI ----------

def show_word_card(row, show_review_buttons=False):
    with st.container(border=True):
        st.subheader(row["french_word"])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**English:** {row['english_translation'] or '-'}")
            st.markdown(f"**Russian:** {row['russian_translation'] or '-'}")
            st.markdown(f"**Pronunciation:** {row['pronunciation'] or '-'}")
        with col2:
            st.markdown(f"**Next review:** {row['next_review']}")
            st.markdown(f"**Reviews:** {row['review_count']}")
            st.markdown(f"**Difficulty:** {row['difficulty']}")

        st.markdown("**Explanation in French:**")
        st.write(row["explanation_fr"] or "-")
        st.markdown("**Explanation in English:**")
        st.write(row["explanation_en"] or "-")

        st.markdown("**Example:**")
        st.write(row["example_fr"] or "-")
        st.write(row["example_en"] or "-")

        if row["notes"]:
            st.markdown("**Notes:**")
            st.write(row["notes"])

        if show_review_buttons:
            st.markdown("**How well did you remember this word?**")
            cols = st.columns(4)
            for i, rating in enumerate(RATING_INTERVALS.keys()):
                with cols[i]:
                    if st.button(rating, key=f"review_{row['id']}_{rating}"):
                        update_review(row["id"], rating)
                        st.success(f"Saved. Next review in {RATING_INTERVALS[rating]} day(s).")
                        st.rerun()


def add_word_page():
    st.header("Add a French word")
    st.write("Type a French word, auto-fill from Wiktionary + MyMemory, then edit and save.")

    prefill = st.session_state.setdefault("prefill", {f: "" for f in AI_FIELDS})

    with st.container(border=True):
        st.markdown("**Auto-fill from public sources**")
        st.caption("Uses fr.wiktionary.org for IPA + French definition, and MyMemory for translations. Free, no key.")

        word_to_generate = st.text_input(
            "French word",
            key="ai_word_input",
            placeholder="préserver",
        )
        if st.button("Auto-fill", type="primary"):
            if not word_to_generate.strip():
                st.error("Enter a French word first.")
            else:
                try:
                    with st.spinner("Fetching data..."):
                        result = generate_word_data(word_to_generate.strip())
                    if not any(result.values()):
                        st.warning("Nothing found. Check spelling, or fill in manually below.")
                    else:
                        st.session_state["prefill"] = result
                        st.session_state["prefill_french"] = word_to_generate.strip()
                        st.success("Fields filled. Review below and save.")
                        st.rerun()
                except requests.RequestException as e:
                    st.error(f"Network error: {e}")

    with st.form("add_word_form", clear_on_submit=True):
        french_word = st.text_input(
            "French word *",
            value=st.session_state.get("prefill_french", ""),
            placeholder="préserver",
        )
        english_translation = st.text_input("English translation", value=prefill["english_translation"])
        russian_translation = st.text_input("Russian translation", value=prefill["russian_translation"])
        pronunciation = st.text_input("Pronunciation", value=prefill["pronunciation"], placeholder="/pʁe.zɛʁ.ve/")
        explanation_fr = st.text_area("Explanation in French", value=prefill["explanation_fr"])
        explanation_en = st.text_area("Explanation in English", value=prefill["explanation_en"])
        example_fr = st.text_area("Example in French", value=prefill["example_fr"])
        example_en = st.text_area("Example in English", value=prefill["example_en"])
        notes = st.text_area("Notes", placeholder="Grammar notes, synonyms, common mistakes...")

        submitted = st.form_submit_button("Save word")

    if submitted:
        if not french_word.strip():
            st.error("Please enter a French word.")
            return
        add_word({
            "french_word": french_word,
            "english_translation": english_translation,
            "russian_translation": russian_translation,
            "pronunciation": pronunciation,
            "explanation_fr": explanation_fr,
            "explanation_en": explanation_en,
            "example_fr": example_fr,
            "example_en": example_en,
            "notes": notes,
        })
        st.session_state["prefill"] = {f: "" for f in AI_FIELDS}
        st.session_state["prefill_french"] = ""
        st.success(f"Saved: {french_word}")


def vocabulary_page():
    st.header("My vocabulary")
    search_term = st.text_input("Search", placeholder="Search French, English, or Russian")
    rows = get_all_words(search_term)

    if not rows:
        st.info("No words found yet.")
        return

    st.write(f"Total words: {len(rows)}")
    for row in rows:
        show_word_card(row)
        if st.button("Delete", key=f"delete_{row['id']}"):
            delete_word(row["id"])
            st.warning(f"Deleted: {row['french_word']}")
            st.rerun()


def review_page():
    st.header("Review today")
    rows = get_words_due_until(date.today())
    if not rows:
        st.success("No words to review today. Great job!")
        return
    st.write(f"Words due today: {len(rows)}")
    for row in rows:
        show_word_card(row, show_review_buttons=True)


def weekly_review_page():
    st.header("Weekly review")
    end_date = date.today() + timedelta(days=7)
    rows = get_words_due_until(end_date)
    if not rows:
        st.success("No words scheduled for review this week.")
        return
    st.write(f"Words to review from today until {end_date.isoformat()}: {len(rows)}")
    for row in rows:
        show_word_card(row)


def statistics_page():
    st.header("Statistics")
    rows = get_all_words()
    total = len(rows)
    due_today = len(get_words_due_until(date.today()))
    due_week = len(get_words_due_until(date.today() + timedelta(days=7)))

    col1, col2, col3 = st.columns(3)
    col1.metric("Total words", total)
    col2.metric("Due today", due_today)
    col3.metric("Due this week", due_week)

    if total:
        counts = {}
        for row in rows:
            counts[row["difficulty"]] = counts.get(row["difficulty"], 0) + 1
        st.subheader("Difficulty")
        st.bar_chart(counts)


def main():
    st.set_page_config(page_title="French Vocabulary Engine", page_icon="FR", layout="wide")
    init_db()

    st.title("French Vocabulary Engine")
    st.caption("Personal French learning app — spaced repetition + free auto-fill.")

    page = st.sidebar.radio(
        "Menu",
        ["Add Word", "My Vocabulary", "Review Today", "Weekly Review", "Statistics"],
    )

    if page == "Add Word":
        add_word_page()
    elif page == "My Vocabulary":
        vocabulary_page()
    elif page == "Review Today":
        review_page()
    elif page == "Weekly Review":
        weekly_review_page()
    elif page == "Statistics":
        statistics_page()


if __name__ == "__main__":
    main()
