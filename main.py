import streamlit as st
from streamlit_cookies_controller import CookieController
import time
controller = CookieController()

if not (controller.get('username') and controller.get('role')):
    tab1, tab2 = st.tabs(['อาจารย์', 'ผู้ดูแลระบบ'])

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
        st.Page('_pages/timetable.py'),
    ]

    pg = st.navigation(pages, position='hidden')
    pg.run()

    with st.sidebar:
        st.page_link(st.Page('_pages/home.py'), label='หน้าแรก', icon=':material/home:')
        st.page_link(st.Page('_pages/timetable.py'), label='ตาราง', icon=':material/home:')