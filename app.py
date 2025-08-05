import os
import psycopg2
import time
from datetime import datetime
import openai

DATABASE_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

SYSTEM_PROMPT = (
    "You must respond to the user input with no more than three words."
    "Only respond with an answer or reaction to the input, not an explanation. "
    "If the input makes no sense, still reply in three words or fewer."
)

def ensure_table():
    retries = 10
    while retries > 0:
        try:    
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    input TEXT,
                    output TEXT,
                    timestamp TIMESTAMPTZ
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            return
        except psycopg2.OperationalError as e:
            print("Database unavailable. Waiting 2 seconds...", str(e))
            retries -= 1
            time.sleep(2)
    raise Exception("Could not connect to the database after several retries.")

def insert_message(user_input, ai_output):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (input, output, timestamp) VALUES (%s, %s, %s)",
        (user_input, ai_output, datetime.utcnow()),
    )
    conn.commit()
    cur.close()
    conn.close()

def get_openai_response(user_input):
    response = openai.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        max_tokens=10,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    ensure_table()
    print("Ready! Type your message below (max 140 chars, 'quit' to exit).")

    while True:
        user_input = input("> ").strip()
        if user_input.lower() in {"quit","exit"}:
            print("Goodbye!")
            break
        if len(user_input) > 140:
            print("Input too long (max 140 characters). Try again.")
            continue
        if not user_input:
            continue
        try: 
            ai_output = get_openai_response(user_input)
            print(ai_output)
            insert_message(user_input, ai_output)
        except Exception as e:
            print("Error:", str)