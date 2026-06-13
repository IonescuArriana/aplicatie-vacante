import os
import json
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import urllib.parse
from geopy.geocoders import Nominatim
import datetime
import plotly.express as px

# --- SETĂRI PAGINĂ ȘI TEMĂ NATIVĂ ---
st.set_page_config(page_title="Hub Vacanțe", page_icon="🧳", layout="wide")

if not os.path.exists(".streamlit"):
    os.makedirs(".streamlit")
theme_config = """
[theme]
base="light"
primaryColor="#D81B60"
backgroundColor="#FFF5F8"
secondaryBackgroundColor="#FFE4EC"
textColor="#333333"
font="sans serif"
"""
config_path = ".streamlit/config.toml"
if not os.path.exists(config_path):
    with open(config_path, "w") as f:
        f.write(theme_config)
    st.rerun()

# ==========================================
# PLASĂ DE SIGURANȚĂ PENTRU MEMORIE (Repară eroarea roșie)
# ==========================================
# Asigurăm aplicația că variabilele de bază există mereu, chiar dacă sunt goale.
default_keys = {
    'orase': {}, 'activitati': [], 'calendar': [],
    'bagaje': {}, 'next_act_id': 1, 'next_cal_id': 1,
    'loaded_vacanta': None, 'vacanta_activa': None
}
for key, val in default_keys.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- SISTEMUL DE BAZĂ DE DATE LOCALĂ (JSON) ---
DATA_DIR = "salvari_vacante"
os.makedirs(DATA_DIR, exist_ok=True)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)


def salveaza_vacanta_in_fisier(nume_vacanta, data_dict):
    cale = os.path.join(DATA_DIR, f"{nume_vacanta}.json")
    with open(cale, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, cls=DateEncoder, indent=4, ensure_ascii=False)


def incarca_vacanta_din_fisier(nume_vacanta):
    cale = os.path.join(DATA_DIR, f"{nume_vacanta}.json")
    if os.path.exists(cale):
        with open(cale, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for ruta in data.get('calendar', []):
                if isinstance(ruta['data'], str):
                    ruta['data'] = datetime.date.fromisoformat(ruta['data'])
            return data
    return None


def sync_to_file():
    if st.session_state.get('vacanta_activa'):
        date_curente = {
            "orase": st.session_state.orase,
            "activitati": st.session_state.activitati,
            "calendar": st.session_state.calendar,
            "bagaje": st.session_state.bagaje,
            "next_act_id": st.session_state.next_act_id,
            "next_cal_id": st.session_state.next_cal_id
        }
        salveaza_vacanta_in_fisier(st.session_state.vacanta_activa, date_curente)


# --- GEOCODING ---
geolocator = Nominatim(user_agent="planificator_vacante_pro")


@st.cache_data
def gaseste_coordonate(nume_locatie, fallback_coords=[41.8719, 12.5674]):
    try:
        locatie = geolocator.geocode(nume_locatie, timeout=5)
        if locatie: return [locatie.latitude, locatie.longitude]
    except:
        pass
    return fallback_coords


# ==========================================
# MENIU LATERAL: HUB-UL DE VACANȚE
# ==========================================
st.sidebar.markdown("## 🌍 Hub Vacanțe")

vacante_disponibile = [f.replace('.json', '') for f in os.listdir(DATA_DIR) if f.endswith('.json')]

with st.sidebar.expander("➕ Creează Vacanță Nouă"):
    noua_vacanta = st.text_input("Nume vacanță (ex: Grecia 2027)")
    if st.button("Creează Fișier"):
        if noua_vacanta and noua_vacanta not in vacante_disponibile:
            date_default = {
                "orase": {}, "activitati": [], "calendar": [],
                "bagaje": {"Documente": {"Pașaport": False, "Bilete": False}, "Electronice": {"Încărcător": False}},
                "next_act_id": 1, "next_cal_id": 1
            }
            salveaza_vacanta_in_fisier(noua_vacanta, date_default)
            # Setăm ca activă și forțăm reîncărcarea memoriei
            st.session_state.vacanta_activa = noua_vacanta
            st.session_state.loaded_vacanta = None
            st.rerun()

st.sidebar.divider()

if not vacante_disponibile:
    st.warning("Nu ai nicio vacanță în baza de date. Creează una din meniul de sus!")
    st.stop()

vacanta_activa = st.sidebar.selectbox("📂 Selectează Vacanța Activă:", vacante_disponibile,
                                      index=vacante_disponibile.index(
                                          st.session_state.vacanta_activa) if st.session_state.vacanta_activa in vacante_disponibile else 0)

# Încărcăm datele DOAR dacă am schimbat vacanța
if st.session_state.loaded_vacanta != vacanta_activa:
    data_vacanta = incarca_vacanta_din_fisier(vacanta_activa)
    if data_vacanta:
        st.session_state.orase = data_vacanta.get('orase', {})
        st.session_state.activitati = data_vacanta.get('activitati', [])
        st.session_state.calendar = data_vacanta.get('calendar', [])
        st.session_state.bagaje = data_vacanta.get('bagaje', {})
        st.session_state.next_act_id = data_vacanta.get('next_act_id', 1)
        st.session_state.next_cal_id = data_vacanta.get('next_cal_id', 1)

    st.session_state.loaded_vacanta = vacanta_activa
    st.session_state.vacanta_activa = vacanta_activa

st.sidebar.divider()
menu = st.sidebar.radio("Meniu Navigare:", [
    "🗺️ Harta Generală",
    "📅 Calendar & Transport",
    "🏙️ Orașe & Cazare",
    "💰 Buget Detaliat (Grafice)",
    "🎒 Checklist Bagaje"
])


def get_gmaps_link(query):
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"


st.markdown(f"##### ✈️ Modifici datele pentru: **{vacanta_activa.upper()}**")
st.divider()

# ==========================================
# 1. HARTA GENERALĂ
# ==========================================
if menu == "🗺️ Harta Generală":
    st.title("🗺️ Traseul General")

    if st.session_state.orase:
        first_city_coords = list(st.session_state.orase.values())[0]["coords"]
        m_general = folium.Map(location=first_city_coords, zoom_start=6)

        for oras, detalii in st.session_state.orase.items():
            folium.Marker(
                detalii["coords"],
                popup=f"📍 {oras} (Cazare: {detalii['cazare']}€)",
                tooltip=oras,
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m_general)

        st_folium(m_general, use_container_width=True, height=500)
    else:
        st.info("Harta este goală. Adaugă orașe din meniul alăturat!")

# ==========================================
# 2. CALENDAR & TRANSPORT
# ==========================================
elif menu == "📅 Calendar & Transport":
    st.title("📅 Jurnal de Călătorie & Rute")

    tab_traseu, tab_adauga = st.tabs(["🛣️ Traseul Meu", "➕ Adaugă Rută Nouă"])

    with tab_adauga:
        with st.form("form_ruta_noua", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            data_ruta = col1.date_input("Data Deplasării", datetime.date.today())
            plecare = col2.text_input("Oraș Plecare")
            destinatie = col3.text_input("Oraș Destinație")

            col4, col5 = st.columns(2)
            mijloc = col4.selectbox("Cum călătoriți?",
                                    ["✈️ Zbor", "🚆 Tren", "🚌 Autobuz", "🚗 Mașină", "🚕 Taxi", "🚢 Feribot"])
            cost_ruta = col5.number_input("Cost total (EUR) pt. Toți", min_value=0.0, step=1.0)

            if st.form_submit_button("Salvează Ruta"):
                if plecare and destinatie:
                    st.session_state.calendar.append({
                        "id": st.session_state.next_cal_id, "data": data_ruta,
                        "de_la": plecare, "pana_la": destinatie,
                        "mijloc": mijloc, "cost": cost_ruta
                    })
                    st.session_state.next_cal_id += 1
                    sync_to_file()
                    st.success("Rută adăugată cu succes!")
                    st.rerun()

    with tab_traseu:
        rute_sortate = sorted(st.session_state.calendar, key=lambda x: x['data'])
        if not rute_sortate: st.info("Nu ai nicio rută planificată încă.")

        for ruta in rute_sortate:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1: st.subheader(f"{ruta['data'].strftime('%d %b')}")
                with c2: st.markdown(f"#### {ruta['de_la']} ➔ {ruta['mijloc']} ➔ {ruta['pana_la']}")
                with c3:
                    st.markdown(f"💶 **{ruta['cost']} €**")
                    if st.button("Șterge ❌", key=f"del_cal_{ruta['id']}", use_container_width=True):
                        st.session_state.calendar = [r for r in st.session_state.calendar if r['id'] != ruta['id']]
                        sync_to_file()
                        st.rerun()

# ==========================================
# 3. ORAȘE & CAZARE
# ==========================================
elif menu == "🏙️ Orașe & Cazare":
    st.title("🏙️ Gestionează Orașe și Activități")

    with st.expander("➕ Click aici pentru a adăuga un oraș NOU", expanded=False):
        with st.form("form_oras_nou", clear_on_submit=True):
            col1, col2 = st.columns(2)
            o_nume = col1.text_input("Nume Oraș (ex: Roma)")
            o_cazare = col2.number_input("Cost TOTAL Cazare în acest oraș (EUR)", min_value=0.0, step=10.0)
            o_food = st.text_input("Ce mâncăm aici? (Recomandări)")

            if st.form_submit_button("Salvează Orașul"):
                if o_nume:
                    with st.spinner(f'Caut coordonatele pentru {o_nume}...'):
                        coords = gaseste_coordonate(f"{o_nume}")
                    st.session_state.orase[o_nume] = {"coords": coords, "food": o_food, "cazare": o_cazare}
                    sync_to_file()
                    st.success("Oraș adăugat!")
                    st.rerun()

    st.divider()

    if st.session_state.orase:
        col_select, col_del = st.columns([3, 1])
        oras_selectat = col_select.selectbox("Alege orașul de explorat:", list(st.session_state.orase.keys()))

        if col_del.button(f"🗑️ Șterge orașul"):
            del st.session_state.orase[oras_selectat]
            st.session_state.activitati = [a for a in st.session_state.activitati if a["oras"] != oras_selectat]
            sync_to_file()
            st.rerun()

        if oras_selectat in st.session_state.orase:
            tab_harta, tab_act = st.tabs(["📍 Harta Orașului", "🎟️ Obiective & Activități"])

            with tab_harta:
                st.success(
                    f"**🏨 Cazare:** {st.session_state.orase[oras_selectat]['cazare']} €  |  **🍕 Recomandări:** {st.session_state.orase[oras_selectat]['food']}")

                coords = st.session_state.orase[oras_selectat]["coords"]
                m_local = folium.Map(location=coords, zoom_start=13)
                folium.Marker(coords, popup="Centru Oraș", icon=folium.Icon(color="red", icon="home")).add_to(m_local)

                for act in [a for a in st.session_state.activitati if a["oras"] == oras_selectat]:
                    is_done = act.get("done", False)
                    folium.Marker(
                        [act.get("lat", coords[0]), act.get("lon", coords[1])], popup=act['nume'],
                        icon=folium.Icon(color="green" if is_done else "orange", icon="ok" if is_done else "star")
                    ).add_to(m_local)

                st_folium(m_local, use_container_width=True, height=450, key=f"map_{oras_selectat}")
                st.markdown(f"🗺️ **[Deschide {oras_selectat} pe Google Maps]({get_gmaps_link(oras_selectat)})**")

            with tab_act:
                activitati_locale = [a for a in st.session_state.activitati if a["oras"] == oras_selectat]
                for act in activitati_locale:
                    with st.container(border=True):
                        c_chk, c_text, c_del = st.columns([1, 4, 1])
                        new_status = c_chk.checkbox("Am fost / Făcut", value=act.get("done", False),
                                                    key=f"done_act_{act['id']}")

                        if new_status != act.get("done", False):
                            for a in st.session_state.activitati:
                                if a["id"] == act["id"]: a["done"] = new_status
                            sync_to_file()
                            st.rerun()

                        text_display = f"~~{act['nume']}~~" if new_status else act['nume']
                        c_text.markdown(f"**{text_display}** ➔ {act['cost']} €")

                        if c_del.button("❌", key=f"del_act_{act['id']}"):
                            st.session_state.activitati = [a for a in st.session_state.activitati if
                                                           a["id"] != act['id']]
                            sync_to_file()
                            st.rerun()

                with st.form(f"form_add_act_{oras_selectat}", clear_on_submit=True):
                    st.write("### ➕ Adaugă obiectiv nou")
                    col_nume, col_cost = st.columns(2)
                    nume_nou = col_nume.text_input("Nume Obiectiv")
                    cost_nou = col_cost.number_input("Cost intrare (EUR/pers)", min_value=0.0, step=1.0)

                    if st.form_submit_button("Salvează Obiectivul"):
                        if nume_nou:
                            with st.spinner("Caut locația exactă pe hartă..."):
                                coords_act = gaseste_coordonate(f"{nume_nou}, {oras_selectat}", fallback_coords=coords)
                            st.session_state.activitati.append({
                                "id": st.session_state.next_act_id, "oras": oras_selectat, "nume": nume_nou,
                                "cost": cost_nou, "lat": coords_act[0], "lon": coords_act[1], "done": False
                            })
                            st.session_state.next_act_id += 1
                            sync_to_file()
                            st.rerun()

# ==========================================
# 4. BUGET DETALIAT (GRAFICE)
# ==========================================
elif menu == "💰 Buget Detaliat (Grafice)":
    st.title("📊 Calculator Buget & Grafice Interactive")

    with st.container(border=True):
        col_curs, col_zile = st.columns(2)
        curs = col_curs.number_input("Curs Valutar (RON/EUR)", value=4.98, step=0.01)
        zile_totale = col_zile.number_input("Câte zile durează vacanța?", value=14, step=1)

        mancare_zi = st.slider("🍕 Buget Mâncare & Diverse / zi / persoană (EUR)", 0, 200, 0)

        total_cazare_eur = sum(detalii.get("cazare", 0) for detalii in st.session_state.orase.values())
        total_transport_eur = sum(ruta.get("cost", 0) for ruta in st.session_state.calendar)
        total_activitati_eur = sum(act["cost"] for act in st.session_state.activitati) * 2
        total_mancare_eur = mancare_zi * zile_totale * 2

        total_eur = total_cazare_eur + total_transport_eur + total_activitati_eur + total_mancare_eur
        total_ron = total_eur * curs

    st.success(f"## 💰 TOTAL ESTIMAT: {total_ron:,.0f} RON (aprox. {total_eur:,.0f} €)")

    metrice = st.columns(4)
    metrice[0].metric("🏨 Cazare", f"€ {total_cazare_eur}")
    metrice[1].metric("🚆 Transport", f"€ {total_transport_eur}")
    metrice[2].metric("🎟️ Activități", f"€ {total_activitati_eur}")
    metrice[3].metric("🍕 Mâncare", f"€ {total_mancare_eur}")

    st.divider()
    st.subheader("📈 Analiză Vizuală Interactivă")

    df_buget = pd.DataFrame({
        "Categorie": ["Cazare", "Transport", "Activități", "Mâncare"],
        "Cost (EUR)": [total_cazare_eur, total_transport_eur, total_activitati_eur, total_mancare_eur]
    })

    col_grafic1, col_grafic2 = st.columns(2)
    with col_grafic1:
        fig_pie = px.pie(df_buget, values='Cost (EUR)', names='Categorie', title='Pondere Cheltuieli',
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_grafic2:
        fig_bar = px.bar(df_buget, x='Categorie', y='Cost (EUR)', title='Sume pe Categorii (EUR)', text_auto=True,
                         color='Categorie', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# 5. CHECKLIST BAGAJE
# ==========================================
elif menu == "🎒 Checklist Bagaje":
    st.title("🎒 Lista de Împachetat")

    with st.expander("⚙️ Adaugă Categorii și Obiecte"):
        c1, c2 = st.columns(2)
        with c1:
            new_cat = st.text_input("Nume categorie nouă")
            if st.button("Crează Categorie") and new_cat:
                if new_cat not in st.session_state.bagaje:
                    st.session_state.bagaje[new_cat] = {}
                    sync_to_file()
                    st.rerun()
        with c2:
            if st.session_state.bagaje:
                cat_sel = st.selectbox("Alege categoria", list(st.session_state.bagaje.keys()))
                new_item = st.text_input("Obiect de pus în bagaj")
                if st.button("Adaugă Obiect") and new_item:
                    if new_item not in st.session_state.bagaje[cat_sel]:
                        st.session_state.bagaje[cat_sel][new_item] = False
                        sync_to_file()
                        st.rerun()

    st.divider()

    if not st.session_state.bagaje:
        st.info("Lista de bagaje este goală.")

    cols = st.columns(3)
    col_idx = 0

    for categorie, obiecte in list(st.session_state.bagaje.items()):
        with cols[col_idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {categorie}")
                if not obiecte:
                    if st.button(f"Șterge Categoria", key=f"delcat_{categorie}"):
                        del st.session_state.bagaje[categorie]
                        sync_to_file()
                        st.rerun()

                for item_name, is_checked in list(obiecte.items()):
                    c_chk, c_del = st.columns([4, 1])

                    new_status = c_chk.checkbox(item_name, value=is_checked, key=f"chk_{categorie}_{item_name}")
                    if new_status != is_checked:
                        st.session_state.bagaje[categorie][item_name] = new_status
                        sync_to_file()
                        st.rerun()

                    if c_del.button("❌", key=f"del_{categorie}_{item_name}"):
                        del st.session_state.bagaje[categorie][item_name]
                        sync_to_file()
                        st.rerun()
        col_idx += 1