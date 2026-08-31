from django.contrib.auth import get_user_model

User = get_user_model()


def get_manageable_people_queryset(request_user):
    """Scope which people a given account may view/manage.

    Admins (and superusers) may manage everyone. Leaders are scoped to
    people who share an active membership in a group the leader leads.
    Everyone else may only see themselves. Never fetch everyone and filter
    client-side - the scoping has to happen in the query.
    """
    if request_user.role == User.Role.ADMIN or request_user.is_superuser:
        return User.objects.all()

    if request_user.role == User.Role.LEADER:
        from groups.models import GroupMembership

        led_group_ids = GroupMembership.objects.filter(
            person=request_user,
            membership_role=GroupMembership.MembershipRole.LEADER,
            is_active=True,
        ).values_list('group_id', flat=True)
        member_ids = GroupMembership.objects.filter(
            group_id__in=led_group_ids, is_active=True
        ).values_list('person_id', flat=True)
        return User.objects.filter(id__in=member_ids)

    return User.objects.filter(id=request_user.id)
