from random import choice, randint
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from random import sample, shuffle

from math_trainer.math_process.base_generator import BaseProblemGenerator


class TimeInformation(NamedTuple):
    """時刻の計算や表示の処理を請け負う
    
    Attributes:
        hour (int): 時
        minute (int): 分
        am_or_pm (Optional[str]): 午前午後の指定。無い場合は24時間の指定だとみなす
    """
    hour: int
    minute: int
    am_or_pm: Optional[str] = None  # 'am', 'pm', または None (24時間制)

    def to_datetime(self):
        """指定された表示に応じて、datetimeオブジェクトを生成する
        
        Returns:
            (datetime): 指定された表示に応じたdatetimeオブジェクト
        """
        if self.am_or_pm is None:
            return datetime(year=1900, month=1, day=1, hour=self.hour, minute=self.minute)
        elif self.am_or_pm == "am":
            if self.hour != 12:
                hour_24 = self.hour
            else:
                hour_24 = 0
        elif self.am_or_pm == "pm":
            if self.hour == 12:
                hour_24 = 12
            else:
                hour_24 = (self.hour % 12) + 12
        else:
            raise ValueError(f"'am_or_pm' must be 'am', 'pm' or None. {self.am_or_pm} is wrong.")
        return datetime(year=1900, month=1, day=1, hour=hour_24, minute=self.minute)
    
    def add_or_subtract_minutes(self, minutes: int) -> 'TimeInformation':
        """与えられた分数に応じてadd,subtractを呼び出し、新しいTimeInformationを返す

        Args:
            minutes (int): 変化させたい分数

        Returns:
            (TimeInformation): 新たなTimeInformation
        """
        if minutes == 0:
            return self
        elif minutes > 0:
            return self._add_minutes(minutes)
        else:
            return self._subtract_minutes(-minutes)

    def _add_minutes(self, minutes: int) -> 'TimeInformation':
        """指定された分数を足して、新しいTimeInformationオブジェクトを返す
        
        Args:
            minutes(int): 増やしたい分数
        
        Returns:
            (TimeInformation): 元の表示形式を引き継ぎつつ、指定の分数が足されたTimeInformation
        """
        new_time = self.to_datetime() + timedelta(minutes=minutes)
        if self.am_or_pm is None:
            return TimeInformation(hour=new_time.hour, minute=new_time.minute)
        else:
            if new_time.hour >= 12:
                am_or_pm = "pm"
            else:
                am_or_pm = "am"
            hour_12 = new_time.hour % 12 or 12  # 0時は12時として扱う
            return TimeInformation(hour=hour_12, minute=new_time.minute, am_or_pm=am_or_pm)

    def _subtract_minutes(self, minutes: int) -> 'TimeInformation':
        """時間から指定された分数を引いて新しいTimeInformationを返す
        
        Args:
            minutes(int): 引きたい分数(正の値)
            
        Returns:
            (TimeInformation): 元の表示形式を引き継ぎつつ、指定の分数が引かれたTimeInformation
        """
        new_time = self.to_datetime() - timedelta(minutes=minutes)
        if self.am_or_pm is None:
            return TimeInformation(hour=new_time.hour, minute=new_time.minute)
        else:
            am_or_pm = "pm" if new_time.hour >= 12 else "am"
            hour_12 = new_time.hour % 12 or 12
            return TimeInformation(hour=hour_12, minute=new_time.minute, am_or_pm=am_or_pm)

    def difference_in_minutes(self, other: 'TimeInformation') -> int:
        """別のTimeInformationとの時間差を分で返す
        
        Args:
            other (TimeInformation): 他のTimeInformation
        
        Returns:
            (int): 分数に変換された差
        """
        delta = self.to_datetime() - other.to_datetime()
        return int(delta.total_seconds() // 60)

    def __str__(self) -> str:
        """午前午後の指定も含めた文字列フォーマット
        
        Returns:
            (str): 問題や回答の表示に利用する文字列
        """
        if self.am_or_pm is None:
            # AM/PMの情報がない場合は24時間制で表示
            if self.minute == 0:
                return f"{self.hour}時"
            return f"{self.hour}時{self.minute}分"
        elif self.am_or_pm == "am":
            # AMの場合、0時は午前12時として扱う
            hour_12 = self.hour % 12 or 12
            if self.minute == 0:
                return f"午前{hour_12}時"
            return f"午前{hour_12}時{self.minute}分"
        elif self.am_or_pm == "pm":
            # PMの場合、12時をそのまま扱い、それ以外は12を超えないよう調整
            hour_12 = self.hour % 12 or 12
            if self.minute == 0:
                return f"午後{hour_12}時"
            return f"午後{hour_12}時{self.minute}分"
        else:
            raise ValueError(f"am_or_pm must be 'None', 'am' or 'pm'. {self.am_or_pm} is wrong.")


class ClockProblemGenerator(BaseProblemGenerator):
    """小学2年生用の時計の問題と解答、および描画に必要な要素の出力

    Args:
        BaseProblemGenerator : 全体に共通する問題の設定
    
    Attributes:
        selected_problem_type (str): 与えられた問題タイプ群からランダムに選択された問題タイプ
        choices (list[str]): 問題の選択肢。正解が1つと偽答が3つ
        self.canvas_required (bool): 問題を描写するにあたって、キャンバスを使った時計の描写が必要か否か
        self.answer_text (str): 答えの文章
        self.problem_text (str): 問題の文章
        self.time_information (TimeInformation): キャンバスへ描写するための時計情報。1,2は複数の情報を必要とする場合
    """
    def __init__(self, **settings: dict):
        """初期化と問題・解答に必要な情報の格納
        
        Args:
            settings (dict): 問題の設定(問題のタイプ,使用する時間幅)

        Raises:
            ValueError: 想定されていない問題タイプが与えられたときに挙上
        """
        super().__init__(**settings)
    
    def _build_one(self) -> dict:
        """1問単位で必要な情報を生成する

        Raises:
            ValueError: 想定されていない問題が型として与えられたときに挙上

        Returns:
            dict: 問題の描画にひつような諸情報
        """
        problem_types = self.settings.get("problem_types", [])
        widths_of_time = self.settings.get("widths_of_time", [])
        selected_problem_type = choice(problem_types)
        selected_width_of_time = choice(widths_of_time)

        # ここからはローカル変数で完結
        canvas_required = False
        problem_text = ""
        answer_text = ""
        choices = []
        draw_type = "single"
        times = []  # [{"hour":.., "minute":..}, ...] を格納
        # attributeエラー防止
        if selected_problem_type == "read_time":
            canvas_required = True
            answer_text, problem_text, time_information, choices = self._make_read_time_problem()
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_without_am_pm_with_picture":
            canvas_required = True
            answer_text, problem_text, time_information, choices = self._make_time_delta_without_am_pm_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_without_am_pm_without_picture":
            canvas_required = False
            answer_text, problem_text, time_information, choices = self._make_time_delta_without_am_pm_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_with_two_clock_pictures":
            canvas_required = True
            draw_type = "double"
            answer_text, problem_text, t1, t2, choices = self._make_time_delta_with_two_clock_pictures(selected_width_of_time)
            times = [
                {"hour": t1.hour, "minute": t1.minute},
                {"hour": t2.hour, "minute": t2.minute},
            ]
        elif selected_problem_type == "time_delta_with_am_pm_with_picture":
            canvas_required = True
            answer_text, problem_text, time_information, choices = self._make_time_delta_with_am_pm_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_with_am_pm_without_picture":
            canvas_required = False
            answer_text, problem_text, time_information, choices = self._make_time_delta_with_am_pm_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_with_24_hours_with_picture":
            canvas_required = True
            answer_text, problem_text, time_information, choices = self._make_time_delta_with_24_hours_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        elif selected_problem_type == "time_delta_with_24_hours_without_picture":
            canvas_required = False
            answer_text, problem_text, time_information, choices = self._make_time_delta_with_24_hours_problem(selected_width_of_time)
            times = [{"hour": time_information.hour, "minute": time_information.minute}]
        else:
            raise ValueError(f"Unexpected problem_type: {selected_problem_type}")
        return {
            "problem_text": problem_text,
            "answer_text": answer_text,
            "choices": choices,
            "problem_type": selected_problem_type,
            "metadata": {
                "draw": {
                    "type": draw_type,
                    "time_information": times,
                },
                "canvas_required": canvas_required,
            },
        }


    def generate(self):
        return self._build_one()

    def calculate_bounds(self, time: TimeInformation, before_or_after: str, use_24h_limit: bool) -> tuple[str, int]:
        """問題の条件に応じて遡るor進めるための限界を計算する

        Args:
            time (TimeInformation): 基準となる時間
            before_or_after (str): before(遡る)とafter(進む)のいずれかの情報
            use_24h_limit (bool): 24時間制を使っているかどうか

        Raises:
            ValueError: before_or_afterがきちんと想定された値になっているか

        Returns:
            word, max_minutes (tuple[str, int]):問題文に利用するword(前,後)と、進めるor遡るの限界分数 
        """
        if before_or_after == "before":
            # 0:01 より前に行かない
            max_minutes = time.difference_in_minutes(TimeInformation(0, 1))
            word = "前"
        elif before_or_after == "after":
            if use_24h_limit:
                # 23:59を超えない
                upper = 23
            else:
                # 11:59 を超えない
                upper = 11
            max_minutes = TimeInformation(upper, 59).difference_in_minutes(time)
            word = "後"
        else:
            raise ValueError(f"'before_or_after' must be 'before' or 'after'. {before_or_after} is wrong assignment.")
        return word, max_minutes

    def pick_valid_delta(self, time: TimeInformation, width_of_time: str, use_24h_limit: bool) -> tuple[str, str, int, int]:
        """リトライを何度か繰り返し、時間幅と時間の表示性の条件に応じて問題の描写に必要な諸要素を渡す

        Args:
            time (TimeInformation): 基準となる時間
            width_of_time (str): less_than_hour(1時間未満)とgreater_than_or_equal_to_one_hour(1時間以上のいずれか)
            use_24h_limit (bool): 24時間制を利用しているか否か

        Raises:
            ValueError: 想定されていない時間幅の指定が入った場合に挙上
            RuntimeError: 100回繰り返しても条件を満たす情報が生成出来なかった場合の挙上

        Returns:
            tuple[str, str, int, int]:
                before_or_after (str): 遡るか進むか
                word (str): 上に応じた前or後
                delta_minutes (int): ランダムに選択された差の分数
                max_minutes (int): 問題の条件に応じうる最大の分数
        """
        # 最大リトライ回数（不毛ループ防止）
        for _ in range(100):
            before_or_after = choice(["before", "after"])
            word, max_minutes = self.calculate_bounds(time, before_or_after, use_24h_limit)
            if width_of_time == "less_than_one_hour":
                if max_minutes <= 0:
                    continue  # 1分も動けない
                upper = min(max_minutes, 59)
                delta_minutes = randint(1, upper)
                return before_or_after, word, delta_minutes, max_minutes
            elif width_of_time == "greater_than_or_equal_to_one_hour":
                if max_minutes < 60:
                    continue  # 60分以上が取れないのでやり直し
                delta_minutes = randint(60, max_minutes)
                return before_or_after, word, delta_minutes, max_minutes
            else:
                raise ValueError(f"width_of_time is invalid: {width_of_time}")
        # 到達しない場合は例外
        raise RuntimeError("Could not pick a valid delta_minutes under constraints.")

    def make_time_information_for_answer(self, time: TimeInformation, delta_hours: int, delta_minutes: int) -> TimeInformation:
        """答えに利用するためのTimeInformationを、時間と分で生成

        Args:
            time (TimeInformation): 基準となる時間
            delta_hours (int): 差となる時間
            delta_minutes (int): 差となる分数

        Returns:
            TimeInformation: 答えで利用されるTimeInformation
        """
        minutes = delta_hours * 60 + delta_minutes
        return time.add_or_subtract_minutes(minutes)

    def make_time_information_for_answer_by_minutes(self, time: TimeInformation, delta_minutes: int) -> TimeInformation:
        """分のみで指定したいときに利用するヘルパー関数

        Args:
            time (TimeInformation): 基準となる時間
            delta_minutes (int): 差となる分数

        Returns:
            TimeInformation: _description_
        """
        return self.make_time_information_for_answer(time, 0, delta_minutes)

    def generate_minutes_for_dummy(self, width_of_time: str, max_minutes: int, delta_minutes_for_answer: int, before_or_after: str) -> list[int]:
        """問題の条件を満たすダミー生成用の分数を3つ生成する

        Args:
            width_of_time (str): 時間幅(less_than_one_hour or greater_than_or_equal_to_one_hour)
            max_minutes (int): 24時間制か否かにより判定されるmax_minutes
            delta_minutes_for_answer (int): 解答に利用された分数(重複防止用)
            before_or_after (str): 前に遡る問題なのか、後に進む問題なのかを

        Returns:
            minutes_for_dummy(list[int]): 条件を満たすダミー生成用の分数3つ
        """
        if width_of_time == "less_than_one_hour":
            lower_minutes, higher_minutes = 1, min(max_minutes, 59)
        elif width_of_time == "greater_than_or_equal_to_one_hour":
            lower_minutes, higher_minutes = 60, max_minutes
        pool = [minute for minute in range(lower_minutes, higher_minutes + 1) if minute != delta_minutes_for_answer]
        candidates_of_minutes = set()
        if len(pool) >= 3:
            candidates_of_minutes.update(sample(pool, 3))
        else:
            candidates_of_minutes.update(pool)
        
        # オフセットを利用して近傍でダミーを生成
        offsets = [1, 2, 3, 5, 10, 15, 20, 30, 45, 59]
        for offset in offsets:
            if len(candidates_of_minutes) >= 3:
                break
            minute = delta_minutes_for_answer + offset
            if (lower_minutes <= minute <= higher_minutes) and (minute != delta_minutes_for_answer):
                candidates_of_minutes.add(minute)
        
        # それでも不足していたときは、片端から埋めていく
        if len(candidates_of_minutes) < 3:
            for minute in range(higher_minutes, lower_minutes - 1, -1):
                if len(candidates_of_minutes) >= 3:
                    break
                if minute != delta_minutes_for_answer:
                    candidates_of_minutes.add(minute)
        
        # 最後まで埋まらなかったときはエラー挙上
        if len(candidates_of_minutes) < 3:
            raise RuntimeError(
                f"Could not prepare 3 dummy minutes under constraints: "
                f"range=[{lower_minutes},{higher_minutes}], answer={delta_minutes_for_answer}"
                )

        # 問題の条件に応じて、正負を切り替える場所
        if before_or_after == "before":
            minutes_for_dummy = [-minute for minute in candidates_of_minutes]
        else:
            minutes_for_dummy = [minute for minute in candidates_of_minutes]
        if len(minutes_for_dummy) > 3:
            minutes_for_dummy = sample(minutes_for_dummy, 3)
        return minutes_for_dummy

    def _make_read_time_problem(self) -> tuple[str, str, TimeInformation, list[str]]:
        """表示された時計を見て、時間を答える問題

        Returns:
            tuple[str, str, TimeInformation, list[str]]:
                answer (str): 正解
                problem (str): 問題文
                time_information (TimeInformation): 正解の基準となっている時間情報
                choices (list[str]): 偽答が混じった選択肢群
        """
        hour = randint(1, 12)
        minute = randint(1, 59)
        time_information = TimeInformation(hour, minute)
        problem = "時計は何時何分ですか?"
        answer = str(time_information)

        minute_offsets = sample([5, 10, 15, 20, 25, 30], 2)
        hour_offsets = sample([1, 2], 1)
        dummy1 = str(time_information.add_or_subtract_minutes(choice([-1, 1]) * minute_offsets[0]))
        dummy2 = str(time_information.add_or_subtract_minutes(choice([-1, 1]) * minute_offsets[1]))
        dummy3 = str(time_information.add_or_subtract_minutes(choice([-1, 1]) * hour_offsets[0] * 60))
        
        choices = [answer, dummy1, dummy2, dummy3]
        shuffle(choices)

        problem = "時計は何時何分ですか?"
        return answer, problem, time_information, choices

    def _make_time_delta_without_am_pm_problem(self, width_of_time: str) -> tuple[str, str, TimeInformation, list[str]]:
        """午前午後の入れ替えを含まない時間の経過を問う問題（AM/PMなし、12時間帯内）

        Args:
            width_of_time (str): 'less_than_one_hour' または 'greater_than_or_equal_to_one_hour'

        Returns:
            tuple[str, str, TimeInformation, list[str]]:
                answer (str): 正解
                problem (str): 問題文
                time (TimeInformation): 基準時刻（描画用）
                choices (list[str]): 選択肢（正解+誤答の計4つ、シャッフル済み）
        """
        hour = randint(1, 11)
        minute = randint(1, 59)
        time = TimeInformation(hour, minute)
        before_or_after, word, delta_minutes, max_minutes = self.pick_valid_delta(time, width_of_time, use_24h_limit=False)

        delta_hour, delta_minute = divmod(delta_minutes, 60)
        if before_or_after == "before":
            signed_hour = -delta_hour
            signed_minute = -delta_minute
        else:
            signed_hour = delta_hour
            signed_minute = delta_minute
        new_time = self.make_time_information_for_answer(time, signed_hour, signed_minute)

        # ---- 問題文 ----
        problem = f"{time}の"
        if delta_hour != 0:
            problem += f"{delta_hour}時間"
        if delta_minute != 0:
            problem += f"{delta_minute}分"
        problem += f"{word}は何時何分ですか。"

        answer = str(new_time)

        # 最終的な選択肢をシャッフル
        minutes_for_dummy = self.generate_minutes_for_dummy(width_of_time, max_minutes, delta_minutes, before_or_after)
        dummies = [str(time.add_or_subtract_minutes(minutes)) for minutes in minutes_for_dummy]
        choices = [answer] + dummies
        shuffle(choices)

        return answer, problem, time, choices

    def _make_time_delta_with_two_clock_pictures(self, width_of_time: str) -> tuple[str, str, TimeInformation, TimeInformation, list[str]]:
        """2つの時計の絵から、経過時間を求める問題

        Args:
            width_of_time (str): 時間幅

        Returns:
            tuple[str, str, TimeInformation, TimeInformation, list[str]]:
                answer (str): 答え
                problem (str): 問題
                time1, time2 (TimeInformation): 2つの時間
                choices (list[str]): 正解と偽答が混じった解答群
        """
        def format_duration(m: int) -> str:
            """分数を~時間...分に変換するヘルパー関数

            Args:
                m (int): 時間

            Returns:
                str: 変換された文字列
            """
            h, mm = divmod(m, 60)
            s = ""
            if h:
                s += f"{h}時間"
            if mm:
                s += f"{mm}分"
            if not s:  # 0分は出題上使わないが安全のため
                s = "0分"
            return s

        # ---- 基準時刻の決定（既存仕様を踏襲） ----
        hour1 = randint(1, 11)
        minute1 = randint(0, 59)
        time1 = TimeInformation(hour1, minute1)

        # ---- 正解の delta を決定（幅条件を厳守）----
        before_or_after, word, delta_minutes, max_minutes = self.pick_valid_delta(time1, width_of_time, use_24h_limit=False)
        if before_or_after == "before":
            signed_minutes = -delta_minutes
        else:
            signed_minutes = delta_minutes
        time2 = self.make_time_information_for_answer_by_minutes(time1, signed_minutes)

        problem = f"右の時計は、左の時計のどれくらい{word}ですか。"
        answer = f"{format_duration(delta_minutes)}{word}"

        minutes_for_dummy = self.generate_minutes_for_dummy(width_of_time, max_minutes, delta_minutes, before_or_after)
        dummies = [f"{format_duration(abs(m))}{word}" for m in minutes_for_dummy]

        choices = [answer] + dummies
        shuffle(choices)

        return answer, problem, time1, time2, choices

    def _make_time_delta_with_am_pm_problem(self, width_of_time: str) -> tuple[str, str, TimeInformation, list[str]]:
        """午前午後の入れ替えを含み、特定時間経過ごとの時間を問う問題

        Args:
            width_of_time (str): 選択された時間幅

        Returns:
            tuple[str, str, TimeInformation, list[str]]]:
                answer (str): 解答
                problem (str): 問題文
                time (TimeInformation): 描画を行うための基準時間の情報
                choices (list[str]): 正解と偽答が含まれる選択肢群
        """
        # --- 基準時刻（既存どおり AM/PM 指定） ---
        am_or_pm = choice(["am", "pm"])
        hour = randint(1, 11)
        minute = randint(0, 59)
        time = TimeInformation(hour, minute, am_or_pm)

        # --- 正解の delta 決定 ---
        before_or_after, word, delta_minutes, max_minutes = self.pick_valid_delta(time, width_of_time, use_24h_limit=True)
        delta_hour, delta_minute = divmod(delta_minutes, 60)
        if before_or_after == "before":
            signed_hour = -delta_hour
            signed_minute = -delta_minute
        else:
            signed_hour = delta_hour
            signed_minute = delta_minute
        new_time = self.make_time_information_for_answer(time, signed_hour, signed_minute)

        # --- 問題文・正解 ---
        problem = f"{time}の"
        if delta_hour != 0:
            problem += f"{delta_hour}時間"
        if delta_minute != 0:
            problem += f"{delta_minute}分"
        problem += f"{word}は何時何分ですか。"
        answer = str(new_time)  # AM/PMを含んだ表示（既存仕様）
        
        minutes_for_dummy = self.generate_minutes_for_dummy(width_of_time, max_minutes, delta_minutes, before_or_after)
        dummies = [str(time.add_or_subtract_minutes(minute)) for minute in minutes_for_dummy]

        choices = [answer] + dummies
        shuffle(choices)

        return answer, problem, time, choices

    def _make_time_delta_with_24_hours_problem(self, width_of_time: str) -> tuple[str, str, TimeInformation, list[str]]:
        """24時間制の経過を問う問題（choices付き）
        
        Args:
            width_of_time (str): 'less_than_one_hour' または 'greater_than_or_equal_to_one_hour'
        
        Returns:
            tuple[str, str, TimeInformation, list[str]]:
                answer (str): 解答（最終時刻）
                problem (str): 問題文
                time (TimeInformation): 基準となる時刻（描画用）
                choices (list[str]): 4択（正解+ダミー3つ）
        """
        # ---- 基準時刻（24時間制）----
        hour = randint(0, 23)
        minute = randint(0, 59)
        time = TimeInformation(hour, minute)

        # ---- 正解の delta を決定（幅条件を厳守）----
        before_or_after, word, delta_minutes, max_minutes = self.pick_valid_delta(time, width_of_time, use_24h_limit=True)
        delta_hour, delta_minute = divmod(delta_minutes, 60)
        if before_or_after == "before":
            signed_minutes = -delta_minutes
        else:
            signed_minutes = delta_minutes
        new_time = self.make_time_information_for_answer_by_minutes(time, signed_minutes)

        # ---- 問題文・正解 ----
        problem = f"{time}の"
        if delta_hour != 0:
            problem += f"{delta_hour}時間"
        if delta_minute != 0:
            problem += f"{delta_minute}分"
        problem += f"{word}は何時何分ですか。"
        answer = str(new_time)  # 24時間制の表示
        
        minutes_for_dummy = self.generate_minutes_for_dummy(width_of_time, max_minutes, delta_minutes, before_or_after)
        dummies = [str(time.add_or_subtract_minutes(minute)) for minute in minutes_for_dummy]
        choices = [answer] + dummies
        shuffle(choices)

        return answer, problem, time, choices
