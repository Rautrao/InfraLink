.PHONY: up down seed test openapi prod-up prod-down backup demo-reset
up:
	docker compose up --build

down:
	docker compose down

seed:
	docker compose exec -T backend make -C /app seed

test:
	docker compose exec backend pytest

openapi:
	docker compose exec backend python -m app.export_openapi

prod-up:
	docker compose -f compose.prod.yaml up --build -d

prod-down:
	docker compose -f compose.prod.yaml down

backup:
	sh ./scripts/db_backup.sh

demo-reset:
	sh ./scripts/demo_reset.sh
