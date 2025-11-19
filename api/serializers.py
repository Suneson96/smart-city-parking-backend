"""Serializers for the smart city parking API."""
# pylint: disable=too-few-public-methods
from rest_framework import serializers
from .models import Driver, CityOperator, ParkingLot, Manage, EventList, ParkingSpot


class DriverSerializer(serializers.ModelSerializer):
    """Serializer for Driver model."""

    class Meta:
        """Meta class for DriverSerializer."""
        model = Driver
        fields = ("id",)


class CityOperatorSerializer(serializers.ModelSerializer):
    """Serializer for CityOperator model."""

    class Meta:
        """Meta class for CityOperatorSerializer."""
        model = CityOperator
        fields = ("id",)


class ParkingLotSerializer(serializers.ModelSerializer):
    """Serializer for ParkingLot model."""

    class Meta:
        """Meta class for ParkingLotSerializer."""
        model = ParkingLot
        fields = ("auth_code", "name", "latitude", "longitude", "address")


class ManageSerializer(serializers.ModelSerializer):
    """Serializer for Manage model."""

    operator_id = serializers.CharField(source="operator.id", read_only=True)
    parking_lot_name = serializers.CharField(source="parking_lot.name", read_only=True)

    class Meta:
        """Meta class for ManageSerializer."""
        model = Manage
        fields = ("id", "operator", "operator_id", "parking_lot", "parking_lot_name")


class EventListSerializer(serializers.ModelSerializer):
    """Serializer for EventList model."""

    parking_lot_name = serializers.CharField(source="parking_lot.name", read_only=True)

    class Meta:
        """Meta class for EventListSerializer."""
        model = EventList
        fields = ("id", "parking_lot", "parking_lot_name")


class ParkingSpotSerializer(serializers.ModelSerializer):
    """Serializer for ParkingSpot model."""

    parking_lot_name = serializers.CharField(source="parking_lot.name", read_only=True)
    event_list_id = serializers.CharField(source="event_list.id", read_only=True)

    class Meta:
        """Meta class for ParkingSpotSerializer."""
        model = ParkingSpot
        fields = (
            "id",
            "parking_lot",
            "parking_lot_name",
            "auth_code",
            "event_list",
            "event_list_id",
        )
