"""
Base OpenAI client for AI-powered financial analysis.
Handles API communication, error handling, and rate limiting.
"""
import logging
import json
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from decimal import Decimal

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    Wrapper around OpenAI API for financial analysis.
    Handles authentication, error handling, and response caching.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')  # Cost-effective model
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.7)
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 1000)

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not configured. AI features will be disabled.")

        # Initialize OpenAI client (lazy loading)
        self._client = None

    @property
    def client(self):
        """Lazy load OpenAI client to avoid import errors if not configured."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
        return self._client

    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured."""
        return self.api_key is not None

    def generate_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        use_cache: bool = True,
        cache_timeout: int = 3600,
        **kwargs
    ) -> Optional[str]:
        """
        Generate a completion from OpenAI with optional caching.

        Args:
            prompt: The user prompt to send to OpenAI
            system_message: Optional system message to set context
            use_cache: Whether to use Django cache for responses
            cache_timeout: Cache timeout in seconds (default 1 hour)
            **kwargs: Additional parameters to pass to OpenAI API

        Returns:
            Generated text response or None if error
        """
        if not self.is_configured():
            logger.error("OpenAI not configured. Cannot generate completion.")
            return None

        # Generate cache key from prompt
        if use_cache:
            cache_key = f"openai_response_{hash(prompt + str(system_message))}"
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info("Using cached OpenAI response")
                return cached_response

        try:
            # Build messages
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            # Merge kwargs with defaults
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                **kwargs
            }

            # Call OpenAI API
            logger.info(f"Calling OpenAI API with model: {self.model}")
            response = self.client.chat.completions.create(**api_params)

            # Extract response text
            response_text = response.choices[0].message.content

            # Cache the response
            if use_cache and response_text:
                cache.set(cache_key, response_text, cache_timeout)

            logger.info(f"OpenAI API call successful. Tokens used: {response.usage.total_tokens}")
            return response_text

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}", exc_info=True)
            return None

    def generate_structured_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a structured JSON response from OpenAI.

        Args:
            prompt: The user prompt
            system_message: Optional system message
            response_format: JSON schema for structured output
            **kwargs: Additional API parameters

        Returns:
            Parsed JSON response or None if error
        """
        if response_format:
            kwargs['response_format'] = response_format

        response_text = self.generate_completion(
            prompt=prompt,
            system_message=system_message,
            use_cache=False,  # Don't cache structured responses
            **kwargs
        )

        if not response_text:
            return None

        # Try to parse JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")
            return None

    def clear_cache(self):
        """Clear all cached OpenAI responses."""
        # This would require a more sophisticated cache key pattern
        # For now, just log
        logger.info("Cache clearing requested (not implemented)")


class AIGRMDiagnosticsAnalyzer:
    """
    AI-powered analysis service for Grievance Redress Mechanism (GRM) performance diagnostics.
    Analyzes workflow bottlenecks, regional performance, and user engagement metrics.
    """

    # Cache timeout for AI insights (15 minutes)
    CACHE_TIMEOUT = 900

    def __init__(self):
        """Initialize the AI GRM Diagnostics Analyzer."""
        self.client = OpenAIClient()

    def is_available(self) -> bool:
        """Check if AI analysis is available (API key configured)."""
        return self.client.is_configured()

    # =====================================================
    # STATUS BOTTLENECKS ANALYSIS
    # =====================================================

    def analyze_status_bottlenecks(
        self,
        bottleneck_data: list,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Analyze status bottleneck data and provide insights on workflow efficiency.

        Args:
            bottleneck_data: List of dicts with keys:
                - status_name: Name of the issue status
                - issues_count: Number of issues in this status
                - avg_days: Average days issues spend in this status
                - performance: 'good', 'at_risk', 'critical', or 'n/a'
                - is_terminal: Whether this is a final/rejected status
            filters: Applied filters (period, region, category)

        Returns:
            Markdown-formatted analysis or None if error
        """
        prompt = self._build_status_bottlenecks_prompt(bottleneck_data, filters)
        system_message = self._get_system_message("status_bottlenecks")

        return self.client.generate_completion(
            prompt=prompt,
            system_message=system_message,
            use_cache=True,
            cache_timeout=self.CACHE_TIMEOUT
        )

    def _build_status_bottlenecks_prompt(
        self,
        data: list,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Build the prompt for status bottleneck analysis."""
        filters_text = self._format_filters(filters)

        # Format the status data into a readable table
        status_lines = []
        critical_statuses = []
        at_risk_statuses = []
        total_issues_in_workflow = 0

        for row in data:
            status_name = row.get('status_name', 'Unknown')
            issues_count = row.get('issues_count', 'N/A')
            avg_days = row.get('avg_days', 'N/A')
            performance = row.get('performance', 'n/a')
            is_terminal = row.get('is_terminal', False)

            if isinstance(issues_count, (int, float)):
                total_issues_in_workflow += issues_count

            # Track problematic statuses
            if performance == 'critical' and not is_terminal:
                critical_statuses.append({
                    'name': status_name,
                    'issues': issues_count,
                    'days': avg_days
                })
            elif performance == 'at_risk' and not is_terminal:
                at_risk_statuses.append({
                    'name': status_name,
                    'issues': issues_count,
                    'days': avg_days
                })

            # Format line
            if is_terminal:
                status_lines.append(f"| {status_name} | {issues_count} | N/A (Terminal) | {performance} |")
            else:
                avg_display = f"{avg_days:.1f} days" if isinstance(avg_days, (int, float)) else avg_days
                status_lines.append(f"| {status_name} | {issues_count} | {avg_display} | {performance} |")

        status_table = "\n".join(status_lines)

        # Build critical issues summary
        critical_summary = ""
        if critical_statuses:
            critical_items = [f"- **{s['name']}**: {s['issues']} issues, avg {s['days']:.1f} days"
                           for s in critical_statuses if isinstance(s['days'], (int, float))]
            critical_summary = f"\n**CRITICAL BOTTLENECKS**:\n" + "\n".join(critical_items)

        if at_risk_statuses:
            at_risk_items = [f"- **{s['name']}**: {s['issues']} issues, avg {s['days']:.1f} days"
                          for s in at_risk_statuses if isinstance(s['days'], (int, float))]
            critical_summary += f"\n\n**AT-RISK STATUSES**:\n" + "\n".join(at_risk_items)

        return f"""
Analyze this GRM (Grievance Redress Mechanism) workflow bottleneck data and provide actionable insights.

{filters_text}

**WORKFLOW STATUS BREAKDOWN**:
| Status | Issues Count | Avg. Time in Status | Performance |
|--------|--------------|---------------------|-------------|
{status_table}

**TOTAL ISSUES IN WORKFLOW**: {total_issues_in_workflow}
{critical_summary}

**CONTEXT**:
- This is a citizen grievance management system for government services
- Issues flow through multiple statuses from intake to resolution
- Lower average time in status indicates better workflow efficiency
- Terminal statuses (Resolved, Rejected) don't have time metrics

**YOUR TASK**:
Provide a concise analysis (150-200 words) covering:

1. **Workflow Health Assessment**
   - Overall workflow efficiency
   - Main bottlenecks identified

2. **Priority Actions**
   - Which status needs immediate attention?
   - What specific steps should be taken?

3. **Recommendations**
   - Process improvements to reduce delays
   - Resource allocation suggestions

Format your response in **markdown**. Be specific about which statuses need attention and why.
"""

    # =====================================================
    # REGION PERFORMANCE ANALYSIS
    # =====================================================

    def analyze_region_performance(
        self,
        region_data: list,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Analyze regional performance data and provide insights.

        Args:
            region_data: List of dicts with keys:
                - region_name: Name of the administrative region
                - open_issues_count: Number of open issues
                - avg_resolution_days: Average days to resolve issues
                - active_workers_count: Number of active workers
                - total_workers: Total workers in region
                - workers_percentage: Percentage of active workers
                - performance_status: 'good', 'at_risk', 'critical'
            filters: Applied filters (period, category)

        Returns:
            Markdown-formatted analysis or None if error
        """
        prompt = self._build_region_performance_prompt(region_data, filters)
        system_message = self._get_system_message("region_performance")

        return self.client.generate_completion(
            prompt=prompt,
            system_message=system_message,
            use_cache=True,
            cache_timeout=self.CACHE_TIMEOUT
        )

    def _build_region_performance_prompt(
        self,
        data: list,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Build the prompt for region performance analysis."""
        filters_text = self._format_filters(filters)

        # Format the region data
        region_lines = []
        critical_regions = []
        best_regions = []
        total_open_issues = 0
        total_active_workers = 0
        total_workers = 0

        for row in data:
            region_name = row.get('region_name', 'Unknown')
            open_issues = row.get('open_issues_count', 0)
            avg_resolution = row.get('avg_resolution_days', 0)
            active_workers = row.get('active_workers_count', 0)
            total_w = row.get('total_workers', 0)
            workers_pct = row.get('workers_percentage', 0)
            performance = row.get('performance_status', 'unknown')

            total_open_issues += open_issues
            total_active_workers += active_workers
            total_workers += total_w

            # Track performance extremes
            if performance == 'critical':
                critical_regions.append({
                    'name': region_name,
                    'issues': open_issues,
                    'resolution': avg_resolution,
                    'workers_pct': workers_pct
                })
            elif performance == 'good':
                best_regions.append({
                    'name': region_name,
                    'issues': open_issues,
                    'resolution': avg_resolution,
                    'workers_pct': workers_pct
                })

            region_lines.append(
                f"| {region_name} | {open_issues} | {avg_resolution:.1f} days | "
                f"{active_workers}/{total_w} ({workers_pct:.0f}%) | {performance} |"
            )

        region_table = "\n".join(region_lines)

        # Build summary sections
        summary = f"""
**AGGREGATE METRICS**:
- Total Open Issues: {total_open_issues}
- Total Active Workers: {total_active_workers} / {total_workers}
- Overall Worker Engagement: {(total_active_workers/total_workers*100) if total_workers > 0 else 0:.0f}%
"""

        if critical_regions:
            critical_items = [
                f"- **{r['name']}**: {r['issues']} open issues, {r['resolution']:.1f} days avg resolution, "
                f"{r['workers_pct']:.0f}% workers active"
                for r in critical_regions[:3]  # Top 3 critical
            ]
            summary += f"\n**REGIONS REQUIRING ATTENTION**:\n" + "\n".join(critical_items)

        if best_regions:
            best_items = [
                f"- **{r['name']}**: {r['issues']} open issues, {r['resolution']:.1f} days avg resolution"
                for r in best_regions[:2]  # Top 2 best
            ]
            summary += f"\n\n**TOP PERFORMING REGIONS**:\n" + "\n".join(best_items)

        return f"""
Analyze this GRM regional performance data and provide actionable insights.

{filters_text}

**PERFORMANCE BY ADMINISTRATIVE REGION**:
| Region | Open Issues | Avg Resolution | Active Workers | Performance |
|--------|-------------|----------------|----------------|-------------|
{region_table}

{summary}

**CONTEXT**:
- This shows grievance handling performance across administrative regions
- Lower open issues and faster resolution times indicate better performance
- Active workers percentage shows staff engagement with the platform
- Critical regions need immediate management attention

**YOUR TASK**:
Provide a concise analysis (150-200 words) covering:

1. **Regional Disparities**
   - Which regions are underperforming and why?
   - What patterns do you observe?

2. **Resource Allocation**
   - Are workers distributed appropriately?
   - Which regions need more support?

3. **Best Practices**
   - What can struggling regions learn from top performers?
   - Specific improvement recommendations

Format your response in **markdown**. Focus on actionable insights for regional managers.
"""

    # =====================================================
    # INACTIVE USERS ANALYSIS
    # =====================================================

    def analyze_inactive_users(
        self,
        users_data: list,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Analyze inactive users data and provide insights on user engagement.

        Args:
            users_data: List of dicts with keys:
                - name: User name
                - role: 'Case Manager' or 'Facilitator'
                - last_activity_days: Days since last activity (None = never)
                - open_issues_count: Number of open issues assigned
                - performance_rating: 'Active', 'Low Activity', 'Inactive'
            filters: Applied filters (role, region, has_open_issues)

        Returns:
            Markdown-formatted analysis or None if error
        """
        prompt = self._build_inactive_users_prompt(users_data, filters)
        system_message = self._get_system_message("inactive_users")

        return self.client.generate_completion(
            prompt=prompt,
            system_message=system_message,
            use_cache=True,
            cache_timeout=self.CACHE_TIMEOUT
        )

    def _build_inactive_users_prompt(
        self,
        data: list,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Build the prompt for inactive users analysis."""
        filters_text = self._format_filters(filters)

        # Analyze the user data
        total_users = len(data)
        case_managers = [u for u in data if u.get('role') == 'Case Manager']
        facilitators = [u for u in data if u.get('role') == 'Facilitator']

        users_with_issues = [u for u in data if u.get('open_issues_count', 0) > 0]
        never_active = [u for u in data if u.get('last_activity_days') is None]

        # Calculate averages
        activity_days = [u.get('last_activity_days') for u in data if u.get('last_activity_days') is not None]
        avg_inactive_days = sum(activity_days) / len(activity_days) if activity_days else 0

        total_open_issues = sum(u.get('open_issues_count', 0) for u in data)

        # Identify most concerning users (inactive with many open issues)
        concerning_users = sorted(
            [u for u in data if u.get('open_issues_count', 0) > 0],
            key=lambda x: x.get('open_issues_count', 0),
            reverse=True
        )[:5]

        concerning_list = ""
        if concerning_users:
            items = []
            for u in concerning_users:
                name = u.get('name', 'Unknown')
                role = u.get('role', 'Unknown')
                open_issues = u.get('open_issues_count', 0)
                last_activity = u.get('last_activity_days')
                activity_text = 'never logged in' if last_activity is None else f'{last_activity} days inactive'
                items.append(f"- **{name}** ({role}): {open_issues} open issues, {activity_text}")
            concerning_list = "\n**USERS REQUIRING IMMEDIATE ATTENTION**:\n" + "\n".join(items)

        return f"""
Analyze this GRM inactive users data and provide insights on staff engagement.

{filters_text}

**INACTIVE USERS SUMMARY**:
- Total Inactive Users: {total_users}
- Case Managers: {len(case_managers)}
- Facilitators: {len(facilitators)}
- Average Days Inactive: {avg_inactive_days:.0f} days
- Users Who Never Logged In: {len(never_active)}

**WORKLOAD IMPACT**:
- Users with Open Issues Assigned: {len(users_with_issues)}
- Total Open Issues Affected: {total_open_issues}
{concerning_list}

**CONTEXT**:
- Case Managers handle citizen grievances directly
- Facilitators support communities and assist with issue reporting
- Inactive users may have unattended citizen grievances
- This represents a backlog risk for the GRM system

**YOUR TASK**:
Provide a concise analysis (150-200 words) covering:

1. **Engagement Assessment**
   - How severe is the inactivity problem?
   - What's the impact on grievance resolution?

2. **Priority Contacts**
   - Which users should be contacted first?
   - What approach would you recommend?

3. **Systemic Recommendations**
   - How to prevent future inactivity?
   - Training or support needs identified

Format your response in **markdown**. Focus on actionable steps for GRM managers.
"""

    # =====================================================
    # HELPER METHODS
    # =====================================================

    def _get_system_message(self, analysis_type: str) -> str:
        """Get appropriate system message based on analysis type."""
        base_message = """You are an expert analyst specializing in Grievance Redress Mechanisms (GRM) \
and public sector performance management. You provide concise, actionable insights to help government \
administrators improve citizen grievance handling. Your recommendations are specific, practical, \
and focused on improving service delivery and citizen satisfaction."""

        specific_contexts = {
            "status_bottlenecks": " Focus on workflow optimization and process bottlenecks. "
                                  "Identify where issues get stuck and recommend process improvements.",
            "region_performance": " Focus on geographic disparities and resource allocation. "
                                  "Identify underperforming regions and recommend targeted interventions.",
            "inactive_users": " Focus on staff engagement and workload management. "
                             "Identify at-risk users and recommend re-engagement strategies."
        }

        return base_message + specific_contexts.get(analysis_type, "")

    def _format_filters(self, filters: Optional[Dict[str, Any]]) -> str:
        """Format filters for display in prompts."""
        if not filters:
            return ""

        filter_parts = []

        if filters.get('period'):
            period_map = {'7d': 'Last 7 days', '30d': 'Last 30 days', '90d': 'Last 90 days'}
            filter_parts.append(f"- Period: {period_map.get(filters['period'], filters['period'])}")

        if filters.get('region_name'):
            filter_parts.append(f"- Region: {filters['region_name']}")

        if filters.get('category_name'):
            filter_parts.append(f"- Category: {filters['category_name']}")

        if filters.get('role_filter'):
            role_map = {'government_worker': 'Case Managers', 'facilitator': 'Facilitators'}
            filter_parts.append(f"- Role: {role_map.get(filters['role_filter'], filters['role_filter'])}")

        if filter_parts:
            return "**FILTERS APPLIED**:\n" + "\n".join(filter_parts) + "\n"

        return ""
