"""
API views.
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
from django.conf import settings

@api_view(['GET'])
def get_example(_):
    """
    A simple API view to test if the API is working.
    """

    return Response({"message": "API is working!"})

@api_view(['POST'])
def signup_user(request):
    """
    Sign up a new user using Firebase Authentication REST API.
    """

    data = request.data
    email = data.get('email')
    password = data.get('password')

    # basic validation before calling Firebase
    if not email or not password:
        return Response({'error': 'email and password are required'}, status=400)
    if len(password) < 6:
        return Response({'error': 'password must be at least 6 characters'}, status=400)

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}'
    payload = {
        'email': email,
        'password': password,
        'returnSecureToken': True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        # return the Firebase error JSON (if any) so client sees the real reason
        try:
            return Response(response.json(), status=response.status_code)
        except ValueError:
            return Response({'error': response.text}, status=response.status_code)
    except requests.exceptions.RequestException as exc:
        return Response({'error': str(exc)}, status=500)

    return Response(response.json())

@api_view(['POST'])
def login_user(request):
    """
    Log in a user using Firebase Authentication REST API.
    """

    data = request.data
    email = data.get('email')
    password = data.get('password')
    idToken = data.get('token')
    providerId = data.get("providerId", "google.com")

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    # Login with provider (Google) using ID token
    if idToken and providerId:
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={api_key}'
        payload = {
            'postBody': f'id_token={idToken}&providerId={providerId}',
            'requestUri': settings.HOST_URL,
            'returnIdpCredential': True,
            'returnSecureToken': True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # return the Firebase error JSON (if any) so client sees the real reason
            try:
                return Response(response.json(), status=response.status_code)
            except ValueError:
                return Response({'error': response.text}, status=response.status_code)
        except requests.exceptions.RequestException as exc:
            return Response({'error': str(exc)}, status=500)
        return Response(response.json())

    # Login with email and password
    if email and password:

        # Validate password
        if len(password) < 6:
            return Response({'error': 'password must be at least 6 characters'}, status=400)

        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}'
        payload = {
            'email': email,
            'password': password,
            'returnSecureToken': True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # return the Firebase error JSON (if any) so client sees the real reason
            try:
                return Response(response.json(), status=response.status_code)
            except ValueError:
                return Response({'error': response.text}, status=response.status_code)
        except requests.exceptions.RequestException as exc:
            return Response({'error': str(exc)}, status=500)
        return Response(response.json())

    return Response({'error': 'email and password are required'}, status=400)

@api_view(['POST'])
def refresh_token(request):
    """
    Refresh Firebase ID token using Firebase Authentication REST API.
    """

    data = request.data
    refresh_token = data.get('refreshToken')

    # basic validation before calling Firebase
    if not refresh_token:
        return Response({'error': 'refreshToken is required'}, status=400)

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://securetoken.googleapis.com/v1/token?key={api_key}'
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        # return the Firebase error JSON (if any) so client sees the real reason
        try:
            return Response(response.json(), status=response.status_code)
        except ValueError:
            return Response({'error': response.text}, status=response.status_code)
    except requests.exceptions.RequestException as exc:
        return Response({'error': str(exc)}, status=500)

    return Response(response.json())
