"""Model definitions for the smart city parking application."""

# pylint: disable=no-member

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.validators import RegexValidator

FIREBASE_UID_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-z0-9_\-]{28}$", message="Invalid Firebase UID format."
)

FIRESTORE_ID_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-z0-9_\-]+$", message="Invalid Firestore document ID."
)


class Driver(models.Model):
    """Model representing a driver."""

    id = models.CharField(
        max_length=28, primary_key=True, validators=[FIREBASE_UID_VALIDATOR]
    )

    def __str__(self):
        return str(self.id)


class CityOperator(models.Model):
    """Model representing a city operator."""

    id = models.CharField(
        max_length=28, primary_key=True, validators=[FIREBASE_UID_VALIDATOR]
    )

    def __str__(self):
        return str(self.id)


class ParkingLot(models.Model):
    """Model representing a parking lot."""

    auth_code = models.CharField(
        max_length=50, auto_created=True, unique=True, null=False, blank=False
    )
    name = models.CharField(max_length=100, unique=True, null=False, blank=False)
    address = models.CharField(max_length=255, unique=True, null=False, blank=False)
    location = models.PointField(
        srid=4326, geography=True, default=Point(12.5683, 55.6761)
    )

    def __str__(self):
        return str(self.name)


class Manage(models.Model):
    """Model representing the management relationship between city operators and parking lots."""

    operator = models.ForeignKey(CityOperator, on_delete=models.CASCADE)
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.operator.id} manages {self.parking_lot.name}"


class EventList(models.Model):
    """Model representing an event list for a parking lot."""

    id = models.CharField(
        max_length=128, primary_key=True, validators=[FIRESTORE_ID_VALIDATOR]
    )
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def __str__(self):
        return f"Event List for {self.parking_lot.name}"


class ParkingSpot(models.Model):
    """Model representing a parking spot within a parking lot."""

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)
    auth_code = models.CharField(
        max_length=50, auto_created=True, unique=True, null=False, blank=False
    )
    event_list = models.ForeignKey(
        EventList, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"Spot {self.auth_code} in {self.parking_lot.name}"
