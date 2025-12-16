import streamlit as st
import pandas as pd
import db

st.title(':red[คาบ]')
st.divider()
upload_data = st.file_uploader("อัปโหลดไฟล์", type=["csv", "xlsx"])

# ==================== CONFIG ====================
TABLE_NAME = "timeslot"
PRIMARY_KEY = "timeslot_id"
REQUIRED_COLS = ['timeslot_id', 'day', 'period', 'start', 'end']
DAY_TYPE_OPTIONS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

# Column config สำหรับเพิ่มใหม่ (แก้ไข timeslot_id ได้)
timeslot_columns_new = {
    "timeslot_id": st.column_config.TextColumn("รหัสคาบ", required=True),
    "timeslot_name": st.column_config.TextColumn("ชื่อคาบ", required=True),
    "timeslot_type": st.column_config.SelectboxColumn("วัน", required=True, options=DAY_TYPE_OPTIONS)
}

# Column config สำหรับแก้ไข (timeslot_id disabled)
timeslot_columns_edit = {
    "timeslot_id": st.column_config.TextColumn("รหัสคาบ", disabled=True),
    "timeslot_name": st.column_config.TextColumn("ชื่อคาบ", required=True),
    "timeslot_type": st.column_config.SelectboxColumn("วัน", required=True, options=DAY_TYPE_OPTIONS)
}


# ==================== FUNCTIONS ====================
def fetch_timeslots():
    """ดึงข้อมูลคาบทั้งหมด"""
    return pd.DataFrame(db.fetch_all(f"SELECT * FROM {TABLE_NAME}"))


def validate_data(df, existing_ids=None):
    """ตรวจสอบความถูกต้องของข้อมูล"""
    errors = []
    warnings = []

    empty_mask = df['timeslot_id'].isna() | (df['timeslot_id'].astype(str).str.strip() == '')
    if empty_mask.any():
        errors.append(f"❌ พบ timeslot_id ว่างเปล่า {empty_mask.sum()} รายการ")

    duplicates = df[df.duplicated(subset=['timeslot_id'], keep=False) & ~empty_mask]
    if not duplicates.empty:
        errors.append(f"❌ พบ timeslot_id ซ้ำในไฟล์ {len(duplicates)} รายการ")

    if existing_ids is not None:
        existing_set = set(existing_ids)
        new_ids = set(df['timeslot_id'].dropna().astype(str).str.strip())
        conflicts = new_ids & existing_set
        if conflicts:
            errors.append(f"❌ พบ timeslot_id ซ้ำกับในระบบ: {', '.join(conflicts)}")

    empty_names = df['timeslot_name'].isna() | (df['timeslot_name'].astype(str).str.strip() == '')
    if empty_names.any():
        warnings.append(f"⚠️ พบ timeslot_name ว่างเปล่า {empty_names.sum()} รายการ")

    invalid_types = ~df['timeslot_type'].isin(DAY_TYPE_OPTIONS) & df['timeslot_type'].notna()
    if invalid_types.any():
        bad_types = df.loc[invalid_types, 'timeslot_type'].unique().tolist()
        errors.append(f"❌ พบ timeslot_type ไม่ถูกต้อง: {', '.join(map(str, bad_types))}")

    return errors, warnings, duplicates


def clean_data(df):
    """ทำความสะอาดข้อมูล"""
    df = df.copy()
    for col in ['timeslot_id', 'timeslot_name']:
        df[col] = df[col].astype(str).str.strip()
    return df


# ==================== MAIN ====================
timeslots = fetch_timeslots()
existing_ids = timeslots['timeslot_id'].tolist() if not timeslots.empty else []

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
            column_config=timeslot_columns_new,
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
                st.dataframe(duplicates, column_config=timeslot_columns_new, use_container_width=True)

        can_save = len(errors) == 0 and len(edited_df) > 0

        if st.button("💾 บันทึก", type="primary", disabled=not can_save, key="save_import"):
            try:
                sql = f"INSERT INTO {TABLE_NAME} (timeslot_id, timeslot_name, timeslot_type) VALUES (?, ?, ?)"
                count = 0
                for _, row in edited_df.iterrows():
                    if row['timeslot_id']:
                        db.execute(sql, (row['timeslot_id'], row['timeslot_name'], row['timeslot_type']))
                        count += 1
                st.success(f"✅ บันทึกสำเร็จ {count} รายการ")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# ==================== EXISTING DATA SECTION ====================
st.divider()
if timeslots.empty:
    st.info("📭 ยังไม่มีข้อมูลในระบบ")
else:
    st.subheader(f"📋 ข้อมูลในระบบ ({len(timeslots)} รายการ)")

    edited_timeslots = st.data_editor(
        timeslots,
        num_rows="dynamic",
        use_container_width=True,
        column_config=timeslot_columns_edit,
        key="existing_editor"
    )

    if not edited_timeslots.equals(timeslots):
        if st.button("💾 บันทึกการแก้ไข", type="primary"):
            try:
                for _, row in edited_timeslots.iterrows():
                    sql = f"UPDATE {TABLE_NAME} SET timeslot_name=?, timeslot_type=? WHERE timeslot_id=?"
                    db.execute(sql, (row['timeslot_name'], row['timeslot_type'], row['timeslot_id']))
                st.success("✅ บันทึกการแก้ไขสำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")