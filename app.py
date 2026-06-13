import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import urllib.parse
from geopy.geocoders import Nominatim
import datetime
import plotly.express as px
import requests
import json

st.set_page_config(page_title="Hub Vacanțe", page_icon="🧳", layout="wide")

# --- CONEXIUNE CLOUD ---
LINK_GOOGLE_SCRIPT = "LIPEȘTE_AICI_LINKUL_TĂU"

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
        data = r.json()
        if not data: return None
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
        payload = json.dumps({"nume_vacanta": st.session_state.vacanta_activa, "date": date}, cls=DateEncoder)
        requests.post(LINK_GOOGLE_SCRIPT, data=payload, headers={"Content-Type": "application/json"})

# --- INIȚIALIZARE MEMORIE ---
default_keys = {'orase': {}, 'activitati': [], 'calendar': [], 'bagaje': {}, 'next_act_id': 1, 'next_cal_id': 1, 'vacanta_activa': None}
for key, val in default_keys.items():
    if key not in st.session_state: st.session_state[key] = val

# --- GEOCODING ---
geolocator = Nominatim(user_agent="planificator_vacante_pro")
@st.cache_data
def gaseste_coordonate(nume):
    try:
        loc = geolocator.geocode(f"{nume}, Italia", timeout=5)
        return [loc.latitude, loc.longitude] if loc else [41.8719, 12.5674]
    except: return [41.8719, 12.5674]

# --- MENIU LATERAL ---
st.sidebar.markdown("## 🌍 Hub Vacanțe")
vacante = obtine_lista_vacante()
noua_v = st.sidebar.text_input("➕ Vacanță nouă")
if st.sidebar.button("Creează"):
    if noua_v and noua_v not in vacante:
        st.session_state.vacanta_activa = noua_v
        st.session_state.orase = {}; st.session_state.activitati = []; st.session_state.calendar = []; st.session_state.bagaje = {"Documente": {}}
        sync_to_cloud()
        st.rerun()

if vacante:
    st.session_state.vacanta_activa = st.sidebar.selectbox("📂 Vacanță activă:", vacante, index=vacante.index(st.session_state.vacanta_activa) if st.session_state.vacanta_activa in vacante else 0)
    data = incarca_vacanta_din_cloud(st.session_state.vacanta_activa)
    if data:
        st.session_state.update(data)

# --- PAGINI ---
menu = st.sidebar.radio("Navigare:", ["🗺️ Harta", "📅 Calendar", "🏙️ Orașe", "💰 Buget", "🎒 Bagaje"])

if menu == "🗺️ Harta":
    st.title("🗺️ Harta Generală")
    if st.session_state.orase:
        coords = list(st.session_state.orase.values())[0]["coords"]
        m = folium.Map(location=coords, zoom_start=6)
        for o, d in st.session_state.orase.items(): folium.Marker(d["coords"], popup=o).add_to(m)
        st_folium(m, use_container_width=True)

elif menu == "📅 Calendar":
    st.title("📅 Calendar")
    with st.form("ruta"):
        c1, c2, c3 = st.columns(3)
        plecare = c1.text_input("Plecare"); destinatie = c2.text_input("Sosire"); cost = c3.number_input("Cost")
        if st.form_submit_button("Adaugă"):
            st.session_state.calendar.append({"id": st.session_state.next_cal_id, "data": datetime.date.today(), "de_la": plecare, "pana_la": destinatie, "cost": cost})
            st.session_state.next_cal_id += 1
            sync_to_cloud(); st.rerun()
    for r in st.session_state.calendar:
        with st.container(border=True):
            st.write(f"{r['de_la']} ➔ {r['pana_la']} | {r['cost']}€")

elif menu == "🏙️ Orașe":
    st.title("🏙️ Orașe & Activități")
    o_nume = st.text_input("Oraș nou")
    if st.button("Adaugă"):
        st.session_state.orase[o_nume] = {"coords": gaseste_coordonate(o_nume), "cazare": 0, "food": ""}
        sync_to_cloud(); st.rerun()
    
    for oras in st.session_state.orase:
        with st.expander(oras):
            new_cazare = st.number_input("Cazare €", value=float(st.session_state.orase[oras]['cazare']), key=f"caz_{oras}")
            if st.button("Salvează", key=f"save_{oras}"):
                st.session_state.orase[oras]['cazare'] = new_cazare
                sync_to_cloud(); st.rerun()

elif menu == "💰 Buget":
    st.title("💰 Buget Detaliat")
    total_cazare = sum(d.get("cazare", 0) for d in st.session_state.orase.values())
    total_act = sum(a['cost'] for a in st.session_state.activitati) * 2
    st.metric("Total Estimativ", f"€ {total_cazare + total_act}")
    
    df = pd.DataFrame({"Cat": ["Cazare", "Activități"], "Valoare": [total_cazare, total_act]})
    st.plotly_chart(px.pie(df, values="Valoare", names="Cat"))

elif menu == "🎒 Bagaje":
    st.title("🎒 Bagaje")
    cat = st.text_input("Categorie nouă")
    if st.button("Adaugă Categorie"):
        st.session_state.bagaje[cat] = {}
        sync_to_cloud(); st.rerun()
    
    for c, items in st.session_state.bagaje.items():
        st.subheader(c)
        item = st.text_input(f"Obiect în {c}", key=f"inp_{c}")
        if st.button("Adaugă", key=f"btn_{c}"):
            st.session_state.bagaje[c][item] = False
            sync_to_cloud(); st.rerun()
        for i, val in items.items():
            st.checkbox(i, value=val, key=f"chk_{c}_{i}")
