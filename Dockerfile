# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for Beets plugins
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mp3gain \
    libchromaprint-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pip-tools for compiling requirements
RUN pip install --no-cache-dir pip-tools

# Copy only the pyproject.toml file first to leverage Docker cache
COPY pyproject.toml pyproject.toml

# Compile requirements.txt from pyproject.toml
# This ensures only necessary, cross-platform dependencies are included
RUN pip-compile pyproject.toml --output-file requirements.txt --no-header --strip-extras

# Install any needed packages specified in the generated requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Always install beets with plugin dependencies
RUN pip install --no-cache-dir beets \
    pylast \
    pyacoustid \
    requests \
    flask \
    beautifulsoup4 \
    discogs-client \
    requests_oauthlib \
    musicbrainzngs

# Make sure beets is in PATH
ENV PATH="/usr/local/bin:${PATH}"
# For user installs, also add the local bin
ENV PATH="/root/.local/bin:${PATH}"

# Verify beets is installed correctly and in PATH
RUN which beet && echo "Beets found at: $(which beet)" && beet --version

# Copy the rest of the application code
COPY . /app

# Make our entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables (can be overridden)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8000
# BEETS_CONFIG_PATH, MUSIC_DIR, DOWNLOAD_DIR will be set via docker-compose

# Use our entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
# Run app.py with optimized gunicorn settings
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "2", "--threads", "2", "--log-level", "debug", "main:app"] 