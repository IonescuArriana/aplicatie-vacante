import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import datetime
import plotly.express as px
import requests
import json

st.set_page_config(page_title="Hub Vacanțe", page_icon="🧳", layout="wide")

# Link-ul tău corect integrat
LINK_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbzOxtOlXfAYRCMcRbKzcufwBZ9mLtXfu5DoH4TUhAHCsjctFrghADSz2kDGfQmOd58G9g/exec"

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date): return obj.isoformat()
        return super().default(obj)

@st.cache_data(ttl=5)
def obtine_lista_vacante():
    try:
        r = requests.get(f"{LINK_GOOGLE_SCRIPT}?action=get_vacante")
        return r.json() if r.status_code == 200 else []
    except: return []

def incarca_vacanta_din_cloud(nume):
    try:
        r = requests.get(f"{LINK_GOOGLE_SCRIPT}?action=get_data&nume={nume}")
        data = r.json() if r.status_code == 200 else {}
        for ruta in data.get('calendar', []):
            if isinstance(ruta.get('data'), str): ruta['data'] = datetime.date.fromisoformat(ruta['data'])
        return data
    except: return None

def sync_to_cloud():
    if st.session_state.get('vacanta_activa'):
        date = {
            "orase": st.session_state.orase, "activitati": st.session_state.activitati,
            "calendar": st.session_state.calendar, "bagaje": st.session_state.bagaje,
            "next_act_id": st.session_state.next_act_id, "next_cal_id": st.session_state.next_cal_id
        }
        try:
            payload = json.dumps({"nume_vacanta": st.session_state.vacanta_activa, "date": date}, cls=DateEncoder)
            requests.post(LINK_GOOGLE_SCRIPT, data=payload, headers={"Content-Type": "application/json"})
        except: pass

# Inițializare stare
defaults = {'orase': {}, 'activitati': [], 'calendar': [], 'bagaje': {}, 'next_act_id': 1, 'next_cal_id': 1, 'vacanta_activa': None}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# Sidebar
st.sidebar.markdown("## 🌍 Hub Vacanțe")
vacante = obtine_lista_vacante()
noua_v = st.sidebar.text_input("➕ Vacanță nouă")
if st.sidebar.button("Creează"):
    if noua_v and noua_v not in vacante:
        st.session_state.vacanta_activa = noua_v
        st.session_state.orase = {}; st.session_state.activitati = []; st.session_state.calendar = []; st.session_state.bagaje = {}
        sync_to_cloud()
        st.rerun()

if vacante:
    st.session_state.vacanta_activa = st.sidebar.selectbox("📂 Vacanță activă:", vacante, index=vacante.index(st.session_state.vacanta_activa) if st.session_state.vacanta_activa in vacante else 0)
    data = incarca_vacanta_din_cloud(st.session_state.vacanta_activa)
    if data:
        st.session_state.update(data)

# Navigare
menu = st.sidebar.radio("Navigare:", ["📅 Calendar", "🏙️ Orașe", "💰 Buget", "🎒 Bagaje"])

if menu == "📅 Calendar":
    st.title("📅 Calendar")
    with st.form("r"):
        c1, c2, c3 = st.columns(3)
        plecare = c1.text_input("Plecare"); destinatie = c2.text_input("Sosire"); cost = c3.number_input("Cost")
        if st.form_submit_button("Adaugă"):
            st.session_state.calendar.append({"id": st.session_state.next_cal_id, "data": str(datetime.date.today()), "de_la": plecare, "pana_la": destinatie, "cost": cost})
            st.session_state.next_cal_id += 1
            sync_to_cloud(); st.rerun()
    for r in st.session_state.calendar:
        st.info(f"{r['de_la']} ➔ {r['pana_la']} | {r['cost']} €")

elif menu == "🏙️ Orașe":
    st.title("🏙️ Orașe")
    o_nume = st.text_input("Oraș nou")
    if st.button("Adaugă"):
        st.session_state.orase[o_nume] = {"cazare": 0}
        sync_to_cloud(); st.rerun()
    for o in st.session_state.orase:
        val = st.number_input(f"Cazare {o} (€)", value=float(st.session_state.orase[o]['cazare']))
        if st.button(f"Save {o}"):
            st.session_state.orase[o]['cazare'] = val
            sync_to_cloud(); st.rerun()

elif menu == "💰 Buget":
    st.title("💰 Buget")
    tot = sum(d.get("cazare", 0) for d in st.session_state.orase.values()) + sum(a['cost'] for a in st.session_state.calendar)
    st.metric("Total Estimativ", f"{tot} €")

elif menu == "🎒 Bagaje":
    st.title("🎒 Bagaje")
    cat = st.text_input("Categorie")
    if st.button("Adaugă Categorie"):
        st.session_state.bagaje[cat] = {}
        sync_to_cloud(); st.rerun()
