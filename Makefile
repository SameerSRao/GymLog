.PHONY: test up down

test:
	cd services/api  && pytest tests/ -v
	cd services/chat && pytest tests/ -v

up:
	docker compose up --build

down:
	docker compose down
