import streamlit as st
import pandas as pd
import folium
import matplotlib
import psycopg2
import math
from math import radians,sin,cos,atan2,sqrt
import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry import Polygon
import numpy as np
from pyproj import Transformer
from datetime import datetime
from typing import List, Optional, Tuple
import json

#bdd="dyn_vm_nice_bigdata"
#bdd="dyn_filtered_full"
bdd="dyn_filtered_clean_code"

def haversine_dist_m(lat1 : float, lon1 : float, lat2 : float, lon2 : float) -> float:
    """
    Calcule la distance en mètres entre deux points géographiques.

    Args:
        lat1 (float): Latitude du point 1.
        lon1 (float): Longitude du point 1.
        lat2 (float): Latitude du point 2.
        lon2 (float): Longitude du point 2.

    Returns:
        float: Distance en mètres.
    """
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return 6371.0 * c*1000


def connect_pgsql_bigdata() -> Optional[psycopg2.extensions.connection]:
    try:
        conn = psycopg2.connect(**st.secrets["local"])
        return conn
    except Exception as e:
        st.error(f"Erreur de connexion en local : {e}")
        return None

def connect_pgsql() -> Optional[psycopg2.extensions.connection]:
    try:
        conn = psycopg2.connect(**st.secrets["pgsql"])
        return conn
    except Exception as e:
        st.error(f"Erreur de connexion à la VM : {e}")
        return None

def connect_vm() -> Optional[psycopg2.extensions.connection]:
    try:
        conn = psycopg2.connect(**st.secrets["vm"])
        return conn
    except Exception as e:
        st.error(f"Erreur de connexion à la VM : {e}")
        return None


       
@st.cache_data
def get_points(date_start : datetime, 
               date_end : datetime, 
               min_lat : float = None, 
               max_lat : float = None, 
               min_long : float = None, 
               max_long : float = None, 
               list_mmsi_user : List[str] = None) -> List[tuple]:
    """
    Récupère toutes les données filtrées par les arguments dans la base de données utilisée pour la visualisation.
    L'utilisateur a le choix de choisir une zone ou une liste de navire (MMSI) individuellent, ou les deux.

    Args :
            date_start : Date de début du filtre au format YYYY-MM-DD.
            date_end : Date de fin du filtre au format YYYY-MM-DD.
            min_lat : Latitude minimum. (limite sud)
            max_lat : Latitude maximum. (limite nord)
            min_long : Longitude minimum. (limite ouest)
            max_long : Longitude maximum (limite est)
            list_mmsi_user : Liste des MMSI des navires d'intérêt.
    
    Returns :
            rows : Liste de lignes organisées dans un tuple(mmsi, lat, long, cog, sog, timestamp)
    
    """
    choice : int = 2

    sql_list=f"""
          SELECT mmsi, lat, long, cog, sog, timestamp
          from {bdd}
          where timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
            and mmsi in ({list_mmsi_user});
          """,f"""
          SELECT mmsi,lat,long,cog,sog,timestamp
          from {bdd}
          where timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
            AND lat BETWEEN {min_lat} AND {max_lat}
            AND long BETWEEN {min_long} AND {max_long};
          """,f"""
          SELECT mmsi,lat,long,cog,sog,timestamp
          from {bdd}
          where timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
            AND lat BETWEEN {min_lat} AND {max_lat}
            AND long BETWEEN {min_long} AND {max_long}
            and mmsi in ({list_mmsi_user});
          """
    
    if min_lat is not None and list_mmsi_user is None:
        choice = 1
    elif list_mmsi_user and min_lat is None:
        choice = 0
 
    
    conn_loc = connect_pgsql_bigdata()
    cur_loc = conn_loc.cursor()
    cur_loc.execute(sql_list[choice])
    rows = cur_loc.fetchall()
    cur_loc.close()
    conn_loc.close()
    return rows
    
@st.cache_data
def get_points_with_traj(date_start : datetime,
                date_end : datetime, 
                date_start_2 : datetime = None, 
                date_end_2 : datetime = None,
                min_lat : float = None , 
                max_lat : float = None, 
                min_long : float = None,
                max_long : float = None, 
                list_mmsi_user : List[str]=None) -> List[tuple]:
    """
    Récupère toutes les données filtrées par les arguments dans la base de données utilisée pour la visualisation.
    L'utilisateur a le choix de choisir une zone ou une liste de navire (MMSI).
    Si l'utilisateur choisi une zone, il doit aussi fournir une deuxième plage temporelle,
    pour choisir la période de récupération des points déjà filtrés par la première plage. (qui étaient dans la zone sélectionnée pendant la période [date_start;date_end] )

    Args :
            date_start : Date de début du filtre sii list_mmsi_user is not None. Dans l'autre cas, c'est la plage temporelle pour sélectionner les points passant par une zone. au format YYYY-MM-DD
            date_end : Date de findu filtre sii list_mmsi_user is not None. Dans l'autre cas, c'est la plage temporelle pour sélectionner les points passant par une zone. au format YYYY-MM-DD
            date_start_2 : Date de début du second filtre. Permet de choisir l'intervalle temporelle, 
            pour observer les points qui étaient dans la zone sélectionner pendant la période [date_start;date_end]. au format YYYY-MM-DD
            date_end_2 : Date de fin du second filtre. Permet de choisir l'intervalle temporelle, 
            pour observer les points qui étaient dans la zone sélectionner pendant la période [date_start;date_end]. au format YYYY-MM-DD
            min_lat : Latitude minimum de la zone de passage. (limite sud)
            max_lat : Latitude maximum de la zone de passage. (limite nord)
            min_long : Longitude minimum de la zone de passage. (limite ouest)
            max_long : Longitude maximum de la zone de passage. (limite est)
            list_mmsi_user : Liste des MMSI des navires d'intérêt.
    
    Returns :
            rows : Liste de lignes organisées dans un tuple(mmsi, lat, long, cog, sog, timestamp)
    
    """
    choice : int  = 2

    sql_tuple = f"""SELECT mmsi, lat, long,cog, sog, timestamp
        FROM {bdd}
        WHERE mmsi IN ({list_mmsi_user})
            AND timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
        """,f"""
        WITH start_points AS (
            SELECT DISTINCT mmsi
            FROM {bdd}
            WHERE lat BETWEEN {min_lat} AND {max_lat}
            AND long BETWEEN {min_long} AND {max_long}
            AND timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
        )
        SELECT mmsi, lat, long,cog, sog, timestamp
        FROM {bdd}
        WHERE mmsi IN (SELECT mmsi FROM start_points)
        AND timestamp >= '{date_start_2}'
        AND timestamp <= '{date_end_2}'
        """,f"""
        WITH start_points AS (
            SELECT DISTINCT mmsi
            FROM {bdd}
            WHERE lat BETWEEN {min_lat} AND {max_lat}
            AND long BETWEEN {min_long} AND {max_long}
            AND timestamp >= '{date_start}'
            AND timestamp <= '{date_end}'
            AND mmsi IN ({list_mmsi_user})
        )
        SELECT mmsi, lat, long,cog, sog, timestamp
        FROM {bdd}
        WHERE mmsi IN (SELECT mmsi FROM start_points)
        AND timestamp >= '{date_start_2}'
        AND timestamp <= '{date_end_2}'
        """
    
    if min_lat is not None and list_mmsi_user is None:
        choice = 1
    elif list_mmsi_user and min_lat is None:
        choice = 0

    conn_loc = connect_pgsql_bigdata()
    cur_loc = conn_loc.cursor()
    cur_loc.execute(sql_tuple[choice])
    rows = cur_loc.fetchall()
    cur_loc.close()
    conn_loc.close()
    return rows

def create_all_df(rows: List[tuple]) -> Tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    """
    Récupère la liste de tuple (de la base de données) pour la transformer en DataFrame pandas.
    Crée une autre DataFrame à partir des données IHS et merge (left outer) pour obtenir un DF complet.
    Récupère la liste des MMSI de tous les navires présents.

    Args :
            rows : Liste de lignes organisées dans un tuple(mmsi, lat, long, cog, sog, timestamp)
    
    Returns :
            df_ihs : DataFrame avec les données statiques (nom, dimensions...) ainsi que les types IHS si disponibles.
            df : DataFrame avec toutes les informations disponibles.
            set_mmsi : set des MMSI des navires. (unordered, unique)
    
    """

    df_1=pd.DataFrame(rows, columns=["mmsi","lat", "long","cog","sog", "timestamp"])
    df_ihs=get_ihs(df_1)
    df_1['mmsi'] = df_1['mmsi'].astype(str)
    df_ihs['mmsi'] = df_ihs['mmsi'].astype(str)
    df = pd.merge(df_1, df_ihs, on='mmsi', how='left')
    set_mmsi = set(df['mmsi'].unique())

    return df_ihs, df, set_mmsi

def create_all_df_screen(rows: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    """
    Récupère la liste de tuple (de la base de données) pour la transformer en DataFrame pandas.
    Trie les lignes dans l'ordre chronologique décroissant pour récupérer le dernier message reçu pour chaque MMSI.
    Crée une autre DataFrame à partir des données IHS et merge (left outer) pour obtenir un DF complet.
    Récupère la liste des MMSI de tous les navires présents.

    Args :
            rows : Liste de lignes organisées dans un tuple(mmsi, lat, long, cog, sog, timestamp)
    
    Returns :
            df_ihs : DataFrame avec les données statiques (nom, dimensions...) ainsi que les types IHS si disponibles.
            df : DataFrame avec toutes les informations disponibles.
            set_mmsi : set des MMSI des navires. (unordered, unique)
    
    """
    df_1 = pd.DataFrame(rows, columns=["mmsi","lat", "long","cog","sog","timestamp"])
    df_1['timestamp'] = pd.to_datetime(df_1['timestamp']).dt.tz_localize(None)
    df_sorted_1=df_1.sort_values(by='timestamp', ascending=False).groupby('mmsi').first().reset_index()
    df_sorted=df_sorted_1
    
    df_ihs=get_ihs(df_sorted)
    df = pd.merge(df_sorted, df_ihs, on='mmsi', how='left')
    set_mmsi = set(df['mmsi'].unique())

    return df_ihs, df, set_mmsi

def per_mmsi_filter(df_complete: pd.DataFrame, set_mmsi: set, df_display: pd.DataFrame) -> pd.DataFrame:
    """
    Filtre les messages affichés sur la carte pour chaque MMSI, dans le cas où l'utilisateur a rentré manuellement une liste de MMSI.
    Permet de choisir combien de messages sont affichés par navire via des sliders.

    Args :
        df_complete : DataFrame de toutes les données disponibles
        set_mmsi : set des MMSI fournis par l'utilisateur.
        df_display : DataFrame ayant la même structure que df_complete, mais filtré pour l'affichage.
    
    Returns :
        df_display : DataFrame filtré.
    """
    ga, dr = st.columns([1, 1])
    ga.write("### Sélection du nombre de points par MMSI")
    dr.markdown(" ---")
    
    
    points_selection: dict = {}
    mmsi_list = list(set_mmsi)
    
    for i, mmsi in enumerate(mmsi_list):
        nb_rows = len(df_complete[df_complete['mmsi'] == mmsi])
        col = ga if i % 2 == 0 else dr
        nb_points = col.slider(
            f"MMSI {mmsi}",
            min_value=0,
            max_value=nb_rows,
            value=int(np.ceil(nb_rows / 2)),
            step=1
        )
        points_selection[mmsi] = nb_points

    df_display_list: list = []

    for mmsi, nb_points in points_selection.items():
        df_mmsi = df_complete[df_complete['mmsi'] == mmsi]
        if len(df_mmsi) > nb_points:
            df_mmsi = df_mmsi.sample(nb_points, random_state=42)
        df_display_list.append(df_mmsi)

    df_display = pd.concat(df_display_list).reset_index(drop=True)
    return df_display

def per_ship_type_filter(df_display : pd.DataFrame, df_ihs : pd.DataFrame) -> pd.DataFrame:
    """
    Filtre les messages affichés sur la carte selon le type de navire d'après la base de données IHS.
    Remplis les cases vides par "Unknown" et utilise les types avec trop peu de représentants dans "Other".
    Le choix se fait en cliquant sur des rubans.

    Args :
            df_display : DataFrame filtré pour l'affichage.
            df_ihs : DataFrame avec les données statiques et IHS si disponibles.
    
    Returns :
            df_display : DataFrame filtré pour l'affichage.
    
    """
    df_display=df_display.copy()
    list_types_ihs = list(df_ihs['Ship type for pie chart'].unique())
    list_types_ihs.append("Unknown")
    type_choice= st.multiselect(
        "Type de bateau à afficher :",
        list_types_ihs,
        default=list_types_ihs
    )   

    

    df_display['Ship type for pie chart'] = df_display['Ship type for pie chart'].fillna("Unknown")
    df_display['Ship type from IHS'] = df_display['Ship type from IHS'].fillna("Unknown")
    df_display=  df_display[df_display['Ship type for pie chart'].isin(type_choice)]

    return df_display

def map_settings(square : list[tuple], df_display : pd.DataFrame, list_mmsi_user : List = None) -> Tuple[tuple, list[tuple], tuple]:
    """
    Donne les données nécessaires à la création d'une carte centrée, zoomée et d'une taille adaptée à la zone sélectionnée.

    Args :
            square : extrémités de la zone sélectionnée.
            df_display : DataFrame des points à afficher.
            list_mmsi_user : liste des mmsi dans le cas où l'utilisateur l'a rentrée manuellement.

    Returns :
            center : centre de la carte. Soit le centre de la zone selectionnée, soit la moyenne des positions des points sélectionnés.
            bounds : limites initiales d'affichage de la carte. Soit la zone sélectionnée, soit les coordonnées des points les plus éloignés (de la liste de MMSI).
            dimensions : dimensions en pixel de la carte sur la page Streamlit. Les ratios de la zone sélectionnée sont préservés.
    """

    max_width : int = 1200
    center : tuple = ()
    bounds : list = [()]
    dimensions : tuple =()
    
    if list_mmsi_user:
        center = (df_display['lat'].mean(),df_display['long'].mean())
        bounds = [(df_display['lat'].min(),df_display['long'].min()),(df_display['lat'].max(),df_display['long'].max())]
    else :
        bounds = square
        center = (np.mean([bounds[0][0], bounds[1][0]]), np.mean([bounds[0][1], bounds[1][1]]))

    size_for_ratio_lat=haversine_dist_m(bounds[0][0],center[1],bounds[0][1] ,center[1])
    longitudinal_distance_m=haversine_dist_m(center[0],bounds[1][0],center[0] ,bounds[1][1])
    norm=max_width/longitudinal_distance_m
    map_width=longitudinal_distance_m*norm
    map_height=size_for_ratio_lat * norm
    dimensions = (map_height,map_width)


    return center, bounds, dimensions

def create_rectangles(bounds : List[tuple]):

    list_rect : List[tuple] = []

    list_rect= [
                [
                (-90.0,-180.0),
                (-90.0,180.0),
                (bounds[0][0],180.0),
                (bounds[0][0],-180.0)
                ],[
                (bounds[0][0],bounds[1][1]),
                (bounds[0][0],180.0),
                (bounds[1][0],180.0),
                (bounds[1][0],bounds[1][1])
                ],[
                (bounds[1][0],-180.0),
                (bounds[1][0],180.0),
                (90.0,180.0),
                (90.0,-180.0)
                ],[
                (bounds[0][0],-180.0),
                (bounds[0][0],bounds[0][1]),
                (bounds[1][0],bounds[0][1]),
                (bounds[1][0],-180.0)
                ]
                ]
    
    return list_rect


def make_dataframe(df : pd.DataFrame):

    st.data_editor(
        df[['mmsi','lat','long','cog','sog','timestamp','Ship type from IHS','Draft', 'Length','Width']],
        column_config={
            "mmsi":st.column_config.Column(
                "MMSI",
                help="Identifiant unique du navire."
            ),
            "lat" : st.column_config.Column(
                "Latitude (°)",
                help="Latitude en degrés"
            ),
            "long" : st.column_config.Column(
                "Longitude (°)",
                help="Latitude en degrés"
            ),
            "cog" : st.column_config.Column(
                "Route (°)",
                help="Angle entre la direction du navire et le nord géographique"
            ),
            "sog" : st.column_config.Column(
                "Vitesse (nd)",
                help="Vitesse en noeuds"
            ),
            "timestamp" : st.column_config.DatetimeColumn(
                "Timestamp",
                help="Heure et date d'émission du message"
            ),
            "Ship type from IHS" : st.column_config.Column(
                label="Type de navire",
                help="Récupéré de la base de données IHS"
            ),
            "Draft" : st.column_config.Column(
                "Tirant d'eau (m)"
            ),
            "Length" : st.column_config.Column(
                "Longueur (m)"
            ),
            "Width" : st.column_config.Column(
                "Largeur (m)"
            ),
        },
        use_container_width=True,
        hide_index=True
    )


def make_gradient_legend(title, vmin : int = None, vmax : int = None, colors = None):
            gradient = ""
            for _, color in enumerate(colors):
                gradient += f'<div style="flex:1;background:{color};height:20px;"></div>'

            if (vmin and vmax) is not None:
                html = f"""
                <div style="
                    position: fixed;
                    bottom: 50px;
                    left: 50px;
                    z-index: 9999;
                    background: white;
                    padding: 20px;
                    border: 3px solid #ccc;
                    font-size:14px;
                    width:200px;
                ">
                    <div style="color:black;font-weight:bold;margin-bottom:8px;">{title}</div>
                    <div style="display:flex;flex-direction:row;">{gradient}</div>
                    <div style="display:flex;justify-content:space-between;">
                        <span style="color:black;">{vmin}</span><span style="color:black;">{vmax}</span>
                    </div>
                </div>
                """
            else:
                html = f"""
                <div style="
                    position: fixed;
                    bottom: 50px;
                    left: 50px;
                    z-index: 9999;
                    background: white;
                    padding: 20px;
                    border: 3px solid #ccc;
                    font-size:14px;
                    width:200px;
                ">
                    <div style="color:black;font-weight:bold;margin-bottom:8px;">{title}</div>
                    <div style="display:flex;flex-direction:row;">{gradient}</div>
                    <div style="display:flex;justify-content:space-between;">

                    </div>
                </div>
                """

            return html

class colormaps():
    """
    Crée une instance de colormap pour associer des couleurs à des valeurs ou catégories.

    Permet de générer une fonction de mapping couleur par ligne, de créer une légende 
    visuelle adaptée, et de gérer différents typesde colormap (linéaire ou catégorielle).

    Attributes:
        norm (matplotlib.colors.Normalize or None): Fonction de normalisation.
        cmap (matplotlib.colors.Colormap or None): Colormap utilisée pour générer les couleurs. (pour plage de valeur ou catégories)
        row_name (str or None): Nom de la colonne utilisée pour la coloration (ex : 'sog' ou 'Draft').
        list (List[str] or None): Liste de types (depuis la BDD IHS) à associer à des couleurs distinctes.

    Methods:
        ship_type_to_color() -> Dict[str, str]:
            Crée un dictionnaire associant chaque type dans list à une couleur.

        color_per_row() -> Callable:
            Retourne une fonction qui prend une ligne (row) et renvoie une couleur selon le mode choisi :
            - Si list est fourni, la couleur dépend du type de navire (catégoriel).
            - Si seule row_name est fourni, la couleur dépend d'une valeur numérique (valeur continue).
            - Sinon, retourne None.

        add_legend(m: folium.Map):
            Ajoute une légende à la carte folium m, selon le type de coloration utilisé :
            - Légende linéaire si row_name est 'sog' ou 'Draft'.
            - Légende catégorielle si list est renseignée.
    """
    def __init__(self, norm=None, cmap=None, row_name: str = None, list_type: List[str] = None):
        """
        Initialise une instance de la classe colormaps.

        Args:
            norm (Optional[matplotlib.colors.Normalize]): Fonction de normalisation pour transformer
                les valeurs numériques en une plage [0,1]. PowerNorm ou Normalize.
            cmap (Optional[matplotlib.colors.Colormap]): Colormap matplotlib utilisée pour
                générer les couleurs.
            row_name (Optional[str]): Nom de la colonne dans les données utilisée pour
                la coloration (ex : 'sog', 'Draft').
            list_type (Optional[List[str]]): Liste des types de navires IHS.
        """
        self.norm = norm
        self.cmap = cmap
        self.list = list_type
        self.row_name = row_name


    def ship_type_to_color(self) -> dict[str, str]:
        """
        Crée un dictionnaire associant chaque type de navire dans la liste self.list
        à une couleur hexadécimale (générée par une colormap).

        Returns:
            dict[str, str]: Dictionnaire où les clés sont les types de navires (str) et
            les valeurs sont les codes couleurs hexadécimaux (str).
        """
        return {stype: matplotlib.colors.rgb2hex(self.cmap(i)) for i, stype in enumerate(self.list)}

    def color_per_row(self):
        """
        Génère une fonction qui, appliquée à une ligne de données, retourne la couleur
        associée à cette ligne selon les régles suivantes :

        - Si self.list est None et self.cmap est défini : 
        la couleur est calculée via la normalisation de la valeur dans la colonne self.row_name.
        - Si self.list est défini :
        la couleur est choisie en fonction du type de navire dans la colonne 'Ship type from IHS'.
        - Sinon, retourne None.

        Returns:
            Callable[[pandas.Series], str] | None: Fonction prenant une ligne et retournant
            une couleur hexadécimale, ou None si aucune coloration possible.
        """
        if self.list is None and self.cmap is not None:
            return lambda row: matplotlib.colors.rgb2hex(
                self.cmap(self.norm(0 if pd.isna(row[self.row_name]) else row[self.row_name]))
            )
        elif self.list is not None:
            color_map = self.ship_type_to_color()
            return lambda row: color_map.get(row['Ship type from IHS'], "#888888")
        else:
            return None

    def add_legend(self, m):
        """
        Ajoute une légende visuelle à la carte Folium m selon la colormap.

        Args:
            m (folium.Map): Objet carte Folium sur lequel ajouter la légende.
        """
        

        if self.row_name == "sog":
            colors = [matplotlib.colors.rgb2hex(self.cmap(self.norm(v))) for v in np.linspace(0,25,50)]
            legend_html = make_gradient_legend("Vitesse (nd)", vmin=0, vmax=25, colors=colors)
            m.get_root().html.add_child(folium.Element(legend_html))

        elif self.row_name == "Draft":
            colors = [matplotlib.colors.rgb2hex(self.cmap(self.norm(v))) for v in np.linspace(0,25,50)]
            legend_html = make_gradient_legend("Tirant d'eau (m)", vmin=0, vmax=25, colors=colors)
            m.get_root().html.add_child(folium.Element(legend_html))

        elif self.list is not None:
            color_map = self.ship_type_to_color()
            legend_html = '<b style="color:black;">Type de navire :</b><br>'
            for stype, color in color_map.items():
                legend_html += (
                    f'<i style="background:{color};width:25px;height:10px;display:inline-block;margin-right:5px;"></i> '
                    f'<span style="color:black">{stype}</span><br>'
                )
            full_html = f'''
            <div style="
                position: fixed;
                bottom: 25px;
                left: 25px;
                z-index: 9999;
                background: white;
                padding: 25px;
                border: 5px solid #ccc;
            ">
                {legend_html}
            </div>
            '''
            m.get_root().html.add_child(folium.Element(full_html))


def get_dest_mmsi(date_start: str, date_end: str, list_mmsi_user: List[int]) -> pd.DataFrame:
    """
    Récupère, pour chaque MMSI spécifié, les 10 dernières destinations enregistrées dans la base
    entre les dates spécifiées.

    Args:
        date_start : date de début au format YYYY-MM-DD.
        date_end : date de fin au format YYYY-MM-DD.
        list_mmsi_user : liste des MMSI sélectionnés par l'utilisateur.

    Returns:
        rows : Une liste de tuples (mmsi, destination), contenant au maximum 10 destinations par MMSI.
    """
    if not list_mmsi_user or str(list_mmsi_user).strip() in ("[]", ""):
        return []

    mmsi_str = ','.join(map(str, list_mmsi_user))
    sql_get = f"""SELECT mmsi, destination 
    FROM (
        SELECT
            mmsi,
            destination,
            ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY timestamp DESC) AS rn
        FROM voyage_data
        WHERE mmsi IN ({mmsi_str})
          AND timestamp >= '{date_start}'
          AND timestamp <= '{date_end}'
    ) sub
    WHERE rn <= 10
    """
    conn_loc = connect_pgsql()
    cur_loc = conn_loc.cursor()
    cur_loc.execute(sql_get)
    rows = cur_loc.fetchall()
    cur_loc.close()
    conn_loc.close()

    df_destinations = pd.DataFrame(rows, columns=["mmsi", "Destinations uniques (dans l'ordre récent)"])
    df_destinations["Destinations uniques (dans l'ordre récent)"] = df_destinations["Destinations uniques (dans l'ordre récent)"].apply(lambda x: x if isinstance(x, str) else "Aucune destination")


    return df_destinations

def get_ihs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Récupère les informations de dimensions et de type de navire depuis la base IHS,
    à partir d'un DataFrame contenant des MMSI.

    Args:
        df: DataFrame contenant une colonne 'mmsi'.

    Returns:
        Un DataFrame contenant les colonnes:
        - mmsi
        - Ship type from IHS
        - Ship type ID
        - a, b, c, d, Draft (dimensions brutes)
        - Length, Width, Size parameter
        - Ship type for pie chart
    """
    mmsi_list = ','.join(map(str, df['mmsi'].unique()))

    sql_get = f"""
    SELECT mmsi, ship_type, ship_type_id, a, b, c, d, draft
    FROM static_data_ihs_id
    WHERE mmsi IN ({mmsi_list});
    """
    conn_loc = connect_pgsql()
    cur_loc = conn_loc.cursor()
    cur_loc.execute(sql_get)
    rows = cur_loc.fetchall()
    rows_df = pd.DataFrame(rows, columns=['mmsi', 'Ship type from IHS', 'Ship type ID', 'a', 'b', 'c', 'd', 'Draft'])

    rows_df['Length'] = rows_df['a'] + rows_df['b']
    rows_df['Width'] = rows_df['c'] + rows_df['d']
    rows_df['Size parameter'] = rows_df['Length'] * rows_df['Width']
    rows_df['Ship type from IHS'] = rows_df['Ship type from IHS'].fillna('Unknown')

    type_counts = rows_df['Ship type from IHS'].value_counts(normalize=True)
    rare_types = type_counts[type_counts < 0.02].index
    rows_df['Ship type for pie chart'] = rows_df['Ship type from IHS'].apply(
        lambda x: 'Other' if x in rare_types else x
    )
    rows_df.replace(0, pd.NA, inplace=True)

    cur_loc.close()
    conn_loc.close()

    return rows_df

def add_points_circle(
    m: folium.Map,
    df: pd.DataFrame,
    colormap: object = None,
    size_choice: str = None,
    opacity_choice: int = 80,
    page_type: str = None
) -> None:
    """
    Ajoute des cercles (ou polygones selon le choix de l'utilisateur) sur une carte Folium à partir d'un DataFrame.

    Args:
        m: objet folium.Map sur lequel ajouter les points.
        df: DataFrame contenant les colonnes lat, long, mmsi, timestamp, sog, Draft, Length, Width.
        colormap: objet Colormap avec méthodes color_per_row() et add_legend(map).
        size_choice: si "Constante", dessine des cercles fixes ; sinon, dessine des buffers à taille variable.
        opacity_choice: opacité entre 0 et 100.
        page_type: active ou non le tracé des trajectoires selon la page.
    
    Returns:
        None
    """
    if colormap:
        df['color'] = df.apply(colormap.color_per_row(), axis=1)
        colormap.add_legend(m)
    else:
        df['color'] = 'blue'
    
    if page_type:
            for mmsi, group in df.groupby('mmsi'):
                group_sorted = group.sort_values('timestamp')
                points = list(zip(group_sorted['lat'], group_sorted['long']))
                if len(points) > 1:
                    folium.PolyLine(
                        locations=points,
                        color='black',
                        weight=2,
                        opacity=0.4,
                        tooltip=f"MMSI: {int(mmsi)}"
                    ).add_to(m)

    if size_choice == "Constante":
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=(row['lat'], row['long']),
                radius=8,
                color=row['color'],
                fill=True,
                fill_color=row['color'],
                fill_opacity=opacity_choice / 100,
                opacity=0,
                tooltip=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}",
                popup=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}"
            ).add_to(m)

    else:
        gdf = gpd.GeoDataFrame(
            df,
            geometry=[Point(lon, lat) for lat, lon in zip(df['lat'], df['long'])],
            crs="EPSG:4326"
        )
        gdf_proj = gdf.to_crs(epsg=3857)
        gdf_proj['geometry'] = gdf_proj.apply(
            lambda row: row.geometry.buffer(float(row['Length']) / 2)
            if pd.notna(row['Length']) and row['Length'] > 0
            else row.geometry.buffer(5),
            axis=1
        )
        gdf_buffered = gdf_proj.to_crs(epsg=4326)

        

        for _, row in gdf_buffered.iterrows():
            folium.GeoJson(
                row['geometry'],
                style_function=lambda feature, color=row['color']: {
                    'color': color,
                    'opacity': opacity_choice / 100,
                    'fillColor': color,
                    'fillOpacity': opacity_choice / 100,
                    'weight': 1,
                },
                tooltip=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}",
                popup=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}"
            ).add_to(m)

def add_points_poly(
    m: folium.Map,
    df: pd.DataFrame,
    colormap: object = None,
    opacity_choice: int = 80,
    page_type: str = None
) -> None:
    """
    Ajoute des polygones (ex: flèches de bateau) sur une carte Folium à partir de géométries précalculées dans `polygon`.

    Args:
        m: objet folium.Map sur lequel ajouter les polygones.
        df: DataFrame avec une colonne`polygon contenant des objets shapely.geometry.Polygon (et tout le reste).
        colormap: objet Colormap avec méthodes color_per_row() et add_legend(map).
        opacity_choice: opacité entre 0 et 100.
        page_type: active ou non le tracé des trajectoires selon la page.
    
    Returns:
        None
    """
    df = df.dropna(subset=['polygon']).copy()

    if colormap:
        df['color'] = df.apply(colormap.color_per_row(), axis=1)
        colormap.add_legend(m)

    gdf = gpd.GeoDataFrame(df, geometry=df["polygon"], crs="EPSG:4326")

    if page_type:
        for mmsi, group in df.groupby('mmsi'):
            group_sorted = group.sort_values('timestamp')
            points = list(zip(group_sorted['lat'], group_sorted['long']))
            if len(points) > 1:
                folium.PolyLine(
                    locations=points,
                    color='black',
                    weight=2,
                    opacity=0.4,
                    tooltip=f"MMSI: {int(mmsi)}"
                ).add_to(m)

    for _, row in gdf.iterrows():
        folium.GeoJson(
            row['geometry'],
            style_function=lambda feature, color=row['color'] if colormap else 'blue': {
                'color': color,
                'opacity': opacity_choice / 100,
                'fillColor': color,
                'fillOpacity': opacity_choice / 100,
                'weight': 1,
            },
            tooltip=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}",
            popup=f"MMSI: {int(row['mmsi'])} | Longueur : {row['Length']} m | Largeur : {row['Width']} m | Tirant d'eau : {row['Draft']} m | Vitesse : {row['sog']} nd | Timestamp : {row['timestamp']}"
        ).add_to(m)

def create_poly_with_arrow(
    df_input: pd.DataFrame
) -> List[Optional[Polygon]]:
    """
    Crée des polygones orientés en forme de bateau avec flèche (provenance des dimensions a, b, c, d + cap).

    Args:
        df_input: DataFrame complet avec les colonnes dynamiques et statiques.

    Returns:
        polys: Une liste de polygones (ou None si données manquantes) représentant chaque navire avec orientation.
    """
    transformer_to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    transformer_to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    arrow_length_factor = 0.2
    boat_length_factor = 1.3
    boat_width_factor = 1

    polys: List[Optional[Polygon]] = []

    required_cols = {"a", "b", "c", "d", "long", "lat"}
    missing = required_cols - set(df_input.columns)
    if missing:
        raise KeyError(f"df_input missing required columns: {sorted(missing)}")

    for _, row in df_input.iterrows():
        if (
            pd.isna(row["a"]) or pd.isna(row["b"]) or pd.isna(row["c"]) or pd.isna(row["d"]) or
            pd.isna(row["long"]) or pd.isna(row["lat"])
        ):
            polys.append(None)
            continue

        a = float(row["a"]) * 0.8 * boat_length_factor
        b = float(row["b"]) * 0.8 * boat_length_factor  
        c = float(row["c"]) * boat_width_factor   
        d = float(row["d"]) * boat_width_factor  

        lon = float(row["long"])
        lat = float(row["lat"])
        cog = float(row.get("cog", 0.0)) if pd.notna(row.get("cog", 0.0)) else 0.0
        angle_deg = cog

        x_center, y_center = transformer_to_m.transform(lon, lat)

        full_poly_corners_ccw = np.array([
            [-c, -b],
            [ d, -b],
            [ d,  a],
            [(-c+d)/2, a + (a+b) * arrow_length_factor],
            [-c,  a]
        ])

        angle_rad = math.radians(-angle_deg)
        rotation = np.array([
            [math.cos(angle_rad), -math.sin(angle_rad)],
            [math.sin(angle_rad),  math.cos(angle_rad)]
        ])
        rotated = (full_poly_corners_ccw @ rotation.T)
        translated = rotated + np.array([x_center, y_center])
        lonlat_corners = [transformer_to_deg.transform(x, y) for x, y in translated]

        polygon = Polygon(lonlat_corners)
        polys.append(polygon)

    return polys



