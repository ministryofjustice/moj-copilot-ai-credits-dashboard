FROM python:3.12.0-alpine3.18

LABEL maintainer="operations-engineering <operations-engineering@digital.justice.gov.uk>"

# Install system dependencies
RUN apk add --no-cache --no-progress \
  libffi-dev \
  build-base \
  curl \
  && apk update \
  && apk upgrade --no-cache --available

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Create user and group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup -u 1051

# Set working directory
WORKDIR /home/operations-engineering-application

# Change ownership of the working directory
RUN chown -R appuser:appgroup /home/operations-engineering-application

# Switch to non-root user
USER 1051

# Copy Pipfile and Pipfile.lock
COPY --chown=appuser:appgroup Pipfile Pipfile.lock ./

# Install dependencies without --system
RUN pipenv install --deploy --ignore-pipfile

# Copy application code
COPY --chown=appuser:appgroup app app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Expose port
EXPOSE 4567

# Healthcheck
HEALTHCHECK --interval=60s --timeout=30s CMD curl -I -XGET http://localhost:4567 || exit 1

# Use pipenv to run gunicorn
ENTRYPOINT ["pipenv", "run", "gunicorn", "--bind=0.0.0.0:4567", "app.run:app()"]
