FROM python:3.13.9-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# LightGBM / NumPy often need OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Reuse the main requirements to get Django + core stack, plus ML deps
COPY requirements.txt requirements-ml.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-ml.txt

# Copy the full project so we can import prediction_app and related modules
COPY . /app/

EXPOSE 8000

CMD ["python", "prediction_service/manage.py", "runserver", "0.0.0.0:8000"]
