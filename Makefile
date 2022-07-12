all: build-and-push
	@echo "All done!"

build-and-push:
	docker build build --push -t rphl/routechoices-dev-server:latest -f docker/django.dockerfile .

build:
	docker build -t rphl/routechoices-dev-server:latest -f docker/django.dockerfile .

push:
	docker push rphl/routechoices-dev-server:latest
