all: build push
	@echo "All done!"

build:
	docker build -t rphl/routechoices-dev-server:latest -f docker/django.dockerfile .

push:
	docker push rphl/routechoices-dev-server:latest