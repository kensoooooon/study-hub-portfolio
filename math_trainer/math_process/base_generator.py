class BaseProblemGenerator:
    def __init__(self, **settings):
        """
        settings: dict
            各問題タイプが自由に定義できる引数。
            例）ClockProblemGeneratorでは `problem_types`, `widths_of_time` など
        """
        self.settings = settings

    def generate(self) -> dict:
        raise NotImplementedError("Subclasses must implement generate()")

    def generate_multiple(self, count: int) -> list[dict]:
        return [self.generate() for _ in range(count)]