import streamlit as st
import pandas as pd
import db

st.title(':red[รายวิชา]')
st.divider()
upload_data = st.file_uploader("อัปโหลดไฟล์", type=["csv", "xlsx"])

# ==================== CONFIG ====================
TABLE_NAME = "subject"
PRIMARY_KEY = "subject_id"
REQUIRED_COLS = ['subject_id', 'subject_name', 'theory', 'practice', 'credit']

# Column config สำหรับเพิ่มใหม่ (แก้ไข subject_id ได้)
subject_columns_new = {
    "subject_id": st.column_config.TextColumn("รหัสวิชา", required=True),
    "subject_name": st.column_config.TextColumn("ชื่อวิชา", required=True),
    "theory": st.column_config.NumberColumn("ทฤษฎี", required=True, min_value=0),
    "practice": st.column_config.NumberColumn("ปฏิบัติ", required=True, min_value=0),
    "credit": st.column_config.NumberColumn("หน่วยกิต", required=True, min_value=0)
}

# Column config สำหรับแก้ไข (subject_id disabled)
subject_columns_edit = {
    "subject_id": st.column_config.TextColumn("รหัสวิชา", disabled=True),
    "subject_name": st.column_config.TextColumn("ชื่อวิชา", required=True),
    "theory": st.column_config.NumberColumn("ทฤษฎี", required=True, min_value=0),
    "practice": st.column_config.NumberColumn("ปฏิบัติ", required=True, min_value=0),
    "credit": st.column_config.NumberColumn("หน่วยกิต", required=True, min_value=0)
}

# ==================== FUNCTIONS ====================
def fetch_subjects():
    """ดึงข้อมูลรายวิชาทั้งหมด"""
    return pd.DataFrame(db.fetch_all(f"SELECT * FROM {TABLE_NAME}"))


def validate_data(df, existing_ids=None):
    """ตรวจสอบความถูกต้องของข้อมูล"""
    errors = []
    warnings = []

    empty_mask = df['subject_id'].isna() | (df['subject_id'].astype(str).str.strip() == '')
    if empty_mask.any():
        errors.append(f"❌ พบ subject_id ว่างเปล่า {empty_mask.sum()} รายการ")

    duplicates = df[df.duplicated(subset=['subject_id'], keep=False) & ~empty_mask]
    if not duplicates.empty:
        errors.append(f"❌ พบ subject_id ซ้ำในไฟล์ {len(duplicates)} รายการ")

    if existing_ids is not None:
        existing_set = set(existing_ids)
        new_ids = set(df['subject_id'].dropna().astype(str).str.strip())
        conflicts = new_ids & existing_set
        if conflicts:
            errors.append(f"❌ พบ subject_id ซ้ำกับในระบบ: {', '.join(conflicts)}")

    empty_names = df['subject_name'].isna() | (df['subject_name'].astype(str).str.strip() == '')
    if empty_names.any():
        warnings.append(f"⚠️ พบ subject_name ว่างเปล่า {empty_names.sum()} รายการ")

    return errors, warnings, duplicates


def clean_data(df):
    """ทำความสะอาดข้อมูล"""
    df = df.copy()
    for col in ['subject_id', 'subject_name']:
        df[col] = df[col].astype(str).str.strip()
    return df


# ==================== MAIN ====================
subjects = fetch_subjects()
existing_ids = subjects['subject_id'].tolist() if not subjects.empty else []

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
                st.dataframe(duplicates, column_config=subject_columns_new, use_container_width=True)

        can_save = len(errors) == 0 and len(edited_df) > 0

        if st.button("💾 บันทึก", type="primary", disabled=not can_save, key="save_import"):
            try:
                sql = f"INSERT INTO {TABLE_NAME} (subject_id, subject_name, theory, practice, credit) VALUES (?, ?, ?, ?, ?)"
                count = 0
                for _, row in edited_df.iterrows():
                    if row['subject_id']:
                        db.execute(sql, (row['subject_id'], row['subject_name'], row['theory'], row['practice'], row['credit']))
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
                    sql = f"UPDATE {TABLE_NAME} SET subject_name=?, theory=?, practice=?, credit=? WHERE subject_id=?"
                    db.execute(sql, (row['subject_name'], row['theory'], row['practice'], row['credit'], row['subject_id']))
                st.success("✅ บันทึกการแก้ไขสำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")