from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsPastor(BasePermission):
    """Full ministry-admin capability: Pastor role or Django superuser."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.role == user.Role.PASTOR or user.is_superuser)
        )


class IsLeaderOrPastor(BasePermission):
    """Coarse-grained staff check. Object-level scoping (e.g. "leads this
    group") must be enforced separately by the view/service."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_leader_or_pastor or user.is_superuser)
        )


class IsLeaderOrPastorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_leader_or_pastor or user.is_superuser)
        )
