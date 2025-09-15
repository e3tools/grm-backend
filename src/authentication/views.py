from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import (
    INACTIVE_USER_ERROR_MESSAGE,
    INVALID_INPUT_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
    PASSWORD_RESET_REQUEST_MESSAGE,
)
from authentication.models import User
from authentication.serializers import (
    CitizenRegistrationSerializer,
    LoginSerializer,
    PasswordResetSerializer,
)
from grm.constants import CITIZEN_SUCCESS_MESSAGE, VALIDATION_FAILED_MESSAGE
from grm.settings import EMAIL_HOST_USER


class BaseLoginAPIView(APIView):
    """
    Base API endpoint for user authentication and token generation.

    Subclasses can extend `extra_validations(user)` to add specific checks
    (e.g., require that the user has a Citizen profile).
    """

    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

    def extra_validations(self, user):
        """
        Hook for subclasses to add extra validation on the authenticated user.
        Must raise a Response if validation fails.
        """
        return None

    def handle_login(self, username, password):
        """
        Core login logic shared by all login views.
        """
        # Check if user exists and active
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None and not user.is_active:
            return Response(
                {"error": INACTIVE_USER_ERROR_MESSAGE},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"error": LOGIN_ERROR_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Subclass hook
        extra_error = self.extra_validations(user)
        if extra_error:
            return extra_error

        # Get or create token for the user
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "message": LOGIN_SUCCESS_MESSAGE,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """
        Handle POST request for user authentication.

        Validates user credentials and returns authentication token.

        Args:
            request: HTTP request containing username and password

        Returns:
            Response: JSON response with token and user info or error message
        """
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": INVALID_INPUT_ERROR_MESSAGE,
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        return self.handle_login(username, password)


class LoginAPIView(BaseLoginAPIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description="Authenticate user credentials and return authentication token.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Authentication token for API requests"
                        ),
                        'user_id': openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Unique identifier for the authenticated user"
                        ),
                        'username': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Username of the authenticated user"
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad request - Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message describing the validation issue"
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description="Field-specific validation errors"
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid credentials",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Authentication error message"),
                    },
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User account is inactive",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Account status error message"),
                    },
                ),
            ),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        return super().post(request)


class CitizenLoginAPIView(BaseLoginAPIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    @swagger_auto_schema(
        operation_summary="Citizen Login",
        operation_description="Authenticate user credentials and return authentication token. "
        "Only users linked to a Citizen profile are allowed.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Authentication token for API requests"
                        ),
                        'user_id': openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Unique identifier for the authenticated user"
                        ),
                        'username': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Username of the authenticated user"
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad request - Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message describing the validation issue"
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description="Field-specific validation errors"
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid credentials or missing Citizen relation",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Authentication error message"),
                    },
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User account is inactive",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Account status error message"),
                    },
                ),
            ),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        return super().post(request)

    def extra_validations(self, user):
        if not hasattr(user, "citizen"):
            return Response(
                {"error": LOGIN_ERROR_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return None


class CitizenRegistrationCreateAPIView(CreateAPIView):
    """
    API View for registering new Citizens.

    This view handles the creation of new User accounts and associated Citizen instances.
    No authentication is required for registration.
    """

    serializer_class = CitizenRegistrationSerializer
    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

    @swagger_auto_schema(
        operation_summary="Register a new citizen",
        operation_description="""
        Register a new citizen account. Creates both a User and associated Citizen record.

        **No authentication required for this endpoint.**
        """,
        tags=['Authentication'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING, description='Unique username for the account', example='john.doe'
                ),
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING, description='First name of the citizen', example='John', max_length=150
                ),
                'last_name': openapi.Schema(
                    type=openapi.TYPE_STRING, description='Last name of the citizen', example='Doe', max_length=150
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description='Unique email address for the account',
                    example='john.doe@example.com',
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Account password (must meet security requirements)',
                    example='SecurePassword123!',
                ),
                'confirm_password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Password confirmation (must match password)',
                    example='SecurePassword123!',
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Citizen registered successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=CITIZEN_SUCCESS_MESSAGE),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID', example=42),
                                'username': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_EMAIL,
                                    description='Username',
                                    example='john.doe',
                                ),
                                'email': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_EMAIL,
                                    description='User email address',
                                    example='john.doe@example.com',
                                ),
                                'first_name': openapi.Schema(
                                    type=openapi.TYPE_STRING, description='User first name', example='John'
                                ),
                                'last_name': openapi.Schema(
                                    type=openapi.TYPE_STRING, description='User last name', example='Doe'
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": VALIDATION_FAILED_MESSAGE,
                        "errors": {
                            "username": ["A user with that username already exists."],
                            "email": ["user with this email address already exists."],
                            "confirm_password": ["Password confirmation does not match."],
                            "password": ["This password is too short. It must contain at least 8 characters."],
                        },
                    }
                },
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while registering the citizen.'
                        )
                    },
                ),
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Register a new citizen.

        Creates a new User account and associated Citizen record.

        Args:
            request: HTTP request object containing registration data

        Returns:
            Response: JSON response with created user data or error details
        """
        try:
            serializer = self.get_serializer(data=request.data)

            if serializer.is_valid():
                user = serializer.save()

                response_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }

                return Response(
                    {'message': CITIZEN_SUCCESS_MESSAGE, 'data': response_data},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {'message': VALIDATION_FAILED_MESSAGE, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ValidationError as e:
            return Response(
                {'message': VALIDATION_FAILED_MESSAGE, 'errors': e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'message': _('An error occurred while registering the citizen.'), 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PasswordResetAPIView(APIView):
    """
    API endpoint for requesting a password reset.

    This view allows users to request a password reset by providing
    their registered email address. If the email exists in the system,
    a password reset token and UID are generated and sent to the user's email.

    Authentication is not required for this endpoint.
    """

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Password Reset Request",
        operation_description="Send password reset instructions to a user via email.",
        request_body=PasswordResetSerializer,
        responses={
            200: openapi.Response(
                description="Password reset email sent successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={"message": openapi.Schema(type=openapi.TYPE_STRING, description="Success message")},
                ),
            ),
            400: openapi.Response(
                description="Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "error": openapi.Schema(type=openapi.TYPE_STRING, description="Error message"),
                        "details": openapi.Schema(type=openapi.TYPE_OBJECT, description="Validation errors"),
                    },
                ),
            ),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        """
        Handle POST request for initiating password reset.

        Args:
            request: HTTP request containing the user's email.

        Returns:
            Response: JSON response with success or error message.
        """
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": INVALID_INPUT_ERROR_MESSAGE, "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Do not reveal whether email exists (security best practice)
            return Response(
                {"message": PASSWORD_RESET_REQUEST_MESSAGE},
                status=status.HTTP_200_OK,
            )

        # Generate token and UID
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Example reset link (frontend should handle this)
        reset_link = f"https://yourfrontend.com/reset-password/{uid}/{token}/"

        # Send email
        send_mail(
            subject="Password Reset Request",
            message=f"Please click the following link to reset your password: {reset_link}",
            from_email=EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=True,
        )

        return Response(
            {"message": PASSWORD_RESET_REQUEST_MESSAGE},
            status=status.HTTP_200_OK,
        )
