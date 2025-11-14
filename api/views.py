"""
API views.
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
from django.conf import settings


def _make_firebase_request(url, payload, timeout=10):
    """
    Helper function to make Firebase API requests with error handling.
    Returns a tuple of (response_data, status_code).
    """
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.HTTPError:
        try:
            return response.json(), response.status_code
        except ValueError:
            return {"error": response.text}, response.status_code
    except requests.exceptions.RequestException as exc:
        return {"error": str(exc)}, 500


@api_view(["GET"])
def get_example(_):
    """
    A simple API view to test if the API is working.
    """

    return Response({"message": "API is working!"})


@api_view(["POST"])
def signup_user(request):
    """
    Sign up a new user using Firebase Authentication REST API.
    """
    data = request.data
    email = data.get("email")
    password = data.get("password")

    # basic validation before calling Firebase
    if not email or not password:
        return Response({"error": "email and password are required"}, status=400)
    if len(password) < 6:
        return Response({"error": "password must be at least 6 characters"}, status=400)

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response(
            {"error": "Firebase API key not configured on server"}, status=500
        )

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}

    response_data, status_code = _make_firebase_request(url, payload)
    return Response(response_data, status=status_code)


@api_view(["POST"])
def login_user(request):
    """
    Log in a user using Firebase Authentication REST API.
    """
    data = request.data
    email = data.get("email")
    password = data.get("password")
    id_token = data.get("token")
    provider_id = data.get("providerId", "google.com")

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response(
            {"error": "Firebase API key not configured on server"}, status=500
        )

    # Login with provider (Google) using ID token
    if id_token and provider_id:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={api_key}"
        payload = {
            "postBody": f"id_token={id_token}&providerId={provider_id}",
            "requestUri": settings.HOST_URL,
            "returnIdpCredential": True,
            "returnSecureToken": True,
        }
        response_data, status_code = _make_firebase_request(url, payload)
        return Response(response_data, status=status_code)

    # Login with email and password
    if email and password:
        # Validate password
        if len(password) < 6:
            return Response(
                {"error": "password must be at least 6 characters"}, status=400
            )

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response_data, status_code = _make_firebase_request(url, payload)
        return Response(response_data, status=status_code)

    return Response({"error": "email and password are required"}, status=400)


@api_view(["POST"])
def refresh_token(request):
    """
    Refresh Firebase ID token using Firebase Authentication REST API.
    """
    data = request.data
    token = data.get("refreshToken")

    # basic validation before calling Firebase
    if not token:
        return Response({"error": "refreshToken is required"}, status=400)

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response(
            {"error": "Firebase API key not configured on server"}, status=500
        )

    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    payload = {"grant_type": "refresh_token", "refresh_token": token}

    response_data, status_code = _make_firebase_request(url, payload, timeout=10)
    return Response(response_data, status=status_code)
