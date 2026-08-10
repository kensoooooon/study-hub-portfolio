# Generated manually (backfill data migration)

from django.db import migrations
from django.db.models import Count


def backfill_organizationadministrator_organization(apps, schema_editor):
    """
    OrganizationAdministrator.organizations(M2M)の内容を、
    新設したorganization(FK)へ複写する。

    Notes:
        M2M所属が0件または2件以上の管理者が1件でも存在する場合は、
        検証で異常データとして検出し、更新を一切行わずにmigrationを
        失敗させる(atomic migrationのため、失敗時は全体がロールバックされる)。
        M2Mフィールド自体はここでは変更しない。
    """
    OrganizationAdministrator = apps.get_model('accounts', 'OrganizationAdministrator')
    db_alias = schema_editor.connection.alias

    admins = OrganizationAdministrator.objects.using(db_alias).annotate(
        org_count=Count('organizations', distinct=True)
    )

    no_org_count = admins.filter(org_count=0).count()
    if no_org_count:
        raise RuntimeError(
            f"M2M所属が0件のOrganizationAdministratorが{no_org_count}件存在します。"
            "backfillを中止します。"
        )

    multi_org_count = admins.filter(org_count__gt=1).count()
    if multi_org_count:
        raise RuntimeError(
            f"M2M所属が2件以上のOrganizationAdministratorが{multi_org_count}件存在します。"
            "backfillを中止します。"
        )

    for admin in admins.iterator():
        organization_id = admin.organizations.using(db_alias).values_list('id', flat=True).get()
        admin.organization_id = organization_id
        admin.save(using=db_alias, update_fields=['organization'])


def reverse_backfill_organizationadministrator_organization(apps, schema_editor):
    """backfillのreverse。organizationをNULLへ戻す(M2Mは変更しない)。"""
    OrganizationAdministrator = apps.get_model('accounts', 'OrganizationAdministrator')
    db_alias = schema_editor.connection.alias

    OrganizationAdministrator.objects.using(db_alias).update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0020_organizationadministrator_organization'),
    ]

    operations = [
        migrations.RunPython(
            backfill_organizationadministrator_organization,
            reverse_code=reverse_backfill_organizationadministrator_organization,
        ),
    ]
