from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
from django.conf import settings

@api_view(['GET'])
def getExample(request):
    return Response({"message": "API is working!"})

@api_view(['POST'])
def signupUser(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')

    # basic validation before calling Firebase
    if not email or not password:
        return Response({'error': 'email and password are required'}, status=400)
    if len(password) < 6:
        return Response({'error': 'password must be at least 6 characters'}, status=400)

    API_KEY = settings.FIREBASE_API_KEY
    if not API_KEY:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}'
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
def loginUser(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')
    refreshToken = data.get('refreshToken')

    # basic validation before calling Firebase
    if not email or not password:
        return Response({'error': 'email and password are required'}, status=400)
    if len(password) < 6:
        return Response({'error': 'password must be at least 6 characters'}, status=400)
    
    API_KEY = settings.FIREBASE_API_KEY
    if not API_KEY:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}'
    payload = {
        'email': email,
        'password': password,
        'returnSecureToken': True
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return Response(response.json())

@api_view(['POST'])
def refreshToken(request):
    data = request.data
    refreshToken = data.get('refreshToken')

    # basic validation before calling Firebase
    if not refreshToken:
        return Response({'error': 'refreshToken is required'}, status=400)
    
    API_KEY = settings.FIREBASE_API_KEY
    if not API_KEY:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://securetoken.googleapis.com/v1/token?key={API_KEY}'
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refreshToken
    }

    try:
        response = requests.post(url, data=payload)
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