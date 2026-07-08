import sqlite3
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

DB_PATH = Path(__file__).with_name("vocabulary.db")


RATING_INTERVALS = {
    "Again": 1,
    "Hard": 3,
    "Good": 7,
    "Easy": 14,
}


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
    next_review = today
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO words (
                french_word,
                english_translation,
                russian_translation,
                explanation_fr,
                explanation_en,
                example_fr,
                example_en,
                pronunciation,
                notes,
                created_at,
                next_review
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                next_review,
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
                (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM words ORDER BY french_word COLLATE NOCASE"
            ).fetchall()
    return rows


def get_words_due_until(end_date):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM words
            WHERE next_review <= ?
            ORDER BY next_review ASC, french_word COLLATE NOCASE
            """,
            (end_date.isoformat(),),
        ).fetchall()
    return rows


def update_review(word_id, rating):
    today = date.today()
    interval = RATING_INTERVALS[rating]
    next_review = today + timedelta(days=interval)
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE words
            SET last_reviewed = ?,
                next_review = ?,
                review_count = review_count + 1,
                difficulty = ?
            WHERE id = ?
            """,
            (today.isoformat(), next_review.isoformat(), rating, word_id),
        )
        conn.commit()


def delete_word(word_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()


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
            for index, rating in enumerate(RATING_INTERVALS.keys()):
                with cols[index]:
                    if st.button(rating, key=f"review_{row['id']}_{rating}"):
                        update_review(row["id"], rating)
                        st.success(f"Saved. You will review this word again in {RATING_INTERVALS[rating]} day(s).")
                        st.rerun()


def add_word_page():
    st.header("Add a French word")
    st.write("Fill in the vocabulary card. Later, you can connect AI to generate these fields automatically.")

    with st.form("add_word_form", clear_on_submit=True):
        french_word = st.text_input("French word *", placeholder="préserver")
        english_translation = st.text_input("English translation", placeholder="to preserve / to protect")
        russian_translation = st.text_input("Russian translation", placeholder="сохранять / оберегать")
        pronunciation = st.text_input("Pronunciation", placeholder="/pʁe.zɛʁ.ve/")
        explanation_fr = st.text_area("Explanation in French", placeholder="Préserver signifie protéger quelque chose pour qu’il reste intact.")
        explanation_en = st.text_area("Explanation in English", placeholder="To preserve means to protect something so it stays safe or unchanged.")
        example_fr = st.text_area("Example in French", placeholder="Il faut préserver la nature.")
        example_en = st.text_area("Example in English", placeholder="We must preserve nature.")
        notes = st.text_area("Notes", placeholder="Grammar notes, synonyms, common mistakes...")

        submitted = st.form_submit_button("Save word")

    if submitted:
        if not french_word.strip():
            st.error("Please enter a French word.")
            return

        add_word(
            {
                "french_word": french_word,
                "english_translation": english_translation,
                "russian_translation": russian_translation,
                "pronunciation": pronunciation,
                "explanation_fr": explanation_fr,
                "explanation_en": explanation_en,
                "example_fr": example_fr,
                "example_en": example_en,
                "notes": notes,
            }
        )
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
        difficulty_counts = {}
        for row in rows:
            difficulty_counts[row["difficulty"]] = difficulty_counts.get(row["difficulty"], 0) + 1
        st.subheader("Difficulty")
        st.bar_chart(difficulty_counts)


def main():
    st.set_page_config(page_title="French Vocabulary Engine", page_icon="🇫🇷", layout="wide")
    init_db()

    st.title("French Vocabulary Engine")
    st.caption("A simple personal app for learning and reviewing French words.")

    page = st.sidebar.radio(
        "Menu",
        [
            "Add Word",
            "My Vocabulary",
            "Review Today",
            "Weekly Review",
            "Statistics",
        ],
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
