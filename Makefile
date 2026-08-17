.PHONY: test migrate upgrade gateway

test:
	pytest

migrate:
	alembic revision --autogenerate

upgrade:
	alembic upgrade head

gateway:
	uvicorn services.gateway.app.main:app --host 0.0.0.0 --port 8000
