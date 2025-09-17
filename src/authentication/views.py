from django.contrib.auth import authenticate
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import render
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views import View
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import (
    CITIZEN_CREATE_ERROR_MESSAGE,
    INACTIVE_USER_ERROR_MESSAGE,
    INVALID_INPUT_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
    PASSWORD_RESET_REQUEST_MESSAGE,
)
from authentication.forms import PasswordResetRequestForm
from authentication.models import User
from authentication.serializers import (
    CitizenRegistrationSerializer,
    LoginSerializer,
    PasswordResetSerializer,
)
from authentication.services import PasswordResetService
from grm.constants import CITIZEN_SUCCESS_MESSAGE, VALIDATION_FAILED_MESSAGE


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
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=CITIZEN_CREATE_ERROR_MESSAGE)
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
                {'message': CITIZEN_CREATE_ERROR_MESSAGE, 'error': str(e)},
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
        PasswordResetService.handle_password_reset_request(request, email)

        return Response(
            {"message": PASSWORD_RESET_REQUEST_MESSAGE},
            status=status.HTTP_200_OK,
        )


class PasswordResetView(View):
    """
    Django view for requesting a password reset via a form.

    This view:
    - Displays a form to collect the user's email.
    - If valid, sends a password reset email with a reset link.
    - Shows a success message regardless of whether the email exists in the system.
    """

    template_name = "authentication/password_reset_form.html"
    success_template_name = "authentication/password_reset_done.html"

    def get(self, request, *args, **kwargs):
        """Render the password reset request form."""
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {"form": form, "title": _("Password Reset")})

    def post(self, request, *args, **kwargs):
        """Handle form submission for password reset request."""
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            PasswordResetService.handle_password_reset_request(request, email)
            return render(
                request,
                self.success_template_name,
                {"title": _("Password Reset Sent"), "message": PASSWORD_RESET_REQUEST_MESSAGE},
            )
        return render(request, self.template_name, {"form": form, "title": _("Password Reset")})


class PasswordResetConfirmView(View):
    """
    View to handle password reset confirmation.

    This view is responsible for:
    - Validating the reset token and user.
    - Displaying a form to set a new password.
    - Updating the user's password upon successful form submission.
    - Showing a success message once the password has been reset.
    """

    template_name = "authentication/password_reset_confirm.html"
    success_template_name = "authentication/password_reset_complete.html"

    def get_user(self, uidb64):
        """
        Retrieve the user based on the base64 encoded user ID.
        """
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def get(self, request, uidb64, token):
        """
        Handle GET request.
        If token is valid, display the password reset form.
        If token is invalid, show an error message.
        """
        user = self.get_user(uidb64)

        context = {'title': _("Reset Password"), "validlink": True}

        if user is not None and default_token_generator.check_token(user, token):
            form = SetPasswordForm(user)
            context["form"] = form
        else:
            context["validlink"] = False
        return render(request, self.template_name, context)

    def post(self, request, uidb64, token):
        """
        Handle POST request.
        Validate and save the new password.
        If successful, render a success template instead of the form.
        """
        user = self.get_user(uidb64)

        context = {'title': _("Reset Password"), "validlink": True}

        if user is None or not default_token_generator.check_token(user, token):
            context["validlink"] = False
            return render(request, self.template_name, context)

        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            # Force a reload of the user so the token is invalidated
            user.refresh_from_db()
            return render(request, self.success_template_name, {"title": _("Password reset complete")})

        context["form"] = form
        return render(request, self.template_name, context)
