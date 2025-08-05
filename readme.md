Interact with ChatGPT and receive 3 word or less answers to all your inputs. All inputs and outputs are saved to a postgres database that can be interacted with via pgadmin.

// run this first:

docker-compose up -d db pgadmin

// then run this: 

docker-compose run --rm app