import pandas as pd
from django.core.management.base import BaseCommand
from chem_trainer.models import Element, ElementalSubstance, Compound, ChemicalEquation
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = "Import chemical data from TSV files"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting import process..."))

        self.import_elements()
        self.import_elemental_substances()

        # Compound の登録を確実に完了させる
        self.import_compounds()
        self.stdout.write(self.style.SUCCESS("Compounds imported successfully."))

        # ChemicalEquation の登録を最後に行う
        self.import_chemical_equations()

        self.stdout.write(self.style.SUCCESS("Data imported successfully."))

    def import_elements(self):
        self.stdout.write(self.style.SUCCESS("Importing Elements..."))
        df = pd.read_csv("data/chem_trainer/Elements.tsv", sep="\t")
        for _, row in df.iterrows():
            obj, created = Element.objects.update_or_create(
                symbol=row["Symbol"],
                defaults={
                    "name_jp": row["Name_JP"],
                    "name_en": row["Name_EN"],
                    "atomic_number": row["Atomic_Number"],
                    "category": row["Category"],
                    "latex": row["LaTeX"],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added Element: {row['Symbol']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Skipped Element: {row['Symbol']}"))

    def import_elemental_substances(self):
        self.stdout.write(self.style.SUCCESS("Importing ElementalSubstances..."))
        df = pd.read_csv("data/chem_trainer/ElementalSubstances.tsv", sep="\t")
        for _, row in df.iterrows():
            element = Element.objects.filter(symbol=row["Element"]).first()
            if not element:
                self.stdout.write(self.style.ERROR(f"Missing Element: {row['Element']}"))
                continue
            obj, created = ElementalSubstance.objects.update_or_create(
                formula=row["Formula"],
                defaults={
                    "name_jp": row["Name_JP"],
                    "name_en": row["Name_EN"],
                    "element": element,
                    "latex": row["LaTeX"],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added ElementalSubstance: {row['Formula']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Skipped ElementalSubstance: {row['Formula']}"))


    def import_compounds(self):
        self.stdout.write(self.style.SUCCESS("Importing Compounds..."))
        df = pd.read_csv("data/chem_trainer/Compounds.tsv", sep="\t")
        for _, row in df.iterrows():
            compound, created = Compound.objects.update_or_create(
                formula=row["Formula"],
                defaults={
                    "name_jp": row["Name_JP"],
                    "name_en": row["Name_EN"],
                    "latex": row["LaTeX"],
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Added Compound: {row['Formula']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Skipped Compound: {row['Formula']}"))

            # **Compound に関連する Element を追加**
            elements = row["Elements"].split(", ")
            for symbol in elements:
                element = Element.objects.filter(symbol=symbol.strip()).first()
                if not element:
                    self.stdout.write(self.style.ERROR(f"Missing Element in Compound: {symbol}"))
                    continue
                compound.elements.add(element)  # `elements` を追加

            # **要素を追加した後でバリデーションを実行**
            try:
                compound.validate_elements()
                compound.save()  # 最終保存
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f"Validation failed for {row['Formula']}: {e}"))


    def import_chemical_equations(self):
        self.stdout.write(self.style.SUCCESS("Importing ChemicalEquations..."))
        df = pd.read_csv("data/chem_trainer/ChemicalEquations.tsv", sep="\t")
        for _, row in df.iterrows():
            equation, created = ChemicalEquation.objects.update_or_create(
                equation=row["Equation"],
                defaults={"latex": row["LaTeX"]},
            )

            if created:
                equation.save()  # **ID を確定させる**
                self.stdout.write(self.style.SUCCESS(f"Added ChemicalEquation: {row['Equation']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Skipped ChemicalEquation: {row['Equation']}"))

            reactants = row["Reactants"].split(", ")
            products = row["Products"].split(", ")

            for formula in reactants:
                compound = Compound.objects.filter(formula=formula.strip()).first()
                substance = ElementalSubstance.objects.filter(formula=formula.strip()).first()

                if compound:
                    equation.reactant_compounds.add(compound)
                elif substance:
                    equation.reactant_substances.add(substance)
                else:
                    self.stdout.write(self.style.ERROR(f"Missing Reactant: {formula}"))

            for formula in products:
                compound = Compound.objects.filter(formula=formula.strip()).first()
                substance = ElementalSubstance.objects.filter(formula=formula.strip()).first()

                if compound:
                    equation.product_compounds.add(compound)
                elif substance:
                    equation.product_substances.add(substance)
                else:
                    self.stdout.write(self.style.ERROR(f"Missing Product: {formula}"))
