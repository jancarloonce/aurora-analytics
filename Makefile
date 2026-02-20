DOCKERHUB_IMAGE = jancarloonce/aurora-analytics

# Dev

dev-up:
	docker-compose up --build

dev-start:
	docker-compose up

dev-down:
	docker-compose down

dev-dashboard:
	docker-compose up --build dashboard

# Prod

prod-build:
	docker build -t $(DOCKERHUB_IMAGE) .

prod-push:
	docker push $(DOCKERHUB_IMAGE)

prod-pull:
	docker pull $(DOCKERHUB_IMAGE)

