.ONESHELL:

# Define the new namespace variable that can be passed as an argument
REPOSITORY_NAME ?= default-namespace
OLD_NAME ?= application
NEW_NAME ?= my-new-project

all:
# Run MegaLinter
lint:
	npx mega-linter-runner -e 'SHOW_ELAPSED_TIME=true'

flake8: venv
	venv/bin/pip3 install flake8
	venv/bin/flake8 --config=./.flake8 --exclude=venv,__pycache__,.pytest_cache,.venv .

trivy-scan:
	@echo "Running Trivy scan..."
	docker build -t localbuild/testimage:latest .
	trivy image --severity HIGH,CRITICAL localbuild/testimage:latest

# Build the Docker image
build:
	docker-compose build

# Run the Docker container
up:
	docker-compose up -d

# Stop and remove the Docker container
down:
	docker-compose down

# View logs for the running container
logs:
	docker-compose logs -f app

# Open a shell inside the running app container
shell:
	docker exec -it operations-engineering-flask-application /bin/sh

# Target to run the Python script with pipenv, passing the reposiotry name and environment as an argument
# make new-namespace REPOSITORY_NAME=example-repo ENVIRONMENT=dev
new-namespace:
	pipenv run python -m bin.make_new_cloud_platform_namespace $(REPOSITORY_NAME) $(ENVIRONMENT)

# Target to clean the pipenv environment
clean:
	pipenv --rm

# Target to rename project using Python script
# Example: make rename NEW_NAME=my-new-project
rename:
	@echo "Renaming project from '$(OLD_NAME)' to '$(NEW_NAME)'"
	pipenv run python -m bin.rename_project . $(OLD_NAME) $(NEW_NAME)

.PHONY: build up down logs shell trivy-scan lint all new-namespace rename clean
