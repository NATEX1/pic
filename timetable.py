from ortools.sat.python import cp_model
import db
from collections import defaultdict
import sys

print("Starting timetable generation...")
print("="*60)

# ======================
# CONFIGURATION
# ======================
model = cp_model.CpModel()

# กลุ่มเรียน
try:
    GROUPS = [g["group_id"] for g in db.fetch_all("SELECT group_id FROM student_group")]
    print(f"✓ Groups loaded: {len(GROUPS)}")
    print(f"  Groups: {GROUPS}")
except Exception as e:
    print(f"✗ Error loading groups: {e}")
    sys.exit(1)

# วิชา
try:
    SUBJECTS = db.fetch_all("SELECT subject_id, theory, practice FROM subject")
    SUBJECT_DICT = {s["subject_id"]: s for s in SUBJECTS}
    print(f"✓ Subjects loaded: {len(SUBJECTS)}")
except Exception as e:
    print(f"✗ Error loading subjects: {e}")
    sys.exit(1)

# คาบเรียน
try:
    TIMESLOTS = db.fetch_all("""
        SELECT timeslot_id, day, period
        FROM timeslot
        WHERE period != 5
        ORDER BY day, period
    """)
    TS_INDEX = {t["timeslot_id"]: i for i, t in enumerate(TIMESLOTS)}
    print(f"✓ Timeslots loaded: {len(TIMESLOTS)}")
except Exception as e:
    print(f"✗ Error loading timeslots: {e}")
    sys.exit(1)

# สร้าง mapping: วัน -> [indices ของ timeslots ในวันนั้น]
DAY_TIMESLOTS = defaultdict(list)
for i, t in enumerate(TIMESLOTS):
    DAY_TIMESLOTS[t["day"]].append(i)

PERIODS_PER_DAY = max(len(slots) for slots in DAY_TIMESLOTS.values())
print(f"✓ Periods per day: {PERIODS_PER_DAY}")
print(f"✓ Total days: {len(DAY_TIMESLOTS)}")
for day in sorted(DAY_TIMESLOTS.keys()):
    print(f"  Day {day}: {len(DAY_TIMESLOTS[day])} periods")

# ลงทะเบียนวิชา
try:
    REG = db.fetch_all("SELECT group_id, subject_id FROM register")
    GROUP_SUBJECTS = {}
    for r in REG:
        GROUP_SUBJECTS.setdefault(r["group_id"], []).append(r["subject_id"])
    print(f"✓ Registrations loaded: {len(REG)}")
    for g in GROUPS:
        print(f"  {g}: {len(GROUP_SUBJECTS.get(g, []))} subjects")
except Exception as e:
    print(f"✗ Error loading registrations: {e}")
    sys.exit(1)

# ครูผู้สอน
try:
    TEACH = db.fetch_all("SELECT subject_id, teacher_id FROM teach")
    SUBJECT_TEACHERS = {}
    for r in TEACH:
        SUBJECT_TEACHERS.setdefault(r["subject_id"], []).append(r["teacher_id"])
    print(f"✓ Teacher assignments loaded: {len(TEACH)}")
except Exception as e:
    print(f"✗ Error loading teacher assignments: {e}")
    sys.exit(1)

# ห้องเรียน
try:
    ROOMS = [r["room_id"] for r in db.fetch_all("SELECT room_id FROM room")]
    print(f"✓ Rooms loaded: {len(ROOMS)}")
except Exception as e:
    print(f"✗ Error loading rooms: {e}")
    sys.exit(1)

# ======================
# CREATE VARIABLES
# ======================
print("\n" + "="*60)
print("Creating variables...")
print("="*60)

x = {}  # (group, subject, teacher, room, start_timeslot) → BoolVar
skipped_subjects = []

for g in GROUPS:
    for sid in GROUP_SUBJECTS.get(g, []):
        s = SUBJECT_DICT[sid]
        hours = (s["theory"] or 0) + (s["practice"] or 0)
        
        # ถ้าวิชามากกว่า periods ต่อวัน ให้ข้ามไป
        if hours > PERIODS_PER_DAY:
            print(f"⚠️  Skipping {g}-{sid}: needs {hours} hours but only {PERIODS_PER_DAY} periods/day")
            skipped_subjects.append((g, sid, hours))
            continue

        teachers = SUBJECT_TEACHERS.get(sid, [])
        if not teachers:
            teachers = ["T00"]  # dummy teacher

        vars_created_for_subject = 0
        
        # สร้างตัวแปรเฉพาะ timeslots ที่ไม่ล้นวัน
        for i in range(len(TIMESLOTS)):
            day = TIMESLOTS[i]["day"]
            day_slots = DAY_TIMESLOTS[day]
            
            # ตรวจสอบว่า i อยู่ในวันนี้หรือไม่
            if i in day_slots:
                pos_in_day = day_slots.index(i)
                
                # ตรวจสอบว่ามีที่พอสำหรับ block หรือไม่
                if pos_in_day + hours <= len(day_slots):
                    # ตรวจสอบว่า indices ต่อเนื่องกัน
                    block_indices = [i + k for k in range(hours)]
                    expected_indices = day_slots[pos_in_day:pos_in_day + hours]
                    
                    if block_indices == expected_indices:
                        for tid in teachers:
                            for rid in ROOMS:
                                x[g, sid, tid, rid, i] = model.NewBoolVar(f"x_{g}_{sid}_{tid}_{rid}_{i}")
                                vars_created_for_subject += 1
        
        if vars_created_for_subject == 0:
            print(f"⚠️  WARNING: No valid slots for {g}-{sid} ({hours} hours)")

print(f"\n✓ Total variables created: {len(x)}")

if skipped_subjects:
    print(f"\n⚠️  Skipped {len(skipped_subjects)} subject assignments (too long):")
    for g, sid, hours in skipped_subjects:
        print(f"  - {g} {sid}: {hours} hours")

# ======================
# CONSTRAINTS
# ======================
print("\n" + "="*60)
print("Adding constraints...")
print("="*60)

# 1. Each subject must be scheduled exactly once
constraint_count = 0
subjects_without_vars = []
for g in GROUPS:
    for sid in GROUP_SUBJECTS.get(g, []):
        vars_ = [x[g, sid, tid, rid, i] for (gg, ss, tid, rid, i) in x if gg==g and ss==sid]
        if vars_:
            model.Add(sum(vars_) == 1)
            constraint_count += 1
        else:
            subjects_without_vars.append((g, sid))
            
print(f"✓ Subject assignment constraints: {constraint_count}")
if subjects_without_vars:
    print(f"⚠️  WARNING: {len(subjects_without_vars)} subjects have no valid timeslots:")
    for g, sid in subjects_without_vars[:5]:  # แสดง 5 รายการแรก
        hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
        print(f"  - {g} {sid} ({hours} hours)")
    if len(subjects_without_vars) > 5:
        print(f"  ... and {len(subjects_without_vars) - 5} more")

# 2. No overlap: GROUP
constraint_count = 0
for g in GROUPS:
    for t in range(len(TIMESLOTS)):
        overlaps = []
        for (gg, sid, tid, rid, i), var in x.items():
            if gg != g:
                continue
            hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
            if i <= t < i + hours:
                overlaps.append(var)
        if overlaps:
            model.Add(sum(overlaps) <= 1)
            constraint_count += 1
print(f"✓ Group no-overlap constraints: {constraint_count}")

# 3. No overlap: TEACHER
all_teachers = set(tid for tids in SUBJECT_TEACHERS.values() for tid in tids)
all_teachers.add("T00")
constraint_count = 0
for tid in all_teachers:
    for t in range(len(TIMESLOTS)):
        overlaps = []
        for (g, sid, tt, rid, i), var in x.items():
            if tt != tid:
                continue
            hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
            if i <= t < i + hours:
                overlaps.append(var)
        if overlaps:
            model.Add(sum(overlaps) <= 1)
            constraint_count += 1
print(f"✓ Teacher no-overlap constraints: {constraint_count}")

# 4. No overlap: ROOM
constraint_count = 0
for rid in ROOMS:
    for t in range(len(TIMESLOTS)):
        overlaps = []
        for (g, sid, tid, rr, i), var in x.items():
            if rr != rid:
                continue
            hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
            if i <= t < i + hours:
                overlaps.append(var)
        if overlaps:
            model.Add(sum(overlaps) <= 1)
            constraint_count += 1
print(f"✓ Room no-overlap constraints: {constraint_count}")

# ======================
# SOLVE
# ======================
print("\n" + "="*60)
print("Starting solver...")
print("="*60)

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 300

print("Solving... (this may take up to 5 minutes)")
status = solver.Solve(model)

print(f"\n{'='*60}")
print(f"SOLVER RESULTS")
print(f"{'='*60}")
print(f"Status: {solver.StatusName(status)}")
print(f"  OPTIMAL: {status == cp_model.OPTIMAL}")
print(f"  FEASIBLE: {status == cp_model.FEASIBLE}")
print(f"  INFEASIBLE: {status == cp_model.INFEASIBLE}")
print(f"Wall time: {solver.WallTime():.2f}s")

# ======================
# INSERT OUTPUT
# ======================
print("\n" + "="*60)
print("Saving results...")
print("="*60)

try:
    db.execute("DELETE FROM output")
    print("✓ Cleared old output data")
except Exception as e:
    print(f"✗ Error clearing output: {e}")

if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print("✓ Solution found! Inserting into database...")
    count = 0
    
    try:
        for (g, sid, tid, rid, i), var in x.items():
            if solver.Value(var) == 1:
                hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
                for k in range(hours):
                    idx = i + k
                    if idx < len(TIMESLOTS):
                        ts_id = TIMESLOTS[idx]["timeslot_id"]
                        db.execute("""
                            INSERT INTO output
                            (group_id, timeslot_id, subject_id, teacher_id, room_id)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (g, ts_id, sid, tid, rid))
                        count += 1
        
        print(f"✓ Inserted {count} rows into output table")
        
        # ตรวจสอบผลลัพธ์
        result = db.fetch_one("SELECT COUNT(*) as count FROM output")
        print(f"✓ Verified: {result['count']} rows in output table")
        
        # แสดงสรุปแต่ละกลุ่ม
        print("\n" + "="*60)
        print("SCHEDULE SUMMARY BY GROUP")
        print("="*60)
        for g in GROUPS:
            result = db.fetch_one(f"SELECT COUNT(DISTINCT subject_id) as count FROM output WHERE group_id = '{g}'")
            scheduled = result['count']
            required = len(GROUP_SUBJECTS.get(g, []))
            status_icon = "✓" if scheduled == required else "⚠️"
            print(f"{status_icon} {g}: {scheduled}/{required} subjects scheduled")
            
    except Exception as e:
        print(f"✗ Error inserting data: {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("✗ No solution found!")
    print("\nPossible reasons:")
    if subjects_without_vars:
        print(f"  - {len(subjects_without_vars)} subjects have no valid timeslots")
    print("  - Not enough rooms for simultaneous classes")
    print("  - Teacher conflicts (one teacher, multiple classes at same time)")
    print("  - Total hours exceed available timeslots")
    print("\nNext steps:")
    print("  1. Check the warnings above")
    print("  2. Consider splitting long subjects")
    print("  3. Add more rooms or timeslots")
    print("  4. Review teacher assignments")

print("\n" + "="*60)
print("DONE!")
print("="*60)