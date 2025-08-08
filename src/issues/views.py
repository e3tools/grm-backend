from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from issues.models import Issue
from issues.serializers import IssueCreateSerializer, IssueDetailSerializer


class IssueCreateAPIView(CreateAPIView):
    """
    API View for creating new Issue objects.

    This view handles the creation of new Issue instances with proper validation
    and error handling. It requires Token authentication and validates all required fields.

    Attributes:
        queryset: Issue queryset for the view
        serializer_class: Serializer used for input validation
        authentication_classes: List of authentication classes (TokenAuthentication)
        permission_classes: List of permission classes (IsAuthenticated)
    """

    queryset = Issue.objects.all()
    serializer_class = IssueCreateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            201: IssueDetailSerializer,
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": "Validation failed.",
                        "errors": {
                            "status": ["This field is required."],
                            "category": ["This field is required."],
                            "issue_type": ["This field is required."],
                            "administrative_region": ["This field is required."]
                        }
                    }
                }
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={
                    "application/json": {
                        "detail": "Invalid token."
                    }
                }
            ),
            500: openapi.Response(
                description="Internal Server Error",
                examples={
                    "application/json": {
                        "message": "An error occurred while creating the issue.",
                        "error": "Error details"
                    }
                }
            )
        },
        operation_description="""
        Create a new Issue object.

        This endpoint allows authenticated users to create a new issue by providing:
        - status: ID of the issue status (required)
        - category: ID of the issue category (required)
        - issue_type: ID of the issue type (required)
        - administrative_region: ID of the administrative region (required)

        Authentication is required via Token Authentication.
        Include the token in the Authorization header: "Token <your_token>"

        The intake_date will be automatically set to the current timestamp.

        Returns the created issue with all related object details.
        """,
        operation_summary="Create a new issue",
        tags=['Issues'],
        security=[{'Token': []}]
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new Issue instance.

        Overrides the default create method to provide custom response format
        and error handling.

        Args:
            request: HTTP request object containing issue data

        Returns:
            Response: JSON response with created issue data or error details
        """
        try:
            # Serialize and validate the incoming data
            serializer = self.get_serializer(data=request.data)

            if serializer.is_valid():
                # Create the issue instance
                issue = serializer.save()

                # Return detailed representation of the created issue
                detail_serializer = IssueDetailSerializer(issue)

                return Response(
                    {
                        'message': _('Issue created successfully.'),
                        'data': detail_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                # Return validation errors
                return Response(
                    {
                        'message': _('Validation failed.'),
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            # Handle unexpected errors
            return Response(
                {
                    'message': _('An error occurred while creating the issue.'),
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
