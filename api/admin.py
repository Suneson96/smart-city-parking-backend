"""Django admin configuration for the smart city parking API."""

# pylint: disable=too-few-public-methods

from django import forms
from django.contrib.gis import admin
from django.contrib.gis.geos import Point
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


class ParkingLotAdminForm(forms.ModelForm):
    """ModelForm enabling manual coordinate entry."""

    latitude = forms.DecimalField(max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        """Meta class for ParkingLotAdminForm."""

        model = ParkingLot
        fields = ("auth_code", "name", "address", "location")
        widgets = {"location": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.location:
            self.fields["latitude"].initial = self.instance.location.y
            self.fields["longitude"].initial = self.instance.location.x

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")
        if latitude is None or longitude is None:
            raise forms.ValidationError("Both latitude and longitude must be provided.")
        cleaned_data["location"] = Point(float(longitude), float(latitude), srid=4326)
        return cleaned_data

    def save(self, commit=True):
        self.instance.location = self.cleaned_data["location"]
        return super().save(commit)


@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    """Admin interface for ParkingLot model."""

    form = ParkingLotAdminForm
    list_display = ("name", "address", "location")
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
