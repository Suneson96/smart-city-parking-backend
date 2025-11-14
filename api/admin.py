"""Django admin configuration for the smart city parking API."""

from django.contrib import admin
from .models import Driver, CityOperator, ParkingLot, Manage, EventList, ParkingSpot


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    """Admin interface for Driver model."""

    list_display = ("id",)
    search_fields = ("id",)


@admin.register(CityOperator)
class CityOperatorAdmin(admin.ModelAdmin):
    """Admin interface for CityOperator model."""

    list_display = ("id",)
    search_fields = ("id",)


@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    """Admin interface for ParkingLot model."""

    list_display = ("name", "address", "latitude", "longitude")
    search_fields = ("name", "address")
    list_filter = ("name",)


@admin.register(Manage)
class ManageAdmin(admin.ModelAdmin):
    """Admin interface for Manage model."""

    list_display = ("operator", "parking_lot")
    search_fields = ("operator__id", "parking_lot__name")
    list_filter = ("parking_lot",)


@admin.register(EventList)
class EventListAdmin(admin.ModelAdmin):
    """Admin interface for EventList model."""

    list_display = ("id", "parking_lot")
    search_fields = ("id", "parking_lot__name")
    list_filter = ("parking_lot",)


@admin.register(ParkingSpot)
class ParkingSpotAdmin(admin.ModelAdmin):
    """Admin interface for ParkingSpot model."""

    list_display = ("auth_code", "parking_lot", "event_list")
    search_fields = ("auth_code", "parking_lot__name")
    list_filter = ("parking_lot", "event_list")
