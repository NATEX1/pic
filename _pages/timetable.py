import streamlit as st
import db

st.title(':red[ตาราง]')
st.divider()

GROUPS = db.fetch_all("SELECT group_id FROM student_group")


col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.selectbox('เลือกกลุ่มการเรียน', options=[''])

with open("timetable.html", "r", encoding="utf-8") as f:
    html = f.read()

st.components.v1.html(html, height=800)
