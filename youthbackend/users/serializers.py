from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}
        
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    
class UserBasicSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'display_name',
            'profile_image',
            ]
        
    def get_display_name(self, obj):
        first = obj.first_name or ""
        last_initial = f"{obj.last_name[0]}." if obj.last_name else ""
        
        name = f"{first} {last_initial}".strip()
        
        if name:
            return name
        
        if obj.email:
            return obj.email.split("@")[0]
        
        return "User"