from django.http import Http404
from django.shortcuts import redirect
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .models import User
from .serializers import UserSerializer
import logging
import os

User = get_user_model()
logger = logging.getLogger(__name__)

class UserList(APIView):
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        Get a list of all users in the database
        """
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """
        Create a new user - returns JWT immediately after signup
        """
        serializer = UserSerializer(data=request.data)
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
    
    def get(self, request, pk):
        """
        Get the User Details
        """
        user = self.get_object(pk)
        if request.user != user:
            return Response(
                {'detail': "You don't have permission to view this account."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """
        Update User Details
        """
        user = self.get_object(pk)
        if request.user != user:
            return Response(
                {'detail': "You don't have permission to edit this account."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        
    def delete(self, request, pk):
        user = self.get_object(pk)
        
        if request.user != user:
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
        serializer = UserSerializer(user)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )