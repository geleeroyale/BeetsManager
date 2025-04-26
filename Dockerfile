# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt requirements.txt

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Always install beets
RUN pip install --no-cache-dir beets

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container (we'll map this later)
# Defaulting to 8000, can be overridden in docker-compose
EXPOSE 8000

# Define environment variables (can be overridden)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8000
# BEETS_CONFIG_PATH, MUSIC_DIR, DOWNLOAD_DIR will be set via docker-compose

# Run app.py when the container launches using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "main:app"] 