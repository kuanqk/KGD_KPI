.PHONY: build up down migrate seed test shell

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	docker-compose run --rm web python manage.py migrate --settings=config.settings.prod

seed:
	docker-compose run --rm web python manage.py loaddata regions/fixtures/regions.json --settings=config.settings.prod
	docker-compose run --rm web python manage.py init_formulas --settings=config.settings.prod

test:
	docker-compose run --rm web python manage.py test --settings=config.settings.dev

shell:
	docker-compose run --rm web python manage.py shell --settings=config.settings.dev
