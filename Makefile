.PHONY: up down seed test openapi
up:
	docker compose up --build

down:
	docker compose down

seed:
	docker compose exec backend python -m seed.seed

test:
	docker compose exec backend pytest

openapi:
	docker compose exec backend python -m app.export_openapi
