from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Citizen, Facilitator, User
from grm.constants import (
    EMAIL_ERROR_MESSAGE,
    PASSWORD_CONFIRMATION_ERROR_MESSAGE,
    USERNAME_ERROR_MESSAGE,
)


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login credentials.

    This serializer validates username and password for authentication
    and returns appropriate error messages for invalid credentials.
    """

    username = serializers.CharField(max_length=150, help_text=_("Username for authentication"))
    password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, help_text=_("Password for authentication")
    )


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for User objects to display minimal user information.
    """

    class Meta:
        model = User
        fields = ['id', 'name']
        read_only_fields = ['id', 'name']


class CitizenRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for citizen registration.

    Handles user creation with required fields and password confirmation validation.
    """

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'password', 'confirm_password']
        extra_kwargs = {
            "email": {"required": False, "allow_blank": True},
        }

    def validate_username(self, value):
        """Validate username is unique."""
        if User.objects.filter(username=value.lower()).exists():
            raise serializers.ValidationError(USERNAME_ERROR_MESSAGE)
        return value

    def validate_email(self, value):
        """Validate email is unique."""
        if value and User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(EMAIL_ERROR_MESSAGE)
        return value

    def validate(self, attrs):
        """Validate password confirmation and strength."""
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError({'confirm_password': PASSWORD_CONFIRMATION_ERROR_MESSAGE})

        # Validate password strength using Django's built-in validators
        try:
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})

        return attrs

    def create(self, validated_data):
        """Create user and associated citizen."""
        validated_data.pop('confirm_password')  # Remove confirm_password

        # Create user
        user = User.objects.create_user(
            username=validated_data['username'].lower(),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=validated_data['email'].lower(),
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
        )

        # Create associated citizen
        Citizen.objects.create(user=user)

        return user


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class FacilitatorProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for Facilitator profile information.

    Provides complete facilitator data including nested serialization
    of user, department, and administrative_region.
    """

    user = UserBasicSerializer(read_only=True)
    department = serializers.SerializerMethodField()
    administrative_region = serializers.SerializerMethodField()

    class Meta:
        model = Facilitator
        fields = [
            'id',
            'user',
            'department',
            'administrative_region',
            'unique_region',
            'village_secretary',
            'created_date',
            'updated_date',
        ]

    def get_department(self, obj):
        """Lazy import to avoid circular import."""
        if not obj.department:
            return None
        from issues.serializers import IssueDepartmentSerializer

        return IssueDepartmentSerializer(obj.department).data

    def get_administrative_region(self, obj):
        """Lazy import to avoid circular import."""
        if not obj.administrative_region:
            return None
        from issues.serializers import AdministrativeRegionSerializer

        return AdministrativeRegionSerializer(obj.administrative_region).data
