from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.models import Organization, OrganizationAdministrator


class Command(BaseCommand):
    help = "Create/Update ops groups for organizations"

    def handle(self, *args, **kwargs):
        group_name = "ops_organizations"
        group, _ = Group.objects.get_or_create(name=group_name)

        permission_map = {  # モデルとマッピングの対応表
            Organization: [  # 組織に対して行える行動
                # Django標準
                "view_organization",
                "add_organization",
                "change_organization",
                # 独自
                "assign_organization_administrator",
                "view_all_organizations",
                "invite_organization_administrator",
            ],
            OrganizationAdministrator: [  # 組織管理者に対して行える行動
                # Django標準
                "view_organizationadministrator",
                # 独自
                "view_all_organization_administrators",
            ],
        }

        permissions = []
        missing = []

        for model, codenames in permission_map.items():
            content_type = ContentType.objects.get_for_model(model)
            found_permissions = list(
                Permission.objects.filter(
                    content_type=content_type,
                    codename__in=codenames,
                )
            )
            found_codenames = {perm.codename for perm in found_permissions}

            permissions.extend(found_permissions)
            missing.extend(sorted(set(codenames) - found_codenames))

        if missing:
            self.stdout.write(self.style.WARNING(f"Missing permissions: {missing}"))
            self.stdout.write(
                self.style.WARNING(
                    "Did you run migrate? Or are custom permissions missing from Meta.permissions?"
                )
            )
            return

        group.permissions.set(permissions)
        self.stdout.write(self.style.SUCCESS(f"Group '{group_name}' updated."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Permissions: {', '.join(sorted({perm.codename for perm in permissions}))}"
            )
        )