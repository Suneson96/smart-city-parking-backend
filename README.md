# Smart City Parking Backend

A REST API for managing smart city parking built with Django REST Framework.

This backend is containerized and runs by default with PostgreSQL using Docker.  
You can also run it locally with SQLite for quick testing.

## Dependencies

- Python 3.9+ [Windows Download](https://apps.microsoft.com/detail/9PNRBTZXMB4Z?hl=neutral&gl=DK&ocid=pdpshare)
- Docker & Docker Compose (for PostgreSQL setup)
- Other dependencies listed in `requirements.txt`

## Installation

### Clone the repository
```sh
git clone https://github.com/Suneson96/smart-city-parking-backend.git
cd smart-city-parking-backend
```

---

## Environment Configuration

Before running the application, copy the content of `.env.example` into a new file named `.env` and update the values according to your setup.

Example minimal `.env` for local use (SQLite):

```env
FIREBASE_API_KEY=your_firebase_key
DJANGO_SECRET_KEY=your_django_key
DJANGO_DEBUG=True
HOST_URL=http://localhost:8000
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

If you run with Docker (PostgreSQL), your `.env` should also include:

```env
POSTGRES_DB=smart_city_parking_db
POSTGRES_USER=parking_user
POSTGRES_PASSWORD=parking_password
DB_HOST=db
DB_PORT=5432
```

---

## Running the Server locally (SQLite)


### 1. Create and activate a virtual environment

For more information about virtual Python environments visit the [Python Documentation](https://docs.python.org/3/library/venv.html)

```sh
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install dependencies

We keep a list of all the Python libraries used in the project in `requirements.txt`.
    To install all libraries at once run:

```sh
pip install -r requirements.txt
```

### 3. Apply database migrations
```sh
python manage.py migrate
```

### 4. Start the development server
```sh
python manage.py runserver
```

The API will be available at `http://localhost:8000/`

---

## Running the Server with Docker (PostgreSQL)

This setup runs Django and PostgreSQL in containers for development and testing.

### 1. Build and start the containers

```sh
docker compose up --build
```

### 2. Apply database migrations inside the container

Once containers are running, open a new terminal and run:

```sh
docker compose exec web python manage.py migrate
```

### 3. Stop the containers

```sh
docker compose down
```

The API will be available at `http://localhost:8000/`

---

## API Endpoints

Simple auth endpoints (proxy to Firebase). All endpoints expect and return JSON. Set the environment variable `FIREBASE_API_KEY` before running the server.

- `GET /` — Test endpoint. Returns { "message": "API is working!" }.
- `POST /signup/` — Create a user. Body: { "email": "...", "password": "..." }.
- `POST /login/` — Sign in. Body: { "token": "...", "providerId": "...", "email": "...", "password": "..." }.
- `POST /refresh-token/` — Refresh tokens. Body: { "refreshToken": "..." }.

### Manual testing of endpoints
Install the [Rest Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension and use the test.rest file to test the endpoints.