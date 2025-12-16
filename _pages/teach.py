import streamlit as st
import pandas as pd
import db

st.title(':red[แผนการสอน]')
st.divider()
upload_data = st.file_uploader("อัปโหลดไฟล์", type=["csv", "xlsx"])

# ==================== CONFIG ====================
TABLE_NAME = "teach"
PRIMARY_KEY = "teacher_id"
REQUIRED_COLS = ['teacher_id', 'subject_id']

# ==================== OPTIONS ====================
def get_teacher_options():
    result = db.fetch_all("SELECT teacher_id FROM teacher")
    if not result:
        return []
    return [row['teacher_id'] for row in result]

def get_subject_options():
    result = db.fetch_all("SELECT DISTINCT subject_id FROM register")
    if not result:
        return []
    return [row['subject_id'] for row in result]

TEACHER_OPTIONS = get_teacher_options()
SUBJECT_OPTIONS = get_subject_options()

# ==================== COLUMN CONFIG ====================
subject_columns_new = {
    "teacher_id": st.column_config.SelectboxColumn(
        "รหัสอาจารย์",
        required=True,
        options=TEACHER_OPTIONS
    ),
    "subject_id": st.column_config.SelectboxColumn(
        "รหัสวิชา",
        required=True,
        options=SUBJECT_OPTIONS
    )
}

subject_columns_edit = {
    "teacher_id": st.column_config.SelectboxColumn(
        "รหัสอาจารย์",
        required=True,
        options=TEACHER_OPTIONS
    ),
    "subject_id": st.column_config.SelectboxColumn(
        "รหัสวิชา",
        required=True,
        options=SUBJECT_OPTIONS
    )
}

# ==================== FUNCTIONS ====================
def fetch_subjects():
    result = db.fetch_all(
        f"SELECT teacher_id, subject_id FROM {TABLE_NAME}"
    )
    if not result:
        return pd.DataFrame(columns=REQUIRED_COLS)
    return pd.DataFrame(result)


def validate_data(df, existing_ids=None):
    errors = []
    warnings = []

    empty_mask = df['teacher_id'].isna() | (df['teacher_id'].astype(str).str.strip() == '')
    if empty_mask.any():
        errors.append(f"❌ พบ teacher_id ว่างเปล่า {empty_mask.sum()} รายการ")

    duplicates = df[df.duplicated(subset=['teacher_id'], keep=False) & ~empty_mask]
    if not duplicates.empty:
        errors.append(f"❌ พบ teacher_id ซ้ำในไฟล์ {len(duplicates)} รายการ")

    if existing_ids is not None:
        existing_set = set(existing_ids)
        new_ids = set(df['teacher_id'].dropna().astype(str).str.strip())
        conflicts = new_ids & existing_set
        if conflicts:
            errors.append(f"❌ พบ teacher_id ซ้ำกับในระบบ: {', '.join(conflicts)}")

    empty_subjects = df['subject_id'].isna() | (df['subject_id'].astype(str).str.strip() == '')
    if empty_subjects.any():
        warnings.append(f"⚠️ พบ subject_id ว่างเปล่า {empty_subjects.sum()} รายการ")

    # แปลง TEACHER_OPTIONS เป็น string เพื่อเปรียบเทียบ
    valid_teachers = [str(t) for t in TEACHER_OPTIONS]
    valid_subjects = [str(s) for s in SUBJECT_OPTIONS]

    invalid_teachers = ~df['teacher_id'].astype(str).isin(valid_teachers) & df['teacher_id'].notna()
    if invalid_teachers.any():
        bad_teachers = df.loc[invalid_teachers, 'teacher_id'].unique().tolist()
        errors.append(
            f"❌ พบ teacher_id ไม่มีในระบบ: {', '.join(map(str, bad_teachers))}"
        )

    invalid_subjects = ~df['subject_id'].astype(str).isin(valid_subjects) & df['subject_id'].notna()
    if invalid_subjects.any():
        bad_subjects = df.loc[invalid_subjects, 'subject_id'].unique().tolist()
        errors.append(
            f"❌ พบ subject_id ไม่มีในระบบ: {', '.join(map(str, bad_subjects))}"
        )

    return errors, warnings, duplicates


def clean_data(df):
    df = df.copy()
    for col in ['teacher_id', 'subject_id']:
        df[col] = df[col].astype(str).str.strip()
    return df

# ==================== MAIN ====================
subjects = fetch_subjects()
existing_ids = subjects['teacher_id'].astype(str).tolist() if not subjects.empty else []

# ==================== IMPORT SECTION ====================
if upload_data is not None:
    if upload_data.name.endswith('.csv'):
        df = pd.read_csv(upload_data)
    else:
        df = pd.read_excel(upload_data)

    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing_cols:
        st.error(f"❌ ไม่พบคอลัมน์: {', '.join(missing_cols)}")
    else:
        st.subheader("📋 Preview และแก้ไขข้อมูล")

        # แปลงเป็น string ก่อนแสดง
        df['teacher_id'] = df['teacher_id'].astype(str)
        df['subject_id'] = df['subject_id'].astype(str)

        edited_df = st.data_editor(
            df[REQUIRED_COLS],
            num_rows="dynamic",
            use_container_width=True,
            column_config=subject_columns_new,
            key="import_editor"
        )

        edited_df = clean_data(edited_df)
        errors, warnings, duplicates = validate_data(edited_df, existing_ids)

        st.info(f"📊 จำนวนทั้งหมด: {len(edited_df)} รายการ")

        for warning in warnings:
            st.warning(warning)

        for error in errors:
            st.error(error)

        if not duplicates.empty:
            with st.expander("ดูรายการที่ซ้ำ"):
                st.dataframe(
                    duplicates,
                    column_config=subject_columns_new,
                    use_container_width=True
                )

        can_save = len(errors) == 0 and len(edited_df) > 0

        if st.button("💾 บันทึก", type="primary", disabled=not can_save):
            try:
                sql = f"""
                    INSERT INTO {TABLE_NAME} (teacher_id, subject_id)
                    VALUES (%s, %s)
                """
                count = 0
                for _, row in edited_df.iterrows():
                    db.execute(sql, (row['teacher_id'], row['subject_id']))
                    count += 1

                st.success(f"✅ บันทึกสำเร็จ {count} รายการ")
                st.balloons()
                st.rerun()

            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# ==================== EXISTING DATA SECTION ====================
st.divider()
if subjects.empty:
    st.info("📭 ยังไม่มีข้อมูลในระบบ")
else:
    st.subheader(f"📋 ข้อมูลในระบบ ({len(subjects)} รายการ)")

    # แปลงเป็น string ก่อนแสดง
    subjects['teacher_id'] = subjects['teacher_id'].astype(str)
    subjects['subject_id'] = subjects['subject_id'].astype(str)

    edited_subjects = st.data_editor(
        subjects,
        num_rows="dynamic",
        use_container_width=True,
        column_config=subject_columns_edit,
        key="existing_editor"
    )

    if not edited_subjects.equals(subjects):
        if st.button("💾 บันทึกการแก้ไข", type="primary"):
            try:
                for _, row in edited_subjects.iterrows():
                    db.execute(
                        f"""
                        UPDATE {TABLE_NAME}
                        SET subject_id=%s
                        WHERE teacher_id=%s
                        """,
                        (row['subject_id'], row['teacher_id'])
                    )
                st.success("✅ บันทึกการแก้ไขสำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")