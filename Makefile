.PHONY: up down migrate seed test lint shell
up:      ; docker compose up --build
down:    ; docker compose down
migrate: ; docker compose exec web python manage.py migrate
seed:    ; docker compose exec web python manage.py seed_demo
test:    ; docker compose exec web pytest -q
lint:    ; docker compose exec web ruff check . && docker compose exec web mypy apps motores
shell:   ; docker compose exec web python manage.py shell
