from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import GroupMembership


def user_leads_group(user, group):
    if user.role == user.Role.ADMIN or user.is_superuser:
        return True
    return GroupMembership.objects.filter(
        group=group, person=user, membership_role=GroupMembership.MembershipRole.LEADER, is_active=True
    ).exists()


class CanManageGroup(BasePermission):
    """Anyone authenticated may read groups; only Admins or that specific
    group's Leader may create/change/delete it."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_leader_or_admin or user.is_superuser

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return user_leads_group(request.user, obj)
