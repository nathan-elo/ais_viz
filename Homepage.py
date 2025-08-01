import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import Draw
import folium
import re
import matplotlib
from func import *



st.set_page_config(
    page_title="AIS MAP - Sélection",
    page_icon=":world_map:",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
with st.sidebar:

    st.info("Il est possible de réduire le panneau latéral via les doubles flèches en haut à droite.")
    st.markdown("---")

    with st.expander("📑 Pages", True):
        st.markdown("## 📍 Page de garde :")
        st.markdown("### Sélection des navires et du type de visualisation.")

        st.markdown("---")
        st.markdown("## 🟦 Mode classique :")
        st.markdown("### Visualisation de tous les messages sélectionnées.")

        st.markdown("## 🟨 Mode trajectoires :")
        st.markdown("### Visualisation de la trajectoire des navires sélectionnés.")

        st.markdown("## 🟩 Mode photo :")
        st.markdown("### Visualisation des derniers messages émis sur une zone.")
        
    st.markdown("---")
    st.warning("⚠️ Il n'est pas conseillé de revenir à la page d'acceuil et de changer de type d'analyse sans recharger la page." \
    " Les premières données entrées seront toujours prises en compte, ce qui pourra mener à des bugs.")

    st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
    st.caption("© 2025 - Visualisation AIS | Nathan - setec international - Pôle Maritime et fluvial")

l,m,r = st.columns([3,4,1])
m.title(" 🚢 Application AIS 🧭")
st.markdown("### Ceci est la première page de l'outil de visualisation des données AIS." \
" L'outil (présenté sous forme de site interactif) est composé de plusieurs" \
" pages, chacune offrant des visuels et informations différentes." \
" Pour sélectionner les données, il est possible de sélectionner une zone sur la carte (via le dessin d'un rectangle exclusivement) ou de fournir une liste de MMSI." \
" Fournir les deux est aussi possible pour le premier mode de visualisation. ")

st.markdown("---")

col_map, col_ui = st.columns([2, 1])

def style_function(feature):
    return {
        'fillColor': feature['properties'].get('fill', 'gray'),
        'color': feature['properties'].get('stroke', 'black'),
        'weight': feature['properties'].get('stroke-width', 1),
        'fillOpacity': feature['properties'].get('fill-opacity', 0.5),
    }



gauche, mid= st.columns([4,2])
with gauche:
    st.markdown("## :one: Sélection des navires via la carte", unsafe_allow_html=True)
    
    m = folium.Map(location=[47,1], zoom_start=5, tiles='OpenStreetMap')
    folium.GeoJson(
    "heatmap.geojson",
    style_function=style_function
    ).add_to(m)
    Draw(export=True).add_to(m)

    norm_density = matplotlib.colors.PowerNorm(gamma=1,vmin=0, vmax=10)
    cmap_density = matplotlib.colormaps.get_cmap('jet')
    colors = [matplotlib.colors.rgb2hex(cmap_density(norm_density(v))) for v in np.linspace(0,9,9)]
    legend_html = make_gradient_legend('Densité des messages',colors=colors)
    m.get_root().html.add_child(folium.Element(legend_html))

    draw_result = st_folium(m, width=800, height=800, key="flux_map",use_container_width=True)

with mid:
    st.markdown("## :one: Sélection des navires via la liste", unsafe_allow_html=True)
    valid_input = False
    list_mmsi_user = st.text_input(label=" ",
        key="mmsi_input_both",
        placeholder="Ex: 123456789,987654321 352009000",
        )
    cleaned = re.sub(r"[\s,]+", ",", list_mmsi_user.strip())

    cleaned = re.sub(r",+$", "", cleaned)

    pattern = r"^(\d{9})(,\d{9})*$" 


    if cleaned != "" and not re.fullmatch(pattern, cleaned):
            st.error("Format incorrect : MMSI de 9 chiffres séparés par des virgules ou espaces, sans virgule finale (ex : 123456789,987654321 352009000)")
    elif cleaned !="":
        valid_input=True
        st.success("Liste de MMSI valide.")


    st.info("La légende sur la carte indique les zones couvertes par les données AIS, pour une journée type (Avril 2025). Les zones grises indiquent une très faible concentration de messages." \
    " S'il n'y a aucune coloration, aucun message n'a été reçu dans cette zone. À noter qu'une carte est disponible pour une période de 2 semaines.")


if (draw_result and draw_result.get("last_active_drawing")):
    shape = draw_result["last_active_drawing"]
    if shape["geometry"]["type"] == "Polygon":
        coords = draw_result["last_active_drawing"]["geometry"]["coordinates"][0]
        lats = [point[1] for point in coords]
        longs = [point[0] for point in coords]
        min_lat, max_lat = min(lats), max(lats)
        min_long, max_long = min(longs), max(longs)

        st.session_state['min_lat'] = min_lat
        st.session_state['max_lat'] = max_lat
        st.session_state['min_long'] = min_long
        st.session_state['max_long'] = max_long
        
        st.session_state['coords'] = coords

        st.success(
            f"Rectangle dessiné :\nLatitudes de **{min_lat:.4f}** à **{max_lat:.4f}**.\n"
            f"Longitudes de **{min_long:.4f}** à **{max_long:.4f}**."
        )
elif valid_input==False:
    st.error("Veuillez dessiner une zone sur la carte, rentrer une liste de MMSI, ou les deux.")
        

    

st.markdown("## :two: Sélection du type de visualisation", unsafe_allow_html=True)
st.markdown("---")
left,middle,right = st.columns(3)

with left:
   st.markdown("## 🟦 Visualisation brute")
   st.markdown("#### Cette option permet de visualiser tous les messages AIS par les filtres choisis. Un navire peut donc apparaître plusieurs fois.")

with middle:
    st.markdown("## 🟨 Visualisation de trajectoires ")
    st.markdown("#### Cette option permet de visualiser la trajectoire des navires correspondant aux filtres choisis. " \
    " Pour ce mode, une petite zone de sélection ou une liste de MMSI réduite sont conseillées pour une meilleure lisibilité.")  

with right:
    st.markdown("## 🟩 Visualisation instantanée")
    st.markdown("#### Cette option permet de récupérer le dernier message émis par chaque navire dans la zone sélectionnée, pour une date choisie.")



left,middle,right = st.columns(3)

with left:
    if st.button("Vers le mode classique", use_container_width=True,key="flux_button",type="primary"):
            if valid_input:
                st.session_state['mmsi_list_flux'] = cleaned
            st.switch_page("pages/1_Messages.py") 
    


with middle:
    if st.button("Vers le mode trajectoire", use_container_width=True,key="traj_button",type="primary"):
        if valid_input:
            st.session_state['mmsi_list_traj'] = cleaned
        st.switch_page("pages/2_Trajectoires.py") 
    


with right:
    if st.button("Vers le mode photo", use_container_width=True,key="screen_button",type="primary"):
        st.switch_page("pages/3_Derniers_messages.py")

st.markdown("---")








    
   
    


st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
st.caption("© 2025 - Visualisation AIS | setec international - Pôle Maritime et fluvial")