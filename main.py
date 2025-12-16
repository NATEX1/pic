import streamlit as st
from streamlit_cookies_controller import CookieController
import time
import db

controller = CookieController()

if not (controller.get('username') and controller.get('role')):
    st.title(":red[เข้าสู่ระบบ]")
    tab1, tab2 = st.tabs(['อาจารย์', 'ผู้ดูแลระบบ'])

    with tab1: 
        with st.form('teacher_form'):
            username = st.text_input('รหัสอาจารย์')
            password = st.text_input('รหัสผ่าน', type='password')
            
            if st.form_submit_button('เข้าสู่ระบบ', type='primary'):
                user = db.fetch_one("SELECT * FROM teachers WHERE teacher_id = %s AND idcard = %s", (username, password))

                if user:
                    controller.set('username', 'admin')
                    controller.set('role', 'admin')
                    st.success('เข้าสู่ระบบสำเร็จ')
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error('รหัสผ่านไม่ถูกต้อง.')

    with tab2:
        with st.form('admin_form'):
            username = st.text_input('ชื่อผู้ใช้')
            password = st.text_input('รหัสผ่าน', type='password')
            
            if st.form_submit_button('เข้าสู่ระบบ', type='primary'):
                if username == 'admin' and password == '123456':
                    controller.set('username', 'admin')
                    controller.set('role', 'admin')
                    st.success('เข้าสู่ระบบสำเร็จ')
                    time.sleep(1.5)
                    st.rerun()
                


else:
    st.set_page_config(layout='wide')
    pages = [
        st.Page('_pages/home.py'),
        st.Page('_pages/subjects.py'),
        st.Page('_pages/teachers.py'),
        st.Page('_pages/rooms.py'),
        st.Page('_pages/timetable.py'),
        st.Page('_pages/logout.py'),
        st.Page('_pages/groups.py'),
    ]

    pg = st.navigation(pages, position='hidden')
    pg.run()

    with st.sidebar:
        st.page_link(st.Page('_pages/home.py'), label='หน้าแรก', icon=':material/home:')
        st.page_link(st.Page('_pages/teachers.py'), label='อาจารย์', icon=':material/group:')
        st.page_link(st.Page('_pages/subjects.py'), label='รายวิชา', icon=':material/book:')
        st.page_link(st.Page('_pages/rooms.py'), label='ห้องเรียน', icon=':material/meeting_room:')
        st.page_link(st.Page('_pages/groups.py'), label='กลุ่มการเรียร', icon=':material/table_view:')
        st.page_link(st.Page('_pages/timetable.py'), label='ตาราง', icon=':material/table_view:')

        st.divider()

        st.page_link(st.Page('_pages/logout.py'), label='ออกจากระบบ', icon=':material/logout:')