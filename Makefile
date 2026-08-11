COMPOSE ?= docker compose

.PHONY: help env build up down restart logs shell test warm-cache backup clean

help:
	@echo "make build       — собрать образ"
	@echo "make up          — запустить бота в фоне"
	@echo "make down        — остановить"
	@echo "make restart     — перезапустить"
	@echo "make logs        — смотреть логи"
	@echo "make shell       — bash внутри контейнера"
	@echo "make test        — прогнать тесты в образе"
	@echo "make warm-cache  — прогреть кэш картинок"
	@echo "make backup      — выгрузить БД в ./backup"
	@echo "make clean       — снести контейнер и том с данными (необратимо)"

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Создан .env — впишите в него BOT_TOKEN и ALLOWED_USER_IDS, затем повторите."; \
		exit 1; \
	fi
	@grep -q '^BOT_TOKEN=.\+' .env || { echo "В .env не заполнен BOT_TOKEN (получить: @BotFather)"; exit 1; }

build: env
	$(COMPOSE) build

up: build
	$(COMPOSE) up -d
	@echo "Бот запущен. Логи: make logs"

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f --tail=100

shell:
	$(COMPOSE) run --rm --entrypoint bash bot

test:
	docker build --target builder -t arabic-bot:test .
	docker run --rm -v "$(CURDIR)/tests:/build/tests:ro" -w /build arabic-bot:test \
		sh -c "/opt/venv/bin/pip install -q pytest pytest-asyncio && /opt/venv/bin/pytest -q"

warm-cache:
	$(COMPOSE) run --rm bot python -m arabic_bot.warm_cache

backup:
	@mkdir -p backup
	$(COMPOSE) cp bot:/data/arabic.db "backup/arabic-$$(date +%Y%m%d-%H%M%S).db"
	@echo "Готово: ./backup"

clean:
	$(COMPOSE) down -v
