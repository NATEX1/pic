import streamlit as st
import pandas as pd
import db

st.title(':blue[กลุ่มการเรียน]')
st.divider()
upload_data = st.file_uploader("อัปโหลดไฟล์", type=["csv", "xlsx"])

# ==================== CONFIG ====================
TABLE_NAME = "student_group"
PRIMARY_KEY = "group_id"
REQUIRED_COLS = ['group_id', 'group_name', 'student_count', 'advisor']

# Column config สำหรับเพิ่มใหม่ (แก้ไข group_id ได้)
group_columns_new = {
    "group_id": st.column_config.TextColumn("รหัสกลุ่มการเรียน", required=True),
    "group_name": st.column_config.TextColumn("ชื่อกลุ่มการเรียน", required=True),
    "student_count": st.column_config.NumberColumn("จำนวนนักเรียน", required=True, default=0),
    "advisor": st.column_config.TextColumn("ครูประจำชั้น", required=True)
}

# Column config สำหรับแก้ไข (group_id disabled)
group_columns_edit = {
    "group_id": st.column_config.TextColumn("รหัสกลุ่มการเรียน", disabled=True),
    "group_name": st.column_config.TextColumn("ชื่อกลุ่มการเรียน", required=True),
    "student_count": st.column_config.NumberColumn("จำนวนนักเรียน", required=True, default=0),
    "advisor": st.column_config.TextColumn("ครูประจำชั้น", required=True)
}


# ==================== FUNCTIONS ====================
def fetch_groups():
    """ดึงข้อมูลกลุ่มการเรียนทั้งหมด"""
    return pd.DataFrame(db.fetch_all(f"SELECT * FROM {TABLE_NAME}"))


def validate_data(df, existing_ids=None):
    """ตรวจสอบความถูกต้องของข้อมูล"""
    errors = []
    warnings = []

    empty_mask = df['group_id'].isna() | (df['group_id'].astype(str).str.strip() == '')
    if empty_mask.any():
        errors.append(f"❌ พบ group_id ว่างเปล่า {empty_mask.sum()} รายการ")

    duplicates = df[df.duplicated(subset=['group_id'], keep=False) & ~empty_mask]
    if not duplicates.empty:
        errors.append(f"❌ พบ group_id ซ้ำในไฟล์ {len(duplicates)} รายการ")

    if existing_ids is not None:
        existing_set = set(existing_ids)
        new_ids = set(df['group_id'].dropna().astype(str).str.strip())
        conflicts = new_ids & existing_set
        if conflicts:
            errors.append(f"❌ พบ group_id ซ้ำกับในระบบ: {', '.join(conflicts)}")

    empty_names = df['group_name'].isna() | (df['group_name'].astype(str).str.strip() == '')
    if empty_names.any():
        warnings.append(f"⚠️ พบ group_name ว่างเปล่า {empty_names.sum()} รายการ")

    empty_advisor = df['advisor'].isna() | (df['advisor'].astype(str).str.strip() == '')
    if empty_advisor.any():
        warnings.append(f"⚠️ พบ advisor ว่างเปล่า {empty_advisor.sum()} รายการ")

    return errors, warnings, duplicates


def clean_data(df):
    """ทำความสะอาดข้อมูล"""
    df = df.copy()
    for col in ['group_id', 'group_name', 'advisor']:
        df[col] = df[col].astype(str).str.strip()
    return df


# ==================== MAIN ====================
groups = fetch_groups()
existing_ids = groups['group_id'].tolist() if not groups.empty else []

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
            column_config=group_columns_new,
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
                st.dataframe(duplicates, column_config=group_columns_new, use_container_width=True)

        can_save = len(errors) == 0 and len(edited_df) > 0

        if st.button("💾 บันทึก", type="primary", disabled=not can_save, key="save_import"):
            try:
                sql = f"INSERT INTO {TABLE_NAME} (group_id, group_name, student_count, advisor) VALUES (?, ?, ?, ?)"
                count = 0
                for _, row in edited_df.iterrows():
                    if row['group_id']:
                        db.execute(sql, (row['group_id'], row['group_name'], row['student_count'], row['advisor']))
                        count += 1
                st.success(f"✅ บันทึกสำเร็จ {count} รายการ")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# ==================== EXISTING DATA SECTION ====================
st.divider()
if groups.empty:
    st.info("📭 ยังไม่มีข้อมูลในระบบ")
else:
    st.subheader(f"📋 ข้อมูลในระบบ ({len(groups)} รายการ)")

    edited_groups = st.data_editor(
        groups,
        num_rows="dynamic",
        use_container_width=True,
        column_config=group_columns_edit,
        key="existing_editor"
    )

    if not edited_groups.equals(groups):
        if st.button("💾 บันทึกการแก้ไข", type="primary"):
            try:
                for _, row in edited_groups.iterrows():
                    sql = f"UPDATE {TABLE_NAME} SET group_name=?, student_count=?, advisor=? WHERE group_id=?"
                    db.execute(sql, (row['group_name'], row['student_count'], row['advisor'], row['group_id']))
                st.success("✅ บันทึกการแก้ไขสำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")