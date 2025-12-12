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

## Prediction Service

The parking occupancy prediction model runs in a **separate Django service** exposed on port `8001`.

When the stack is running (`docker compose up --build -d`), the prediction endpoint is:

- `POST http://localhost:8001/predict/`

### Request body

JSON, with:

- **Required**
  - `timestamp_utc` (string, ISO8601) – prediction timestamp in UTC, e.g. `"2025-01-01T10:00:00Z"`.
  - `lat` (float) – latitude of the parking lot.
  - `lon` (float) – longitude of the parking lot.
  - `total_spaces` (integer) – capacity of the parking lot.

- **Optional**
  - `external_id` (string) – ID of the parking lot used during model training. If present, the service may use historical lag features, which can increase confidence.
  - `events` (array) – recent occupancy events to derive lag features, each with:
    - `timestamp` (string, ISO8601, UTC)
    - `occupied_spots`:
      - either a numeric count (string/int), e.g. `"15"` or `15`, or
      - a list of occupied spot IDs, e.g. `["spot-1", "spot-2"]`.
  - `occupied_spots_24h_ago` (number or string) – occupied spaces exactly 24 hours before `timestamp_utc`, used for a 24h lag if available.
  - Weather and lag fields (if you already provide them):
    - Weather: `temperature_2m`, `relative_humidity_2m`, `precipitation`, `cloud_cover`, `wind_speed_10m`, `wind_direction_10m`.
    - Lags: `occ_rate_lag1h`, `occ_rate_lag24h`, `occ_rate_roll3h`.

If any weather or lag fields are missing, the service will:

- Fetch current weather from Open-Meteo (for missing weather vars).
- Use historical training data (when `external_id` is present) or event history (when `events` is provided) to approximate lag features.

### Response body

A successful response (`200 OK`) returns JSON like:

```json
{
  "external_id": "02e71643-9263-4ac9-9b9d-efe634811bd0",
  "timestamp_utc": "2025-01-01 10:00:00+00:00",
  "p_busy": 0.23,
  "predicted_occupied": 23,
  "predicted_free": 77,
  "confidence_score": 0.7,
  "confidence_level": "medium",
  "confidence_reasons": [
    "lags_not_available",
    "weather_imputed_or_missing"
  ]
}
```

- `p_busy` – model probability that the lot is “busy” at `timestamp_utc`.
- `predicted_occupied` / `predicted_free` – integer counts derived from `p_busy` and `total_spaces`.
- `confidence_score` – float in `[0, 1]` summarising how much information the model had (higher is better).
- `confidence_level` – `"high"`, `"medium"`, or `"low"` based on `confidence_score`.
- `confidence_reasons` – list of human-readable tags explaining why confidence was reduced (e.g. missing `external_id`, missing lags, imputed weather, probability near decision boundary).

If the request is invalid, the service returns an error JSON with an appropriate HTTP status (typically `400`) and a short error message.

### Example without external_id

You can also call the prediction service without providing an `external_id`:

```bash
curl -X POST http://localhost:8001/predict/ \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp_utc": "2025-01-01T10:00:00Z",
    "lat": 55.6761,
    "lon": 12.5683,
    "total_spaces": 100
  }'
```

Example response:

```json
{
  "external_id": "nan",
  "timestamp_utc": "2025-01-01 10:00:00+00:00",
  "p_busy": 0.006463637529550959,
  "predicted_occupied": 1,
  "predicted_free": 99,
  "confidence_score": 0.49999999999999994,
  "confidence_level": "low",
  "confidence_reasons": [
    "external_id_missing",
    "lags_not_available"
  ]
}
```

In this case, confidence is lower because the service cannot use historical lag features tied to a known `external_id`.

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

### City Admin Parking Spots (Authenticated)

All `cadmin/parking-spots/` endpoints require Firebase authentication via the `Authorization: Bearer <idToken>` header.

- `GET /cadmin/parking-spots/` — Get all parking spots for a specific parking lot managed by the authenticated city operator. Body: { "parking_lot_id": ... }.
- `POST /cadmin/parking-spots/` — Add a new parking spot to a parking lot. Body: { "parking_lot_id": ... }. Returns the auth_code for the parking spot.
- `DELETE /cadmin/parking-spots/` — Delete a parking spot. Body: { "id": ... }.

### Parking Events (Parking Spot Authenticated)

The parking events endpoint requires parking spot authentication via the `Authorization: Bearer <auth_code>` header, where `auth_code` is the unique authentication code assigned to each parking spot.

- `POST /parking-events/` — Record a parking spot occupancy event. Body: { "occupied": true } or { "occupied": false }. Updates the event list in Firestore with the current occupancy status.

### Manual testing of endpoints
Install the [Rest Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension and use the test.rest file to test the endpoints.
