.PHONY: install dev backend frontend test lint build docker up notebook sample

PY ?= python3.11
VENV = .venv
BIN = $(VENV)/bin

install:
	$(PY) -m venv $(VENV) && $(BIN)/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

backend:
	cd backend && ../$(BIN)/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && ../$(BIN)/pytest -q

lint:
	cd backend && ../$(BIN)/ruff check .
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

docker:
	docker build -t basira:local .

up:
	docker compose up --build

notebook:
	$(BIN)/jupyter nbconvert --to notebook --execute --inplace notebooks/pipeline_demo.ipynb

sample:
	bash scripts/make_sample.sh
