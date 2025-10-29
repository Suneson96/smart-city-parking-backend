# Smart City Parking Backend

A REST API for managing smart city parking built with Django REST Framework.

## Dependencies

- Python 3.9+ [Windows Download](https://apps.microsoft.com/detail/9PNRBTZXMB4Z?hl=neutral&gl=DK&ocid=pdpshare)
- Other dependencies listed in `requirements.txt`

## Installation

### 1. Clone the repository
```sh
git clone https://github.com/Suneson96/smart-city-parking-backend.git
cd smart-city-parking-backend
```

### 2. Create and activate a virtual environment

For more information about virtual Python environments visit the [Python Documentation](https://docs.python.org/3/library/venv.html)

```sh
python -m venv .venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

We keep a list of all the Python libraries used in the project in `requirements.txt`.
    To install all libraries at once run:

```sh
pip install -r requirements.txt
```

## Running the Server

### 1. Apply database migrations
```sh
python manage.py migrate
```

### 2. Start the development server
```sh
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`

## API Endpoints

- `GET /` - Test endpoint that returns a welcome message

