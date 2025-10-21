Interact with ChatGPT and receive 3 word or less answers to all your inputs. All inputs and outputs are saved to a postgres database that can be interacted with via pgadmin.

// run this first:

docker-compose up -d db pgadmin

// then run this: 

docker-compose run --rm app

### Seed the database with random data

To insert thousands of random records (outputs limited to three words):

```
docker-compose run --rm app python seed_db.py --rows 5000
```

Useful flags:

- `--rows`: how many records to insert (default: 5000).
- `--batch-size`: how many rows to request from OpenAI per batch (default: 50).

Environment variables:

- `DATABASE_URL` (set automatically when using `docker-compose`).
- `OPENAI_API_KEY` (required so the seeder can call the OpenAI API).
- `OPENAI_MODEL` (optional override, defaults to `gpt-4.1-nano`).
