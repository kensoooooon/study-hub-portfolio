import csv
import os
from django.core.management.base import BaseCommand
from chem_trainer.models import Element, ElementalSubstance, Compound, ChemicalEquation

class Command(BaseCommand):
    """
    python manage.py update_chem_data data/chemical_data.tsv
    のように利用する
    """
    help = "TSVファイルの内容に基づいて、化学データを更新・追加する（削除なし）"

    def add_arguments(self, parser):
        parser.add_argument("tsv_file", type=str, help="化学データを含むTSVファイルのパス")

    def handle(self, *args, **kwargs):
        tsv_file = kwargs["tsv_file"]

        if not os.path.exists(tsv_file):
            self.stdout.write(self.style.ERROR(f"指定されたTSVファイルが見つかりません: {tsv_file}"))
            return

        with open(tsv_file, encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter="\t")

            for row in reader:
                equation_text = row["Equation"]
                latex_text = row["LaTeX"]

                # ✅ 既存の化学反応式を検索
                equation_obj, created = ChemicalEquation.objects.update_or_create(
                    equation=equation_text,
                    defaults={"latex": latex_text}
                )

                # ✅ 新規追加された場合のログ
                if created:
                    self.stdout.write(self.style.SUCCESS(f"新規追加: {equation_text}"))
                else:
                    # ✅ LaTeXが更新された場合のログ
                    if equation_obj.latex != latex_text:
                        self.stdout.write(self.style.WARNING(f"更新: {equation_text} の LaTeX を変更"))

                # ✅ 反応物・生成物の登録・更新
                reactant_names = row["Reactants"].split(", ")
                product_names = row["Products"].split(", ")

                reactants = []
                products = []

                # ✅ 反応物の処理
                for name in reactant_names:
                    compound, _ = Compound.objects.get_or_create(formula=name)
                    reactants.append(compound)

                # ✅ 生成物の処理
                for name in product_names:
                    compound, _ = Compound.objects.get_or_create(formula=name)
                    products.append(compound)

                # ✅ 反応物・生成物の ManyToMany 関係を更新
                equation_obj.reactant_compounds.set(reactants)
                equation_obj.product_compounds.set(products)

        self.stdout.write(self.style.SUCCESS("データの更新が完了しました。"))
