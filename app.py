import json
import os
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

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

AI_FIELDS = [
    "alt_form",
    "pronunciation",
    "alt_pronunciation",
    "english_translation",   # holds "Meaning / English"
    "russian_translation",   # holds "Русский"
    "explanation_fr",        # holds "Use / Français" (the "On utilise..." sentence)
    "example_fr",
    "example_en",
    "example_ru",
]

EX_SEP = "\n\n"  # separator between example sentences inside a single column


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
                alt_form TEXT,
                pronunciation TEXT,
                alt_pronunciation TEXT,
                english_translation TEXT,
                russian_translation TEXT,
                explanation_fr TEXT,
                explanation_en TEXT,
                example_fr TEXT,
                example_en TEXT,
                example_ru TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                last_reviewed TEXT,
                next_review TEXT NOT NULL,
                review_count INTEGER NOT NULL DEFAULT 0,
                difficulty TEXT NOT NULL DEFAULT 'New'
            )
            """
        )
        # Migrations for older DBs
        cols = [r[1] for r in conn.execute("PRAGMA table_info(words)").fetchall()]
        for col in ["alt_form", "alt_pronunciation", "example_ru"]:
            if col not in cols:
                conn.execute(f"ALTER TABLE words ADD COLUMN {col} TEXT")
        conn.commit()


def add_word(data):
    today = date.today().isoformat()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO words (
                french_word, alt_form, pronunciation, alt_pronunciation,
                english_translation, russian_translation,
                explanation_fr,
                example_fr, example_en, example_ru,
                notes, created_at, next_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["french_word"].strip(),
                data.get("alt_form", "").strip(),
                data.get("pronunciation", "").strip(),
                data.get("alt_pronunciation", "").strip(),
                data.get("english_translation", "").strip(),
                data.get("russian_translation", "").strip(),
                data.get("explanation_fr", "").strip(),
                data.get("example_fr", "").strip(),
                data.get("example_en", "").strip(),
                data.get("example_ru", "").strip(),
                data.get("notes", "").strip(),
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


# ---------- Gemini (free tier, no billing) ----------

def get_api_key() -> str:
    if st.session_state.get("gemini_api_key"):
        return st.session_state["gemini_api_key"]
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def generate_word_data(french_word: str, api_key: str) -> dict:
    """Ask Gemini for a fully-structured flashcard. Free-tier friendly."""
    prompt = f"""You are a French vocabulary teacher preparing flashcards for a Russian-speaking learner of French.

For the French word or expression: "{french_word}"

Return ONLY a JSON object with these EXACT keys:
- "word": string — the canonical French form
- "alt_form": string — alternate form when relevant (feminine for adjectives, feminine noun, plural, or noun/verb variant). Empty string "" if none.
- "pronunciation": string — IPA in square brackets, e.g. "[ɑ̃.kɔ̃.bʁɑ̃]"
- "alt_pronunciation": string — IPA of alt_form. Empty "" if no alt_form.
- "meaning_en": string — short comma-separated English meanings, e.g. "bulky, cumbersome, takes up too much space"
- "meaning_ru": string — short comma-separated Russian meanings, e.g. "громоздкий, неудобный, занимающий много места"
- "use_fr": string — ONE natural French sentence starting with "On utilise" explaining when to use the word
- "examples": array of EXACTLY 3 objects, each with keys "fr", "en", "ru" — short, natural sentences. If the word can be both a noun and a verb, include both senses across the examples.

Return ONLY the JSON. No markdown code fences, no commentary."""

    r = requests.post(
        GEMINI_URL,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.4,
            },
        },
        timeout=45,
    )
    r.raise_for_status()
    payload = r.json()

    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected Gemini response: {payload}")

    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    data = json.loads(text)
    examples = data.get("examples") or []

    return {
        "alt_form": (data.get("alt_form") or "").strip(),
        "pronunciation": (data.get("pronunciation") or "").strip(),
        "alt_pronunciation": (data.get("alt_pronunciation") or "").strip(),
        "english_translation": (data.get("meaning_en") or "").strip(),
        "russian_translation": (data.get("meaning_ru") or "").strip(),
        "explanation_fr": (data.get("use_fr") or "").strip(),
        "example_fr": EX_SEP.join((e.get("fr") or "").strip() for e in examples),
        "example_en": EX_SEP.join((e.get("en") or "").strip() for e in examples),
        "example_ru": EX_SEP.join((e.get("ru") or "").strip() for e in examples),
    }


# ---------- UI helpers ----------

def _split_ex(block: str) -> list:
    return [s.strip() for s in (block or "").split(EX_SEP) if s.strip()]


def _val(row, key):
    """Safe access for optional columns."""
    try:
        v = row[key]
        return v if v is not None else ""
    except (KeyError, IndexError):
        return ""


def show_word_card(row, show_review_buttons=False, idx=None):
    with st.container(border=True):
        head = row["french_word"]
        alt = _val(row, "alt_form")
        if alt:
            head = f"{head} / {alt}"
        if idx is not None:
            st.subheader(f"{idx}. {head}")
        else:
            st.subheader(head)

        st.markdown(f"**Meaning / English:** {_val(row, 'english_translation') or '-'}")
        st.markdown(f"**Русский:** {_val(row, 'russian_translation') or '-'}")

        use_fr = _val(row, "explanation_fr")
        if use_fr:
            st.markdown(f"**Use / Français :** {use_fr}")

        fr_lines = _split_ex(_val(row, "example_fr"))
        en_lines = _split_ex(_val(row, "example_en"))
        ru_lines = _split_ex(_val(row, "example_ru"))

        if fr_lines:
            st.markdown("**Examples:**")
            for i, fr in enumerate(fr_lines):
                st.markdown(f"**Exemple :** {fr}")
                if i < len(en_lines) and en_lines[i]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;English: {en_lines[i]}", unsafe_allow_html=True)
                if i < len(ru_lines) and ru_lines[i]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;Русский: {ru_lines[i]}", unsafe_allow_html=True)

        pron = _val(row, "pronunciation")
        alt_pron = _val(row, "alt_pronunciation")
        if pron or alt_pron:
            combined = " / ".join(x for x in [pron, alt_pron] if x)
            st.markdown(f"**Prononciation :** {combined}")

        with st.expander("Review info"):
            st.caption(
                f"Next review: {row['next_review']} · Reviews: {row['review_count']} · Difficulty: {row['difficulty']}"
            )

        notes = _val(row, "notes")
        if notes:
            st.markdown(f"**Notes:** {notes}")

        if show_review_buttons:
            st.markdown("**How well did you remember this word?**")
            cols = st.columns(4)
            for i, rating in enumerate(RATING_INTERVALS.keys()):
                with cols[i]:
                    if st.button(rating, key=f"review_{row['id']}_{rating}"):
                        update_review(row["id"], rating)
                        st.success(f"Saved. Next review in {RATING_INTERVALS[rating]} day(s).")
                        st.rerun()


# ---------- Pages ----------

def add_word_page():
    st.header("Add a French word")

    prefill = st.session_state.setdefault("prefill", {f: "" for f in AI_FIELDS})
    api_key = get_api_key()

    with st.container(border=True):
        st.markdown("**Auto-fill with Gemini** (free tier)")
        st.caption("Uses Google Gemini to generate a full flashcard: alt form, both IPAs, meaning EN + RU, use in French, 3 example triples.")
        if not api_key:
            st.warning("No Gemini API key found. Paste one in the sidebar, or set GEMINI_API_KEY in your environment / secrets.toml.")

        word_to_generate = st.text_input(
            "French word",
            key="ai_word_input",
            placeholder="encombrant",
        )
        if st.button("Auto-fill", type="primary", disabled=not api_key):
            if not word_to_generate.strip():
                st.error("Enter a French word first.")
            else:
                try:
                    with st.spinner("Asking Gemini..."):
                        result = generate_word_data(word_to_generate.strip(), api_key)
                    st.session_state["prefill"] = result
                    st.session_state["prefill_french"] = word_to_generate.strip()
                    st.success("Fields filled. Review below and save.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Gemini didn't return valid JSON. Try again.")
                except requests.HTTPError as e:
                    st.error(f"Gemini API error: {e.response.status_code} — {e.response.text[:300]}")
                except Exception as e:
                    st.error(f"Error: {e}")

    with st.form("add_word_form", clear_on_submit=True):
        french_word = st.text_input(
            "French word *",
            value=st.session_state.get("prefill_french", ""),
            placeholder="encombrant",
        )
        alt_form = st.text_input("Alt form (feminine / plural / noun-vs-verb)", value=prefill["alt_form"])

        c1, c2 = st.columns(2)
        with c1:
            pronunciation = st.text_input("Pronunciation", value=prefill["pronunciation"], placeholder="[ɑ̃.kɔ̃.bʁɑ̃]")
        with c2:
            alt_pronunciation = st.text_input("Alt pronunciation", value=prefill["alt_pronunciation"], placeholder="[ɑ̃.kɔ̃.bʁɑ̃t]")

        english_translation = st.text_input("Meaning / English", value=prefill["english_translation"])
        russian_translation = st.text_input("Русский", value=prefill["russian_translation"])
        explanation_fr = st.text_area("Use / Français (On utilise...)", value=prefill["explanation_fr"])

        st.caption("Examples: keep sentences in matching order across FR / EN / RU (separated by blank lines).")
        example_fr = st.text_area("Examples in French", value=prefill["example_fr"], height=160)
        example_en = st.text_area("Examples in English", value=prefill["example_en"], height=160)
        example_ru = st.text_area("Examples in Russian", value=prefill["example_ru"], height=160)

        notes = st.text_area("Notes", placeholder="Grammar notes, synonyms, common mistakes...")

        submitted = st.form_submit_button("Save word")

    if submitted:
        if not french_word.strip():
            st.error("Please enter a French word.")
            return
        add_word({
            "french_word": french_word,
            "alt_form": alt_form,
            "pronunciation": pronunciation,
            "alt_pronunciation": alt_pronunciation,
            "english_translation": english_translation,
            "russian_translation": russian_translation,
            "explanation_fr": explanation_fr,
            "example_fr": example_fr,
            "example_en": example_en,
            "example_ru": example_ru,
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
    for i, row in enumerate(rows, start=1):
        show_word_card(row, idx=i)
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
    for i, row in enumerate(rows, start=1):
        show_word_card(row, show_review_buttons=True, idx=i)


def weekly_review_page():
    st.header("Weekly review")
    end_date = date.today() + timedelta(days=7)
    rows = get_words_due_until(end_date)
    if not rows:
        st.success("No words scheduled for review this week.")
        return
    st.write(f"Words to review from today until {end_date.isoformat()}: {len(rows)}")
    for i, row in enumerate(rows, start=1):
        show_word_card(row, idx=i)


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


def sidebar_api_key():
    with st.sidebar:
        st.markdown("### Gemini API key")
        st.caption("Get a free key at aistudio.google.com/apikey")
        current = st.session_state.get("gemini_api_key", "")
        key_input = st.text_input(
            "Paste your Gemini key",
            value=current,
            type="password",
            help="Free tier, no billing needed. Or set GEMINI_API_KEY in env / secrets.toml.",
        )
        if key_input != current:
            st.session_state["gemini_api_key"] = key_input


def main():
    st.set_page_config(page_title="French Vocabulary Engine", page_icon="FR", layout="wide")
    init_db()

    st.title("French Vocabulary Engine")
    st.caption("Personal French flashcards — powered by Gemini free tier + spaced repetition.")

    sidebar_api_key()

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
