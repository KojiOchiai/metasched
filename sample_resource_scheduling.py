from ortools.sat.python import cp_model


def main():
    # 入力データ
    Tasks = {
        "T1": {"dur": 5, "reagent": "A", "demand": 3},
        "T2": {"dur": 4, "reagent": "A", "demand": 2},
        "T3": {"dur": 6, "reagent": "B", "demand": 2},
        "T4": {"dur": 3, "reagent": "A", "demand": 2},
        "T5": {"dur": 4, "reagent": "B", "demand": 1},
    }

    Tubes = {
        "RA1": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA2": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA3": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA4": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA5": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA6": {"dur": 2, "reagent": "A", "capacity": 5},
        "RA7": {"dur": 2, "reagent": "A", "capacity": 5},
        "RB1": {"dur": 2, "reagent": "B", "capacity": 3},
        "RB2": {"dur": 2, "reagent": "B", "capacity": 3},
    }

    slot_capacity = 2

    model = cp_model.CpModel()
    horizon = 500  # 十分な時間範囲

    all_tasks = list(Tasks.keys())
    all_tubes = list(Tubes.keys())

    # タスク → チューブの割当
    task_to_tube = {}
    task_starts = {}
    task_ends = {}
    task_intervals = {}

    # チューブ → 補充スケジュール
    tube_start = {}
    tube_end = {}
    tube_intervals = {}

    # 各タスクの選択可能なチューブ集合（reagent一致）
    task_possible_tubes = {
        t: [r for r in all_tubes if Tubes[r]["reagent"] == Tasks[t]["reagent"]]
        for t in all_tasks
    }

    # 変数定義
    for t in all_tasks:
        dur = Tasks[t]["dur"]
        demand = Tasks[t]["demand"]
        possible_tubes = task_possible_tubes[t]

        task_to_tube[t] = {}
        task_starts[t] = {}
        task_ends[t] = {}
        task_intervals[t] = {}

        for tube in possible_tubes:
            # タスクがこのチューブを選ぶか
            used = model.NewBoolVar(f"{t}_uses_{tube}")
            start = model.NewIntVar(0, horizon, f"{t}_start_{tube}")
            end = model.NewIntVar(0, horizon, f"{t}_end_{tube}")
            interval = model.NewOptionalIntervalVar(
                start, dur, end, used, f"{t}_interval_{tube}"
            )

            task_to_tube[t][tube] = used
            task_starts[t][tube] = start
            task_ends[t][tube] = end
            task_intervals[t][tube] = interval

        # 必ず1本選ぶ
        model.AddExactlyOne(task_to_tube[t][tube] for tube in possible_tubes)

    # チューブの使用状態を追跡
    tube_is_used = {}

    for tube in all_tubes:
        # このチューブが使用されるかどうか
        is_used = model.NewBoolVar(f"{tube}_is_used")
        tube_is_used[tube] = is_used

        dur = Tubes[tube]["dur"]
        start = model.NewIntVar(0, horizon, f"{tube}_refill_start")
        end = model.NewIntVar(0, horizon, f"{tube}_refill_end")

        # チューブが使用される場合は通常の補充時間、使用されない場合は時間0
        refill_dur = model.NewIntVar(0, dur, f"{tube}_refill_dur")
        model.Add(refill_dur == dur).OnlyEnforceIf(is_used)
        model.Add(refill_dur == 0).OnlyEnforceIf(is_used.Not())

        # OptionalIntervalVarではなく、使用されない場合は継続時間0のIntervalVarを使用
        interval = model.NewIntervalVar(
            start, refill_dur, end, f"{tube}_refill_interval"
        )

        # 使用されない場合、開始時間は0（任意でも良いが、視覚化のため）
        model.Add(start == 0).OnlyEnforceIf(is_used.Not())
        model.Add(end == 0).OnlyEnforceIf(is_used.Not())

        tube_start[tube] = start
        tube_end[tube] = end
        tube_intervals[tube] = interval

    # タスク開始は該当チューブ補充終了以降
    for t in all_tasks:
        for tube in task_possible_tubes[t]:
            # タスクがこのチューブを使う場合、チューブは使用中とマーク
            model.AddImplication(task_to_tube[t][tube], tube_is_used[tube])

            # タスクがこのチューブを使い、チューブが使用される場合、タスク開始は補充終了後
            model.Add(task_starts[t][tube] >= tube_end[tube]).OnlyEnforceIf(
                task_to_tube[t][tube]
            )

    # 全タスクのインターバル変数を収集（重複回避のため）
    active_task_intervals = []

    for t in all_tasks:
        for tube in task_possible_tubes[t]:
            active_task_intervals.append(task_intervals[t][tube])

    # チューブ容量制約
    for tube in all_tubes:
        demand_sum = []
        for t in all_tasks:
            if tube in task_to_tube[t]:
                demand = Tasks[t]["demand"]
                b = task_to_tube[t][tube]
                demand_sum.append(model.NewIntVar(0, demand, f"{t}_{tube}_demand_used"))
                model.Add(demand_sum[-1] == demand).OnlyEnforceIf(b)
                model.Add(demand_sum[-1] == 0).OnlyEnforceIf(b.Not())

        if demand_sum:
            model.Add(sum(demand_sum) <= Tubes[tube]["capacity"])

    # タスクと補充作業は重複不可
    all_intervals = active_task_intervals + [tube_intervals[tube] for tube in all_tubes]
    model.AddNoOverlap(all_intervals)

    # スロット占有区間（補充終了 〜 最後のタスク終了）
    slot_intervals = []
    for tube in all_tubes:
        latest_task_end = model.NewIntVar(0, horizon, f"{tube}_latest_task_end")

        related_ends = []
        for t in all_tasks:
            if tube in task_to_tube[t]:
                end = task_ends[t][tube]
                b = task_to_tube[t][tube]
                v = model.NewIntVar(0, horizon, f"{t}_{tube}_end_contrib")
                model.Add(v == end).OnlyEnforceIf(b)
                model.Add(v == 0).OnlyEnforceIf(b.Not())
                related_ends.append(v)

        if related_ends:
            model.AddMaxEquality(latest_task_end, related_ends)
            dur = model.NewIntVar(0, horizon, f"{tube}_slot_dur")
            model.Add(dur == latest_task_end - tube_end[tube])
            slot = model.NewIntervalVar(
                tube_end[tube], dur, latest_task_end, f"{tube}_slot_interval"
            )
            slot_intervals.append(slot)

    # スロット同時使用上限制約
    model.AddCumulative(slot_intervals, [1] * len(slot_intervals), slot_capacity)

    # メイクスパン
    makespan = model.NewIntVar(0, horizon, "makespan")
    all_task_ends_active = [
        (task_ends[t][tube], task_to_tube[t][tube])
        for t in all_tasks
        for tube in task_possible_tubes[t]
    ]
    for end_var, active in all_task_ends_active:
        model.Add(makespan >= end_var).OnlyEnforceIf(active)

    # 補充作業のスタート時間のばらつきを抑える（目的1）
    refill_starts = [tube_start[tube] for tube in all_tubes]
    refill_latest = model.NewIntVar(0, horizon, "refill_latest")
    refill_earliest = model.NewIntVar(0, horizon, "refill_earliest")
    model.AddMaxEquality(refill_latest, refill_starts)
    model.AddMinEquality(refill_earliest, refill_starts)
    refill_spread = model.NewIntVar(0, horizon, "refill_spread")
    model.Add(refill_spread == refill_latest - refill_earliest)

    # 使用されるチューブの数を計算
    used_tube_count = model.NewIntVar(0, len(all_tubes), "used_tube_count")
    model.Add(used_tube_count == sum(tube_is_used.values()))

    # 目的関数：使用チューブ数、spread、makespan の重み付き最小化
    model.Minimize(used_tube_count * 100 + refill_spread * 2 + makespan)

    # ソルバー
    solver = cp_model.CpSolver()
    # solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Status: {solver.StatusName(status)}")
        print(f"Makespan: {solver.Value(makespan)}")
        print(f"Refill spread: {solver.Value(refill_spread)}")
        print(f"使用チューブ数: {solver.Value(used_tube_count)}")

        print("\n補充スケジュール:")
        for tube in all_tubes:
            if solver.Value(tube_is_used[tube]):
                s = solver.Value(tube_start[tube])
                e = solver.Value(tube_end[tube])
                print(f"  {tube}: start={s}, end={e}")
            else:
                print(f"  {tube}: 使用なし")

        print("\nタスクスケジュール:")
        # タスク情報を収集して開始時間でソート
        task_info = []
        for t in all_tasks:
            for tube in task_possible_tubes[t]:
                if solver.Value(task_to_tube[t][tube]):
                    s = solver.Value(task_starts[t][tube])
                    e = solver.Value(task_ends[t][tube])
                    task_info.append((t, tube, s, e))
                    break
        # 開始時間でソート
        task_info.sort(key=lambda x: x[2])
        for t, tube, s, e in task_info:
            print(f"  {t} → {tube}: start={s}, end={e}, duration={e - s}")
    else:
        print("解が見つかりませんでした")


if __name__ == "__main__":
    main()
