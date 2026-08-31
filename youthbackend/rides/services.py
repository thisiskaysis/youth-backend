"""Ride request workflow. Not group-scoped like volunteers/prayer - any
Leader/Pastor can triage transport requests, matching how this operates in
practice (a small transport-coordinator pool, not per-group ownership)."""
from django.contrib.auth import get_user_model

from notifications.catalog import Category, NotificationType
from notifications.services import notify, notify_many

from .models import RideRequest

User = get_user_model()


def create_ride_request(*, person, event=None, requested_date=None, direction, area='', notes=''):
    ride = RideRequest.objects.create(
        person=person, event=event, requested_date=requested_date,
        direction=direction, area=area, notes=notes,
    )
    notify_many(
        User.objects.filter(role__in=[User.Role.LEADER, User.Role.PASTOR]),
        Category.LEADER_RIDES, NotificationType.RIDE_REQUEST_NEW,
        title='New ride request',
        body=f'{person} requested transport.',
        deep_link_type='ride_request', deep_link_id=ride.id,
        data={'ride_request_id': ride.id},
    )
    return ride


def update_ride(ride, **fields):
    previous_status = ride.status
    for field, value in fields.items():
        setattr(ride, field, value)
    ride.save()

    if ride.status == previous_status:
        return ride

    if ride.status == RideRequest.Status.CONFIRMED:
        notify(
            ride.person, Category.RIDES, NotificationType.RIDE_CONFIRMED,
            title='Your ride is confirmed',
            body='Check the app for details.',
            deep_link_type='ride_request', deep_link_id=ride.id,
            data={'ride_request_id': ride.id},
        )
    elif ride.status == RideRequest.Status.CANCELLED:
        notify(
            ride.person, Category.RIDES, NotificationType.RIDE_CHANGED_CANCELLED,
            title='Your ride was cancelled',
            body='Please arrange alternative transport.',
            deep_link_type='ride_request', deep_link_id=ride.id,
            data={'ride_request_id': ride.id}, urgent=True,
        )
    elif previous_status != RideRequest.Status.REQUESTED:
        # A change once already in progress is worth a nudge; the initial
        # REQUESTED -> ARRANGING transition isn't materially interesting.
        notify(
            ride.person, Category.RIDES, NotificationType.RIDE_STATUS_UPDATED,
            title='Your ride status has changed',
            body=f'Status: {ride.get_status_display()}.',
            deep_link_type='ride_request', deep_link_id=ride.id,
            data={'ride_request_id': ride.id},
        )
    return ride
