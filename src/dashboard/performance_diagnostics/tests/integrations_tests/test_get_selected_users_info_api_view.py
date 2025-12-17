from django.urls import reverse

from authentication.factories import (
    FacilitatorFactory,
    GovernmentWorkerFactory,
    UserFactory,
)
from grm.tests.base import DashboardTestCase


class GetSelectedUsersInfoAPIViewTest(DashboardTestCase):
    """Tests for GetSelectedUsersInfoAPIView (AJAX endpoint to get user info for modal)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:performance_diagnostics:api_get_selected_users")

        # Create test users with different contact info scenarios
        self.user_with_both = UserFactory(first_name="John", last_name="Doe")
        GovernmentWorkerFactory(user=self.user_with_both, administrative_region=self.root_region)

        self.user_email_only = UserFactory(phone_number="")
        FacilitatorFactory(user=self.user_email_only, administrative_region=self.root_region)

        self.user_no_contact = UserFactory(email="", phone_number="", first_name="Alice", last_name="Williams")
        FacilitatorFactory(user=self.user_no_contact, administrative_region=self.root_region)

    def test_get_selected_users_info_success(self):
        """API should return user information for selected users."""
        data = {'user_ids': [self.user_with_both.id, self.user_email_only.id]}

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()

        assert response_data['success'] is True
        assert 'users' in response_data
        assert len(response_data['users']) == 2

        # Verify user data structure
        user_info = response_data['users'][0]
        assert 'id' in user_info
        assert 'name' in user_info
        assert 'email' in user_info
        assert 'phone' in user_info
        assert 'has_email' in user_info
        assert 'has_phone' in user_info

    def test_get_users_with_email_contact(self):
        """API should correctly identify users with email addresses."""
        data = {'user_ids': [self.user_with_both.id, self.user_email_only.id]}

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        response_data = resp.json()

        users = response_data['users']

        # Both users should have email
        for user in users:
            assert user['has_email'] is True
            assert user['email'] != 'No email'

    def test_get_users_with_phone_contact(self):
        """API should correctly identify users with phone numbers."""
        data = {'user_ids': [self.user_with_both.id]}

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        response_data = resp.json()

        users = response_data['users']

        # Both users should have phone
        for user in users:
            assert user['has_phone'] is True
            assert user['phone'] != 'No phone'

    def test_get_users_without_contact_info(self):
        """API should handle users without any contact information."""
        data = {'user_ids': [self.user_no_contact.id]}

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        response_data = resp.json()

        user = response_data['users'][0]
        assert user['has_email'] is False
        assert user['has_phone'] is False
        assert 'No email' in user['email']
        assert 'No phone' in user['phone']

    def test_get_users_ordered_by_name(self):
        """API should return users ordered by first name, last name."""
        data = {
            'user_ids': [
                self.user_no_contact.id,  # Alice Williams
                self.user_with_both.id,  # John Doe
            ]
        }

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        response_data = resp.json()

        users = response_data['users']
        names = [u['name'] for u in users]

        # Should be ordered: Alice, Bob, John
        assert names[0] == "Alice Williams"
        assert names[1] == "John Doe"

    def test_empty_user_ids_returns_error(self):
        """API should return error when no user IDs provided."""
        data = {'user_ids': []}

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert response_data['success'] is False
        assert 'error' in response_data

    def test_missing_user_ids_parameter(self):
        """API should return error when user_ids parameter is missing."""
        resp = self.get(self.url, data={}, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert response_data['success'] is False

    def test_non_existent_user_ids(self):
        """API should handle non-existent user IDs gracefully."""
        data = {'user_ids': [99999, 88888]}  # IDs that don't exist

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()
        assert response_data['success'] is True
        assert len(response_data['users']) == 0

    def test_exclude_not_worker_user_ids(self):
        """API should handle not worker user IDs gracefully."""
        data = {'user_ids': [self.manager.id, self.normal_user.id]}  # IDs that don't exist

        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()
        assert response_data['success'] is True
        assert len(response_data['users']) == 0

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager should be forbidden from accessing the endpoint."""
        data = {'user_ids': [self.user_with_both.id]}

        resp = self.get(self.url, data=data, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404."""
        data = {'user_ids': [self.user_with_both.id]}

        resp = self.get(self.url, data=data, user=self.manager)
        assert resp.status_code == 404

    def test_get_forbidden_for_unauthenticated(self):
        """
        Requests without authentication should be rejected.
        The mixin used returns 404 for unauthenticated AJAX calls.
        """
        data = {'user_ids': [self.user_with_both.id]}

        resp = self.get(self.url, data=data, authorized=False, ajax=True)
        assert resp.status_code == 404
