import streamlit as st
from streamlit_cookies_controller import CookieController
import time

controller = CookieController()

st.write('คุณต้องการออกจากระบบหรือไม่?')
if st.button('ออกจากระบบ'):
    controller.remove('username')
    controller.remove('role')
    time.sleep(1.5)
    st.success('ออกจากระบบสำเร็จกรุณารีเฟรช!')