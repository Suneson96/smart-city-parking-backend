# Get uv (fast Python package installer) from official image
FROM ghcr.io/astral-sh/uv:latest AS uv

# Use the official lightweight Python image based on Debian 12 (Bookworm)
FROM python:3.13.9-slim-bookworm
 
# Create the app directory
RUN mkdir /app
 
# Set the working directory inside the container
WORKDIR /app
 
# Set environment variables to optimize Python
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
#Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1 

# Install essential system packages (compiler, curl) and clean up cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv and uvx from the uv image
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=uv /uvx /usr/local/bin/uvx
 
# Copy dependency list first for caching (only rebuild if requirements change)
COPY requirements.txt  /app/
 
# Install Python dependencies globally in the container using uv
RUN uv pip install --system -r requirements.txt
 
# Copy the Django project to the container
COPY . /app/
 
# Expose the Django port
EXPOSE 8000
 
# Run Django’s development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]