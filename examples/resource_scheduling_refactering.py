from typing import Any, Dict, List, Tuple

from ortools.sat.python import cp_model


class Task:
    """タスクを表すクラス"""

    def __init__(self, name: str, duration: int, reagent: str, demand: int):
        """
        タスクの初期化

        Args:
            name: タスク名
            duration: タスクの実行時間
            reagent: 必要な試薬のタイプ
            demand: 必要な試薬の量
        """
        self.name = name
        self.duration = duration
        self.reagent = reagent
        self.demand = demand

        # モデル変数（後で初期化）
        self.tube_assignments: dict[str, cp_model.IntVar] = {}
        self.start_times: dict[str, cp_model.IntVar] = {}
        self.end_times: dict[str, cp_model.IntVar] = {}
        self.intervals: dict[str, cp_model.IntervalVar] = {}

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Task":
        """辞書からTaskオブジェクトを作成"""
        return cls(
            name=name,
            duration=data["dur"],
            reagent=data["reagent"],
            demand=data["demand"],
        )

    def initialize_variables(
        self, model: cp_model.CpModel, horizon: int, possible_tubes: List[str]
    ):
        """モデル内の変数を初期化"""
        for tube in possible_tubes:
            # タスクがこのチューブを選ぶか
            used = model.NewBoolVar(f"{self.name}_uses_{tube}")
            start = model.NewIntVar(0, horizon, f"{self.name}_start_{tube}")
            end = model.NewIntVar(0, horizon, f"{self.name}_end_{tube}")
            interval = model.NewOptionalIntervalVar(
                start, self.duration, end, used, f"{self.name}_interval_{tube}"
            )

            self.tube_assignments[tube] = used
            self.start_times[tube] = start
            self.end_times[tube] = end
            self.intervals[tube] = interval

        # 必ず1本のチューブを選ぶ制約
        model.AddExactlyOne(self.tube_assignments[tube] for tube in possible_tubes)


class Tube:
    """試薬チューブを表すクラス"""

    def __init__(self, name: str, refill_duration: int, reagent: str, capacity: int):
        """
        チューブの初期化

        Args:
            name: チューブ名
            refill_duration: 補充にかかる時間
            reagent: 試薬のタイプ
            capacity: 容量
        """
        self.name = name
        self.refill_duration = refill_duration
        self.reagent = reagent
        self.capacity = capacity

        # モデル変数（後で初期化）
        self.is_used: cp_model.IntVar | None = None
        self.start_time: cp_model.IntVar | None = None
        self.end_time: cp_model.IntVar | None = None
        self.interval: cp_model.IntervalVar | None = None
        self.slot_interval: cp_model.IntervalVar | None = (
            None  # (補充後〜最後のタスク終了までの期間)
        )

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Tube":
        """辞書からTubeオブジェクトを作成"""
        return cls(
            name=name,
            refill_duration=data["dur"],
            reagent=data["reagent"],
            capacity=data["capacity"],
        )

    def initialize_variables(self, model: cp_model.CpModel, horizon: int):
        """モデル内の変数を初期化"""
        # このチューブが使用されるかどうか
        self.is_used = model.NewBoolVar(f"{self.name}_is_used")

        self.start_time = model.NewIntVar(0, horizon, f"{self.name}_refill_start")
        self.end_time = model.NewIntVar(0, horizon, f"{self.name}_refill_end")

        # チューブが使用される場合は通常の補充時間、使用されない場合は時間0
        refill_dur = model.NewIntVar(0, self.refill_duration, f"{self.name}_refill_dur")
        model.Add(refill_dur == self.refill_duration).OnlyEnforceIf(self.is_used)
        model.Add(refill_dur == 0).OnlyEnforceIf(self.is_used.Not())

        # OptionalIntervalVarではなく、使用されない場合は継続時間0のIntervalVarを使用
        self.interval = model.NewIntervalVar(
            self.start_time, refill_dur, self.end_time, f"{self.name}_refill_interval"
        )

        # 使用されない場合、開始時間は0（任意でも良いが、視覚化のため）
        model.Add(self.start_time == 0).OnlyEnforceIf(self.is_used.Not())
        model.Add(self.end_time == 0).OnlyEnforceIf(self.is_used.Not())


class SchedulingModel:
    """スケジューリングモデルを表すクラス"""

    def __init__(self, slot_capacity: int = 4, horizon: int = 500):
        """
        モデルの初期化

        Args:
            slot_capacity: スロットの最大容量
            horizon: 計画期間
        """
        self.model = cp_model.CpModel()
        self.slot_capacity = slot_capacity
        self.horizon = horizon

        self.tasks: Dict[str, Task] = {}
        self.tubes: Dict[str, Tube] = {}

        # 各タスクの選択可能なチューブ集合（reagent一致）
        self.task_possible_tubes: Dict[str, List[str]] = {}

        # 目的関数の変数
        self.makespan = None
        self.refill_spread = None

    def add_task(self, task: Task):
        """タスクを追加"""
        self.tasks[task.name] = task

    def add_tube(self, tube: Tube):
        """チューブを追加"""
        self.tubes[tube.name] = tube

    def initialize(self):
        """モデルの初期化を行う"""
        # 各タスクの選択可能なチューブ集合（reagent一致）を計算
        for task_name, task in self.tasks.items():
            self.task_possible_tubes[task_name] = [
                tube_name
                for tube_name, tube in self.tubes.items()
                if tube.reagent == task.reagent
            ]

            # タスクの変数を初期化
            task.initialize_variables(
                self.model, self.horizon, self.task_possible_tubes[task_name]
            )

        # チューブの変数を初期化
        for tube in self.tubes.values():
            tube.initialize_variables(self.model, self.horizon)

        # 制約を追加
        self._add_constraints()

        # 目的関数を設定
        self._set_objective()

    def _add_constraints(self):
        """すべての制約を追加"""
        self._add_task_tube_constraints()
        self._add_no_overlap_constraints()
        self._add_tube_capacity_constraints()
        self._add_slot_usage_constraints()

    def _add_task_tube_constraints(self):
        """タスクとチューブの関係に関する制約"""
        # タスク開始は該当チューブ補充終了以降
        for task_name, task in self.tasks.items():
            for tube_name in self.task_possible_tubes[task_name]:
                tube = self.tubes[tube_name]

                # タスクがこのチューブを使う場合、チューブは使用中とマーク
                self.model.AddImplication(
                    task.tube_assignments[tube_name], tube.is_used
                )

                # タスクがこのチューブを使い、チューブが使用される場合、タスク開始は補充終了後
                self.model.Add(
                    task.start_times[tube_name] >= tube.end_time
                ).OnlyEnforceIf(task.tube_assignments[tube_name])

    def _add_tube_capacity_constraints(self):
        """チューブの容量制約"""
        for tube_name, tube in self.tubes.items():
            demand_sum = []

            for task_name, task in self.tasks.items():
                if tube_name in task.tube_assignments:
                    demand = task.demand
                    b = task.tube_assignments[tube_name]
                    demand_var = self.model.NewIntVar(
                        0, demand, f"{task_name}_{tube_name}_demand_used"
                    )
                    self.model.Add(demand_var == demand).OnlyEnforceIf(b)
                    self.model.Add(demand_var == 0).OnlyEnforceIf(b.Not())
                    demand_sum.append(demand_var)

            if demand_sum:
                self.model.Add(sum(demand_sum) <= tube.capacity)

    def _add_no_overlap_constraints(self):
        """タスクとチューブの補充は重複しないという制約"""
        # 全タスクのインターバル変数を収集
        active_task_intervals = []
        for task in self.tasks.values():
            for tube_name in self.task_possible_tubes[task.name]:
                active_task_intervals.append(task.intervals[tube_name])

        # チューブ補充のインターバル
        tube_intervals = [tube.interval for tube in self.tubes.values()]

        # タスクと補充作業は重複不可
        all_intervals = active_task_intervals + tube_intervals
        self.model.AddNoOverlap(all_intervals)

    def _add_slot_usage_constraints(self):
        """スロットの同時使用数制約"""
        # スロット占有区間（補充終了 〜 最後のタスク終了）
        slot_intervals = []

        for tube_name, tube in self.tubes.items():
            latest_task_end = self.model.NewIntVar(
                0, self.horizon, f"{tube_name}_latest_task_end"
            )

            related_ends = []
            for task_name, task in self.tasks.items():
                if tube_name in task.tube_assignments:
                    end = task.end_times[tube_name]
                    b = task.tube_assignments[tube_name]
                    v = self.model.NewIntVar(
                        0, self.horizon, f"{task_name}_{tube_name}_end_contrib"
                    )
                    self.model.Add(v == end).OnlyEnforceIf(b)
                    self.model.Add(v == 0).OnlyEnforceIf(b.Not())
                    related_ends.append(v)

            if related_ends:
                self.model.AddMaxEquality(latest_task_end, related_ends)
                dur = self.model.NewIntVar(0, self.horizon, f"{tube_name}_slot_dur")
                self.model.Add(dur == latest_task_end - tube.end_time)
                tube.slot_interval = self.model.NewIntervalVar(
                    tube.end_time, dur, latest_task_end, f"{tube_name}_slot_interval"
                )
                slot_intervals.append(tube.slot_interval)

        # スロット同時使用上限制約
        self.model.AddCumulative(
            slot_intervals, [1] * len(slot_intervals), self.slot_capacity
        )

    def _set_objective(self):
        """目的関数を設定"""
        # メイクスパン（最後のタスクの終了時刻）
        self.makespan = self.model.NewIntVar(0, self.horizon, "makespan")
        all_task_ends_active = [
            (task.end_times[tube_name], task.tube_assignments[tube_name])
            for task_name, task in self.tasks.items()
            for tube_name in self.task_possible_tubes[task_name]
        ]
        for end_var, active in all_task_ends_active:
            self.model.Add(self.makespan >= end_var).OnlyEnforceIf(active)

        # 補充作業のスタート時間のばらつきを抑える（目的1）
        refill_starts = [tube.start_time for tube in self.tubes.values()]
        refill_latest = self.model.NewIntVar(0, self.horizon, "refill_latest")
        refill_earliest = self.model.NewIntVar(0, self.horizon, "refill_earliest")
        self.model.AddMaxEquality(refill_latest, refill_starts)
        self.model.AddMinEquality(refill_earliest, refill_starts)
        self.refill_spread = self.model.NewIntVar(0, self.horizon, "refill_spread")
        self.model.Add(self.refill_spread == refill_latest - refill_earliest)

        # 目的関数：補充のばらつき、makespanの重み付き最小化
        self.model.Minimize(self.refill_spread * 20 + self.makespan)


class SchedulingSolver:
    """スケジューリングモデルを解くソルバークラス"""

    def __init__(self, model: SchedulingModel, time_limit_seconds: float = 3.0):
        """
        ソルバーの初期化

        Args:
            model: 解くモデル
            time_limit_seconds: 解法の時間制限
        """
        self.model = model
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.status = None

    def solve(self) -> bool:
        """
        モデルを解く

        Returns:
            解が見つかったかどうか
        """
        self.status = self.solver.Solve(self.model.model)
        return self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def get_status_name(self) -> str:
        """解の状態名を取得"""
        return self.solver.StatusName(self.status)

    def get_makespan(self) -> int:
        """メイクスパンを取得"""
        assert self.model.makespan is not None, "makespan is None"
        return self.solver.Value(self.model.makespan)

    def get_refill_spread(self) -> int:
        """補充のばらつきを取得"""
        assert self.model.refill_spread is not None, "refill_spread is None"
        return self.solver.Value(self.model.refill_spread)

    def get_used_tube_count(self) -> int:
        """使用されるチューブ数を取得"""
        count = 0
        for tube in self.model.tubes.values():
            assert tube.is_used is not None, f"is_used is None for {tube.name}"
            if self.solver.Value(tube.is_used) == 1:
                count += 1
        return count

    def get_tube_schedule(self) -> List[Tuple[str, int, int]]:
        """チューブの補充スケジュールを取得"""
        result: List[Tuple[str, int, int]] = []
        for tube_name, tube in self.model.tubes.items():
            assert tube.is_used is not None, f"is_used is None for {tube.name}"
            assert tube.start_time is not None, f"start_time is None for {tube.name}"
            assert tube.end_time is not None, f"end_time is None for {tube.name}"

            if self.solver.Value(tube.is_used) == 1:
                s = self.solver.Value(tube.start_time)
                e = self.solver.Value(tube.end_time)
                result.append((tube_name, s, e))
        return result

    def get_task_schedule(self) -> List[Tuple[str, str, int, int]]:
        """タスクのスケジュールを取得（開始時間でソート済み）"""
        result: List[Tuple[str, str, int, int]] = []
        for task_name, task in self.model.tasks.items():
            for tube_name in self.model.task_possible_tubes[task_name]:
                # 変数の存在チェック
                assert tube_name in task.tube_assignments, (
                    f"tube_assignment missing for {task_name}-{tube_name}"
                )
                assert tube_name in task.start_times, (
                    f"start_time missing for {task_name}-{tube_name}"
                )
                assert tube_name in task.end_times, (
                    f"end_time missing for {task_name}-{tube_name}"
                )

                if self.solver.Value(task.tube_assignments[tube_name]) == 1:
                    s = self.solver.Value(task.start_times[tube_name])
                    e = self.solver.Value(task.end_times[tube_name])
                    result.append((task_name, tube_name, s, e))
                    break
        # 開始時間でソート
        return sorted(result, key=lambda x: x[2])


def main():
    # 入力データ
    task_data = {
        "T1": {"dur": 5, "reagent": "A", "demand": 3},
        "T2": {"dur": 4, "reagent": "A", "demand": 2},
        "T3": {"dur": 6, "reagent": "B", "demand": 2},
        "T4": {"dur": 3, "reagent": "A", "demand": 2},
        "T5": {"dur": 3, "reagent": "A", "demand": 2},
        "T6": {"dur": 3, "reagent": "A", "demand": 2},
        "T7": {"dur": 3, "reagent": "A", "demand": 2},
        "T8": {"dur": 3, "reagent": "A", "demand": 2},
        "T9": {"dur": 4, "reagent": "B", "demand": 1},
        "T10": {"dur": 4, "reagent": "B", "demand": 1},
    }

    tube_data = {
        "RA1": {"dur": 2, "reagent": "A", "capacity": 3},
        "RA2": {"dur": 2, "reagent": "A", "capacity": 4},
        "RA3": {"dur": 2, "reagent": "A", "capacity": 4},
        "RA4": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA5": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA6": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA7": {"dur": 2, "reagent": "A", "capacity": 5},
        "RB1": {"dur": 2, "reagent": "B", "capacity": 5},
        "RB2": {"dur": 2, "reagent": "B", "capacity": 5},
        "RB3": {"dur": 2, "reagent": "B", "capacity": 3},
    }

    # モデルを作成
    model = SchedulingModel(slot_capacity=4)

    # タスクとチューブを追加
    for name, data in task_data.items():
        model.add_task(Task.from_dict(name, data))

    for name, data in tube_data.items():
        model.add_tube(Tube.from_dict(name, data))

    # モデルの初期化
    model.initialize()

    # ソルバーを作成して解く
    solver = SchedulingSolver(model)
    if solver.solve():
        # 結果の表示
        print(f"Status: {solver.get_status_name()}")
        print(f"Makespan: {solver.get_makespan()}")
        print(f"Refill spread: {solver.get_refill_spread()}")
        print(f"使用チューブ数: {solver.get_used_tube_count()}")

        print("\n補充スケジュール:")
        for tube_name, start, end in solver.get_tube_schedule():
            print(f"  {tube_name}: {start} ~ {end}")

        unused_tubes = set(model.tubes.keys()) - set(
            t[0] for t in solver.get_tube_schedule()
        )
        for tube_name in unused_tubes:
            print(f"  {tube_name}: 使用なし")

        print("\nタスクスケジュール:")
        for task_name, tube_name, start, end in solver.get_task_schedule():
            print(
                f"  {task_name} → {tube_name}: {start} ~ {end}, duration={end - start}"
            )
    else:
        print("解が見つかりませんでした")


if __name__ == "__main__":
    main()
