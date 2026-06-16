# 🗄️ Flask Application Template

This repository serves as a template for creating Flask applications with a structured design, best practices, and tooling for development and deployment. It includes Docker support, linting, and configurations to help standardise projects within the team.

## Features

- **Flask Framework**: Organised structure for Flask projects, enabling scalability.
- **Docker**: Pre-configured Docker support for containerisation.
- **Pipenv**: Dependency management using Pipenv for virtual environments and package versioning.
- **Helm**: Helm charts for Kubernetes deployments.
- **Pre-commit Hooks**: Pre-configured linting and code style enforcement using `flake8`, `pylint`, and `black`.
- **Testing Setup**: Integrated with `pytest` for testing.
- **Error Handling**: Custom middleware for error handling.

## Directory Structure

```bash
.
├── Dockerfile                  
├── LICENSE                      
├── Pipfile                      # Pipenv dependencies
├── Pipfile.lock                 # Locked dependencies for Pipenv
├── README.md                    
├── app/                         # Application source code
│   ├── __init__.py              # Application factory
│   ├── app.py                   # Entry point for the app
│   ├── main/                    # Main application module
│   │   ├── config/              # Configuration files for the application
│   │   │   ├── app_config.py    # Application-specific configurations i.e. env vars
│   │   │   ├── cors_config.py   # CORS configuration
│   │   │   ├── error_handlers_config.py
│   │   │   ├── jinja_config.py  
│   │   │   ├── limiter_config.py 
│   │   │   ├── logging_config.py
│   │   │   ├── routes_config.py 
│   │   │   └── sentry_config.py 
│   │   ├── middleware/          # Middleware for request/response handling
│   │   │   ├── error_handler.py  # Custom error handler middleware
│   │   ├── routes/              
│   │   │   ├── main.py          # Main route definitions
│   │   │   └── robots.py        # Robots.txt handler route
│   │   ├── services/            # Service layer, where you put things like slack and github services
│   │   └── validators/          # Input validation
│   ├── run.py                   # Script to run the application
│   ├── static/                  # Static files (images, JS, CSS, fonts)
│   └── templates/               # HTML templates
│       ├── components/          # Reusable HTML components
│       └── pages/               # Page templates
├── docker-compose.yaml          
├── docker-test.yaml             
├── helm/                        # Helm chart for cloud platform deployments
│   └── application/             
│       ├── Chart.yaml           # Helm chart metadata
│       ├── templates/           # Kubernetes resource templates
│       ├── values-dev.yaml      # Development environment values
│       └── values-prod.yaml     # Production environment values
└── makefile                     # Makefile for automating common tasks
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone git@github.com:ministryofjustice/operations-engineering-flask-template.git
cd operations-engineering-flask-template
```

### 2. Install Dependencies with Pipenv

Ensure you have Pipenv installed:

```bash
pip install pipenv
```

Install the dependencies:

```bash
pipenv install --dev
```

Activate the virtual environment:

```bash
pipenv shell
```

### 3. Rename your application


After cloning this template repository, you may want to rename the project to your desired application name. This project includes a Python script to help automate the renaming process.

#### Steps to Rename the Project:

1. **Run the rename script**:
   
   Once you've cloned the repository, you can rename all instances of the placeholder name (`application`) to your desired project name. Use the following command:

   ```bash
   make rename NEW_NAME=<your-new-project-name>
   ```

   For example, to rename the project to `my-flask-app`:

   ```bash
   make rename NEW_NAME=my-flask-app
   ```

2. **Verify the renaming**:

   The `rename_project.py` script will replace the placeholder name `application` with your new project name across all relevant files and directories. After running the rename command, you can check that the project structure, files, and configurations have been updated accordingly.


### 4. Running the Application

Start the Flask application locally using docker-compose:

```bash
docker-compose build
docker-compose up
```

The application will be available at `http://localhost:4567/`.

### 5. Running Tests

To run the unit tests using `pytest`:

```bash
pipenv run pytest
```

## Deployment

### Kubernetes (Helm)

This project includes Helm charts for Kubernetes deployment. You can use the `helm/application/` directory to deploy your application with Helm. Modify `values-dev.yaml` or `values-prod.yaml` as necessary for your environment.

```bash
helm install my-app ./helm/application
```

## Linting and Code Style

- **flake8**: Enforces PEP8 style guide for Python code.
- **pylint**: Provides code analysis and checks for common errors.
- **black**: Ensures consistent code formatting (automatically run by `pre-commit`).

### Running Linters

```bash
pipenv run flake8
pipenv run pylint app
```

## Configuration

The application configuration is modularised in the `app/main/config/` directory. Each aspect of the app’s configuration (e.g., CORS, error handlers, logging) is stored in its own file. Modify the configurations to suit your application needs.

## Extending the Template

Feel free to extend the template by adding more services and blueprints or integrating additional tools such as databases or external APIs.


### Contributions

If you have suggestions or improvements to this template, open a pull request or raise an issue.

### License

This project is licensed under the MIT License.
