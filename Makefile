.PHONY: install dev backend frontend test lint build docker up notebook sample ml ml-train

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

# ML: download QuerYD videos, train the gap-relevance model, evaluate on unseen videos
ml:
	$(BIN)/pip install -r ml/requirements.txt
	$(BIN)/python ml/run_all.py --train 17 --test 13

# Re-train and re-evaluate on already downloaded videos
ml-train:
	$(BIN)/python ml/run_all.py --skip-download
