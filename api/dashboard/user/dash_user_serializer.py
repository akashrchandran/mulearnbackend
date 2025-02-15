import uuid

from django.db import transaction
from rest_framework import serializers

from db.organization import Organization, UserOrganizationLink
from db.task import UserIgLink
from db.user import User, UserRoleLink
from utils.permission import JWTUtils
from utils.types import OrganizationType
from utils.utils import DateTimeUtils


class UserDashboardSerializer(serializers.ModelSerializer):
    karma = serializers.IntegerField(source="wallet_user.karma", default=None)
    level = serializers.CharField(source="user_lvl_link_user.level.name", default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "muid",
            "discord_id",
            "email",
            "mobile",
            "created_at",
            "karma",
            "level",
        ]


class UserSerializer(serializers.ModelSerializer):
    joined = serializers.CharField(source="created_at")
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "muid",
            "first_name",
            "last_name",
            "email",
            "mobile",
            "gender",
            "dob",
            "active",
            "exist_in_guild",
            "joined",
            "roles",
            "profile_pic",
        ]

    def get_roles(self, obj):
        return [
            user_role_link.role.title
            for user_role_link in obj.user_role_link_user.all()
        ]


class CollegeSerializer(serializers.ModelSerializer):
    org_type = serializers.CharField(source="org.org_type")
    department = serializers.CharField(source="department.pk")
    country = serializers.CharField(source="country.pk")
    state = serializers.CharField(source="state.pk")
    district = serializers.CharField(source="district.pk")

    class Meta:
        model = UserOrganizationLink
        fields = [
            "org",
            "org_type",
            "department",
            "graduation_year",
            "country",
            "state",
            "district",
        ]


class OrgSerializer(serializers.ModelSerializer):
    org_type = serializers.CharField(source="org.org_type", read_only=True)

    class Meta:
        model = UserOrganizationLink
        fields = ["org", "org_type"]


class UserDetailsSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="id")

    igs = serializers.ListField(write_only=True)
    department = serializers.CharField(write_only=True)
    graduation_year = serializers.CharField(write_only=True)

    organizations = serializers.SerializerMethodField(read_only=True)
    interest_groups = serializers.SerializerMethodField(read_only=True)
    role = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "first_name",
            "last_name",
            "email",
            "mobile",
            "gender",
            "discord_id",
            "dob",
            "role",
            "organizations",
            "department",
            "graduation_year",
            "interest_groups",
            "igs",
        ]

    def validate(self, data):
        if "id" not in data:
            raise serializers.ValidationError("User id is a required field")

        if (
            "email" in data
            and User.objects.filter(email=data["email"])
            .exclude(id=data["user_id"].id)
            .all()
        ):
            raise serializers.ValidationError("This email is already in use")
        return super().validate(data)

    def update(self, instance, validated_data):
        user_id = JWTUtils.fetch_user_id(self.context["request"])
        admin = User.objects.get(id=user_id)
        user = User.objects.get(id=validated_data["id"])
        orgs = validated_data.get("orgs")
        department = validated_data.get("department")
        graduation_year = validated_data.get("graduation_year")
        interest_groups = validated_data.get("igs")

        with transaction.atomic():
            if orgs is not None:
                existing_orgs = UserOrganizationLink.objects.filter(user=user)
                new_orgs = [
                    UserOrganizationLink(
                        id=uuid.uuid4(),
                        user=user,
                        org_id=org_id,
                        created_by=admin,
                        created_at=DateTimeUtils.get_current_utc_time(),
                        verified=True,
                        department_id=department,
                        graduation_year=graduation_year,
                    )
                    for org_id in orgs
                ]
                existing_orgs.delete()
                UserOrganizationLink.objects.bulk_create(new_orgs)

            if interest_groups is not None:
                existing_ig = UserIgLink.objects.filter(user=user)
                new_ig = [
                    UserIgLink(
                        id=uuid.uuid4(),
                        user=user,
                        ig_id=ig,
                        created_by=admin,
                        created_at=DateTimeUtils.get_current_utc_time(),
                    )
                    for ig in interest_groups
                ]
                existing_ig.delete()
                UserIgLink.objects.bulk_create(new_ig)

            return super().update(instance, validated_data)

    def get_organizations(self, user):
        organization_links = user.user_organization_link_user.select_related("org")
        if not organization_links.exists():
            return None

        organizations_data = []
        for link in organization_links:
            if link.org.org_type == OrganizationType.COLLEGE.value:
                serializer = CollegeSerializer(link)
            else:
                serializer = OrgSerializer(link)

            organizations_data.append(serializer.data)
        return organizations_data

    def get_interest_groups(self, user):
        return user.user_ig_link_user.all().values_list("ig", flat=True)

    def get_role(self, user):
        return user.user_role_link_user.all().values_list("role", flat=True)


class UserVerificationSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source="user.fullname")
    user_id = serializers.ReadOnlyField(source="user.id")
    discord_id = serializers.ReadOnlyField(source="user.discord_id")
    muid = serializers.ReadOnlyField(source="user.muid")
    email = serializers.ReadOnlyField(source="user.email")
    mobile = serializers.ReadOnlyField(source="user.mobile")
    role_title = serializers.ReadOnlyField(source="role.title")

    class Meta:
        model = UserRoleLink
        fields = [
            "id",
            "user_id",
            "discord_id",
            "muid",
            "full_name",
            "verified",
            "role_id",
            "role_title",
            "email",
            "mobile",
        ]


class UserDetailsEditSerializer(serializers.ModelSerializer):
    organizations = serializers.ListField(write_only=True)
    roles = serializers.ListField(write_only=True)
    interest_groups = serializers.ListField(write_only=True)
    department = serializers.CharField(write_only=True)
    graduation_year = serializers.CharField(write_only=True)
    admin = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "mobile",
            "gender",
            "dob",
            "organizations",
            "roles",
            "discord_id",
            "interest_groups",
            "department",
            "graduation_year",
            "admin",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if (
            college := instance.user_organization_link_user.filter(
                org__org_type=OrganizationType.COLLEGE.value
            )
            .select_related("org__district__zone__state__country", "department")
            .first()
        ):
            data.update(
                {
                    "country": getattr(college.district.zone.state.country, "id", None),
                    "state": getattr(college.district.zone.state, "id", None),
                    "district": getattr(college.district, "id", None),
                    "department": getattr(college.department, "id", None),
                    "graduation_year": college.graduation_year,
                }
            )

        data.update(
            {
                "organizations": list(
                    instance.user_organization_link_user.all().values_list(
                        "org_id", flat=True
                    )
                ),
                "roles": list(
                    instance.user_role_link_user.all().values_list("role_id", flat=True)
                ),
                "interest_groups": list(
                    instance.user_ig_link_user.all().values_list("ig_id", flat=True)
                ),
            }
        )

        return data

    def update(self, instance, validated_data):
        admin = validated_data.pop("admin")
        admin = User.objects.filter(id=admin).first()
        current_time = DateTimeUtils.get_current_utc_time()

        with transaction.atomic():
            if isinstance(
                organization_ids := validated_data.pop("organizations", None), list
            ):
                instance.user_organization_link_user.all().delete()
                organizations = Organization.objects.filter(
                    id__in=organization_ids
                ).order_by("org_type")

                if (
                    organizations.exists()
                    and organizations.first().org_type != OrganizationType.COLLEGE.value
                ):
                    validated_data.pop("department", None)
                    validated_data.pop("graduation_year", None)

                UserOrganizationLink.objects.bulk_create(
                    [
                        UserOrganizationLink(
                            user=instance,
                            org=org,
                            created_by=admin,
                            created_at=current_time,
                            verified=True,
                            department_id=validated_data.pop("department", None),
                            graduation_year=validated_data.pop("graduation_year", None),
                        )
                        for org in organizations
                    ]
                )

            if isinstance(role_ids := validated_data.pop("roles", None), list):
                instance.user_role_link_user.all().delete()
                UserRoleLink.objects.bulk_create(
                    [
                        UserRoleLink(
                            user=instance,
                            role_id=role_id,
                            created_by=admin,
                            created_at=current_time,
                            verified=True,
                        )
                        for role_id in role_ids
                    ]
                )

            if isinstance(
                interest_group_ids := validated_data.pop("interest_groups", None), list
            ):
                instance.user_ig_link_user.all().delete()
                UserIgLink.objects.bulk_create(
                    [
                        UserIgLink(
                            user=instance,
                            ig_id=ig,
                            created_by=admin,
                            created_at=current_time,
                        )
                        for ig in interest_group_ids
                    ]
                )

            return super().update(instance, validated_data)
