import secrets

from rest_framework import serializers

from .models import User


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


class UserSerializer(serializers.ModelSerializer):
    """Read representation of a profile. Deliberately excludes qr_token -
    a person's own QR is only ever returned via the `/me` endpoint, and
    password is never returned regardless of caller."""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_image', 'role', 'status', 'date_of_birth', 'school_year',
            'phone_number', 'guardian_name', 'guardian_phone', 'guardian_email',
            'emergency_contact_name', 'emergency_contact_phone',
            'is_provisional', 'date_joined',
        ]
        read_only_fields = fields


class MeSerializer(UserSerializer):
    """Adds the caller's own QR token - never exposed for other people."""

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['qr_token']
        read_only_fields = fields


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Public sign-up. `role`/`status`/`qr_token` are never client-settable
    here - every new account starts as an ordinary Youth/User."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSelfUpdateSerializer(serializers.ModelSerializer):
    """Fields a signed-in person may change on their own profile."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile_image', 'phone_number']


class UserStaffUpdateSerializer(serializers.ModelSerializer):
    """Fields a Leader may change on a youth profile they are authorised to
    manage. Role is deliberately excluded - only an Admin can regrade
    someone's role (see UserAdminUpdateSerializer)."""

    class Meta:
        model = User
        fields = UserSelfUpdateSerializer.Meta.fields + [
            'date_of_birth', 'school_year',
            'guardian_name', 'guardian_phone', 'guardian_email',
            'emergency_contact_name', 'emergency_contact_phone',
            'status',
        ]


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """Adds role management, restricted to Admins or superusers."""

    class Meta:
        model = User
        fields = UserStaffUpdateSerializer.Meta.fields + ['role']


class VisitorCreateSerializer(serializers.ModelSerializer):
    """Quick-create a provisional first-time-visitor profile at check-in,
    so nobody is turned away from the door for lacking the app/account."""

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'date_of_birth', 'school_year']
        extra_kwargs = {'first_name': {'required': True}}

    def create(self, validated_data):
        username = f"visitor-{secrets.token_hex(4)}"
        while User.objects.filter(username=username).exists():
            username = f"visitor-{secrets.token_hex(4)}"
        user = User(username=username, is_provisional=True, role=User.Role.YOUTH, **validated_data)
        user.set_unusable_password()
        user.save()
        return user
