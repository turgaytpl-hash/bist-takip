"""
app.py — Fon Analizi test uygulaması
Çalıştır: streamlit run app.py
"""
import streamlit as st
st.set_page_config(
    page_title="Fon Analizi",
    page_icon="📁",
    layout="wide",
)

from fon_analizi_tab import tab_fon_analizi
tab_fon_analizi()
