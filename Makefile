all: build push
	@echo "All done!"

build:
	docker build -t rphlo/routechoices-dev-server:latest -f docker/django.dockerfile .

push:
	docker push rphlo/routechoices-dev-server:latest
