from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from issues.models import Issue, IssueStatus
from issues.serializers import (
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueStatusSerializer,
)


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
                            "administrative_region": ["This field is required."],
                        },
                    }
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(
                description="Internal Server Error",
                examples={
                    "application/json": {
                        "message": "An error occurred while creating the issue.",
                        "error": "Error details",
                    }
                },
            ),
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
        security=[{'Token': []}],
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
                    {'message': _('Issue created successfully.'), 'data': detail_serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            else:
                # Return validation errors
                return Response(
                    {'message': _('Validation failed.'), 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            # Handle unexpected errors
            return Response(
                {'message': _('An error occurred while creating the issue.'), 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueStatusPagination(PageNumberPagination):
    """
    Custom pagination class for IssueStatus list.

    Provides page-based pagination with customizable page size.
    Default page size is 20 items per page, with a maximum of 100.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'


class IssueStatusListAPIView(ListAPIView):
    """
    API View for listing IssueStatus objects with pagination.

    This view provides a paginated read-only list of all available issue statuses.
    It requires Token authentication and returns paginated results.

    Attributes:
        queryset: IssueStatus queryset ordered by name
        serializer_class: Serializer used for response formatting
        authentication_classes: List of authentication classes (TokenAuthentication)
        permission_classes: List of permission classes (IsAuthenticated)
        pagination_class: Pagination class for paginated responses
    """

    queryset = IssueStatus.objects.all().order_by('name')
    serializer_class = IssueStatusSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = IssueStatusPagination

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of results per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of Issue Statuses",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Total number of items'),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description='URL to next page', nullable=True),
                        'previous': openapi.Schema(
                            type=openapi.TYPE_STRING, description='URL to previous page', nullable=True
                        ),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Status ID'),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING, description='Status name'),
                                    'final_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is final status'
                                    ),
                                    'initial_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is initial status'
                                    ),
                                    'rejected_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is rejected status'
                                    ),
                                    'open_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is open status'
                                    ),
                                },
                            ),
                        ),
                    },
                ),
                examples={
                    "application/json": {
                        "count": 25,
                        "next": "http://localhost:8000/api/issue-statuses/?page=3",
                        "previous": "http://localhost:8000/api/issue-statuses/?page=1",
                        "results": [
                            {
                                "id": 1,
                                "name": "Créé",
                                "final_status": False,
                                "initial_status": True,
                                "rejected_status": False,
                                "open_status": False,
                            },
                            {
                                "id": 2,
                                "name": "Ouverte",
                                "final_status": False,
                                "initial_status": False,
                                "rejected_status": False,
                                "open_status": True,
                            },
                        ],
                    }
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
        },
        operation_description="""
        Retrieve a paginated list of all available Issue Status objects.

        This endpoint returns issue statuses in the system, ordered alphabetically by name.
        Each status includes information about whether it's:
        - A final status (issue cannot progress further)
        - An initial status (new issues start with this status)
        - A rejected status (issue was rejected)
        - An open status (issue is still active/open)

        Authentication is required via Token Authentication.
        Include the token in the Authorization header: "Token <your_token>"

        **Pagination Parameters:**
        - `page`: Page number (default: 1)
        - `page_size`: Number of items per page (default: 20, max: 100)

        **Response Format:**
        - `count`: Total number of items
        - `next`: URL to the next page (null if no next page)
        - `previous`: URL to the previous page (null if no previous page)
        - `results`: Array of status objects for current page
        """,
        operation_summary="List all issue statuses (paginated)",
        tags=['Issue Statuses'],
        security=[{'Token': []}],
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueStatus objects.

        Returns a paginated list of all issue statuses available in the system.
        The list is ordered alphabetically by status name.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issue statuses
        """
        return super().get(request, *args, **kwargs)
