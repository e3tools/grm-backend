from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.serializers import UserBasicSerializer
from dashboard.grm.constants import (
    ALERT_CHOICE,
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    EMAIL_CHOICE,
    RATING_ERROR_MESSAGE,
)
from grm.utils import email_is_valid
from issues.models import (
    AdministrativeRegion,
    Citizen,
    CitizenAgeGroup,
    CitizenGroup,
    Comment,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueType,
    SubProjectGroup,
)


class AdministrativeRegionBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for AdministrativeRegion objects.
    Provides read-only representation of administrative region information.

    Displays the administrative region with custom field names as required.
    """

    administrative_id = serializers.CharField(source='id', read_only=True)
    name = serializers.CharField(read_only=True)

    class Meta:
        model = AdministrativeRegion
        fields = ['administrative_id', 'name']
        read_only_fields = ['administrative_id', 'name']


class IssueCategoryBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for IssueCategory objects.
    """

    class Meta:
        model = IssueCategory
        fields = ['id', 'name']


class SubProjectGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = SubProjectGroup
        fields = ['id', 'name']


class IssueTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueType
        fields = ['id', 'name']


class CitizenAgeGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitizenAgeGroup
        fields = ['id', 'name']


class CitizenGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitizenGroup
        fields = ['id', 'name', 'type']


class IssueStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueStatus
        fields = ['id', 'name', 'final_status', 'initial_status', 'rejected_status', 'open_status']


class IssueSerializer(serializers.ModelSerializer):
    """
    Serializer for the Issue model.

    This serializer provides a complete representation of the issue with nested
    user information for assignee and reporter fields, and properly formatted
    datetime fields.

    Read-only fields:
        - id: Primary key, automatically generated
        - intake_date: Automatically set on creation, formatted as ISO string
        - assignee: Nested User object
        - reporter: Nested User object
        - status: Nested IssueStatus object
    """

    intake_date = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    reporter = UserBasicSerializer(read_only=True)
    administrative_region = AdministrativeRegionBasicSerializer(read_only=True)
    status = IssueStatusSerializer(read_only=True)
    category = IssueCategoryBasicSerializer(read_only=True)
    issue_type = IssueTypeSerializer(
        read_only=True,
    )

    class Meta:
        model = Issue
        fields = [
            'id',
            'tracking_code',
            'intake_date',
            'administrative_region',
            'reporter',
            'assignee',
            'status',
            'category',
            'issue_type',
        ]
        read_only_fields = ['id', 'intake_date', 'reporter', 'assignee', 'administrative_region']


class DepartmentAdministrativeLevelSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueDepartmentAdministrativeLevel model.

    This serializer extracts and formats the department and administrative level
    information for use in IssueCategory serialization.
    """

    name = serializers.CharField(source='department.name', read_only=True)
    id = serializers.IntegerField(source='department.id', read_only=True)
    administrative_level = serializers.CharField(source='administrative_level.name', read_only=True)

    class Meta:
        model = IssueDepartmentAdministrativeLevel
        fields = ['name', 'id', 'administrative_level']


class IssueCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for IssueCategory model with custom department serialization.

    This serializer provides detailed information about issue categories including
    their assigned departments with administrative levels, and adds convenience
    fields 'label' and 'value' for frontend usage.
    """

    # Custom serialization for department fields
    assigned_department = DepartmentAdministrativeLevelSerializer(read_only=True)
    assigned_appeal_department = DepartmentAdministrativeLevelSerializer(read_only=True)
    assigned_escalation_department = DepartmentAdministrativeLevelSerializer(read_only=True)

    # Additional convenience fields
    label = serializers.CharField(source='name', read_only=True)
    value = serializers.IntegerField(source='id', read_only=True)
    parent_id = serializers.IntegerField(source='parent.id', read_only=True, allow_null=True)

    class Meta:
        model = IssueCategory
        fields = [
            'id',
            'name',
            'abbreviation',
            'assigned_department',
            'assigned_appeal_department',
            'assigned_escalation_department',
            'parent_id',
            'confidentiality_level',
            'redirection_protocol',
            'label',
            'value',
        ]
        read_only_fields = ['id']


class AdministrativeRegionSerializer(serializers.ModelSerializer):
    """
    Serializer for AdministrativeRegion model.
    """

    class Meta:
        model = AdministrativeRegion
        fields = ['id', 'name', 'administrative_level', 'parent']


class CitizenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Citizen
        fields = '__all__'


class IssueDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed Issue representation.
    Includes nested serializers for related objects.
    """

    status = IssueStatusSerializer(read_only=True)
    category = IssueCategorySerializer(read_only=True)
    issue_type = IssueTypeSerializer(read_only=True)
    administrative_region = AdministrativeRegionSerializer(read_only=True)

    class Meta:
        model = Issue
        fields = ['id', 'intake_date', 'status', 'category', 'issue_type', 'administrative_region']


class IssueCreateSerializer(serializers.ModelSerializer):
    category = serializers.IntegerField(required=True)
    citizen = CitizenSerializer(required=False)
    contact_medium = serializers.CharField(required=True)
    contact_information = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=True)
    intake_date = serializers.DateTimeField(required=True)
    issue_type = serializers.CharField(required=True)
    issue_sub_type = serializers.CharField(required=True)
    ongoing_issue = serializers.BooleanField(required=False, default=False)
    tracking_code = serializers.CharField(required=True)
    administrative_region = serializers.PrimaryKeyRelatedField(
        queryset=AdministrativeRegion.objects.all(), required=True
    )

    class Meta:
        model = Issue
        fields = [
            'description',
            'status',
            'category',
            'issue_type',
            'administrative_region',
            'reporter',
            'assignee',
            'citizen',
            'component',
            'sub_component',
            'contact_medium',
            'contact_method',
            'contact_information',
            'ongoing_issue',
            'tracking_code',
            'intake_date',
            'issue_sub_type',
            'location_description',
        ]

    def create(self, validated_data):
        citizen_data = validated_data.pop('citizen')
        citizen = Citizen(
            name=citizen_data['name'],
            age_group=citizen_data['age_group'],
            type=citizen_data['type'],
            group=citizen_data['group'],
            group_2=citizen_data['group_2'],
        )
        citizen.save()
        category_data = validated_data.pop('category')
        issue_type_data = validated_data.pop('issue_type')
        issue_sub_type_data = validated_data.pop('issue_sub_type')

        issue = Issue(
            citizen_id=citizen.id,
            category_id=category_data,
            issue_type_id=issue_type_data,
            issue_sub_type_id=issue_sub_type_data,
            **validated_data
        )
        issue.save()
        return issue

    def validate(self, data):
        """
        Performs object-level validation for cross-field dependencies.
        """
        contact_medium = data.get('contact_medium')
        contact_method = data.get('contact_method')
        contact_information = data.get('contact_information')

        if contact_medium == ALERT_CHOICE and not contact_method:
            raise serializers.ValidationError({"contact_method": CONTACT_MEDIUM_ERROR_MESSAGE})

        elif contact_method == EMAIL_CHOICE and not email_is_valid(contact_information):
            raise serializers.ValidationError({"contact_information": CONTACT_INFO_EMAIL_ERROR_MESSAGE})

        elif contact_method != EMAIL_CHOICE and email_is_valid(contact_information):
            raise serializers.ValidationError({"contact_information": CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE})
        return data


class IssueUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating specific fields of an Issue.

    Only allows updating the fields that are permitted for modification:
    escalate_flag, reject_flag, rating, escalation_reason, status, research_result
    """

    class Meta:
        model = Issue
        fields = ['escalate_flag', 'reject_flag', 'rating', 'escalation_reason', 'status', 'research_result']

    def validate_rating(self, value):
        """Validate rating is between 1 and 5 if provided."""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError(RATING_ERROR_MESSAGE)
        return value


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer for Comment objects.
    Provides read-only representation of user information.
    """

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'comment', 'user', 'issue', 'due_date']


class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Comment objects.

    This serializer is used specifically for comment creation and only
    includes the comment text field. The issue and user are set automatically
    in the view.
    """

    comment = serializers.CharField(
        required=True, allow_blank=False, max_length=1000, help_text="The comment text content"
    )

    class Meta:
        model = Comment
        fields = ['comment']

    def validate_comment(self, value):
        """
        Validate the comment text.

        Args:
            value: The comment text to validate

        Returns:
            str: The validated comment text

        Raises:
            ValidationError: If the comment is empty or only whitespace
        """
        if not value or not value.strip():
            raise serializers.ValidationError(_("Comment cannot be empty."))

        return value.strip()


class IssueAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the IssueAttachment model, following the project's conventions.

    This serializer provides a representation of the attachment, including a read-only
    'url' field derived from the file field.

    Read-only fields:
        - id: Primary key
        - url: The URL of the uploaded file
        - uploaded_by: Nested User object (assuming a UserBasicSerializer is available)
        - created_date: Datetime field, automatically set on creation
    """

    issue = IssueSerializer(read_only=True)
    url = serializers.CharField(source='file.url', read_only=True)
    uploaded_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = IssueAttachment
        fields = [
            'id',
            'url',
            'issue',
            'file',
            'uploaded_by',
            'created_date',
        ]
        read_only_fields = ['id', 'url', 'uploaded_by', 'created_date']


class IssueAttachmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating IssueAttachment objects.

    This serializer is used specifically for handling file uploads. The 'uploaded_by'
    field is not included here as it will be set automatically by the view.
    """

    class Meta:
        model = IssueAttachment
        fields = ['file']
