import argparse
import json
import os
import random
from datetime import datetime, timedelta

import openai
import psycopg2
from psycopg2.extras import execute_values


DEFAULT_BATCH_SIZE = 50
DEFAULT_TOTAL_ROWS = 5000
DEFAULT_MODEL = "gpt-4.1-nano"
MAX_ATTEMPTS_PER_BATCH = 5


def ensure_table(connection):
    """Create the messages table if it does not already exist."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                input TEXT,
                output TEXT,
                timestamp TIMESTAMPTZ
            )
            """
        )


def random_timestamp():
    days_ago = random.randint(0, 364)
    seconds_in_day = 24 * 60 * 60
    random_seconds = random.randint(0, seconds_in_day)
    return datetime.utcnow() - timedelta(days=days_ago, seconds=random_seconds)


def extract_json(text):
    """Remove fences the model might add and parse JSON content."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    return json.loads(cleaned.strip())


def generate_batch(batch_size, model):
    prompt = (
        "Create realistic chat interactions between a user and a helpful assistant. "
        f"Return exactly {batch_size} records as JSON with fields `input` and `output`. "
        "Rules: the `output` must be three words or fewer, the `input` should vary in tone, "
        "and do not include explanations or additional text."
    )

    max_tokens = min(4000, max(300, batch_size * 35))
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You produce datasets of short conversations. "
                    "Output only valid JSON as requested."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=1.0,
    )
    payload = response.choices[0].message.content
    records = extract_json(payload)
    if not isinstance(records, list):
        raise ValueError("Expected a JSON array of records.")

    rows = []
    discarded = 0
    for record in records:
        input_text = str(record.get("input", "")).strip()
        output_text = str(record.get("output", "")).strip()
        if not input_text or not output_text:
            raise ValueError("Received empty input or output from OpenAI.")
        if len(output_text.split()) > 3:
            discarded += 1
            continue
        rows.append((input_text, output_text, random_timestamp()))
    return rows, discarded


def seed_messages(total_rows, batch_size):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")
    openai.api_key = api_key

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

    with psycopg2.connect(database_url) as connection:
        ensure_table(connection)
        inserted = 0
        while inserted < total_rows:
            remaining = total_rows - inserted
            current_batch_size = min(batch_size, remaining)
            rows = []
            attempts = 0
            while len(rows) < current_batch_size:
                attempts += 1
                if attempts > MAX_ATTEMPTS_PER_BATCH:
                    raise RuntimeError(
                        "Unable to collect enough valid outputs (<=3 words) "
                        f"after {MAX_ATTEMPTS_PER_BATCH} attempts."
                    )
                needed = current_batch_size - len(rows)
                try:
                    new_rows, discarded = generate_batch(needed, model)
                except ValueError as exc:
                    print(f"Batch generation failed ({exc}); retrying...")
                    continue
                rows.extend(new_rows)
                if discarded:
                    print(
                        f"Discarded {discarded} outputs over three words; "
                        "requesting replacements..."
                    )
                if not new_rows:
                    # Guard against empty batches so we do not loop forever.
                    print("Received zero valid rows, trying again...")
            with connection.cursor() as cursor:
                execute_values(
                    cursor,
                    """
                    INSERT INTO messages (input, output, timestamp)
                    VALUES %s
                    """,
                    rows,
                )
            connection.commit()
            inserted += current_batch_size
            print(f"Inserted {inserted}/{total_rows} rows...")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Seed the messages table with OpenAI-generated data. "
            "Outputs are limited to three words."
        )
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_TOTAL_ROWS,
        help=f"Number of rows to insert (default: {DEFAULT_TOTAL_ROWS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per OpenAI batch (default: {DEFAULT_BATCH_SIZE})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    seed_messages(args.rows, args.batch_size)
    print("Seeding complete.")


if __name__ == "__main__":
    main()
