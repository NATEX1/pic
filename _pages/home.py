import  streamlit as st
import pandas as pd
import db
import altair as alt

st.title(':red[หน้าหลัก]')
st.divider()

#data fetching
teacher_count = pd.DataFrame(db.fetch_all("select * from teacher"))
student_count = db.fetch_all(
    "SELECT SUM(student_count) AS student_count FROM student_group"
)[0]["student_count"]
room_count = pd.DataFrame(db.fetch_all("select * from room"))
subject_count = pd.DataFrame(db.fetch_all("select * from subject"))
student_group_count = pd.DataFrame(db.fetch_all("SELECT * FROM `student_group`"))


col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="ครูทั้งหมด", value=len(teacher_count), border=True)

with col2:
    st.metric(label="นักเรียนทั้งหมด", value=student_count, border=True)

with col3:
    st.metric(label="ห้องเรียนทั้งหมด", value=len(room_count), border=True)


col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="วิชาทั้งหมด", value=len(subject_count), border=True)

with col2 :
    st.metric(label="กลุ่มการเรียน", value=len(student_group_count), border=True)



# # รวม student_count ตาม group_id
# group_df = (
#     student_group_count
#     .groupby("group_id", as_index=False)["student_count"]
#     .sum()
# )

# chart = alt.Chart(student_group_count).mark_bar(
#     color="#e53935"
# ).encode(
#     x=alt.X(
#         "group_name:N",
#         title="กลุ่มการเรียน",
#         axis=alt.Axis(labelAngle=0)  # <<< แนวนอน
#     ),
#     y=alt.Y("sum(student_count):Q", title="จำนวนนักเรียน"),
#     tooltip=[
#         alt.Tooltip("group_name:N", title="กลุ่มการเรียน"),
#         alt.Tooltip("sum(student_count):Q", title="จำนวนนักเรียน")
#     ]
# )

# st.altair_chart(chart, use_container_width=True)






