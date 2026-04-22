export COMPOSE_ENV_FILES := .env.prod

.PHONY: init doctor load up up-build down logs status config clean

init:
	./truenas.sh init

doctor:
	./truenas.sh doctor

load:
	./truenas.sh load

up:
	./truenas.sh up

up-build:
	./truenas.sh up-build

down:
	./truenas.sh down

logs:
	./truenas.sh logs

status:
	./truenas.sh status

config:
	./truenas.sh config

clean:
	./truenas.sh clean
