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
    "day": st.column_config.SelectboxColumn("วัน", required=True, options=DAY_TYPE_OPTIONS),
    "period": st.column_config.NumberColumn("คาบที่", required=True, min_value=1, max_value=20),
    "start": st.column_config.TextColumn("เวลาเริ่ม (HH:MM)", required=True),
    "end": st.column_config.TextColumn("เวลาสิ้นสุด (HH:MM)", required=True),
}

# Column config สำหรับแก้ไข (timeslot_id disabled)
timeslot_columns_edit = {
    "timeslot_id": st.column_config.TextColumn("รหัสคาบ", disabled=True),
    "day": st.column_config.SelectboxColumn("วัน", required=True, options=DAY_TYPE_OPTIONS),
    "period": st.column_config.NumberColumn("คาบที่", required=True, min_value=1, max_value=20),
    "start": st.column_config.TextColumn("เวลาเริ่ม (HH:MM)", required=True),
    "end": st.column_config.TextColumn("เวลาสิ้นสุด (HH:MM)", required=True),
}


# ==================== FUNCTIONS ====================
def fetch_timeslots():
    """ดึงข้อมูลคาบทั้งหมด"""
    return pd.DataFrame(db.fetch_all(f"SELECT * FROM {TABLE_NAME}"))


def convert_time_columns(df):
    """แปลงคอลัมน์เวลาให้เป็น string format HH:MM"""
    df = df.copy()
    for col in ['start', 'end']:
        if col in df.columns:
            # กรณี timedelta (จาก Excel)
            if pd.api.types.is_timedelta64_dtype(df[col]):
                df[col] = df[col].apply(lambda x: str(x).split()[-1][:5] if pd.notna(x) else '')
            # กรณี datetime
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%H:%M')
            # กรณีอื่น แปลงเป็น string
            else:
                df[col] = df[col].astype(str).str.strip()
                # ตัด seconds ออกถ้ามี (HH:MM:SS -> HH:MM)
                df[col] = df[col].apply(lambda x: x[:5] if len(x) >= 5 and ':' in x else x)
    return df


def validate_time_format(time_str):
    """ตรวจสอบรูปแบบเวลา HH:MM"""
    import re
    if pd.isna(time_str) or str(time_str).strip() == '':
        return False
    pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
    return bool(re.match(pattern, str(time_str).strip()))


def validate_data(df, existing_ids=None):
    """ตรวจสอบความถูกต้องของข้อมูล"""
    errors = []
    warnings = []

    # ตรวจสอบ timeslot_id ว่าง
    empty_mask = df['timeslot_id'].isna() | (df['timeslot_id'].astype(str).str.strip() == '')
    if empty_mask.any():
        errors.append(f"❌ พบ timeslot_id ว่างเปล่า {empty_mask.sum()} รายการ")

    # ตรวจสอบ timeslot_id ซ้ำในไฟล์
    duplicates = df[df.duplicated(subset=['timeslot_id'], keep=False) & ~empty_mask]
    if not duplicates.empty:
        errors.append(f"❌ พบ timeslot_id ซ้ำในไฟล์ {len(duplicates)} รายการ")

    # ตรวจสอบ timeslot_id ซ้ำกับในระบบ
    if existing_ids is not None:
        existing_set = set(existing_ids)
        new_ids = set(df['timeslot_id'].dropna().astype(str).str.strip())
        conflicts = new_ids & existing_set
        if conflicts:
            errors.append(f"❌ พบ timeslot_id ซ้ำกับในระบบ: {', '.join(conflicts)}")

    # ตรวจสอบ day ไม่ถูกต้อง
    invalid_days = ~df['day'].isin(DAY_TYPE_OPTIONS) & df['day'].notna()
    if invalid_days.any():
        bad_days = df.loc[invalid_days, 'day'].unique().tolist()
        errors.append(f"❌ พบวันไม่ถูกต้อง: {', '.join(map(str, bad_days))}")

    # ตรวจสอบ period ว่าง
    empty_period = df['period'].isna()
    if empty_period.any():
        warnings.append(f"⚠️ พบ period ว่างเปล่า {empty_period.sum()} รายการ")

    # ตรวจสอบรูปแบบเวลา start
    invalid_start = df['start'].apply(lambda x: not validate_time_format(x))
    if invalid_start.any():
        errors.append(f"❌ พบรูปแบบเวลาเริ่มไม่ถูกต้อง {invalid_start.sum()} รายการ (ต้องเป็น HH:MM)")

    # ตรวจสอบรูปแบบเวลา end
    invalid_end = df['end'].apply(lambda x: not validate_time_format(x))
    if invalid_end.any():
        errors.append(f"❌ พบรูปแบบเวลาสิ้นสุดไม่ถูกต้อง {invalid_end.sum()} รายการ (ต้องเป็น HH:MM)")

    # ตรวจสอบ start > end
    valid_times = ~invalid_start & ~invalid_end
    if valid_times.any():
        invalid_range = df[valid_times].apply(lambda row: row['start'] >= row['end'], axis=1)
        if invalid_range.any():
            errors.append(f"❌ พบเวลาเริ่มมากกว่าหรือเท่ากับเวลาสิ้นสุด {invalid_range.sum()} รายการ")

    return errors, warnings, duplicates


def clean_data(df):
    """ทำความสะอาดข้อมูล"""
    df = df.copy()
    df['timeslot_id'] = df['timeslot_id'].astype(str).str.strip()
    df['day'] = df['day'].astype(str).str.strip()
    df['start'] = df['start'].astype(str).str.strip()
    df['end'] = df['end'].astype(str).str.strip()
    return df


# ==================== MAIN ====================
timeslots = fetch_timeslots()
if not timeslots.empty:
    timeslots = convert_time_columns(timeslots)
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
        # แปลงคอลัมน์เวลา
        df = convert_time_columns(df)

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
                sql = f"INSERT INTO {TABLE_NAME} (timeslot_id, day, period, start, end) VALUES (?, ?, ?, ?, ?)"
                count = 0
                for _, row in edited_df.iterrows():
                    if row['timeslot_id']:
                        db.execute(sql, (row['timeslot_id'], row['day'], row['period'], row['start'], row['end']))
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
                    sql = f"UPDATE {TABLE_NAME} SET day=?, period=?, start=?, end=? WHERE timeslot_id=?"
                    db.execute(sql, (row['day'], row['period'], row['start'], row['end'], row['timeslot_id']))
                st.success("✅ บันทึกการแก้ไขสำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")