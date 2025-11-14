"""
API views.
"""

from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
from django.conf import settings
from functools import wraps
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from . import models
import os

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if cred_path:
        if not os.path.isabs(cred_path):
            cred_path = os.path.join(settings.BASE_DIR, cred_path)
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)


def firebase_authenticated(view_func):
    """
    Decorator to validate Firebase ID token and attach user UID to request.
    Expects 'Authorization: Bearer <idToken>' header.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header with Bearer token required'}, status=401)
        
        id_token = auth_header.split('Bearer ')[1]
        
        try:
            # Verify the ID token
            decoded_token = firebase_auth.verify_id_token(id_token)
            request.firebase_uid = decoded_token['uid']
            return view_func(request, *args, **kwargs)
        except firebase_auth.InvalidIdTokenError:
            return Response({'error': 'Invalid ID token'}, status=401)
        except firebase_auth.ExpiredIdTokenError:
            return Response({'error': 'ID token has expired'}, status=401)
        except Exception as e:
            return Response({'error': f'Authentication failed: {str(e)}'}, status=401)
    
    return wrapper


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
            return {'error': response.text}, response.status_code
    except requests.exceptions.RequestException as exc:
        return {'error': str(exc)}, 500


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

    response_data, status_code = _make_firebase_request(url, payload)
    return Response(response_data, status=status_code)

@api_view(['POST'])
def login_user(request):
    """
    Log in a user using Firebase Authentication REST API.
    """
    data = request.data
    email = data.get('email')
    password = data.get('password')
    id_token = data.get('token')
    provider_id = data.get("providerId", "google.com")

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    # Login with provider (Google) using ID token
    if id_token and provider_id:
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={api_key}'
        payload = {
            'postBody': f'id_token={id_token}&providerId={provider_id}',
            'requestUri': settings.HOST_URL,
            'returnIdpCredential': True,
            'returnSecureToken': True
        }
        response_data, status_code = _make_firebase_request(url, payload)
        return Response(response_data, status=status_code)

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
        response_data, status_code = _make_firebase_request(url, payload)
        return Response(response_data, status=status_code)

    return Response({'error': 'email and password are required'}, status=400)

@api_view(['POST'])
def refresh_token(request):
    """
    Refresh Firebase ID token using Firebase Authentication REST API.
    """
    data = request.data
    token = data.get('refreshToken')

    # basic validation before calling Firebase
    if not token:
        return Response({'error': 'refreshToken is required'}, status=400)

    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        return Response({'error': 'Firebase API key not configured on server'}, status=500)

    url = f'https://securetoken.googleapis.com/v1/token?key={api_key}'
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': token
    }

    response_data, status_code = _make_firebase_request(url, payload, timeout=10)
    return Response(response_data, status=status_code)

@api_view(['GET'])
@firebase_authenticated
def operator_parking_lots(request):
    """
    Get all parking lots managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    firebase_uid = request.firebase_uid
    
    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)
        
        # Get all parking lots managed by this operator
        managed_relations = models.Manage.objects.filter(operator=operator).select_related('parking_lot')
        
        # Serialize the parking lots
        parking_lots_data = []
        for manage in managed_relations:
            lot = manage.parking_lot
            parking_lots_data.append({
                'id': lot.id,
                'auth_code': lot.auth_code,
                'name': lot.name,
                'latitude': lot.latitude,
                'longitude': lot.longitude,
                'address': lot.address
            })
        
        return Response({
            'operator_id': firebase_uid,
            'parking_lots': parking_lots_data,
            'count': len(parking_lots_data)
        }, status=200)
        
    except models.CityOperator.DoesNotExist:
        return Response({
            'error': 'City operator not found for this Firebase UID',
            'firebase_uid': firebase_uid
        }, status=404)
    except Exception as e:
        return Response({
            'error': f'Failed to retrieve parking lots: {str(e)}'
        }, status=500)

