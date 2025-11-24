"""
API views.
"""

# pylint: disable=no-member

import os
from functools import wraps
from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import IntegrityError
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from . import models

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
                    "auth_code": lot.auth_code,
                    "name": lot.name,
                    "location": {
                        "latitude": lot.location.y,
                        "longitude": lot.location.x,
                    },
                    "address": lot.address,
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
    except (models.ParkingLot.DoesNotExist, models.Manage.DoesNotExist) as e:
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
            auth_code=data.get("auth_code"),
            name=data.get("name"),
            location=Point(
                float(data.get("longitude")), float(data.get("latitude")), srid=4326
            ),
            address=data.get("address"),
        )

        # Create management relation
        models.Manage.objects.create(operator=operator, parking_lot=lot)

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
    except (ValueError, TypeError, KeyError) as e:
        return Response({"error": f"Failed to add parking lot: {str(e)}"}, status=500)
    except IntegrityError as e:
        return Response(
            {"error": f"Database integrity error: {str(e)}"}, status=500
        )


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
        lot.auth_code = data.get("auth_code", lot.auth_code)
        lot.name = data.get("name", lot.name)
        lot.location = Point(
            float(data.get("longitude", lot.location.x)),
            float(data.get("latitude", lot.location.y)),
            srid=4326,
        )
        lot.address = data.get("address", lot.address)
        lot.save()

        return Response(
            {
                "message": "Parking lot updated successfully",
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
        return Response(
            {"error": f"Database integrity error: {str(e)}"}, status=500
        )
    except (ValueError, TypeError, KeyError) as e:
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

        # Delete the parking lot
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
        return Response(
            {"error": f"Database integrity error: {str(e)}"}, status=500
        )
    except (ValueError, TypeError) as e:
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
def parking_lots(_):
    """
    Get all parking lots.
    """

    all_parking_lots = models.ParkingLot.objects.all()
    parking_lots_data = []
    for lot in all_parking_lots:
        parking_lots_data.append(
            {
                "id": lot.id,
                "auth_code": lot.auth_code,
                "name": lot.name,
                "location": {
                    "latitude": lot.location.y,
                    "longitude": lot.location.x,
                },
                "address": lot.address,
            }
        )

    return Response(
        {"parking_lots": parking_lots_data, "count": len(parking_lots_data)}, status=200
    )
