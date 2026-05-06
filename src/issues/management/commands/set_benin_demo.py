"""
Seed a Benin demo (12 départements, 77 communes) only when the SQL database is still empty.

If any application data already exists (users, regions, issues, statuses, or levels),
the command exits without changing anything. No CouchDB, no CLI flags, no prompts.

The demo user is created with ``grm_owner`` and ``grm_manager`` so dashboard login and
mixins match production expectations, and all wizard sections are marked completed so
you are not forced through the customization wizard.

Log in on the dashboard using **email** ``DEMO_EMAIL`` and password ``DEMO_PASSWORD``
(the form label is “Email”, not username).

Edit the module-level constants for demo credentials, facilitator count, demo issue count (default **75**),
attachment probability, or ``CASE_MANAGER_PASSWORD``. Set ``NUM_DEMO_ISSUES`` to ``0`` to skip
facilitators, org structure (workers/heads), issues, metrics aggregation, and Pinecone upload.
"""

import logging
import random
from datetime import timedelta
from typing import List, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authentication.models import Facilitator, GovernmentWorker, User
from grm.constants import ANONYMOUS_CHOICE, FEWER_ISSUES_CHOICE, LOW_CHOICE
from issues.management.data.benin_communes import (
    COMMUNES,
    DEPT_CODE_TO_NAME,
    commune_coordinates,
)
from issues.models import (
    AdministrativeLevel,
    AdministrativeRegion,
    Citizen,
    CitizenAgeGroup,
    CitizenGroup,
    Component,
    SubComponent,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueStatusChange,
    IssueSubType,
    IssueType,
)
from wizard.constants import CITIZEN_GROUP2_CHOICE, CITIZEN_GROUP_CHOICE, COMPLETED_CHOICE
from wizard.models import WizardSection

logger = logging.getLogger(__name__)

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@grm-benin.local"
DEMO_PASSWORD = "demo"
FACILITATOR_PASSWORD = DEMO_PASSWORD
CASE_MANAGER_PASSWORD = DEMO_PASSWORD
NUM_FACILITATORS = 5
NUM_DEMO_ISSUES = 75
ATTACHMENT_PROBABILITY = 0.45
MIN_ATTACHMENTS_PER_ISSUE = 0
# Minimal valid 1×1 PNG (for IssueAttachment demo files)
DEMO_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500001d0d75280000000049454e44ae426082"
)
# Days-ago values cycled for User.last_activity (dashboard uses whole days + performance bands).
DEMO_LAST_ACTIVITY_DAYS_CYCLE = (
    0,
    1,
    2,
    4,
    6,
    3,
    5,
    10,
    14,
    7,
    12,
    8,
    11,
    9,
    15,
    18,
    13,
    16,
    19,
    17,
    0,
    2,
    5,
    1,
    4,
)


class Command(BaseCommand):
    help = (
        "Load Benin demo data only when the database has no users, administrative regions, "
        "issues, statuses, or administrative levels yet. Otherwise does nothing."
    )

    def handle(self, *args, **options):
        if self._database_has_app_data():
            self.stdout.write(
                self.style.WARNING(
                    "Database already contains data (users, regions, issues, statuses, or levels); "
                    "skipping Benin demo setup."
                )
            )
            return

        with transaction.atomic():
            self._create_benin_administrative_tree()

        call_command("reorder_administrative_levels")
        call_command("update_region_hierarchical_names")

        with transaction.atomic():
            self._create_reference_data()

        self._create_superuser()
        self._complete_wizard_for_demo()

        if NUM_DEMO_ISSUES > 0:
            self._seed_conference_demo()

        self.stdout.write(self.style.SUCCESS("Benin demo data loaded (empty database)."))

    def _patch_user_last_activity_demo(self, user: User) -> None:
        """Varied last_activity so performance / user tables do not show 'Never' for demo users."""
        idx = getattr(self, "_demo_last_activity_i", 0)
        self._demo_last_activity_i = idx + 1
        days = DEMO_LAST_ACTIVITY_DAYS_CYCLE[idx % len(DEMO_LAST_ACTIVITY_DAYS_CYCLE)]
        when = timezone.now() - timedelta(
            days=int(days),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        User.objects.filter(pk=user.pk).update(last_activity=when)

    def _create_demo_staff_user(
        self,
        username: str,
        email: str,
        phone: str,
        first_name: str,
        last_name: str,
        password: str,
    ) -> User:
        user = User(
            username=username,
            email=email,
            phone_number=phone,
            first_name=first_name,
            last_name=last_name,
            is_staff=False,
            is_superuser=False,
            is_active=True,
            grm_owner=False,
            grm_manager=False,
        )
        user.set_password(password)
        user.save()
        self._patch_user_last_activity_demo(user)
        return user

    def _seed_org_structure(self, facilitator_rows: List[Tuple[User, AdministrativeRegion]]) -> None:
        """
        Department heads, GovernmentWorkers at commune + department + country tiers
        so assignee, escalation/de-escalation, and appeal reassignment all have targets.
        """
        d1 = IssueDepartment.objects.get(name="Comité communautaire de gestion des plaintes")
        d2 = IssueDepartment.objects.get(name="Comité local de gestion des plaintes")
        d3 = IssueDepartment.objects.get(name="Secrétariat technique à la coordination")

        root = AdministrativeRegion.objects.filter(parent__isnull=True).first()
        if not root:
            self.stdout.write(self.style.ERROR("No country root region; skipping org structure."))
            return

        head_d1 = self._create_demo_staff_user(
            "head_d1_demo",
            "head-d1-village@grm-benin.local",
            "+22962000001",
            "Chef",
            "Comité village",
            CASE_MANAGER_PASSWORD,
        )
        head_d2 = self._create_demo_staff_user(
            "head_d2_demo",
            "head-d2-local@grm-benin.local",
            "+22962000002",
            "Chef",
            "Comité local",
            CASE_MANAGER_PASSWORD,
        )
        head_d3 = self._create_demo_staff_user(
            "head_d3_demo",
            "head-d3-appeal@grm-benin.local",
            "+22962000003",
            "Chef",
            "Secrétariat appel",
            CASE_MANAGER_PASSWORD,
        )
        d1.head = head_d1
        d2.head = head_d2
        d3.head = head_d3
        d1.save(update_fields=["head"])
        d2.save(update_fields=["head"])
        d3.save(update_fields=["head"])

        demo_communes = {r[1].id: r[1] for r in facilitator_rows}
        parent_regions = {c.parent for c in demo_communes.values() if c.parent_id}
        first_commune = facilitator_rows[0][1]
        first_parent = first_commune.parent
        if not first_parent:
            self.stdout.write(self.style.ERROR("Facilitator commune has no parent department; skipping org structure."))
            return

        GovernmentWorker.objects.create(user=head_d1, department=d1, administrative_region=first_parent)
        GovernmentWorker.objects.create(user=head_d2, department=d2, administrative_region=first_parent)
        GovernmentWorker.objects.create(user=head_d3, department=d3, administrative_region=root)

        for commune in sorted(demo_communes.values(), key=lambda r: r.id):
            u = self._create_demo_staff_user(
                f"cm_d1_c{commune.id}",
                f"case-mgr-d1-c{commune.id}@grm-benin.local",
                f"+2298101{commune.id % 10000:04d}",
                "Gestionnaire",
                f"Plaintes {commune.name[:20]}",
                CASE_MANAGER_PASSWORD,
            )
            GovernmentWorker.objects.create(user=u, department=d1, administrative_region=commune)

        u_hot = self._create_demo_staff_user(
            "cm_d1_hot_b",
            f"case-mgr-d1-c{first_commune.id}-b@grm-benin.local",
            f"+2298103{first_commune.id % 10000:04d}",
            "Gestionnaire",
            "Adjoint démo",
            CASE_MANAGER_PASSWORD,
        )
        GovernmentWorker.objects.create(user=u_hot, department=d1, administrative_region=first_commune)

        for parent in sorted(parent_regions, key=lambda r: r.id):
            if GovernmentWorker.objects.filter(department=d1, administrative_region=parent).exists():
                continue
            u = self._create_demo_staff_user(
                f"cm_d1_dept_{parent.id}",
                f"case-mgr-d1-dept-{parent.id}@grm-benin.local",
                f"+2298102{parent.id % 10000:04d}",
                "Coordinateur",
                f"Département {parent.name[:18]}",
                CASE_MANAGER_PASSWORD,
            )
            GovernmentWorker.objects.create(user=u, department=d1, administrative_region=parent)

        if first_parent and not GovernmentWorker.objects.filter(department=d2, administrative_region=first_parent).exists():
            u_d2 = self._create_demo_staff_user(
                "cm_d2_demo",
                "case-mgr-d2@grm-benin.local",
                f"+2298104{first_parent.id % 10000:04d}",
                "Agent",
                "Comité local démo",
                CASE_MANAGER_PASSWORD,
            )
            GovernmentWorker.objects.create(user=u_d2, department=d2, administrative_region=first_parent)

        self.stdout.write(
            self.style.NOTICE(
                "Org structure: department heads (d1/d2/d3), commune + department d1 workers, "
                "dual case manager on first demo commune, d2 line worker, d3 appeal worker at country."
            )
        )

    def _database_has_app_data(self) -> bool:
        """True if anything suggests this is no longer a brand-new app database."""
        if User.objects.exists():
            return True
        if AdministrativeRegion.objects.exists():
            return True
        if AdministrativeLevel.objects.exists():
            return True
        if Issue.objects.exists():
            return True
        if IssueStatus.objects.exists():
            return True
        return False

    def _create_benin_administrative_tree(self):
        lvl_country = AdministrativeLevel.objects.create(name="country")
        lvl_commune = AdministrativeLevel.objects.create(name="commune")
        lvl_village = AdministrativeLevel.objects.create(name="village")

        root = AdministrativeRegion(
            name="Bénin",
            administrative_level=lvl_country,
            parent=None,
            latitude=9.3077,
            longitude=2.3158,
        )
        root.save()

        dept_regions: dict[str, AdministrativeRegion] = {}
        for code, label in DEPT_CODE_TO_NAME.items():
            lat, lon = commune_coordinates(code, f"dept-{code}")
            reg = AdministrativeRegion(
                name=label,
                administrative_level=lvl_commune,
                parent=root,
                latitude=lat,
                longitude=lon,
            )
            reg.save()
            dept_regions[code] = reg

        for dept_code, commune_name in COMMUNES:
            parent = dept_regions[dept_code]
            lat, lon = commune_coordinates(dept_code, commune_name)
            commune = AdministrativeRegion(
                name=commune_name,
                administrative_level=lvl_village,
                parent=parent,
                latitude=lat,
                longitude=lon,
            )
            commune.save()

        self.stdout.write(
            self.style.NOTICE(
                f"Created administrative tree: 1 country, {len(dept_regions)} departments, "
                f"{len(COMMUNES)} communes."
            )
        )

    def _create_reference_data(self):
        IssueStatus.objects.create(
            name="Créé",
            final_status=False,
            initial_status=True,
            rejected_status=False,
            open_status=False,
            threshold_days=5,
            threshold_days_to_escalate=10,
        )
        IssueStatus.objects.create(
            name="Ouverte",
            final_status=False,
            initial_status=False,
            rejected_status=False,
            open_status=True,
            threshold_days=7,
            threshold_days_to_escalate=14,
        )
        IssueStatus.objects.create(
            name="Rejetée",
            final_status=False,
            initial_status=False,
            rejected_status=True,
            open_status=False,
            threshold_days=3,
            threshold_days_to_escalate=None,
        )
        IssueStatus.objects.create(
            name="Terminée",
            final_status=True,
            initial_status=False,
            rejected_status=False,
            open_status=False,
            threshold_days=14,
            threshold_days_to_escalate=None,
        )

        d1 = IssueDepartment.objects.create(name="Comité communautaire de gestion des plaintes")
        d2 = IssueDepartment.objects.create(name="Comité local de gestion des plaintes")
        d3 = IssueDepartment.objects.create(name="Secrétariat technique à la coordination")

        lvl_country = AdministrativeLevel.objects.get(name="country")
        lvl_commune = AdministrativeLevel.objects.get(name="commune")
        lvl_village = AdministrativeLevel.objects.get(name="village")

        ida_village = IssueDepartmentAdministrativeLevel.objects.create(department=d1, administrative_level=lvl_village)
        ida_commune = IssueDepartmentAdministrativeLevel.objects.create(department=d2, administrative_level=lvl_commune)
        ida_country = IssueDepartmentAdministrativeLevel.objects.create(department=d3, administrative_level=lvl_country)

        t_info = IssueType.objects.create(name="Demande d'information et accès")
        t_infra = IssueType.objects.create(name="Plaintes infrastructure et environnement")
        t_recours = IssueType.objects.create(name="Recours, indemnisation et médiation")

        subtype_rows = [
            (t_info, "Informations publiques et calendrier"),
            (t_info, "Accès aux documents de projet"),
            (t_info, "Délais et procédures du mécanisme"),
            (t_infra, "Eau, forages et assainissement"),
            (t_infra, "Routes, travaux et nuisances"),
            (t_recours, "Indemnisation et contreparties"),
            (t_recours, "Médiation et conflits fonciers"),
        ]
        subtypes: List[IssueSubType] = []
        for parent_type, sub_name in subtype_rows:
            subtypes.append(IssueSubType.objects.create(name=sub_name, parent=parent_type))

        category_rows = [
            ("Catégorie démo — Transparence (fictif)", "DEMO1"),
            ("Catégorie démo — Dossiers citoyens (fictif)", "DEMO2"),
            ("Catégorie démo — Délais et voies de recours (fictif)", "DEMO3"),
            ("Catégorie démo — Eau et équipements (fictif)", "DEMO4"),
            ("Catégorie démo — Travaux et environnement (fictif)", "DEMO5"),
            ("Catégorie démo — Indemnisation (fictif)", "DEMO6"),
            ("Catégorie démo — Médiation locale (fictif)", "DEMO7"),
        ]
        for sub, (cat_name, abbrev) in zip(subtypes, category_rows):
            IssueCategory.objects.create(
                name=cat_name,
                abbreviation=abbrev,
                assigned_department=ida_village,
                assigned_escalation_department=ida_commune,
                assigned_appeal_department=ida_country,
                parent=sub,
                confidentiality_level=LOW_CHOICE,
                redirection_protocol=FEWER_ISSUES_CHOICE,
            )

        component_specs = [
            {
                "name": "Infrastructures et développement socio-économique (Investir dans la résilience)",
                "description": (
                    "Investir dans la résilience via le développement mené par les communautés, les infrastructures et l’appui économique."
                ),
                "subs": [
                    (
                        "Développement mené par les communautés (DMC)",
                        "Renforcer l’autonomisation des communautés via une planification ascendante afin de prioriser et gérer les sous-projets.",
                    ),
                    (
                        "Appui aux infrastructures",
                        "Construction d’infrastructures socio-économiques, notamment des écoles, des forages d’eau et des centres communautaires.",
                    ),
                    (
                        "Appui économique",
                        "Financement des groupements d’intérêt économique (GIE) pour stimuler les économies locales et générer des revenus, en particulier pour les femmes et les jeunes.",
                    ),
                ],
            },
            {
                "name": "Renforcement des capacités et cohésion sociale",
                "description": "Renforcer les capacités locales, l’inclusion, le dialogue et les mécanismes de gestion des conflits.",
                "subs": [
                    (
                        "Mécanismes d’inclusion",
                        "Renforcer les capacités des Comités de développement villageois (CDV) et assurer l’inclusion des groupes marginalisés et des réfugiés dans la planification locale.",
                    ),
                    (
                        "Activités de cohésion sociale",
                        "Renforcer les liens sociaux, le dialogue et les mécanismes de gestion des conflits entre communautés hôtes et populations déplacées.",
                    ),
                    (
                        "Mécanismes de gestion des conflits",
                        "Appuyer les mécanismes locaux de prévention et de gestion des conflits entre communautés hôtes et populations déplacées.",
                    ),
                ],
            },
            {
                "name": "Coordination régionale et gestion",
                "description": "Faciliter la coordination régionale et renforcer les institutions pour la résilience transfrontalière.",
                "subs": [
                    (
                        "Collaboration régionale",
                        "Faciliter le dialogue et la coordination dans le nord du Bénin et avec les pays voisins (Côte d’Ivoire, Ghana, Togo).",
                    ),
                    (
                        "Appui institutionnel",
                        "Renforcer les autorités locales (préfectures et communes) et appuyer l’Agence béninoise de gestion intégrée des espaces frontaliers (ABGEF).",
                    ),
                    (
                        "Appui à l’ABGEF (Agence béninoise de gestion intégrée des espaces frontaliers)",
                        "Appui institutionnel à l’ABGEF et à la gestion intégrée des espaces frontaliers.",
                    ),
                ],
            },
        ]

        for spec in component_specs:
            comp = Component.objects.create(name=spec["name"], description=spec["description"])
            for sub_name, sub_desc in spec["subs"]:
                SubComponent.objects.create(name=sub_name, description=sub_desc, parent=comp)

        CitizenAgeGroup.objects.create(name="18–35 ans")
        CitizenAgeGroup.objects.create(name="36–50 ans")
        CitizenAgeGroup.objects.create(name="51 ans et plus")

        CitizenGroup.objects.create(
            name="GRM Démo — Association de producteurs",
            type=CITIZEN_GROUP_CHOICE,
        )
        CitizenGroup.objects.create(
            name="GRM Démo — Comité de veille communautaire",
            type=CITIZEN_GROUP2_CHOICE,
        )

        self.stdout.write(
            self.style.NOTICE(
                "Created issue statuses, departments, 3 issue types, 7 subtypes/categories, components/subcomponents, "
                "age groups, and demo citizen groups."
            )
        )

    def _create_superuser(self):
        user = User(
            username=DEMO_USERNAME,
            email=DEMO_EMAIL,
            phone_number="+22900000001",
            first_name="Démo",
            last_name="GRM",
            is_staff=True,
            is_superuser=True,
            is_active=True,
            grm_owner=True,
            grm_manager=True,
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser {DEMO_USERNAME} created ({DEMO_EMAIL}). "
                f"Log in with that email address and the demo password."
            )
        )

    def _complete_wizard_for_demo(self):
        """Avoid login and middleware blocking on incomplete wizard (WizardSection rows come from migrations)."""
        n = WizardSection.objects.update(status=COMPLETED_CHOICE)
        self.stdout.write(self.style.NOTICE(f"Wizard: marked {n} section(s) as completed for demo access."))

    def _seed_conference_demo(self) -> None:
        """Facilitators, confirmed issues (citizens, attachments, status history), metrics, optional Pinecone."""
        random.seed(42)
        self._demo_last_activity_i = 0
        facilitator_rows = self._create_facilitators()
        if not facilitator_rows:
            self.stdout.write(self.style.ERROR("Could not create facilitators; skipping conference demo issues."))
            return

        self._seed_org_structure(facilitator_rows)

        d1_dept = IssueDepartment.objects.get(name="Comité communautaire de gestion des plaintes")
        communes = list(AdministrativeRegion.objects.filter(administrative_level__name="village"))
        categories = list(IssueCategory.objects.order_by("id"))
        components = list(Component.objects.order_by("id"))
        components_by_name = {c.name: c for c in components}
        # Map the existing 7 demo categories to realistic project components.
        component_name_by_abbrev = {
            "DEMO1": "Renforcement des capacités et cohésion sociale",
            "DEMO2": "Renforcement des capacités et cohésion sociale",
            "DEMO3": "Renforcement des capacités et cohésion sociale",
            "DEMO4": "Infrastructures et développement socio-économique (Investir dans la résilience)",
            "DEMO5": "Infrastructures et développement socio-économique (Investir dans la résilience)",
            "DEMO6": "Coordination régionale et gestion",
            "DEMO7": "Coordination régionale et gestion",
        }
        subcomponents_by_component_id = {}
        if components:
            for sc in SubComponent.objects.filter(parent__in=components).order_by("id"):
                subcomponents_by_component_id.setdefault(sc.parent_id, []).append(sc)
        st_created = IssueStatus.objects.filter(initial_status=True).first()
        st_open = IssueStatus.objects.filter(open_status=True).first()
        st_rejected = IssueStatus.objects.filter(rejected_status=True).first()
        st_done = IssueStatus.objects.filter(final_status=True).first()
        age_groups = list(CitizenAgeGroup.objects.all())
        citizen_groups = list(CitizenGroup.objects.all())
        if (
            not communes
            or len(categories) < 7
            or len(components) < 1
            or not all([st_created, st_open, st_rejected, st_done, age_groups])
            or any(c.parent is None or c.parent.parent is None for c in categories)
        ):
            self.stdout.write(self.style.ERROR("Missing reference rows; skipping conference demo issues."))
            return

        descriptions = [
            "Retard dans la distribution des intrants agricoles ; les bénéficiaires n'ont pas été informés.",
            "Plainte concernant l'accès à l'eau potable : forage en panne depuis plusieurs semaines.",
            "Demande de clarification sur les critères d'éligibilité au mécanisme de réclamation.",
            "Signalement d'un conflit foncier impliquant un projet d'infrastructure ; médiation demandée.",
            "Insatisfaction sur le délai de traitement d'une plainte précédente (suivi).",
            "Information sur les dates d'audience publique et les documents à fournir.",
            "Réclamation relative aux indemnisations : montants perçus différents des engagements annoncés.",
        ]

        group_a = citizen_groups[0] if len(citizen_groups) > 0 else None
        group_b = citizen_groups[1] if len(citizen_groups) > 1 else None

        created_issues: List[Issue] = []
        now = timezone.now()
        status_cycle = [st_open, st_done, st_rejected, st_open, st_created, st_open]
        appeal_indices = {i for i in (7, 22, 37, 52, 67) if i < NUM_DEMO_ISSUES}
        escalation_indices = set()
        if NUM_DEMO_ISSUES >= 6:
            for j in range(NUM_DEMO_ISSUES - 1, -1, -1):
                if j not in appeal_indices:
                    escalation_indices.add(j)
                if len(escalation_indices) >= 3:
                    break

        for i in range(NUM_DEMO_ISSUES):
            fac_user, region = facilitator_rows[i % len(facilitator_rows)]
            intake = now - timedelta(days=random.randint(5, 150))

            if i in appeal_indices:
                status = st_open
                resolution_date = None
            elif i in escalation_indices:
                status = st_open
                resolution_date = None
            else:
                status = status_cycle[i % len(status_cycle)]
                resolution_date = None
                if getattr(status, "final_status", False) or getattr(status, "rejected_status", False):
                    resolution_date = intake + timedelta(days=random.randint(3, 25))

            appeal_status = i in appeal_indices
            appeal_reason = (
                "Demande d'appel démo (données fictives) — contestation du traitement initial."
                if appeal_status
                else ""
            )
            escalate_flag = i in escalation_indices
            escalation_reason = (
                "Escalade démo : arbitrage requis au niveau départemental (données fictives)."
                if escalate_flag
                else ""
            )
            escalated_date = (now - timedelta(days=2)) if escalate_flag else None

            citizen = None
            if i % 2 == 0:
                citizen = Citizen.objects.create(
                    name=f"Plaignant·e démo {i + 1}",
                    age_group=random.choice(age_groups),
                    group=group_a if i % 4 == 0 else None,
                    group_2=group_b if i % 6 == 0 else None,
                )

            gw = (
                GovernmentWorker.objects.filter(department=d1_dept, administrative_region=region)
                .order_by("id")
                .first()
            )
            assignee_user = gw.user if gw else None

            category = random.choice(categories)
            issue_sub = category.parent
            issue_type = issue_sub.parent

            desired_component_name = component_name_by_abbrev.get(getattr(category, "abbreviation", "") or "")
            component = (
                components_by_name.get(desired_component_name)
                if desired_component_name
                else (random.choice(components) if components else None)
            )
            sub_components = subcomponents_by_component_id.get(getattr(component, "id", None), [])
            sub_component = random.choice(sub_components) if sub_components else None

            issue = Issue.objects.create(
                administrative_region=region,
                category=category,
                issue_type=issue_type,
                issue_sub_type=issue_sub,
                component=component,
                sub_component=sub_component,
                reporter=fac_user,
                assignee=assignee_user,
                citizen=citizen,
                intake_date=intake,
                issue_date=intake,
                confirmed=True,
                tracking_code=f"DEMO-BEN-{i + 1:05d}",
                status=status,
                resolution_date=resolution_date,
                description=random.choice(descriptions),
                rating=random.randint(1, 5),
                contact_medium=ANONYMOUS_CHOICE,
                appeal_status=appeal_status,
                appeal_reason=appeal_reason,
                escalate_flag=escalate_flag,
                escalation_reason=escalation_reason,
                escalated_date=escalated_date,
            )
            created_issues.append(issue)
            # Same pattern as post-confirm flow: list views show internal_code, not tracking_code.
            Issue.objects.filter(pk=issue.pk).update(internal_code=issue.get_internal_code())

            IssueStatusChange.objects.filter(issue=issue, exited_at__isnull=True).update(entered_at=intake)

            if status == st_open and st_created and i % 3 == 0:
                IssueStatusChange.objects.create(
                    issue=issue,
                    status=st_created,
                    entered_at=intake - timedelta(days=random.randint(4, 10)),
                    exited_at=intake - timedelta(days=1),
                )

            want_attachment = (i < max(1, MIN_ATTACHMENTS_PER_ISSUE)) or (random.random() < ATTACHMENT_PROBABILITY)
            if want_attachment:
                att = IssueAttachment(issue=issue, uploaded_by=fac_user)
                att.file.save(f"demo-benin-{issue.id}.png", ContentFile(DEMO_TINY_PNG), save=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(facilitator_rows)} facilitator(s) and {len(created_issues)} confirmed demo issues "
                f"(assignees: case managers; {len(categories)} categories, seeded random per issue; "
                f"{len(appeal_indices)} in appeal; {len(escalation_indices)} flagged for "
                f"escalation demo; attachments and status history where applicable)."
            )
        )

        self.stdout.write(self.style.NOTICE("Populating performance and bottleneck aggregates…"))
        call_command(
            "populate_performance_metrics",
            "--create-global",
            "--create-regions",
            "--create-categories",
            "--create-region-category",
            "--create-status-bottlenecks",
            "--limit-regions",
            "10",
            "--limit-categories",
            "10",
        )
        call_command("populate_region_performance_metrics")
        call_command("populate_status_bottlenecks", "--no-lock")

        pinecone_key = str(getattr(settings, "PINECONE_API_KEY", "") or "").strip()
        if pinecone_key:
            try:
                call_command("etl_upload_issues_to_pinecone")
                self.stdout.write(self.style.SUCCESS("Pinecone upload finished (confirmed, non-vectorized issues)."))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Pinecone upload failed (search may stay empty): {exc}"))
                logger.exception("etl_upload_issues_to_pinecone from set_benin_demo")
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "PINECONE_API_KEY is empty: configure .env and run "
                    "`python manage.py etl_upload_issues_to_pinecone` for semantic search."
                )
            )

    def _create_facilitators(self) -> List[Tuple[User, AdministrativeRegion]]:
        """Dashboard login remains on the demo manager; facilitators seed realistic reporters."""
        communes = list(AdministrativeRegion.objects.filter(administrative_level__name="village"))
        if not communes:
            return []

        n = min(NUM_FACILITATORS, len(communes))
        rows: List[Tuple[User, AdministrativeRegion]] = []
        for i in range(n):
            email = f"facilitator-{i + 1}@grm-benin.local"
            region = communes[i % len(communes)]
            user = User(
                username=f"facilitator_demo_{i + 1}",
                email=email,
                phone_number=f"+229600{i + 1:05d}",
                first_name="Facilitateur",
                last_name=f"Démo {i + 1}",
                is_staff=False,
                is_superuser=False,
                is_active=True,
                grm_owner=False,
                grm_manager=False,
            )
            user.set_password(FACILITATOR_PASSWORD)
            user.save()
            self._patch_user_last_activity_demo(user)
            Facilitator.objects.create(user=user, administrative_region=region)
            rows.append((user, region))

        self.stdout.write(self.style.NOTICE(f"Created {len(rows)} facilitator account(s) (not for dashboard login)."))
        return rows
