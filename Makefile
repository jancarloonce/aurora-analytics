DOCKERHUB_IMAGE = jancarloonce/aurora-analytics

# Dev

dev-up:
	docker-compose up --build

dev-start:
	docker-compose up

dev-down:
	docker-compose down

dev-read:
	docker-compose run --rm ingester python reader.py

# Prod 

prod-build:
	docker build -t $(DOCKERHUB_IMAGE) .

prod-push:
	docker push $(DOCKERHUB_IMAGE)

prod-pull:
	docker pull $(DOCKERHUB_IMAGE)

prod-run:
	docker run \
		-e APP_ENV=production \
		-e AWS_REGION=us-east-1 \
		$(DOCKERHUB_IMAGE)
