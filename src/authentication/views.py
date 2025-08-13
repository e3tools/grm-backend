from django.conf import settings
from django.contrib.auth import authenticate
from django.http import Http404
from drf_yasg import openapi
from drf_yasg.openapi import IN_QUERY, Parameter
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, parsers, renderers, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import ADL, MAJOR
from authentication.models import User
from authentication.serializers import (
    ADLActiveResponseSerializer,
    ADLAdministrativeRegionResponseSerializer,
    CredentialSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserAuthSerializer,
)
from client import get_db
from grm.utils import (
    get_administrative_level_descendants,
    get_parent_administrative_level,
)


class RegisterAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (
        parsers.FormParser,
        parsers.MultiPartParser,
        parsers.JSONParser,
    )
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = RegisterSerializer

    def get_serializer_context(self):
        return {"request": self.request, "format": self.format_kwarg, "view": self}

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        request_body=RegisterSerializer(),
        responses={201: CredentialSerializer()},
        operation_description="Allowed user types: adl or major",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        doc_id = serializer.validated_data["doc_id"]
        credentials = {
            "username": settings.COUCHDB_USERNAME,
            "password": settings.COUCHDB_PASSWORD,
            "doc_id": doc_id,
        }
        credential_serializer = CredentialSerializer(data=credentials)
        credential_serializer.is_valid(raise_exception=True)
        return Response(credential_serializer.data, status=status.HTTP_201_CREATED)


class AuthenticateAPIView(RegisterAPIView):
    serializer_class = UserAuthSerializer

    @swagger_auto_schema(
        request_body=UserAuthSerializer(),
        responses={200: CredentialSerializer()},
        operation_description="Allowed user types: adl or major",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        doc_id = serializer.validated_data["doc_id"]
        credentials = {
            "username": settings.COUCHDB_USERNAME,
            "password": settings.COUCHDB_PASSWORD,
            "doc_id": doc_id,
        }
        credential_serializer = CredentialSerializer(data=credentials)
        credential_serializer.is_valid(raise_exception=True)
        return Response(credential_serializer.data, status=status.HTTP_200_OK)


class ADLActiveAPIView(generics.GenericAPIView):
    @swagger_auto_schema(
        responses={200: ADLActiveResponseSerializer()},
        operation_description="Get adl user status",
        manual_parameters=[
            Parameter(
                "email",
                IN_QUERY,
                description="Email of an facilitator user",
                type="string",
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        email = request.GET.get("email")
        selector = {"representative.email": email, "type": {"$in": [ADL, MAJOR]}}
        eadl_db = get_db()
        docs = eadl_db.get_query_result(selector)
        try:
            doc = eadl_db[docs[0][0]["_id"]]
        except Exception:
            raise Http404

        is_active = (
            doc["representative"]["is_active"]
            if "representative" in doc and "is_active" in doc["representative"]
            else False
        )

        reponse_data = {"is_active": is_active}
        reponse_serializer = ADLActiveResponseSerializer(data=reponse_data)
        reponse_serializer.is_valid(raise_exception=True)
        return Response(reponse_data, status=status.HTTP_200_OK)


class ADLAdministrativeRegionAPIView(generics.GenericAPIView):
    @swagger_auto_schema(
        responses={200: ADLAdministrativeRegionResponseSerializer()},
        operation_description="Get adl user administrative region info",
        manual_parameters=[
            Parameter(
                "email",
                IN_QUERY,
                description="Email of an facilitator user",
                type="string",
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        email = request.GET.get("email")
        selector = {"representative.email": email, "type": {"$in": [ADL, MAJOR]}}
        eadl_db = get_db()
        docs = eadl_db.get_query_result(selector)
        try:
            doc = eadl_db[docs[0][0]["_id"]]
        except Exception:
            raise Http404

        administrative_level = doc["administrative_level"]
        administrative_id = doc["administrative_region"]

        ids = [f"${administrative_id}$"]
        while True:
            parent = get_parent_administrative_level(eadl_db, administrative_id)
            ids.append("$%s$" % parent["administrative_id"])
            administrative_id = parent["administrative_id"]
            if parent["parent_id"] is None:
                break

        if administrative_level != "village":
            descendants = get_administrative_level_descendants(eadl_db, doc["administrative_region"], [])
            for descendant in descendants:
                ids.append("$%s$" % descendant)

        reponse_data = {"levels": ids}
        reponse_serializer = ADLAdministrativeRegionResponseSerializer(data=reponse_data)
        print(f"get-adl-region : {reponse_data}")
        reponse_serializer.is_valid(raise_exception=True)
        return Response(reponse_data, status=status.HTTP_200_OK)


class LoginView(APIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

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
                {'error': 'Invalid input data', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # Authenticate user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None and not user.is_active:
            return Response({'error': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)

        user = authenticate(username=username, password=password)

        if user is None:
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

        # Get or create token for the user
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {'token': token.key, 'user_id': user.id, 'username': user.username, 'message': 'Login successful'},
            status=status.HTTP_200_OK,
        )
