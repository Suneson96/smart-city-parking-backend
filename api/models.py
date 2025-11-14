from django.db import models
from django.core.validators import RegexValidator

FIREBASE_UID_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-z0-9_\-]{28}$',
    message="Invalid Firebase UID format."
)

FIRESTORE_ID_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-z0-9_\-]+$',
    message="Invalid Firestore document ID."
)

class Driver(models.Model):
    id = models.CharField(max_length=28, primary_key=True, validators=[FIREBASE_UID_VALIDATOR])

    def __str__(self):
        return self.id
    
class CityOperator(models.Model):
    id = models.CharField(max_length=28, primary_key=True, validators=[FIREBASE_UID_VALIDATOR])

    def __str__(self):
        return self.id
    
class ParkingLot(models.Model):
    auth_code = models.CharField(max_length=50, auto_created=True, unique=True, null=False, blank=False)
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name
    
class Manage(models.Model):
    operator = models.ForeignKey(CityOperator, on_delete=models.CASCADE)
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.operator.id} manages {self.parking_lot.name}"
    
class EventList(models.Model):
    id = models.CharField(max_length=128, primary_key=True, validators=[FIRESTORE_ID_VALIDATOR])
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def __str__(self):
        return f"Event List for {self.parking_lot.name}"
    
class ParkingSpot(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)
    auth_code = models.CharField(max_length=50, auto_created=True, unique=True, null=False, blank=False)
    event_list = models.ForeignKey(EventList, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Spot {self.auth_code} in {self.parking_lot.name}"
    