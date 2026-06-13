import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import datetime
import plotly.express as px
import requests
import json
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Hub Vacante", page_icon="🧳", layout="wide")

# ============================================================
# CONFIG
# ============================================================
# Lipeste aici link-ul Web App (Apps Script) - trebuie sa se termine cu /exec
LINK_GOOGLE_SCRIPT = "https://script.google.com/macros/s/AKfycbxIurwUt2JydmHp0S8EcE__BgRSTk5EtFD-_EVQ9A1Zeiyr8Oss0EKgpefiG4-NFTY5WA/exec"

TRANSPORT_TIPURI = ["Avion", "Tren", "Autobuz", "Masina", "Vapor/Feribot", "Altele"]
TRANSPORT_ICONS = {
    "Avion": "✈️", "Tren": "🚆", "Autobuz": "🚌",
    "Masina": "🚗", "Vapor/Feribot": "⛴️", "Altele": "🧳",
}
ACTIVITATE_TIPURI = ["Atractie/Muzeu", "Mancare", "Cumparaturi", "Plaja", "Altele"]
ACTIVITATE_ICONS = {
    "Atractie/Muzeu": "🏛️", "Mancare": "🍝", "Cumparaturi": "🛍️",
    "Plaja": "🏖️", "Altele": "📍",
}

DEFAULT_SETARI = {"numar_persoane": 2, "curs_eur_ron": 5.25, "buget_total_ron": 10000.0}


# ============================================================
# UTILS
# ============================================================
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


def to_date(d):
    if isinstance(d, str):
        try:
            return datetime.date.fromisoformat(d)
        except ValueError:
            return datetime.date.today()
    if isinstance(d, datetime.date):
        return d
    return datetime.date.today()


def cloud_activ():
    return LINK_GOOGLE_SCRIPT.startswith("http")


# ============================================================
# CLOUD SYNC (Google Sheets prin Apps Script)
# ============================================================
@st.cache_data(ttl=5)
def obtine_lista_vacante():
    if not cloud_activ():
        return []
    try:
        r = requests.get(LINK_GOOGLE_SCRIPT, params={"action": "get_vacante"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=5)
def incarca_vacanta_din_cloud(nume):
    if not cloud_activ():
        return None
    try:
        r = requests.get(LINK_GOOGLE_SCRIPT, params={"action": "get_data", "nume": nume}, timeout=10)
        data = r.json()
        if not data:
            return None
        for ruta in data.get("transport", []):
            ruta["data"] = to_date(ruta.get("data"))
        for act in data.get("activitati", []):
            act["data"] = to_date(act.get("data"))
        return data
    except Exception:
        return None


def sync_to_cloud():
    obtine_lista_vacante.clear()
    incarca_vacanta_din_cloud.clear()
    if not cloud_activ() or not st.session_state.get("vacanta_activa"):
        return
    date = {
        "orase": st.session_state.orase,
        "activitati": st.session_state.activitati,
        "transport": st.session_state.transport,
        "bagaje": st.session_state.bagaje,
        "setari": st.session_state.setari,
        "next_act_id": st.session_state.next_act_id,
        "next_trans_id": st.session_state.next_trans_id,
    }
    payload = json.dumps({"nume_vacanta": st.session_state.vacanta_activa, "date": date}, cls=DateEncoder)
    try:
        requests.post(LINK_GOOGLE_SCRIPT, data=payload, headers={"Content-Type": "application/json"}, timeout=10)
    except Exception as e:
        st.warning(f"Sincronizare cloud esuata: {e}")


# ============================================================
# GEOCODING
# ============================================================
geolocator = Nominatim(user_agent="planificator_vacante_pro")


@st.cache_data
def gaseste_coordonate(nume):
    for query in (nume, f"{nume}, Italia"):
        try:
            loc = geolocator.geocode(query, timeout=5)
            if loc:
                return [loc.latitude, loc.longitude]
        except Exception:
            continue
    return [41.8719, 12.5674]  # fallback: centrul Italiei


# ============================================================
# INITIALIZARE STARE
# ============================================================
DEFAULT_KEYS = {
    "orase": {},
    "activitati": [],
    "transport": [],
    "bagaje": {},
    "setari": DEFAULT_SETARI.copy(),
    "next_act_id": 1,
    "next_trans_id": 1,
    "vacanta_activa": None,
}
for key, val in DEFAULT_KEYS.items():
    if key not in st.session_state:
        st.session_state[key] = json.loads(json.dumps(val)) if isinstance(val, (dict, list)) else val


def reset_vacanta(date=None):
    base = date or {}
    st.session_state.orase = base.get("orase", {})
    st.session_state.activitati = base.get("activitati", [])
    st.session_state.transport = base.get("transport", [])
    st.session_state.bagaje = base.get("bagaje", {})
    st.session_state.setari = {**DEFAULT_SETARI, **base.get("setari", {})}
    st.session_state.next_act_id = base.get("next_act_id", 1)
    st.session_state.next_trans_id = base.get("next_trans_id", 1)


# ============================================================
# SIDEBAR - gestionare vacanta + setari generale
# ============================================================
st.sidebar.markdown("## 🌍 Hub Vacante")

if not cloud_activ():
    st.sidebar.warning("Sincronizarea cloud e dezactivata. Lipeste link-ul Apps Script (LINK_GOOGLE_SCRIPT) in app.py ca sa salvezi datele si pe Google Sheets.")

vacante = obtine_lista_vacante()

with st.sidebar.expander("➕ Vacanta noua"):
    noua_v = st.text_input("Nume vacanta", key="input_noua_vacanta")
    if st.button("Creeaza vacanta"):
        if noua_v and noua_v not in vacante:
            st.session_state.vacanta_activa = noua_v
            reset_vacanta()
            sync_to_cloud()
            st.rerun()
        elif noua_v in vacante:
            st.sidebar.error("Exista deja o vacanta cu acest nume.")
        else:
            st.sidebar.error("Introdu un nume.")

if vacante:
    idx = vacante.index(st.session_state.vacanta_activa) if st.session_state.vacanta_activa in vacante else 0
    selected = st.sidebar.selectbox("📂 Vacanta activa:", vacante, index=idx)
    if selected != st.session_state.vacanta_activa or not st.session_state.orase and st.session_state.vacanta_activa == selected:
        st.session_state.vacanta_activa = selected
        data = incarca_vacanta_din_cloud(selected)
        if data:
            reset_vacanta(data)

if st.session_state.vacanta_activa:
    st.sidebar.success(f"Vacanta activa: **{st.session_state.vacanta_activa}**")

with st.sidebar.expander("⚙️ Setari generale", expanded=False):
    st.session_state.setari["numar_persoane"] = st.number_input(
        "Numar persoane", min_value=1, max_value=20,
        value=int(st.session_state.setari.get("numar_persoane", 2)), key="set_persoane"
    )
    st.session_state.setari["curs_eur_ron"] = st.number_input(
        "Curs valutar EUR -> RON", min_value=1.0, max_value=10.0, step=0.01,
        value=float(st.session_state.setari.get("curs_eur_ron", 5.25)), key="set_curs"
    )
    st.session_state.setari["buget_total_ron"] = st.number_input(
        "Buget total disponibil (RON)", min_value=0.0, step=100.0,
        value=float(st.session_state.setari.get("buget_total_ron", 10000.0)), key="set_buget"
    )
    if st.button("💾 Salveaza setari"):
        sync_to_cloud()
        st.sidebar.success("Salvat!")

NUM_PERS = st.session_state.setari.get("numar_persoane", 2)
CURS = st.session_state.setari.get("curs_eur_ron", 5.25)

# ============================================================
# NAVIGARE
# ============================================================
menu = st.sidebar.radio("Navigare:", ["🗺️ Harta", "🚀 Transport", "🏙️ Orase & Activitati", "💰 Buget", "🎒 Bagaje"])

if not st.session_state.vacanta_activa:
    st.title("🧳 Hub Vacante")
    st.info("Creeaza sau selecteaza o vacanta din meniul din stanga pentru a incepe.")
    st.stop()

st.title(f"🧳 {st.session_state.vacanta_activa}")

# ============================================================
# PAGINA: HARTA
# ============================================================
if menu == "🗺️ Harta":
    st.header("🗺️ Harta generala")

    if not st.session_state.orase:
        st.info("Nu ai adaugat inca orase. Mergi la pagina 'Orase & Activitati' pentru a adauga unul.")
    else:
        coords_list = [d["coords"] for d in st.session_state.orase.values()]
        center_lat = sum(c[0] for c in coords_list) / len(coords_list)
        center_lon = sum(c[1] for c in coords_list) / len(coords_list)
        m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

        for nume, d in st.session_state.orase.items():
            cazare = d.get("cazare_total", 0)
            popup_html = f"<b>{nume}</b><br>Cazare: {cazare:.0f} EUR<br>Nopti: {d.get('nopti', 0)}"
            folium.Marker(
                d["coords"], popup=popup_html, tooltip=nume,
                icon=folium.Icon(color="blue", icon="home"),
            ).add_to(m)

        # linii pentru rute de transport intre orase cunoscute
        for ruta in st.session_state.transport:
            de_la, pana_la = ruta.get("de_la", ""), ruta.get("pana_la", "")
            if de_la in st.session_state.orase and pana_la in st.session_state.orase:
                p1 = st.session_state.orase[de_la]["coords"]
                p2 = st.session_state.orase[pana_la]["coords"]
                folium.PolyLine(
                    [p1, p2], color="red", weight=2.5, opacity=0.7,
                    tooltip=f"{TRANSPORT_ICONS.get(ruta.get('tip',''), '')} {de_la} -> {pana_la}",
                ).add_to(m)

        st_folium(m, use_container_width=True, height=500)

# ============================================================
# PAGINA: TRANSPORT
# ============================================================
elif menu == "🚀 Transport":
    st.header("🚀 Transport (avion, tren, autobuz...)")

    with st.expander("➕ Adauga ruta de transport", expanded=len(st.session_state.transport) == 0):
        with st.form("form_transport_nou", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            tip = c1.selectbox("Tip transport", TRANSPORT_TIPURI, format_func=lambda t: f"{TRANSPORT_ICONS[t]} {t}")
            data_r = c2.date_input("Data", value=datetime.date.today())
            durata = c3.text_input("Durata (ex: 1h 30min)")

            c4, c5 = st.columns(2)
            de_la = c4.text_input("De la (oras / aeroport)")
            pana_la = c5.text_input("Pana la (oras / aeroport)")

            c6, c7 = st.columns(2)
            cost = c6.number_input("Cost (EUR)", min_value=0.0, step=1.0)
            per_persoana = c7.checkbox(f"Costul de mai sus e per persoana (x{NUM_PERS})", value=False)

            nota = st.text_input("Nota / Sursa (ex: Wizz Air, FrecciaYOUNG, etc.)")

            if st.form_submit_button("Adauga"):
                st.session_state.transport.append({
                    "id": st.session_state.next_trans_id,
                    "tip": tip, "data": data_r, "durata": durata,
                    "de_la": de_la, "pana_la": pana_la,
                    "cost": cost, "per_persoana": per_persoana, "nota": nota,
                })
                st.session_state.next_trans_id += 1
                sync_to_cloud()
                st.rerun()

    if not st.session_state.transport:
        st.info("Nu ai adaugat inca trasee de transport.")
    else:
        for ruta in sorted(st.session_state.transport, key=lambda r: to_date(r.get("data"))):
            rid = ruta["id"]
            edit_key = f"edit_trans_{rid}"
            with st.container(border=True):
                if st.session_state.get(edit_key):
                    with st.form(f"form_edit_trans_{rid}"):
                        c1, c2, c3 = st.columns(3)
                        e_tip = c1.selectbox("Tip", TRANSPORT_TIPURI, index=TRANSPORT_TIPURI.index(ruta.get("tip", "Altele")),
                                              format_func=lambda t: f"{TRANSPORT_ICONS[t]} {t}", key=f"etip_{rid}")
                        e_data = c2.date_input("Data", value=to_date(ruta.get("data")), key=f"edata_{rid}")
                        e_durata = c3.text_input("Durata", value=ruta.get("durata", ""), key=f"edur_{rid}")

                        c4, c5 = st.columns(2)
                        e_de_la = c4.text_input("De la", value=ruta.get("de_la", ""), key=f"edl_{rid}")
                        e_pana_la = c5.text_input("Pana la", value=ruta.get("pana_la", ""), key=f"epl_{rid}")

                        c6, c7 = st.columns(2)
                        e_cost = c6.number_input("Cost (EUR)", min_value=0.0, step=1.0, value=float(ruta.get("cost", 0)), key=f"ecost_{rid}")
                        e_pp = c7.checkbox(f"Per persoana (x{NUM_PERS})", value=ruta.get("per_persoana", False), key=f"epp_{rid}")

                        e_nota = st.text_input("Nota", value=ruta.get("nota", ""), key=f"enota_{rid}")

                        cs1, cs2 = st.columns(2)
                        if cs1.form_submit_button("💾 Salveaza"):
                            ruta.update({"tip": e_tip, "data": e_data, "durata": e_durata, "de_la": e_de_la,
                                          "pana_la": e_pana_la, "cost": e_cost, "per_persoana": e_pp, "nota": e_nota})
                            st.session_state[edit_key] = False
                            sync_to_cloud()
                            st.rerun()
                        if cs2.form_submit_button("Anuleaza"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    cost_total = ruta.get("cost", 0) * (NUM_PERS if ruta.get("per_persoana") else 1)
                    cost_ron = cost_total * CURS
                    c1, c2, c3 = st.columns([5, 2, 2])
                    with c1:
                        st.markdown(f"**{TRANSPORT_ICONS.get(ruta.get('tip',''),'')} {ruta.get('tip','')}** — "
                                     f"{ruta.get('de_la','?')} ➔ {ruta.get('pana_la','?')}")
                        meta = f"📅 {to_date(ruta.get('data'))}"
                        if ruta.get("durata"):
                            meta += f" • ⏱ {ruta['durata']}"
                        if ruta.get("nota"):
                            meta += f" • {ruta['nota']}"
                        st.caption(meta)
                    with c2:
                        st.metric("Cost total", f"{cost_total:.0f} € / {cost_ron:.0f} RON")
                    with c3:
                        b1, b2 = st.columns(2)
                        if b1.button("✏️", key=f"btn_edit_trans_{rid}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                        if b2.button("🗑️", key=f"btn_del_trans_{rid}"):
                            st.session_state.transport = [r for r in st.session_state.transport if r["id"] != rid]
                            sync_to_cloud()
                            st.rerun()

# ============================================================
# PAGINA: ORASE & ACTIVITATI
# ============================================================
elif menu == "🏙️ Orase & Activitati":
    st.header("🏙️ Orase & Activitati")

    with st.expander("➕ Adauga oras nou", expanded=len(st.session_state.orase) == 0):
        with st.form("form_oras_nou", clear_on_submit=True):
            o_nume = st.text_input("Nume oras")
            c1, c2, c3 = st.columns(3)
            o_cazare = c1.number_input("Cazare totala (EUR)", min_value=0.0, step=10.0)
            o_nopti = c2.number_input("Numar nopti", min_value=0, step=1)
            o_mese = c3.number_input("Mese / zi - tot grupul (EUR)", min_value=0.0, step=5.0)
            o_note = st.text_area("Note")
            if st.form_submit_button("Adauga oras"):
                if o_nume and o_nume not in st.session_state.orase:
                    st.session_state.orase[o_nume] = {
                        "coords": gaseste_coordonate(o_nume),
                        "cazare_total": o_cazare, "nopti": o_nopti,
                        "mese_zi": o_mese, "note": o_note,
                    }
                    sync_to_cloud()
                    st.rerun()
                elif not o_nume:
                    st.error("Introdu un nume de oras.")
                else:
                    st.error("Acest oras exista deja.")

    if not st.session_state.orase:
        st.info("Nu ai adaugat inca orase.")
    else:
        for oras, d in list(st.session_state.orase.items()):
            with st.expander(f"📍 {oras}  —  cazare {d.get('cazare_total',0):.0f}€ / {d.get('nopti',0)} nopti", expanded=False):
                edit_key = f"edit_oras_{oras}"
                if st.session_state.get(edit_key):
                    with st.form(f"form_edit_oras_{oras}"):
                        c1, c2, c3 = st.columns(3)
                        e_cazare = c1.number_input("Cazare totala (EUR)", min_value=0.0, step=10.0, value=float(d.get("cazare_total", 0)))
                        e_nopti = c2.number_input("Numar nopti", min_value=0, step=1, value=int(d.get("nopti", 0)))
                        e_mese = c3.number_input("Mese / zi - tot grupul (EUR)", min_value=0.0, step=5.0, value=float(d.get("mese_zi", 0)))
                        e_note = st.text_area("Note", value=d.get("note", ""))
                        cs1, cs2 = st.columns(2)
                        if cs1.form_submit_button("💾 Salveaza"):
                            d.update({"cazare_total": e_cazare, "nopti": e_nopti, "mese_zi": e_mese, "note": e_note})
                            st.session_state[edit_key] = False
                            sync_to_cloud()
                            st.rerun()
                        if cs2.form_submit_button("Anuleaza"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.write(f"💶 Cazare totala: **{d.get('cazare_total',0):.0f} €**  •  🛏️ Nopti: **{d.get('nopti',0)}**  •  🍝 Mese/zi (grup): **{d.get('mese_zi',0):.0f} €**")
                        if d.get("note"):
                            st.caption(d["note"])
                    with c2:
                        b1, b2 = st.columns(2)
                        if b1.button("✏️", key=f"btn_edit_oras_{oras}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                        if b2.button("🗑️", key=f"btn_del_oras_{oras}"):
                            del st.session_state.orase[oras]
                            st.session_state.activitati = [a for a in st.session_state.activitati if a["oras"] != oras]
                            sync_to_cloud()
                            st.rerun()

                st.markdown("---")
                st.markdown("**Activitati / obiective**")

                acts = [a for a in st.session_state.activitati if a["oras"] == oras]
                for a in acts:
                    aid = a["id"]
                    edit_a_key = f"edit_act_{aid}"
                    if st.session_state.get(edit_a_key):
                        with st.form(f"form_edit_act_{aid}"):
                            c1, c2, c3 = st.columns(3)
                            e_nume = c1.text_input("Denumire", value=a.get("nume", ""))
                            e_tip = c2.selectbox("Tip", ACTIVITATE_TIPURI,
                                                  index=ACTIVITATE_TIPURI.index(a.get("tip", "Altele")) if a.get("tip") in ACTIVITATE_TIPURI else 4,
                                                  format_func=lambda t: f"{ACTIVITATE_ICONS[t]} {t}")
                            e_cost = c3.number_input("Cost (EUR)", min_value=0.0, step=1.0, value=float(a.get("cost", 0)))
                            e_pp = st.checkbox(f"Per persoana (x{NUM_PERS})", value=a.get("per_persoana", False))
                            e_data = st.date_input("Data", value=to_date(a.get("data")))
                            cs1, cs2 = st.columns(2)
                            if cs1.form_submit_button("💾 Salveaza"):
                                a.update({"nume": e_nume, "tip": e_tip, "cost": e_cost, "per_persoana": e_pp, "data": e_data})
                                st.session_state[edit_a_key] = False
                                sync_to_cloud()
                                st.rerun()
                            if cs2.form_submit_button("Anuleaza"):
                                st.session_state[edit_a_key] = False
                                st.rerun()
                    else:
                        cost_total = a.get("cost", 0) * (NUM_PERS if a.get("per_persoana") else 1)
                        c1, c2, c3 = st.columns([4, 2, 1])
                        with c1:
                            st.write(f"{ACTIVITATE_ICONS.get(a.get('tip',''),'📍')} **{a.get('nume','')}** ({to_date(a.get('data'))})")
                        with c2:
                            st.write(f"{cost_total:.0f} € / {cost_total*CURS:.0f} RON")
                        with c3:
                            b1, b2 = st.columns(2)
                            if b1.button("✏️", key=f"btn_edit_act_{aid}"):
                                st.session_state[edit_a_key] = True
                                st.rerun()
                            if b2.button("🗑️", key=f"btn_del_act_{aid}"):
                                st.session_state.activitati = [x for x in st.session_state.activitati if x["id"] != aid]
                                sync_to_cloud()
                                st.rerun()

                with st.form(f"form_act_nou_{oras}", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    na_nume = c1.text_input("Denumire activitate")
                    na_tip = c2.selectbox("Tip", ACTIVITATE_TIPURI, format_func=lambda t: f"{ACTIVITATE_ICONS[t]} {t}", key=f"na_tip_{oras}")
                    na_cost = c3.number_input("Cost (EUR)", min_value=0.0, step=1.0, key=f"na_cost_{oras}")
                    na_pp = st.checkbox(f"Per persoana (x{NUM_PERS})", value=False, key=f"na_pp_{oras}")
                    na_data = st.date_input("Data", value=datetime.date.today(), key=f"na_data_{oras}")
                    if st.form_submit_button("➕ Adauga activitate"):
                        if na_nume:
                            st.session_state.activitati.append({
                                "id": st.session_state.next_act_id, "oras": oras, "nume": na_nume,
                                "tip": na_tip, "cost": na_cost, "per_persoana": na_pp, "data": na_data,
                            })
                            st.session_state.next_act_id += 1
                            sync_to_cloud()
                            st.rerun()

# ============================================================
# PAGINA: BUGET
# ============================================================
elif menu == "💰 Buget":
    st.header("💰 Buget detaliat")

    transport_total_eur = sum(
        r.get("cost", 0) * (NUM_PERS if r.get("per_persoana") else 1) for r in st.session_state.transport
    )
    cazare_total_eur = sum(d.get("cazare_total", 0) for d in st.session_state.orase.values())
    mese_total_eur = sum(d.get("mese_zi", 0) * d.get("nopti", 0) for d in st.session_state.orase.values())
    activitati_total_eur = sum(
        a.get("cost", 0) * (NUM_PERS if a.get("per_persoana") else 1) for a in st.session_state.activitati
    )

    total_eur = transport_total_eur + cazare_total_eur + mese_total_eur + activitati_total_eur
    total_ron = total_eur * CURS
    buget_ron = st.session_state.setari.get("buget_total_ron", 10000.0)
    ramas_ron = buget_ron - total_ron

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total estimat", f"{total_eur:.0f} €", f"{total_ron:.0f} RON")
    c2.metric("Buget disponibil", f"{buget_ron:.0f} RON")
    c3.metric("Ramas", f"{ramas_ron:.0f} RON", delta_color="normal" if ramas_ron >= 0 else "inverse")
    c4.metric("Per persoana", f"{total_eur/NUM_PERS:.0f} € / {total_ron/NUM_PERS:.0f} RON")

    st.progress(min(max(total_ron / buget_ron, 0), 1.0) if buget_ron > 0 else 0)
    if ramas_ron < 0:
        st.error(f"Ai depasit bugetul cu {-ramas_ron:.0f} RON!")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Distributie pe categorii")
        df_cat = pd.DataFrame({
            "Categorie": ["Transport", "Cazare", "Mese", "Activitati"],
            "EUR": [transport_total_eur, cazare_total_eur, mese_total_eur, activitati_total_eur],
        })
        df_cat["RON"] = df_cat["EUR"] * CURS
        df_cat = df_cat[df_cat["EUR"] > 0]
        if not df_cat.empty:
            fig = px.pie(df_cat, values="RON", names="Categorie", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Adauga date despre transport, cazare, mese sau activitati.")

    with col2:
        st.subheader("Cost pe oras")
        rows = []
        for oras, d in st.session_state.orase.items():
            cazare = d.get("cazare_total", 0)
            mese = d.get("mese_zi", 0) * d.get("nopti", 0)
            act = sum(a.get("cost", 0) * (NUM_PERS if a.get("per_persoana") else 1)
                      for a in st.session_state.activitati if a["oras"] == oras)
            rows.append({"Oras": oras, "Cazare": cazare * CURS, "Mese": mese * CURS, "Activitati": act * CURS})
        if rows:
            df_oras = pd.DataFrame(rows)
            fig2 = px.bar(df_oras, x="Oras", y=["Cazare", "Mese", "Activitati"], barmode="stack")
            fig2.update_layout(yaxis_title="RON")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Adauga orase pentru a vedea graficul.")

    st.subheader("Cheltuieli pe zile (transport + activitati)")
    rows = []
    for r in st.session_state.transport:
        cost = r.get("cost", 0) * (NUM_PERS if r.get("per_persoana") else 1) * CURS
        rows.append({"Data": to_date(r.get("data")), "Suma (RON)": cost, "Tip": f"{TRANSPORT_ICONS.get(r.get('tip',''),'')} Transport"})
    for a in st.session_state.activitati:
        cost = a.get("cost", 0) * (NUM_PERS if a.get("per_persoana") else 1) * CURS
        rows.append({"Data": to_date(a.get("data")), "Suma (RON)": cost, "Tip": "🏛️ Activitate"})
    if rows:
        df_zi = pd.DataFrame(rows)
        fig3 = px.bar(df_zi, x="Data", y="Suma (RON)", color="Tip")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Adauga transport sau activitati cu data pentru a vedea evolutia pe zile.")

# ============================================================
# PAGINA: BAGAJE
# ============================================================
elif menu == "🎒 Bagaje":
    st.header("🎒 Lista de bagaje")

    with st.form("form_categorie_noua", clear_on_submit=True):
        c1, c2 = st.columns([4, 1])
        cat_noua = c1.text_input("Categorie noua (ex: Documente, Haine, Electronice)")
        if c2.form_submit_button("➕ Adauga categorie"):
            if cat_noua and cat_noua not in st.session_state.bagaje:
                st.session_state.bagaje[cat_noua] = {}
                sync_to_cloud()
                st.rerun()

    if not st.session_state.bagaje:
        st.info("Nu ai adaugat inca nicio categorie de bagaje.")

    for cat in list(st.session_state.bagaje.keys()):
        items = st.session_state.bagaje[cat]
        bifate = sum(1 for v in items.values() if v)
        with st.expander(f"{cat} ({bifate}/{len(items)})", expanded=False):
            for item, val in list(items.items()):
                c1, c2 = st.columns([5, 1])
                with c1:
                    nou_val = st.checkbox(item, value=val, key=f"chk_{cat}_{item}")
                    if nou_val != val:
                        st.session_state.bagaje[cat][item] = nou_val
                        sync_to_cloud()
                with c2:
                    if st.button("🗑️", key=f"del_item_{cat}_{item}"):
                        del st.session_state.bagaje[cat][item]
                        sync_to_cloud()
                        st.rerun()

            with st.form(f"form_item_nou_{cat}", clear_on_submit=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                item_nou = c1.text_input("Obiect nou", key=f"input_item_{cat}")
                add = c2.form_submit_button("➕")
                delcat = c3.form_submit_button("🗑️ Categorie")
                if add and item_nou:
                    st.session_state.bagaje[cat][item_nou] = False
                    sync_to_cloud()
                    st.rerun()
                if delcat:
                    del st.session_state.bagaje[cat]
                    sync_to_cloud()
                    st.rerun()
