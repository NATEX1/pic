import streamlit as st
from ortools.sat.python import cp_model
from collections import defaultdict
import db
import time
from string import Template
import pandas as pd

# ======================
# PAGE SETUP
# ======================
st.title(":red[ตารางเรียน]")
st.divider()


# ======================
# LOAD GROUPS
# ======================
GROUPS = [g["group_id"] for g in db.fetch_all("SELECT group_id FROM student_group")]


cols = st.columns(5)

output = pd.DataFrame(db.fetch_all("SELECT * FROM output"))

with cols[0]:
    generate_button = st.button(
        label="Generate ตารางใหม่", 
        type="primary")

with cols[1]:
    export_output = st.download_button(label="Export Output", type="primary", 
        data=output.to_csv(index=False).encode('utf-8'),
        file_name='output.csv',
        mime='text/csv')

# Progress bar & status text
progress_bar = st.progress(0)
status_text = st.empty()

# ======================
# FUNCTION TO GENERATE TIMETABLE
# ======================
def generate_timetable():
    status_text.text("🔹 Loading subjects...")
    SUBJECTS = db.fetch_all("SELECT subject_id, theory, practice FROM subject")
    SUBJECT_DICT = {s["subject_id"]: s for s in SUBJECTS}
    time.sleep(0.2)

    status_text.text("🔹 Loading timeslots...")
    TIMESLOTS = db.fetch_all("""
        SELECT timeslot_id, day, period
        FROM timeslot
        WHERE period != 5
        ORDER BY day, period
    """)
    TS_INDEX = {t["timeslot_id"]: i for i, t in enumerate(TIMESLOTS)}
    DAY_TIMESLOTS = defaultdict(list)
    for i, t in enumerate(TIMESLOTS):
        DAY_TIMESLOTS[t["day"]].append(i)
    PERIODS_PER_DAY = max(len(slots) for slots in DAY_TIMESLOTS.values())
    time.sleep(0.2)

    status_text.text("🔹 กำลังโหลดการลงทะเบียน...")
    REG = db.fetch_all("SELECT group_id, subject_id FROM register")
    GROUP_SUBJECTS = defaultdict(list)
    for r in REG:
        GROUP_SUBJECTS[r["group_id"]].append(r["subject_id"])
    time.sleep(0.2)

    status_text.text("🔹 กำลังโหลดงานครู...")
    TEACH = db.fetch_all("SELECT subject_id, teacher_id FROM teach")
    SUBJECT_TEACHERS = defaultdict(list)
    for r in TEACH:
        SUBJECT_TEACHERS[r["subject_id"]].append(r["teacher_id"])
    time.sleep(0.2)

    status_text.text("🔹 กำลังโหลดห้อง...")
    ROOMS = [r["room_id"] for r in db.fetch_all("SELECT room_id FROM room")]
    time.sleep(0.2)

    # ======================
    # CREATE VARIABLES
    # ======================
    status_text.text("🔹 การสร้างตัวแปร...")
    model = cp_model.CpModel()
    x = {}
    skipped_subjects = []

    total_subjects = sum(len(GROUP_SUBJECTS.get(g, [])) for g in GROUPS)
    counter = 0

    for g in GROUPS:
        for sid in GROUP_SUBJECTS.get(g, []):
            counter += 1
            progress_bar.progress(int(counter / total_subjects * 10))  # 10% for variable creation
            s = SUBJECT_DICT[sid]
            hours = (s["theory"] or 0) + (s["practice"] or 0)

            if hours > PERIODS_PER_DAY:
                skipped_subjects.append((g, sid, hours))
                continue

            teachers = SUBJECT_TEACHERS.get(sid, []) or ["T00"]
            for i in range(len(TIMESLOTS)):
                day = TIMESLOTS[i]["day"]
                day_slots = DAY_TIMESLOTS[day]
                if i in day_slots:
                    pos_in_day = day_slots.index(i)
                    if pos_in_day + hours <= len(day_slots):
                        block_indices = [i + k for k in range(hours)]
                        expected_indices = day_slots[pos_in_day:pos_in_day + hours]
                        if block_indices == expected_indices:
                            for tid in teachers:
                                for rid in ROOMS:
                                    x[g, sid, tid, rid, i] = model.NewBoolVar(f"x_{g}_{sid}_{tid}_{rid}_{i}")

    # ======================
    # ADD CONSTRAINTS
    # ======================
    status_text.text("🔹 การเพิ่มข้อจำกัด...")
    time.sleep(0.2)

    # 1. Each subject exactly once
    for g in GROUPS:
        for sid in GROUP_SUBJECTS.get(g, []):
            vars_ = [x[g, sid, tid, rid, i] for (gg, ss, tid, rid, i) in x if gg == g and ss == sid]
            if vars_:
                model.Add(sum(vars_) == 1)

    # 2. No overlap: GROUP
    for g in GROUPS:
        for t in range(len(TIMESLOTS)):
            overlaps = [var for (gg, sid, tid, rid, i), var in x.items()
                        if gg == g and i <= t < i + ((SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0))]
            if overlaps:
                model.Add(sum(overlaps) <= 1)

    # 3. No overlap: TEACHER
    all_teachers = set(tid for tids in SUBJECT_TEACHERS.values() for tid in tids)
    all_teachers.add("T00")
    for tid in all_teachers:
        for t in range(len(TIMESLOTS)):
            overlaps = [var for (g, sid, tt, rid, i), var in x.items()
                        if tt == tid and i <= t < i + ((SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0))]
            if overlaps:
                model.Add(sum(overlaps) <= 1)

    # 4. No overlap: ROOM
    for rid in ROOMS:
        for t in range(len(TIMESLOTS)):
            overlaps = [var for (g, sid, tid, rr, i), var in x.items()
                        if rr == rid and i <= t < i + ((SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0))]
            if overlaps:
                model.Add(sum(overlaps) <= 1)

    # ======================
    # SOLVE
    # ======================
    status_text.text("🔹 ตารางเวลาการแก้ปัญหา...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 300
    status = solver.Solve(model)
    progress_bar.progress(90)

    # ======================
    # INSERT OUTPUT
    # ======================
    status_text.text("🔹 บันทึกผลลัพธ์ลงฐานข้อมูล...")
    db.execute("DELETE FROM output")
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (g, sid, tid, rid, i), var in x.items():
            if solver.Value(var) == 1:
                hours = (SUBJECT_DICT[sid]["theory"] or 0) + (SUBJECT_DICT[sid]["practice"] or 0)
                for k in range(hours):
                    idx = i + k
                    if idx < len(TIMESLOTS):
                        ts_id = TIMESLOTS[idx]["timeslot_id"]
                        db.execute(
                            "INSERT INTO output (group_id, timeslot_id, subject_id, teacher_id, room_id) VALUES (%s,%s,%s,%s,%s)",
                            (g, ts_id, sid, tid, rid)
                        )
    progress_bar.progress(100)
    status_text.text("✅ Completed! ตารางเรียนถูกสร้างแล้ว")
    st.rerun()

# ======================
# BUTTON ACTION
# ======================
if generate_button:
    generate_timetable()


tabs = st.tabs(['ตารางเรียน', 'ตารางสอน'])

with tabs[0]:
    cols = st.columns(5)
    with cols[0]:
        selected_group = st.selectbox("เลือกกลุ่มการเรียน", options=GROUPS)

    # ======================
    # LOAD OUTPUT DATA AND RENDER
    # ======================
    rows = db.fetch_all("""
    SELECT 
        t.day,
        t.period,
        s.subject_name,
        s.subject_id,
        te.teacher_name,
        r.room_name
    FROM output o
    LEFT JOIN timeslot t ON o.timeslot_id = t.timeslot_id
    LEFT JOIN subject s ON o.subject_id = s.subject_id
    LEFT JOIN teacher te ON o.teacher_id = te.teacher_id
    LEFT JOIN room r ON o.room_id = r.room_id
    WHERE o.group_id = %s
    ORDER BY t.day, t.period;
    """, (selected_group,))

    data = {}
    DAY_MAP = {"Mon":"MON","Tue":"TUE","Wed":"WED","Thu":"THU","Fri":"FRI"}

    for r in rows:
        day = DAY_MAP.get(r["day"])
        period = r["period"]
        key = f"{day}_{period}"
        data.setdefault(key, [])
        text = f"<b>{r['subject_id']}</b><br><span style='font-size:10px'>({r['teacher_name']} - ห้อง {r['room_name']})</span>"
        data[key].append(text)

    # Fill empty cells
    for d in ["MON","TUE","WED","THU","FRI"]:
        for p in range(1,13):
            data.setdefault(f"{d}_{p}", [])

    # HTML string
    html_data = {k: "<br>".join(v) if v else "<p style='visibility:hidden;'>-</p>" for k,v in data.items()}

    # Subject list
    SUBJECTS = db.fetch_all("""
    SELECT s.subject_name, s.subject_id, s.theory, s.practice, s.credit
    FROM register r
    JOIN subject s ON r.subject_id = s.subject_id
    WHERE r.group_id=%s
    ORDER BY s.subject_id
    """,(selected_group,))

    group_data = db.fetch_one("SELECT * FROM student_group WHERE group_id = %s", (selected_group))

    for i in range(1, 15):
        key = f"SUBJ_{i}"
        if i-1 < len(SUBJECTS):
            s = SUBJECTS[i-1]
            html_data[key] = f"[{s['subject_id']}] [{s['theory']}-{s['practice']}-{s['credit']}] {s['subject_name']}"
        else:
            html_data[key] = "<p style='visibility:hidden;'>-</p>"

    html_data['GROUP_ID'] = selected_group
    html_data['ADVISOR'] = group_data['advisor']
    html_data['GROUP_NAME'] = group_data['group_name']

    # Render HTML
    with open("timetable.html","r",encoding="utf-8") as f:
        html = Template(f.read()).safe_substitute(html_data)
    st.components.v1.html(html,height=800,scrolling=True)


with tabs[1]:
    TEACHERS = db.fetch_all("SELECT teacher_id, teacher_name FROM teacher")
    teacher_options = {t["teacher_name"]: t["teacher_id"] for t in TEACHERS}

    cols = st.columns(5)
    with cols[0]:
        selected_teacher_name = st.selectbox("เลือกครู", options=list(teacher_options.keys()))
        selected_teacher_id = teacher_options[selected_teacher_name]

    # ======================
    # LOAD OUTPUT DATA
    # ======================
    rows = db.fetch_all("""
    SELECT 
        t.day,
        t.period,
        s.subject_name,
        s.subject_id,
        o.group_id,
        r.room_name
    FROM output o
    LEFT JOIN timeslot t ON o.timeslot_id = t.timeslot_id
    LEFT JOIN subject s ON o.subject_id = s.subject_id
    LEFT JOIN room r ON o.room_id = r.room_id
    WHERE o.teacher_id = %s
    ORDER BY t.day, t.period, o.group_id
    """, (selected_teacher_id,))

    # ======================
    # PROCESS DATA
    # ======================
    DAY_MAP = {"Mon": "MON", "Tue": "TUE", "Wed": "WED", "Thu": "THU", "Fri": "FRI"}
    data = {}

    for r in rows:
        day = DAY_MAP.get(r["day"])
        period = r["period"]
        key = f"{day}_{period}"
        data.setdefault(key, [])
        text = f"<b>{r['subject_id']}</b><br><span style='font-size:10px'>({r['group_id']} - ห้อง {r['room_name']})</span>"
        data[key].append(text)

    # Fill empty cells
    for d in ["MON","TUE","WED","THU","FRI"]:
        for p in range(1,13):
            data.setdefault(f"{d}_{p}", [])

    SUBJECTS = db.fetch_all("""
    SELECT DISTINCT s.subject_name, s.subject_id, s.theory, s.practice, s.credit
    FROM teach t
    JOIN subject s ON t.subject_id = s.subject_id
    WHERE t.teacher_id=%s
    ORDER BY s.subject_id
    """,(selected_teacher_id,))

    html_data = {k: "<br>".join(v) if v else "<p style='visibility:hidden;'>-</p>" for k,v in data.items()}

    # เพิ่มรายชื่อวิชาที่ครูสอน
    for i in range(1, 15):
        key = f"SUBJ_{i}"
        if i-1 < len(SUBJECTS):
            s = SUBJECTS[i-1]
            html_data[key] = f"[{s['subject_id']}] [{s['theory']}-{s['practice']}-{s['credit']}] {s['subject_name']}"
        else:
            html_data[key] = "<p style='visibility:hidden;'>-</p>"

    # เพิ่มชื่อครู
    html_data['TEACHER_NAME'] = selected_teacher_name

    html_data['ADVISOR'] = selected_teacher_name

    # ======================
    # RENDER HTML
    # ======================
    with open("timetable_teacher.html", "r", encoding="utf-8") as f:
        template = Template(f.read())
    html = template.safe_substitute(html_data)

    st.components.v1.html(html, height=800, scrolling=True)
