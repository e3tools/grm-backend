from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueType,
)


class IssueStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueStatus model.
    Provides read-only representation of issue status information.
    """

    class Meta:
        model = IssueStatus
        fields = ['id', 'name', 'final_status', 'initial_status', 'rejected_status', 'open_status']


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

    class Meta:
        model = IssueCategory
        fields = [
            'id',
            'name',
            'abbreviation',
            'assigned_department',
            'assigned_appeal_department',
            'assigned_escalation_department',
            'confidentiality_level',
            'redirection_protocol',
            'label',
            'value',
        ]
        read_only_fields = ['id']


class IssueTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueType model.
    Provides read-only representation of issue type information.
    """

    class Meta:
        model = IssueType
        fields = ['id', 'name']


class AdministrativeRegionSerializer(serializers.ModelSerializer):
    """
    Serializer for AdministrativeRegion model.
    Provides read-only representation of administrative region information.
    """

    class Meta:
        model = AdministrativeRegion
        fields = ['id', 'name', 'administrative_level', 'parent']


class IssueCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Issue objects.
    Validates required fields and foreign key relationships.
    """

    class Meta:
        model = Issue
        fields = ['status', 'category', 'issue_type', 'administrative_region']

    def validate_status(self, value):
        """
        Validate that the provided status exists and is active.
        """
        if not value:
            raise serializers.ValidationError(_("Status is required."))
        return value

    def validate_category(self, value):
        """
        Validate that the provided category exists.
        """
        if not value:
            raise serializers.ValidationError(_("Category is required."))
        return value

    def validate_issue_type(self, value):
        """
        Validate that the provided issue type exists.
        """
        if not value:
            raise serializers.ValidationError(_("Issue type is required."))
        return value

    def validate_administrative_region(self, value):
        """
        Validate that the provided administrative region exists.
        """
        if not value:
            raise serializers.ValidationError(_("Administrative region is required."))
        return value


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
