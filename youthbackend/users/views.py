from django.db.models import Q
from django.http import Http404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from core.audit import log_audit
from core.pagination import StandardResultsSetPagination
from core.permissions import IsLeaderOrPastor
from .serializers import (
    MeSerializer,
    UserBasicSerializer,
    UserPastorUpdateSerializer,
    UserRegistrationSerializer,
    UserSelfUpdateSerializer,
    UserSerializer,
    UserStaffUpdateSerializer,
    VisitorCreateSerializer,
)
from .permissions import get_manageable_people_queryset
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class UserList(APIView):

    def get_permissions(self):
        # Sign-up is public; listing people requires staff scope.
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsLeaderOrPastor()]

    def get(self, request):
        """
        Get the people the requesting Leader/Pastor is authorised to see.
        """
        users = get_manageable_people_queryset(request.user).order_by('first_name', 'last_name')
        serializer = UserBasicSerializer(users, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """
        Create a new user - returns JWT immediately after signup.
        Role/status are never accepted from this payload; every new
        account starts as an ordinary Youth/User (see UserRegistrationSerializer).
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Generate JWT
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': serializer.data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class PeopleSearch(APIView):
    """
    Scoped people search for Leaders/Pastors, e.g. for manual attendance
    check-in or group management. Never returns people outside the
    requester's authorised scope.
    """
    permission_classes = [IsLeaderOrPastor]

    def get(self, request):
        queryset = get_manageable_people_queryset(request.user)

        query = request.query_params.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(username__icontains=query)
            )

        group_id = request.query_params.get('group')
        if group_id:
            queryset = queryset.filter(group_memberships__group_id=group_id, group_memberships__is_active=True)

        school_year = request.query_params.get('school_year')
        if school_year:
            queryset = queryset.filter(school_year=school_year)

        queryset = queryset.order_by('first_name', 'last_name').distinct()

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserBasicSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class VisitorCreate(APIView):
    """
    Quick-create a provisional first-time-visitor profile at the door.
    """
    permission_classes = [IsLeaderOrPastor]

    def post(self, request):
        serializer = VisitorCreateSerializer(data=request.data)
        if serializer.is_valid():
            person = serializer.save()
            log_audit(actor=request.user, action='person.visitor_created', entity=person)
            return Response(UserSerializer(person).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
class UserDetail(APIView):
    """
    Single User views
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise Http404

    def _can_view(self, requester, target):
        if requester == target or requester.role == User.Role.PASTOR or requester.is_superuser:
            return True
        return get_manageable_people_queryset(requester).filter(pk=target.pk).exists()

    def get(self, request, pk):
        """
        Get the User Details
        """
        user = self.get_object(pk)
        if not self._can_view(request.user, user):
            return Response(
                {'detail': "You don't have permission to view this account."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """
        Update User Details. Which fields may be changed depends on who is
        asking: self-edit is limited to safe fields, Leaders may update
        managed youth's ministry/guardian fields, and only Pastors may
        change role/status.
        """
        user = self.get_object(pk)
        requester = request.user

        if requester == user:
            serializer_class = UserSelfUpdateSerializer
        elif requester.role == User.Role.PASTOR or requester.is_superuser:
            serializer_class = UserPastorUpdateSerializer
        elif requester.role == User.Role.LEADER and get_manageable_people_queryset(requester).filter(pk=user.pk).exists():
            serializer_class = UserStaffUpdateSerializer
        else:
            return Response(
                {'detail': "You don't have permission to edit this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = serializer_class(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if requester != user:
                log_audit(
                    actor=requester,
                    action='person.updated',
                    entity=user,
                    changes={k: str(v) for k, v in serializer.validated_data.items()},
                )
            return Response(UserSerializer(user).data)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        
    def delete(self, request, pk):
        user = self.get_object(pk)
        requester = request.user

        if not (requester == user or requester.role == User.Role.PASTOR or requester.is_superuser):
            return Response(
                {'detail': "You don't have permission to delete this account."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
class CurrentUser(APIView):
    """
    This is spefically used to get current logged-in user info based on Token
    Custom endpoint users/me for easy front end connection (no PK)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        serializer = MeSerializer(user)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )