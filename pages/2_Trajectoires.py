import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from datetime import date, timedelta
from folium.plugins import MeasureControl
from numerize.numerize import numerize

from func import *

page_type='traj'

rng = np.random.default_rng(seed=42)

st.set_page_config(
    page_title="AIS - TRAJECTORIES MODE",
    page_icon="🟨",
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
    

    if st.button("Retour à la page d'acceuil", use_container_width=True, key="return_from_first", type="primary"):
        st.switch_page("Homepage.py")

    st.markdown("---")

    with st.expander("📑 Pages", True):

        st.markdown("## 🟨 Mode trajectoires :")
        st.markdown("### Sur cette page, il est important de sélectionner deux plages temporelles dans le cas où vous avez dessiné une zone à la page précédente." \
        " La première défini l'intervalle de temps pendant laquel un navire doit se trouver dans la zone sélectionnée." \
        " La seconde est un filtre temporel classique, actif sur les points récupérés par la première.Tous les filtres s'appliquent directement." \
        " De plus, si une liste de MMSI a été entrée, il est possible de choisir le nombre de points affchés par navire.")


st.title("AIS - 🟨 Mode trajectoire")
st.markdown("---")

gauche,droite = st.columns(2)

# Vérifie que les paramètres existent
required_keys = ['min_lat', 'max_lat', 'min_long', 'max_long', 'coords']
zone_chosen = all(k in st.session_state for k in required_keys)
list_chosen= ('mmsi_list_flux' in st.session_state)
if not (zone_chosen or list_chosen):
    st.warning("Veuillez d'abord sélectionner une zone sur la page de sélection ou fournir une liste de MMSI.")
    st.stop()


min_lat = st.session_state.get('min_lat', None)
max_lat = st.session_state.get('max_lat', None)
min_long = st.session_state.get('min_long', None)
max_long = st.session_state.get('max_long', None)
coords = st.session_state.get('coords', [])
square= [(min_lat,min_long),(max_lat,max_long)] if min_lat is not None else None
list_mmsi_user = st.session_state.get('mmsi_list_traj', [])


st.markdown("---")
date_min = date(2025, 1, 1)
date_max = date(2025, 12, 31)
date_range = gauche.slider("#### Sélection de la plage temporelle pour la zone d'intérêt",
    min_value=date_min,
    max_value=date_max,
    value=(date_min, date_max),
    step=timedelta(days=1),
    format="YYYY-MM-DD"
)

date_range_traj = gauche.slider(
            "#### Sélection de la plage temporelle pour les trajectoires des points selectionnés",
            min_value=date_min,
            max_value=date_max,
            value=(date_range[0], date_range[0]+ timedelta(days=1)),
            step=timedelta(days=1),
            format="YYYY-MM-DD",
            key="traj_date_slider"
        )
    

if (date_range_traj[0]!=date_range[0]) or (date_range_traj[1]!=(date_range[0]+ timedelta(days=1))):


    rows = get_points_with_traj(date_range[0], date_range[1],date_range_traj[0], date_range_traj[1],min_lat, max_lat, min_long, max_long, list_mmsi_user)


    if rows:

        df_ihs, df_complete, set_mmsi = create_all_df(rows)
        list_mmsi=list(set_mmsi)

        list_type_ihs = df_ihs['Ship type for pie chart'].fillna("Unknown").unique()
        df_dest = get_dest_mmsi(date_range[0], date_range[1], list_mmsi)
       
        
        st.session_state['df_ihs']=df_ihs
        st.session_state['df']=df_complete
        st.session_state['df_dest']=df_dest

        max_points = gauche.slider(
        "Nombre de points affichés sur la carte",
        min_value=1000,
        max_value=10000,
        value=min(1000, len(df_complete)),
        step=500
        )


        if list_mmsi_user:
            df_display = per_mmsi_filter(df_complete,list_mmsi,df_complete)
        with droite:
            df_display=per_ship_type_filter(df_complete,df_ihs)

        if len(df_display) > max_points:
            df_display = df_display.sort_values("timestamp").sample(frac=max_points/len(df_display) , random_state=5).iloc[:max_points] 
            max_timestamp = df_display['timestamp'].max()
            st.error(f"Attention : les points sont affichés jusqu'au {max_timestamp}. Pour afficher plus de points, augmentez le nombre maximum de points affichés.")

        else:
            df_display = df_display.sort_values("timestamp")



        opacity_choice=gauche.slider(
            "Sélection de l'opacité des navires (%)",
            min_value=0,
            max_value=100,
            value=80,
            step=1
            )      

        


        center, bounds, dimensions = map_settings(square,df_display,list_mmsi)

        m4 = folium.Map(location=[center[0], center[1]],zoom_control=True, scrollWheelZoom=True,dragging=True, tiles='OpenStreetMap')

        if coords:

            if not list_mmsi_user:
                for poly in create_rectangles(bounds):
                    folium.Polygon(
                        locations= poly, 
                        color='white',
                        weight=0,
                        fill=True,
                        fill_opacity=0.6,
                    ).add_to(m4)

            folium.Polygon(
                locations= [
                    bounds[0], 
                    (bounds[0][0],bounds[1][1]),
                    bounds[1],
                    (bounds[1][0],bounds[0][1])
                            ],
                color='gray',
                weight=2,
                fill=False
            ).add_to(m4)

        
        norm_sog = matplotlib.colors.PowerNorm(gamma=0.8,vmin=0, vmax=25)
        cmap_sog = matplotlib.colormaps.get_cmap('jet')
        colormap_speed=colormaps(norm_sog,cmap_sog,'sog')

        norm_draft = matplotlib.colors.PowerNorm(gamma=0.6,vmin=0, vmax=26)
        cmap_draft = matplotlib.colormaps.get_cmap('jet')
        colormap_draft=colormaps(norm_draft,cmap_draft,'Draft')

        cmap_types = matplotlib.colormaps.get_cmap('tab20')
        colormap_type=colormaps(cmap=cmap_types,list_type=list_type_ihs)

        cmap_choice = droite.radio(
            "Couleur des points :",
            options=["Pas de coloration","Vitesse", "Tirant d'eau", "Type de navire"],
            index=0,
            horizontal=True,
            key="cmap_choice"
        )
        size_choice = droite.radio(
            "Taille des points :",
            options=["Constante", "Taille des navires"],
            index=0,
            horizontal=True,
            key="size_choice"
        )
        shape_choice = droite.radio(
            "Forme des navires :",
            options=["Ronde", "Réelle"],
            index=0,
            horizontal=True,
            key="shape_choice"
        )
        
        color_map_dict = {
        "Pas de coloration": None,
        "Vitesse": colormap_speed,
        "Tirant d'eau": colormap_draft,
        "Type de navire": colormap_type
        }


        st.sidebar.metric("MMSI distincts récupérés :", numerize(len(set_mmsi)))
        st.sidebar.download_button(
                label="Télécharger la liste des mmsi (CSV)",
                data=pd.DataFrame(set_mmsi, columns=["mmsi"]).to_csv(index=False).encode('utf-8'),
                file_name="mmsi_selection.csv",
                mime="text/csv"
            )
        st.sidebar.metric("Messages AIS récupérés :", numerize(len(df_complete)))
        if shape_choice == "Réelle":
            st.sidebar.metric("Messages affichés après filtres :", numerize(len(df_display["Length"].dropna())))
            st.sidebar.info("Certains navires ont des dimensions inconnues et ne sont donc pas affichés quand l'option de forme réelle est sélectionnée.")
        else:
            st.sidebar.metric("Messages affichés après filtres :", numerize(len(df_display)))

        if shape_choice=="Réelle":

            df_display['polygon']= create_poly_with_arrow(df_display)
            add_points_poly(m4, df_display, color_map_dict[cmap_choice],opacity_choice,page_type='traj')

        elif shape_choice=="Ronde":

            add_points_circle(m4, df_display, color_map_dict[cmap_choice], size_choice,opacity_choice,page_type='traj')

                

        m4.fit_bounds(bounds,padding=(0, 0))
        m4.add_child(MeasureControl(primary_length_unit='meters'))
        st_folium(m4,use_container_width=True)


        st.info("Si vous voulez garder la carte, vous pouvez télécharger la page en HTML." \
        " De plus, il est possible de mesurer des distance sur la carte avec l'outil en haut à droite de celle-ci.")
        st.markdown("---")
            
        st.markdown("## Tableau des données affichées.")    
        st.text(" Il est possible de le télécharger.")
        make_dataframe(df_display)

        if st.button("Visualiser les graphs",use_container_width=True,key="flux_graph_button",type= "primary"):
                    st.switch_page("pages/6_traj_graphs.py") 

    else:
        st.error("Aucun MMSI dans la sélection, veuillez modifier les filtres.")



    with st.sidebar:
        st.markdown("---")
        st.warning("⚠️ Il n'est pas conseillé de revenir à la page d'acceuil et de changer de type d'analyse sans recharger la page." \
        " Les premières données entrées seront toujours prises en compte, ce qui pourra mener à des bugs.")

        st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
        st.caption("© 2025 - Visualisation AIS | Nathan - setec international - Pôle Maritime et fluvial")


    st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
    st.caption("© 2025 - Visualisation AIS | setec international - Pôle Maritime et fluvial")