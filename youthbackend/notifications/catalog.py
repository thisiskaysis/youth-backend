"""Stable, machine-readable notification vocabulary shared by backend
services, templates and (eventually) frontend settings screens - see
NOTIFICATIONS.xlsx sheet 07 "Notification Types" for the source spec.
"""
from django.db import models


class Category(models.TextChoices):
    # Youth/volunteer-facing
    VOLUNTEER_REQUESTS = 'VOLUNTEER_REQUESTS', 'Volunteer Serving > Requests'
    VOLUNTEER_REMINDERS = 'VOLUNTEER_REMINDERS', 'Volunteer Serving > Reminders'
    VOLUNTEER_CHANGES = 'VOLUNTEER_CHANGES', 'Volunteer Serving > Changes'
    RIDES = 'RIDES', 'Rides'
    INBOX = 'INBOX', 'Inbox'
    EVENTS = 'EVENTS', 'Events'
    FORMS = 'FORMS', 'Forms & Consent'
    PRAYER = 'PRAYER', 'Prayer'
    GROUPS = 'GROUPS', 'Groups'
    PROFILE = 'PROFILE', 'Profile'
    # Leader/admin-facing
    LEADER_ATTENDANCE = 'LEADER_ATTENDANCE', 'Leadership > Attendance'
    LEADER_ROSTER = 'LEADER_ROSTER', 'Leadership > Roster'
    LEADER_RIDES = 'LEADER_RIDES', 'Leadership > Rides'
    LEADER_PRAYER = 'LEADER_PRAYER', 'Leadership > Prayer'
    LEADER_FOLLOWUP = 'LEADER_FOLLOWUP', 'Leadership > Follow-up'
    LEADER_CMS = 'LEADER_CMS', 'Leadership > CMS'
    LEADER_DIGEST = 'LEADER_DIGEST', 'Leadership > Weekly Summary'


class NotificationType(models.TextChoices):
    VOLUNTEER_ASSIGNMENT_REQUESTED = 'VOLUNTEER_ASSIGNMENT_REQUESTED', 'Volunteer assignment requested'
    VOLUNTEER_RESPONSE_REMINDER = 'VOLUNTEER_RESPONSE_REMINDER', 'Volunteer response reminder'
    VOLUNTEER_SERVING_SOON = 'VOLUNTEER_SERVING_SOON', 'Serving soon'
    VOLUNTEER_SERVING_TODAY = 'VOLUNTEER_SERVING_TODAY', 'Serving today'
    VOLUNTEER_ASSIGNMENT_CHANGED = 'VOLUNTEER_ASSIGNMENT_CHANGED', 'Assignment changed'
    VOLUNTEER_ASSIGNMENT_CANCELLED = 'VOLUNTEER_ASSIGNMENT_CANCELLED', 'Assignment cancelled'
    RIDE_STATUS_UPDATED = 'RIDE_STATUS_UPDATED', 'Ride status updated'
    RIDE_CONFIRMED = 'RIDE_CONFIRMED', 'Ride confirmed'
    RIDE_CHANGED_CANCELLED = 'RIDE_CHANGED_CANCELLED', 'Ride changed/cancelled'
    MESSAGE_RECEIVED = 'MESSAGE_RECEIVED', 'New direct message'
    EVENT_ANNOUNCED = 'EVENT_ANNOUNCED', 'Event announced'
    EVENT_REMINDER = 'EVENT_REMINDER', 'Event reminder'
    EVENT_CHANGED_CANCELLED = 'EVENT_CHANGED_CANCELLED', 'Event changed/cancelled'
    FORM_ASSIGNED = 'FORM_ASSIGNED', 'Form assigned'
    FORM_DUE_REMINDER = 'FORM_DUE_REMINDER', 'Form due reminder'
    FORM_OVERDUE = 'FORM_OVERDUE', 'Form overdue'
    PRAYER_RESPONSE_AVAILABLE = 'PRAYER_RESPONSE_AVAILABLE', 'Prayer response available'
    GROUP_ADDED = 'GROUP_ADDED', 'Added to group'
    GROUP_REMOVED = 'GROUP_REMOVED', 'Removed from group'
    PROFILE_ACTION_REQUIRED = 'PROFILE_ACTION_REQUIRED', 'Profile action required'
    ATTENDANCE_RECONCILIATION_REMINDER = 'ATTENDANCE_RECONCILIATION_REMINDER', 'Attendance reconciliation reminder'
    ATTENDANCE_NOT_CLOSED = 'ATTENDANCE_NOT_CLOSED', 'Attendance session not closed'
    ROSTER_DECLINED = 'ROSTER_DECLINED', 'Volunteer declined'
    ROSTER_PENDING_SUMMARY = 'ROSTER_PENDING_SUMMARY', 'Pending roster responses'
    ROSTER_UNFILLED_SUMMARY = 'ROSTER_UNFILLED_SUMMARY', 'Roster has unfilled positions'
    RIDE_REQUEST_NEW = 'RIDE_REQUEST_NEW', 'New ride request'
    RIDE_UNASSIGNED_REMINDER = 'RIDE_UNASSIGNED_REMINDER', 'Ride request unassigned'
    PRIVATE_PRAYER_NEW = 'PRIVATE_PRAYER_NEW', 'New leaders-only prayer request'
    PRAYER_ESCALATED = 'PRAYER_ESCALATED', 'Prayer request escalated'
    FOLLOWUP_DUE = 'FOLLOWUP_DUE', 'Follow-up due soon'
    FOLLOWUP_OVERDUE = 'FOLLOWUP_OVERDUE', 'Follow-up overdue'
    CONTENT_PUBLISH_FAILED = 'CONTENT_PUBLISH_FAILED', 'Scheduled content failed to publish'
    PUSH_CAMPAIGN_FAILED = 'PUSH_CAMPAIGN_FAILED', 'Scheduled push failed'
    WEEKLY_MINISTRY_SUMMARY = 'WEEKLY_MINISTRY_SUMMARY', 'Weekly ministry summary'


# Recommended launch defaults per category (NOTIFICATIONS.xlsx sheets 05/11).
# A user's own NotificationPreference.category_overrides can override these.
CATEGORY_DEFAULTS = {
    Category.VOLUNTEER_REQUESTS: {'push': True, 'email': True},
    Category.VOLUNTEER_REMINDERS: {'push': True, 'email': False},
    Category.VOLUNTEER_CHANGES: {'push': True, 'email': True},
    Category.RIDES: {'push': True, 'email': True},
    Category.INBOX: {'push': True, 'email': False},
    Category.EVENTS: {'push': True, 'email': False},
    Category.FORMS: {'push': True, 'email': True},
    Category.PRAYER: {'push': True, 'email': False},
    Category.GROUPS: {'push': False, 'email': False},
    Category.PROFILE: {'push': True, 'email': False},
    Category.LEADER_ATTENDANCE: {'push': True, 'email': False},
    Category.LEADER_ROSTER: {'push': True, 'email': False},
    Category.LEADER_RIDES: {'push': True, 'email': False},
    Category.LEADER_PRAYER: {'push': True, 'email': False},
    Category.LEADER_FOLLOWUP: {'push': True, 'email': True},
    Category.LEADER_CMS: {'push': True, 'email': True},
    Category.LEADER_DIGEST: {'push': False, 'email': True},
}
