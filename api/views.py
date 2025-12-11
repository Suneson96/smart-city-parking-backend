"""
API views.
"""

# pylint: disable=no-member
# pylint: disable=broad-except

import os
from functools import wraps
from datetime import datetime, timedelta, timezone
import requests
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import IntegrityError
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, firestore
from . import models
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Q

# Initialize Firebase Admin SDK
try:
    firebase_admin.get_app()
except ValueError:
    # App not initialized yet
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
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Authorization header with Bearer token required"}, status=401
            )

        id_token = auth_header.split("Bearer ")[1]

        try:
            # Verify the ID token
            decoded_token = firebase_auth.verify_id_token(id_token)
            request.firebase_uid = decoded_token["uid"]
            return view_func(request, *args, **kwargs)
        except firebase_auth.InvalidIdTokenError:
            return Response({"error": "Invalid ID token"}, status=401)
        except (firebase_auth.CertificateFetchError, ValueError, KeyError) as e:
            return Response({"error": f"Authentication failed: {str(e)}"}, status=401)

    return wrapper


def parking_spot_authenticated(view_func):
    """
    Decorator to validate parking spot auth_code and attach parking spot to request.
    Expects 'Authorization: Bearer <auth_code>' header.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Authorization header with Bearer token required"}, status=401
            )

        auth_code = auth_header.split("Bearer ")[1]

        try:
            # Hash the provided token and verify it
            auth_code_hash = models.hash_token(auth_code)
            parking_spot = models.ParkingSpot.objects.get(auth_code_hash=auth_code_hash)
            request.parking_spot = parking_spot
            return view_func(request, *args, **kwargs)
        except models.ParkingSpot.DoesNotExist:
            return Response({"error": "Invalid auth code"}, status=401)
        except Exception as e:
            return Response({"error": f"Authentication failed: {str(e)}"}, status=401)

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
            return {"error": response.text}, response.status_code
    except requests.exceptions.RequestException as exc:
        return {"error": str(exc)}, 500


@api_view(["POST"])
def predict_proxy(request):
    """
    Proxy /predict/ to the separate prediction Django service.

    Request JSON contract (forwarded as-is to the prediction service):
      - required: timestamp_utc (ISO8601 str),
                  lat (float), lon (float), total_spaces (int)
      - optional: external_id (str), events, occupied_spots_24h_ago,
                  and precomputed WEATHER_VARS/LAG_VARS

    Response JSON contract (relayed from the prediction service):
      - external_id (str)
      - timestamp_utc (str)
      - p_busy (float)
      - predicted_occupied (int or null)
      - predicted_free (int or null)
    """
    predict_url = getattr(
        settings,
        "PREDICT_SERVICE_URL",
        "http://predict:8000/predict/",
    )

    try:
        resp = requests.post(predict_url, json=request.data, timeout=20)
    except requests.RequestException as exc:
        return Response(
            {"error": f"Prediction service unavailable: {str(exc)}"},
            status=503,
        )

    try:
        data = resp.json()
    except ValueError:
        return Response(
            {
                "error": f"Prediction service returned invalid JSON "
                f"(status {resp.status_code})"
            },
            status=502,
        )

    return Response(data, status=resp.status_code)


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


@api_view(["GET"])
@firebase_authenticated
def check_user_role(request):
    """
    Check if the authenticated user is a city operator or has a pending request.
    Returns the user's role and status.
    """
    firebase_uid = request.firebase_uid

    try:
        # Check if user is a city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)
        return Response(
            {
                "is_city_operator": True,
                "user_id": firebase_uid,
                "role": "city_operator",
                "operator_request_status": None
            },
            status=200,
        )
    except models.CityOperator.DoesNotExist:
        # Check if user has an operator request
        try:
            operator_request = models.OperatorRequest.objects.get(user_id=firebase_uid)
            return Response(
                {
                    "is_city_operator": False,
                    "user_id": firebase_uid,
                    "role": "driver",
                    "operator_request_status": operator_request.status
                },
                status=200,
            )
        except models.OperatorRequest.DoesNotExist:
            # User exists but is not a city operator and has no request
            return Response(
                {
                    "is_city_operator": False,
                    "user_id": firebase_uid,
                    "role": "driver",
                    "operator_request_status": None
                },
                status=200,
            )


@api_view(["POST"])
@firebase_authenticated
def request_operator_access(request):
    """
    Create a request for the authenticated user to become a city operator.
    """
    firebase_uid = request.firebase_uid

    try:
        # Check if user is already a city operator
        models.CityOperator.objects.get(id=firebase_uid)
        return Response(
            {"error": "User is already a city operator"},
            status=400,
        )
    except models.CityOperator.DoesNotExist:
        pass

    try:
        # Check if user already has a pending or approved request
        existing_request = models.OperatorRequest.objects.get(user_id=firebase_uid)
        
        if existing_request.status == 'pending':
            return Response(
                {
                    "message": "You already have a pending operator request",
                    "status": existing_request.status,
                    "requested_at": existing_request.requested_at
                },
                status=200,
            )
        elif existing_request.status == 'approved':
            return Response(
                {
                    "message": "Your operator request has been approved",
                    "status": existing_request.status
                },
                status=200,
            )
        elif existing_request.status == 'rejected':
            # Allow resubmission if previously rejected
            existing_request.status = 'pending'
            existing_request.notes = None
            existing_request.save()
            return Response(
                {
                    "message": "Operator access request resubmitted successfully",
                    "status": "pending",
                    "requested_at": existing_request.requested_at
                },
                status=201,
            )
    except models.OperatorRequest.DoesNotExist:
        # Create new operator request
        operator_request = models.OperatorRequest.objects.create(
            user_id=firebase_uid,
            status='pending'
        )
        return Response(
            {
                "message": "Operator access request submitted successfully",
                "status": operator_request.status,
                "requested_at": operator_request.requested_at
            },
            status=201,
        )


def cadmin_get_parking_lots(request):
    """
    Get all parking lots managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    firebase_uid = request.firebase_uid

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Get all parking lots managed by this operator
        managed_relations = models.Manage.objects.filter(
            operator=operator
        ).select_related("parking_lot")

        # Serialize the parking lots
        parking_lots_data = []
        for manage in managed_relations:
            lot = manage.parking_lot
            parking_lots_data.append(
                {
                    "id": lot.id,
                    "name": lot.name,
                    "location": {
                        "latitude": lot.location.y,
                        "longitude": lot.location.x,
                    },
                    "address": lot.address,
                    "capacity": lot.capacity,
                    "price_per_hour": float(lot.price_per_hour) if lot.price_per_hour else None,
                }
            )

        return Response(
            {
                "operator_id": firebase_uid,
                "parking_lots": parking_lots_data,
                "count": len(parking_lots_data),
            },
            status=200,
        )

    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.ParkingLot.DoesNotExist as e:
        return Response(
            {"error": f"Parking lot does not exist {str(e)}"}, status=500
        )
    except models.Manage.DoesNotExist as e:
        return Response(
            {"error": f"Manage relation does not exist {str(e)}"}, status=500
        )
    except Exception as e:
        return Response(
            {"error": f"Failed to retrieve parking lots: {str(e)}"}, status=500
        )


def cadmin_add_parking_lot(request):
    """
    Add a new parking lot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    firebase_uid = request.firebase_uid
    data = request.data

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Create new parking lot
        lot = models.ParkingLot.objects.create(
            name=data.get("name"),
            location=Point(
                float(data.get("longitude")), float(data.get("latitude")), srid=4326
            ),
            address=data.get("address"),
            price_per_hour=data.get("price_per_hour", None),
        )

        # Create management relation
        models.Manage.objects.create(operator=operator, parking_lot=lot)

        # Create eventlist document on firebase firestore
        try:

            db = firestore.client()
            eventlist_ref = db.collection("eventlists").document(str(lot.id))
            eventlist_template = {
                "parking_lot_id": lot.id,
                "parking_lot_name": lot.name,
                "events": [{"occupied_spots": [], "timestamp": datetime.now(timezone.utc)}],
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            eventlist_ref.set(eventlist_template)
        except (ValueError, ConnectionError, RuntimeError) as e:
            # Log the error but don't fail the parking lot creation
            print(f"Warning: Failed to create eventlist document: {str(e)}")

        return Response(
            {
                "message": "Parking lot added successfully",
                "parking_lot": {
                    "id": lot.id,
                    "auth_code": lot.auth_code,
                    "name": lot.name,
                    "location": {
                        "latitude": lot.location.y,
                        "longitude": lot.location.x,
                    },
                    "address": lot.address,
                },
            },
            status=201,
        )

    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except Exception as e:
        return Response({"error": f"Failed to add parking lot: {str(e)}"}, status=500)


def cadmin_update_parking_lot(request):
    """
    Update an existing parking lot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    if not request.data.get("id"):
        return Response({"error": "Parking lot ID is required for update"}, status=400)
    lot_id = request.data.get("id")
    firebase_uid = request.firebase_uid
    data = request.data

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Verify that the operator manages the parking lot
        manage_relation = models.Manage.objects.get(
            operator=operator, parking_lot__id=lot_id
        )

        lot = manage_relation.parking_lot

        # Update parking lot details
        lot.name = data.get("name", lot.name)
        lot.location = Point(
            float(data.get("longitude", lot.location.x)),
            float(data.get("latitude", lot.location.y)),
            srid=4326,
        )
        lot.address = data.get("address", lot.address)
        
        # Update price_per_hour if provided
        if "price_per_hour" in data:
            lot.price_per_hour = data.get("price_per_hour")
        
        lot.save()

        return Response(
            {
                "message": "Parking lot updated successfully",
                "parking_lot": {
                    "id": lot.id,
                    "name": lot.name,
                    "location": {
                        "latitude": lot.location.y,
                        "longitude": lot.location.x,
                    },
                    "address": lot.address,
                    "price_per_hour": float(lot.price_per_hour) if lot.price_per_hour else None,
                },
            },
            status=200,
        )

    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.Manage.DoesNotExist:
        return Response(
            {
                "error": "This parking lot is not managed by the authenticated city operator",
                "parking_lot_id": lot_id,
            },
            status=403,
        )
    except Exception as e:
        return Response(
            {"error": f"Failed to update parking lot: {str(e)}"}, status=500
        )


def cadmin_delete_parking_lot(request):
    """
    Delete an existing parking lot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    if not request.data.get("id"):
        return Response(
            {"error": "Parking lot ID is required for deletion"}, status=400
        )

    firebase_uid = request.firebase_uid
    lot_id = request.data.get("id")

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Verify that the operator manages the parking lot
        manage_relation = models.Manage.objects.get(
            operator=operator, parking_lot__id=lot_id
        )

        lot = manage_relation.parking_lot
        lot_id_for_firestore = str(lot.id)

        # Delete eventlist document from firebase firestore
        try:
            db = firestore.client()
            eventlist_ref = db.collection("eventlists").document(lot_id_for_firestore)
            eventlist_ref.delete()
            print(
                f"Successfully deleted eventlist document for parking lot {lot_id_for_firestore}"
            )
        except (ValueError, ConnectionError, RuntimeError) as e:
            # Log the error but don't fail the parking lot deletion
            print(f"Warning: Failed to delete eventlist document: {str(e)}")

        # Delete the parking lot from database
        lot.delete()

        return Response(
            {"message": "Parking lot deleted successfully", "parking_lot_id": lot_id},
            status=200,
        )

    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.Manage.DoesNotExist:
        return Response(
            {
                "error": "This parking lot is not managed by the authenticated city operator",
                "parking_lot_id": lot_id,
            },
            status=403,
        )
    except IntegrityError as e:
        return Response({"error": f"Database integrity error: {str(e)}"}, status=500)

    except Exception as e:
        return Response(
            {"error": f"Failed to delete parking lot: {str(e)}"}, status=500
        )


@api_view(["GET", "POST", "PUT", "DELETE"])
@firebase_authenticated
def cadmin_parking_lots(request):
    """
    Get all parking lots managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    if request.method == "GET":
        return cadmin_get_parking_lots(request)
    if request.method == "POST":
        return cadmin_add_parking_lot(request)
    if request.method == "PUT":
        return cadmin_update_parking_lot(request)
    if request.method == "DELETE":
        return cadmin_delete_parking_lot(request)

    return Response({"error": "Method not allowed"}, status=405)


@api_view(["GET"])
def parking_lots(request):
    """
    Get all parking lots with optional filtering by distance and price.
    
    Query parameters:
    - latitude: User's latitude (required for distance filtering)
    - longitude: User's longitude (required for distance filtering)
    - max_distance: Maximum distance in kilometers (optional)
    - max_price: Maximum price per hour in DKK (optional)
    """
    
    # Get query parameters
    user_lat = request.GET.get("latitude")
    user_lon = request.GET.get("longitude")
    max_distance = request.GET.get("max_distance")
    max_price = request.GET.get("max_price")
    
    # Start with base queryset
    parking_lots_query = models.ParkingLot.objects.all()
    
    # Filter by price if specified (include NULL/0 prices)
    if max_price:
        try:
            max_price_decimal = float(max_price)
            parking_lots_query = parking_lots_query.filter(
                Q(price_per_hour__lte=max_price_decimal) | 
                Q(price_per_hour__isnull=True) |
                Q(price_per_hour=0)
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid max_price parameter"}, status=400
            )
    
    # Calculate distances and filter if user location provided
    user_location = None
    if user_lat and user_lon:
        try:
            user_location = Point(float(user_lon), float(user_lat), srid=4326)
            
            # Filter by distance if specified
            if max_distance:
                try:
                    max_distance_meters = float(max_distance) * 1000  # Convert km to meters
                    parking_lots_query = parking_lots_query.filter(
                        location__distance_lte=(user_location, max_distance_meters)
                    )
                except (ValueError, TypeError):
                    return Response(
                        {"error": "Invalid max_distance parameter"}, status=400
                    )
            
            # Annotate with distance for ordering and display
            parking_lots_query = parking_lots_query.annotate(
                distance=Distance('location', user_location)
            ).order_by('distance')
            
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid latitude or longitude parameters"}, status=400
            )

    # Execute query and build response
    parking_lots_data = []
    for lot in parking_lots_query:
        lot_data = {
            "id": lot.id,
            "name": lot.name,
            "location": {
                "latitude": lot.location.y,
                "longitude": lot.location.x,
            },
            "address": lot.address,
            "capacity": lot.capacity,
            "price_per_hour": float(lot.price_per_hour) if lot.price_per_hour else None,
        }
        
        # Add distance if calculated
        if user_location and hasattr(lot, 'distance'):
            # Convert meters to kilometers
            lot_data["distance"] = round(lot.distance.km, 2)
        
        parking_lots_data.append(lot_data)

    return Response(
        {"parking_lots": parking_lots_data, "count": len(parking_lots_data)}, status=200
    )


def cadmin_get_parking_spots(request):
    """
    Get all parking spots managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    firebase_uid = request.firebase_uid
    parking_lot_id = request.GET.get("parking_lot_id")

    if not parking_lot_id:
        return Response(
            {"error": "parking_lot_id query parameter is required"}, status=400
        )

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Verify that the operator manages the parking lot
        manage_relation = models.Manage.objects.get(
            operator=operator, parking_lot__id=parking_lot_id
        )

        lot = manage_relation.parking_lot

        # Get all parking spots in this parking lot
        parking_spots = models.ParkingSpot.objects.filter(parking_lot=lot)
        lot_eventlist = firestore.client().collection("eventlists").document(
            str(lot.id)
        ).get()

        if lot_eventlist.exists:
            lot_eventlist_data = lot_eventlist.to_dict()
            latest_event = lot_eventlist_data.get("events", [])[-1]
            occupied_spots = set(latest_event.get("occupied_spots", []))
        else:
            occupied_spots = set()

        is_occupied = lambda spot_id: str(spot_id) in occupied_spots

        parking_spots_data = []
        for spot in parking_spots:
            parking_spots_data.append(
                {
                    "id": spot.id,
                    "spot_number": spot.id,  # Using id as spot_number for now
                    "parking_lot_id": lot.id,
                    "is_occupied": is_occupied(spot.id),
                    "auth_code_prefix": spot.auth_code_prefix,
                }
            )

        return Response(parking_spots_data, status=200)
    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.Manage.DoesNotExist:
        return Response(
            {
                "error": "This parking lot is not managed by the authenticated city operator",
                "parking_lot_id": parking_lot_id,
            },
            status=403,
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to retrieve parking spots: {str(e)}"}, status=500
        )


def cadmin_add_parking_spot(request):
    """
    Add a new parking spot to a parking lot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    firebase_uid = request.firebase_uid
    data = request.data

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Verify that the operator manages the parking lot
        lot_id = data.get("parking_lot_id")
        manage_relation = models.Manage.objects.get(
            operator=operator, parking_lot__id=lot_id
        )

        lot = manage_relation.parking_lot

        # Generate secure token
        auth_token = models.generate_parking_spot_token()
        auth_code_hash = models.hash_token(auth_token)
        auth_code_prefix = models.get_token_prefix(auth_token)

        # Create new parking spot
        spot = models.ParkingSpot.objects.create(
            parking_lot=lot,
            auth_code_hash=auth_code_hash,
            auth_code_prefix=auth_code_prefix,
        )

        # Increment parking lot capacity
        lot.capacity += 1
        lot.save()

        return Response(
            {
                "message": "Parking spot added successfully",
                "parking_spot": {
                    "id": spot.id,
                    "auth_code": auth_token,  # Full token returned only once on creation
                    "auth_code_prefix": auth_code_prefix,
                    "parking_lot_id": lot.id,
                },
                "warning": "Save this auth_code securely. It will not be shown again.",
            },
            status=201,
        )

    except models.CityOperator.DoesNotExist:
        return Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.Manage.DoesNotExist:
        return Response(
            {
                "error": "This parking lot is not managed by the authenticated city operator",
                "parking_lot_id": lot_id,
            },
            status=403,
        )

    except Exception as e:
        return Response({"error": f"Failed to add parking spot: {str(e)}"}, status=500)


def cadmin_delete_parking_spot(request):
    """
    Delete an existing parking spot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    if not request.data.get("id"):
        return Response(
            {"error": "Parking spot ID is required for deletion"}, status=400
        )

    firebase_uid = request.firebase_uid
    spot_id = request.data.get("id")
    response = None

    try:
        # Get the city operator
        operator = models.CityOperator.objects.get(id=firebase_uid)

        # Verify that the operator manages the parking spot
        spot = models.ParkingSpot.objects.get(id=spot_id)
        _ = models.Manage.objects.get(operator=operator, parking_lot=spot.parking_lot)

        # Get the parking lot to decrement capacity
        lot = spot.parking_lot

        # Delete the parking spot from database
        spot.delete()

        # Decrement parking lot capacity
        if lot.capacity > 0:
            lot.capacity -= 1
            lot.save()

        return Response(
            {
                "message": "Parking spot deleted successfully",
                "parking_spot_id": spot_id,
            },
            status=200,
        )

    except models.CityOperator.DoesNotExist:
        response = Response(
            {
                "error": "City operator not found for this Firebase UID",
                "firebase_uid": firebase_uid,
            },
            status=404,
        )
    except models.Manage.DoesNotExist:
        response = Response(
            {
                "error": "This parking spot is not managed by the authenticated city operator",
                "parking_spot_id": spot_id,
            },
            status=403,
        )
    except models.ParkingSpot.DoesNotExist:
        response = Response({"error": "Parking spot not found"}, status=404)

    except Exception as e:
        response = Response(
            {"error": f"Failed to delete parking spot: {str(e)}"}, status=500
        )
    return response


@api_view(["GET", "POST", "DELETE"])
@firebase_authenticated
def cadmin_parking_spots(request):
    """
    Add a new parking spot to a parking lot managed by the authenticated city operator.
    Requires Firebase authentication via Authorization header.
    """
    if request.method == "GET":
        return cadmin_get_parking_spots(request)
    if request.method == "POST":
        return cadmin_add_parking_spot(request)
    if request.method == "DELETE":
        return cadmin_delete_parking_spot(request)
    return Response({"error": "Method not allowed"}, status=405)


@api_view(["POST"])
@parking_spot_authenticated
def post_parking_spot_event(request):
    """
    Post parking spot event to update occupied spots in Firestore.
    Expects: {"occupied": true} or {"occupied": false}
    """
    parking_spot = request.parking_spot
    occupied = request.data.get("occupied")

    if occupied is None or not isinstance(occupied, bool):
        return Response(
            {"error": "Invalid 'occupied' value. Must be true or false."}, status=400
        )

    try:
        parking_lot_id = str(parking_spot.parking_lot.id)
        eventlist_ref = (
            firestore.client().collection("eventlists").document(parking_lot_id)
        )
        eventlist_doc = eventlist_ref.get()
        if not eventlist_doc.exists:
            return Response({"error": "Event list document does not exist"}, status=404)

        eventlist_data = eventlist_doc.to_dict()
        events = eventlist_data.get("events", [])
        latest_event = events[-1]
        occupied_spots = set(latest_event.get("occupied_spots", []))
        spot_id = str(parking_spot.id)
        is_currently_occupied = spot_id in occupied_spots

        # Check if the status is already the same as the current state
        if occupied == is_currently_occupied:
            status_text = "occupied" if occupied else "vacant"
            return Response(
                {"message": f"Parking spot already marked as {status_text}"},
                status=200,
            )

        # Update occupied spots based on new status
        if occupied:
            occupied_spots.add(spot_id)
        else:
            occupied_spots.discard(spot_id)

        new_event = {
            "occupied_spots": list(occupied_spots),
            "timestamp": datetime.now(timezone.utc),
        }
        events.append(new_event)

        eventlist_ref.update(
            {"events": events, "updated_at": firestore.SERVER_TIMESTAMP}
        )

        return Response(
            {"message": "Parking spot event recorded successfully"}, status=200
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to record parking spot event: {str(e)}"}, status=500
        )

@api_view(["GET"])
def request_forecast(request):
    """
    Request parking occupancy forecast from external service.
    
    Query parameters:
    - parking_lot_id: ID of the parking lot (required)
    - hours_ahead: Hours ahead to predict (1, 2, or 3, default: 1)
    """
    # Validate query parameters
    parking_lot_id = request.GET.get("parking_lot_id")
    if not parking_lot_id:
        return Response(
            {"error": "parking_lot_id query parameter is required"}, status=400
        )
    
    try:
        prediction_hours_ahead = int(request.GET.get("hours_ahead", 1))
    except (ValueError, TypeError):
        return Response(
            {"error": "hours_ahead must be a valid integer"}, status=400
        )
    
    if prediction_hours_ahead not in [1, 2, 3]:
        return Response(
            {"error": "hours_ahead query parameter must be 1, 2, or 3"}, status=400
        )

    # Retrieve parking lot and event data
    try:
        parking_lot = models.ParkingLot.objects.get(id=parking_lot_id)
        
        # Get Firestore event data
        firestore_client = firestore.client()
        eventlist_ref = firestore_client.collection("eventlists").document(
            str(parking_lot.id)
        )
        eventlist_doc = eventlist_ref.get()
        
        if not eventlist_doc.exists:
            return Response(
                {"error": "Event list document does not exist"}, status=404
            )
        
        eventlist_data = eventlist_doc.to_dict()
        events = eventlist_data.get("events", [])
        
        if not events:
            return Response(
                {"error": "No events found for this parking lot"}, status=404
            )

    except models.ParkingLot.DoesNotExist:
        return Response({"error": "Parking lot not found"}, status=404)
    except Exception as e:
        return Response(
            {"error": f"Failed to retrieve parking lot data: {str(e)}"}, status=500
        )

    # Process event data for forecast
    try:
        now = datetime.now(timezone.utc)
        
        # Get occupancy status 24 hours ago
        target_time = now - timedelta(hours=24)
        event_24h_ago = min(
            events,
            key=lambda event: abs(
                event["timestamp"].replace(tzinfo=timezone.utc) - target_time
            ),
        )
        occupancy_status_24h_ago = len(event_24h_ago.get("occupied_spots", []))
        
        # Get events from the last 3 hours
        three_hours_ago = now - timedelta(hours=3)
        recent_events = [
            {
                "occupied_spots": event.get("occupied_spots", []),
                "timestamp": event["timestamp"].replace(tzinfo=timezone.utc).isoformat(),
            }
            for event in events
            if event["timestamp"].replace(tzinfo=timezone.utc) >= three_hours_ago
        ]
        
        # If no recent events, use the most recent event available
        if not recent_events:
            latest_event = max(
                events, key=lambda e: e["timestamp"].replace(tzinfo=timezone.utc)
            )
            recent_events = [
                {
                    "occupied_spots": latest_event.get("occupied_spots", []),
                    "timestamp": latest_event["timestamp"]
                    .replace(tzinfo=timezone.utc)
                    .isoformat(),
                }
            ]
        
        prediction_timestamp = now + timedelta(hours=prediction_hours_ahead)

    except Exception as e:
        return Response(
            {"error": f"Failed to process event data: {str(e)}"}, status=500
        )

    # Request forecast from external service
    try:
        forecast_service_url = settings.FORECAST_SERVICE_URL
        if not forecast_service_url:
            return Response(
                {"error": "Forecast service URL not configured on server"}, status=500
            )
        
        url = f"{forecast_service_url}/forecast"
        payload = {
            "latitude": parking_lot.location.y,
            "longitude": parking_lot.location.x,
            "prediction_timestamp": prediction_timestamp.isoformat(),
            "capacity": parking_lot.capacity,
            "status_24h_ago": occupancy_status_24h_ago,
            "status_3h_until_now": recent_events,
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        forecast_data = response.json()
        
        return Response({"forecast": forecast_data}, status=200)
    
    except requests.RequestException as e:
        return Response(
            {"error": f"Failed to retrieve forecast data: {str(e)}"}, status=500
        )
    except Exception as e:
        return Response(
            {"error": f"Unexpected error: {str(e)}"}, status=500
        )