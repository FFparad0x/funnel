# Variables
IMAGE_NAME = hidden.cr.cloud.ru/dev/funnel:v1.1.0
CONTAINER_NAME = funnelbot-container
# Get current date and time for version
VERSION = $(shell date +%Y%m%d.%H%M%S)

VERSION = 1.0

# Default target
.PHONY: all
all: build

# Build the Docker image
.PHONY: build
build:
	docker build -t $(IMAGE_NAME):$(VERSION) .
	docker tag $(IMAGE_NAME):$(VERSION) $(IMAGE_NAME):latest



# Run the container
.PHONY: run
run:
	docker run -d \
		--name $(CONTAINER_NAME) \
		--restart unless-stopped \
		--env-file .env \
		-v $(PWD)/channels.yaml:/app/channels.yaml \
		$(IMAGE_NAME):latest

# Stop and remove the container
.PHONY: stop
stop:
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true

# Remove the Docker image
.PHONY: clean
clean: stop
	docker rmi $(IMAGE_NAME):$(VERSION) || true
	docker rmi $(IMAGE_NAME):latest || true

# Show logs
.PHONY: logs
logs:
	docker logs -f $(CONTAINER_NAME)

# Restart the container
.PHONY: restart
restart: stop run

# Rebuild and restart
.PHONY: rebuild
rebuild: clean build run

# Help
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make build    - Build the Docker image"
	@echo "  make run      - Run the container"
	@echo "  make stop     - Stop and remove the container"
	@echo "  make clean    - Remove the Docker image"
	@echo "  make logs     - Show container logs"
	@echo "  make restart  - Restart the container"
	@echo "  make rebuild  - Rebuild and restart the container"
	@echo "  make help     - Show this help message" 