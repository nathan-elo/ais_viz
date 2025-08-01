import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from func import *




st.set_page_config(
    page_title="AIS MAP - Résultats",
    page_icon="🟨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("AIS - 🟨 Mode trajectoire - Graphiques")
st.markdown("---")


st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:

    st.info("Vous pouvez cependant retourner à la page précédente sans perdre vos données.")
    

    if st.button("Retour à la page précédente", use_container_width=True, key="return_from_first", type="primary"):
        st.switch_page("pages/2_Trajectoires.py")
    
    st.markdown("---")

    with st.expander("📑 Pages", True):

        st.markdown("## 🟨 Mode trajectoire - Graphiques :")
        st.markdown("### Sur cette page, les graphiques tirées des données de la page précédente sont disponibles." \
        " Le filtre sur le type des navires n'est pas récupéré et est à appliquer une nouvelle fois directement ici." \
        " Il est possible de télécharger les graphiques en faisant \" Clic droit + Enregistrer l'image sous \".")

df_ihs=st.session_state.get('df_ihs')
df=st.session_state.get("df")
df_dest=st.session_state.get("df_dest")


df_filtered_unique = (
    per_ship_type_filter(df, df_ihs)
    .drop_duplicates()
    .groupby('mmsi', as_index=False)
    .first()
)

df_filtered_unique['mmsi'] = df_filtered_unique['mmsi'].astype(int)

df_filtered_unique = df_filtered_unique.merge(df_dest, how='left', on='mmsi')

df_filtered_unique["Destinations uniques (dans l'ordre récent)"] = df_filtered_unique["Destinations uniques (dans l'ordre récent)"].astype(str)


 
col1, col2, col3 = st.columns(3)

with st.container():
    
    with col1:
        plt.figure(figsize=(8, 8))
        plt.hist(df_filtered_unique['Width'].dropna(), bins=max(20,int(len(df_ihs['mmsi'].unique().tolist())/5)), color='blue', alpha=0.7)
        plt.axvline(df_filtered_unique['Width'].mean(), color='red', linestyle='--', label='Largeur moyenne')
        plt.title('Distribution des largeurs')
        plt.xlabel('Largeur (m)')
        plt.ylabel('Nombre de navires')
        plt.legend()
        plt.grid(True)
        st.pyplot(plt, clear_figure=True, use_container_width=False)
    with col2:
        plt.figure(figsize=(8, 8))
        plt.hist(df_filtered_unique['Length'].dropna(), bins=max(20,int(len(df_ihs['mmsi'].unique().tolist())/5)), color='blue', alpha=0.7)
        plt.axvline(df_filtered_unique['Length'].mean(), color='red', linestyle='--', label='Longueur moyenne')
        plt.title('Distribution des longueurs')
        plt.xlabel('Longueur (m)')
        plt.ylabel('Nombre de navires')
        plt.legend()
        plt.grid(True)
        st.pyplot(plt, clear_figure=True, use_container_width=False)
    with col3:
        plt.figure(figsize=(8, 8))
        plt.hist(df_filtered_unique['Draft'].dropna(), bins=max(20,int(len(df_ihs['mmsi'].unique().tolist())/5)), color='blue', alpha=0.7)
        plt.axvline(df_filtered_unique['Draft'].mean(), color='red', linestyle='--', label='Tirant d\'eau moyen')
        plt.title('Distribution des tirants d\'eau')
        plt.xlabel('Tirant d\'eau (m)')
        plt.ylabel('Nombre de navires')
        plt.legend()
        plt.grid(True)
        st.pyplot(plt, clear_figure=True, use_container_width=False)

st.markdown("---")


with st.container():

    with col1:
        plt.figure(figsize=(10,6))
        pie_counts = df_filtered_unique['Ship type for pie chart'].value_counts()
        pie_labels = pie_counts.index
        plt.pie(pie_counts, labels=pie_labels, autopct='%1.1f%%', pctdistance=0.81, startangle=140)
        plt.title('Répartition des types de navires')
        plt.grid(True)
        st.pyplot(plt, clear_figure=True, use_container_width=False)

    with col2:
        grouped = (
                df_filtered_unique.groupby(['Length', 'Width'])
                .agg(count=('mmsi', 'count'), mean_draft=('Draft', 'mean'))
                .reset_index()
        )
        plt.figure(figsize=(10,6))
        scatter = plt.scatter(
            grouped['Length'], grouped['Width'],
            c=grouped['mean_draft'], s=grouped['count'] * 10,
            cmap='viridis', alpha=0.5
        )
        plt.colorbar(scatter, label="Tirant d'eau moyen (m)")
        plt.title('Longueur vs largeur (taille en fonction du nombre de navires)')
        plt.xlabel('Longueur (m)')
        plt.ylabel('Largeur (m)')
        plt.grid(True)
        st.pyplot(plt, clear_figure=True, use_container_width=False)

    with col3:

        plt.figure(figsize=(10,6))

        df_box = df_filtered_unique[['Draft', 'Ship type for pie chart']].dropna()
        if not df_box['Draft'].empty:
            df_box_sorted = df_box.sort_values(by='Ship type for pie chart') 
            types = df_box_sorted['Ship type for pie chart'].unique()

            data_to_plot = [df_box_sorted[df_box_sorted['Ship type for pie chart'] == t]['Draft'] for t in types]

            plt.boxplot(data_to_plot, tick_labels=types, showfliers=False)
            plt.title("Tirant d'eau par type de navire")
            plt.xlabel("Type de navire")
            plt.ylabel("Tirant d'eau (m)")
            plt.xticks(rotation=45)
            plt.grid(True)

            st.pyplot(plt, clear_figure=True, use_container_width=False)

    

    df_dest_grouped = (
    df_filtered_unique
    .groupby("mmsi")["Destinations uniques (dans l'ordre récent)"]
    .apply(lambda x: ",".join(sorted(set(d.strip() for d in x if pd.notna(d)))))
    .reset_index()
    )

    df_dest_grouped["Destinations uniques (dans l'ordre récent)"] = df_dest_grouped["Destinations uniques (dans l'ordre récent)"].replace("nan", "Non renseignées").fillna("Non renseignées")

    col1,col2= st.columns([1, 2])
    with col1:
        st.subheader("Destinations uniques (dans l'ordre récent)")


        st.data_editor(
        df_dest_grouped,
        column_config={
            "mmsi":st.column_config.Column(
                "MMSI",
                help="Identifiant unique du navire."
            ),
            "Destinations uniques (dans l'ordre récent)":st.column_config.Column(
                "Destinations uniques (dans l'ordre récent)"
            )
            },
        use_container_width=True,
        hide_index=True
    )

with st.sidebar:


    st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
    st.caption("© 2025 - Visualisation AIS | Nathan - setec international - Pôle Maritime et fluvial")



st.markdown("---")
st.markdown("<hr style='opacity:0.3'>", unsafe_allow_html=True)
st.caption("© 2025 - Visualisation AIS | setec international - Pôle Maritime et fluvial")
