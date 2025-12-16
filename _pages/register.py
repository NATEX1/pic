import streamlit as st
import pandas as pd
import db

# ==================== PAGE ====================
st.title(":red[ลงทะเบียนเรียน]")
st.divider()
upload_file = st.file_uploader("อัปโหลดไฟล์ (csv / xlsx)", type=["csv", "xlsx"])

# ==================== CONFIG ====================
TABLE_NAME = "register"
REQUIRED_COLS = ["group_id", "subject_id"]

# ==================== MASTER DATA ====================
def get_group_options():
    rows = db.fetch_all("SELECT group_id FROM `student_group`")
    return [r["group_id"] for r in rows] if rows else []

def get_subject_options():
    rows = db.fetch_all("SELECT subject_id FROM subject")
    return [r["subject_id"] for r in rows] if rows else []

GROUP_OPTIONS = get_group_options()
SUBJECT_OPTIONS = get_subject_options()

# ==================== COLUMN CONFIG ====================
columns_new = {
    "group_id": st.column_config.SelectboxColumn(
        "กลุ่มเรียน", required=True, options=GROUP_OPTIONS
    ),
    "subject_id": st.column_config.SelectboxColumn(
        "รหัสวิชา", required=True, options=SUBJECT_OPTIONS
    ),
}

columns_edit = {
    "group_id": st.column_config.TextColumn("กลุ่มเรียน", disabled=True),
    "subject_id": st.column_config.TextColumn("รหัสวิชา", disabled=True),
}

# ==================== DB FUNCTIONS ====================
def fetch_register():
    rows = db.fetch_all(f"SELECT group_id, subject_id FROM {TABLE_NAME}")
    return pd.DataFrame(rows, columns=REQUIRED_COLS) if rows else pd.DataFrame(columns=REQUIRED_COLS)

def get_existing_pairs():
    df = fetch_register()
    return set(zip(df["group_id"], df["subject_id"]))

# ==================== UTIL ====================
def clean_data(df):
    df = df.copy()
    for c in REQUIRED_COLS:
        df[c] = df[c].astype(str).str.strip()
    return df

def validate_data(df, existing_pairs):
    errors = []

    # ว่าง
    empty = df["group_id"].eq("") | df["subject_id"].eq("")
    if empty.any():
        errors.append(f"❌ พบข้อมูลว่าง {empty.sum()} รายการ")

    # ซ้ำในไฟล์
    dup_file = df[df.duplicated(subset=REQUIRED_COLS, keep=False)]
    if not dup_file.empty:
        errors.append(f"❌ พบข้อมูลซ้ำในไฟล์ {len(dup_file)} รายการ")

    # ซ้ำในระบบ
    file_pairs = set(zip(df["group_id"], df["subject_id"]))
    conflict = file_pairs & existing_pairs
    if conflict:
        text = ", ".join([f"({g}, {s})" for g, s in conflict])
        errors.append(f"❌ ซ้ำกับข้อมูลในระบบ: {text}")

    # group ไม่ถูกต้อง
    bad_group = ~df["group_id"].isin(GROUP_OPTIONS)
    if bad_group.any():
        errors.append("❌ พบ group_id ไม่อยู่ในระบบ")

    # subject ไม่ถูกต้อง
    bad_subject = ~df["subject_id"].isin(SUBJECT_OPTIONS)
    if bad_subject.any():
        errors.append("❌ พบ subject_id ไม่อยู่ในระบบ")

    return errors, dup_file

# ==================== IMPORT SECTION ====================
existing_pairs = get_existing_pairs()

if upload_file:
    df = (
        pd.read_csv(upload_file)
        if upload_file.name.endswith(".csv")
        else pd.read_excel(upload_file)
    )

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        st.error(f"❌ ไม่พบคอลัมน์: {', '.join(missing)}")
    else:
        st.subheader("📋 Preview & แก้ไขข้อมูล")

        edited_df = st.data_editor(
            df[REQUIRED_COLS],
            num_rows="dynamic",
            use_container_width=True,
            column_config=columns_new,
            key="import_editor",
        )

        edited_df = clean_data(edited_df)
        errors, dup_file = validate_data(edited_df, existing_pairs)

        st.info(f"📊 จำนวนข้อมูล: {len(edited_df)}")

        for e in errors:
            st.error(e)

        if not dup_file.empty:
            with st.expander("ดูข้อมูลที่ซ้ำในไฟล์"):
                st.dataframe(dup_file, use_container_width=True)

        can_save = len(errors) == 0 and len(edited_df) > 0

        if st.button("💾 บันทึก", type="primary", disabled=not can_save, key="save_import"):
            try:
                sql = f"INSERT INTO {TABLE_NAME} (group_id, subject_id) VALUES (?, ?)"
                count = 0
                for _, r in edited_df.iterrows():
                    if r.group_id and r.subject_id:
                        db.execute(sql, (r.group_id, r.subject_id))
                        count += 1
                st.success(f"✅ บันทึกสำเร็จ {count} รายการ")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# ==================== EXISTING DATA ====================
st.divider()
register_df = fetch_register()

if register_df.empty:
    st.info("📭 ยังไม่มีข้อมูลในระบบ")
else:
    st.subheader(f"📋 ข้อมูลในระบบ ({len(register_df)} รายการ)")

    edited_existing = st.data_editor(
        register_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config=columns_edit,
        key="existing_editor",
    )

    if not edited_existing.equals(register_df):
        if st.button("💾 บันทึกการแก้ไข", type="primary"):
            try:
                db.execute(f"DELETE FROM {TABLE_NAME}")
                sql = f"INSERT INTO {TABLE_NAME} (group_id, subject_id) VALUES (?, ?)"
                for _, r in edited_existing.iterrows():
                    db.execute(sql, (r.group_id, r.subject_id))
                st.success("✅ บันทึกการแก้ไขเรียบร้อย")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")