# Smart City Parking Backend

A REST API for managing smart city parking built with Django REST Framework.

This backend is containerized and runs with PostgreSQL/PostGIS using Docker.

## Dependencies

- Python 3.13+ [Windows Download](https://apps.microsoft.com/detail/9PNRBTZXMB4Z?hl=neutral&gl=DK&ocid=pdpshare)
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

```env
FIREBASE_API_KEY=your_firebase_key
GOOGLE_APPLICATION_CREDENTIALS=firebase-settings-file-name.json 
DJANGO_SECRET_KEY=your_django_key
DJANGO_DEBUG=True
HOST_URL=http://localhost:8000
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
POSTGRES_DB=smart_city_parking_db
POSTGRES_USER=parking_user
POSTGRES_PASSWORD=parking_password
DB_HOST=db
DB_PORT=5432
```

---


## Running the Server with Docker 

This setup runs Django and PostgreSQL/PostGIS in containers for development and testing.

### 1. Build and start the containers

This command builds the images (including necessary GIS libraries), starts the database (with PostGIS), and runs the Django backend. **Database migrations are automatically applied** via the `entrypoint.sh` script once the database is healthy.

```sh
docker compose up --build -d
```

*(Use `-d` to run containers in the background.)*

### 2. Create Superuser (Optional)

You need an admin account to access the Django admin dashboard (`http://localhost:8000/admin/`).

```sh
docker compose exec web python manage.py createsuperuser
```


### 3. Stop the containers

```sh
docker compose down
```

The API will be available at `http://localhost:8000/`

---

## API Endpoints

Simple auth endpoints (proxy to Firebase). All endpoints expect and return JSON. Set the environment variable `FIREBASE_API_KEY` before running the server.

### Authentication

- `GET /` — Test endpoint. Returns { "message": "API is working!" }.
- `POST /signup/` — Create a user. Body: { "email": "...", "password": "..." }.
- `POST /login/` — Sign in. Body: { "token": "...", "providerId": "...", "email": "...", "password": "..." }.
- `POST /refresh-token/` — Refresh tokens. Body: { "refreshToken": "..." }.

### Parking Lots

- `GET /parking-lots/` — Get all parking lots. Returns a list of all parking lots with their details.

### City Admin Parking Lots (Authenticated)

All `cadmin/parking-lots/` endpoints require Firebase authentication via the `Authorization: Bearer <idToken>` header.

- `GET /cadmin/parking-lots/` — Get all parking lots managed by the authenticated city operator.
- `POST /cadmin/parking-lots/` — Add a new parking lot. Body: { "auth_code": "...", "name": "...", "latitude": ..., "longitude": ..., "address": "..." }.
- `PUT /cadmin/parking-lots/` — Update an existing parking lot. Body: { "id": "...", "auth_code": "...", "name": "...", "latitude": ..., "longitude": ..., "address": "..." }.
- `DELETE /cadmin/parking-lots/` — Delete a parking lot. Body: { "id": "..." }.

### Manual testing of endpoints
Install the [Rest Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension and use the test.rest file to test the endpoints.

