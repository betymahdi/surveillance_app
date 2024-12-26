
# dashboard.py
import streamlit as st
import psutil
import time
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from collections import deque
import threading
from queue import Queue
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from config import MONITORING_CONFIG

class SurveillanceServeur:
    def __init__(self):
        # Paramètres de surveillance
        self.seuil_alerte = MONITORING_CONFIG['alerts']['default_threshold']
        self.max_points = MONITORING_CONFIG['alerts']['history_size']

        # Configuration email
        self.email_config = MONITORING_CONFIG['email']

        # Historique des données
        self.historique_cpu = deque(maxlen=self.max_points)
        self.historique_ram = deque(maxlen=self.max_points)
        self.historique_temps = deque(maxlen=self.max_points)
        self.alert_queue = Queue()  # File pour stocker les alertes

        # Drapeau pour le thread de surveillance
        self.surveillance_active = False

    def envoyer_email_alerte(self, sujet, message):
        """Envoyer un email d'alerte"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender']
            msg['To'] = self.email_config['receiver']
            msg['Subject'] = sujet
            msg.attach(MIMEText(message, 'plain'))

            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['sender'], self.email_config['password'])
                server.send_message(msg)
            return True
        except Exception as e:
            st.error(f"Erreur d'envoi d'email: {e}")
            return False
#Récupérer les données en temps réel sur l'utilisation du CPU, de la RAM et du disque
    def obtenir_metriques(self):
        """Collecter les métriques système actuelles"""
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disque = psutil.disk_usage('/').percent
        return cpu, ram, disque
# la détection avec envoi d'e-mails en cas d'anomalie.
    def detecter_anomalie(self, valeur, nom_metrique):
        """Détecter une anomalie et envoyer une alerte si nécessaire"""
        if valeur > self.seuil_alerte:
            timestamp = datetime.now()
            message = f"ALERTE: {nom_metrique} élevé(e) - {valeur}%"
            self.alert_queue.put((timestamp, message))  # Ajouter l'alerte à la file

# Envoyer email d'alerte
            sujet = f"Alerte Système - {nom_metrique} Critique"
            contenu_email = f"""
            Alerte de surveillance système

            Métrique: {nom_metrique}
            Valeur actuelle: {valeur}%
            Seuil d'alerte: {self.seuil_alerte}%
            Timestamp: {timestamp}

            Ceci est un message automatique généré par le système de surveillance.
            """
            self.envoyer_email_alerte(sujet, contenu_email)
            return True
        return False

    def obtenir_alertes(self):
        """Récupérer les alertes en attente depuis la file d'attente"""
        alertes = []
        while not self.alert_queue.empty():
            alertes.append(self.alert_queue.get())
        return alertes

    def mise_a_jour_historique(self):
        """Mettre à jour l'historique des métriques"""
        cpu, ram, disque = self.obtenir_metriques()
        timestamp = datetime.now()

        self.historique_cpu.append(cpu)
        self.historique_ram.append(ram)
        self.historique_temps.append(timestamp)

        # Vérifier les anomalies
        self.detecter_anomalie(cpu, "CPU")
        self.detecter_anomalie(ram, "RAM")
        self.detecter_anomalie(disque, "Disque")

    def creer_graphique_temps_reel(self):
        """Créer le graphique pour le dashboard"""
        df = pd.DataFrame({
            'Temps': list(self.historique_temps),
            'CPU': list(self.historique_cpu),
            'RAM': list(self.historique_ram)
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Temps'], y=df['CPU'], name='CPU %', line=dict(color='#1f77b4')))
        fig.add_trace(go.Scatter(x=df['Temps'], y=df['RAM'], name='RAM %', line=dict(color='#ff7f0e')))

        fig.update_layout(
            title='Utilisation CPU et RAM en Temps Réel',
            xaxis_title='Temps',
            yaxis_title='Utilisation (%)',
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig

    def demarrer_surveillance(self):
        """Démarrer la surveillance en arrière-plan"""
        self.surveillance_active = True
        thread = threading.Thread(target=self._boucle_surveillance)
        thread.daemon = True
        thread.start()

    def arreter_surveillance(self):
        """Arrêter la surveillance"""
        self.surveillance_active = False

    def _boucle_surveillance(self):
        """Boucle principale de surveillance"""
        while self.surveillance_active:
            self.mise_a_jour_historique()
            time.sleep(MONITORING_CONFIG['alerts']['check_interval'])

def main():
    st.set_page_config(page_title="Surveillance Serveur", layout="wide", initial_sidebar_state="expanded")

    st.title("📊 Dashboard de Surveillance Serveur")

# Initialisation du moniteur démarre la surveillance en temps réel
    if 'moniteur' not in st.session_state:
        st.session_state.moniteur = SurveillanceServeur()
        st.session_state.moniteur.demarrer_surveillance()

 # Contrôles dans la sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        seuil = st.slider("Seuil d'alerte (%)", 0, 100, st.session_state.moniteur.seuil_alerte)
        st.session_state.moniteur.seuil_alerte = seuil

# Métriques actuelles affichage des métriques actuelles (CPU, RAM, et Disque)
    col1, col2, col3 = st.columns(3)
    cpu, ram, disque = st.session_state.moniteur.obtenir_metriques()

    with col1:
        st.metric(label="CPU", value=f"{cpu}%", delta=f"{cpu}%")

    with col2:
        st.metric(label="RAM", value=f"{ram}%", delta=f"{ram}%")

    with col3:
        st.metric(label="Disque", value=f"{disque}%")

# Graphique temps réel
    st.plotly_chart(st.session_state.moniteur.creer_graphique_temps_reel(), use_container_width=True)

# Alertes récentes
    st.subheader("🚨 Alertes Récentes")
    alertes = st.session_state.moniteur.obtenir_alertes()
    if alertes:
        for timestamp, message in alertes:
            st.warning(f"{timestamp.strftime('%H:%M:%S')} - {message}")
    else:
        st.info("Aucune alerte pour le moment")

# Informations détaillées
    with st.expander("📋 Détails du Système"):
        st.subheader("Informations CPU")
        st.write(f"Nombre de cœurs physiques : {psutil.cpu_count(logical=False)}")
        st.write(f"Nombre de cœurs logiques : {psutil.cpu_count(logical=True)}")

        st.subheader("Informations Mémoire")
        mem = psutil.virtual_memory()
        st.write(f"Mémoire totale : {mem.total / (1024**3):.2f} GB")
        st.write(f"Mémoire disponible : {mem.available / (1024**3):.2f} GB")
        st.write(f"Mémoire utilisée : {mem.used / (1024**3):.2f} GB")

        st.subheader("Informations Disque")
        disk = psutil.disk_usage('/')
        st.write(f"Espace total : {disk.total / (1024**3):.2f} GB")
        st.write(f"Espace utilisé : {disk.used / (1024**3):.2f} GB")
        st.write(f"Espace libre : {disk.free / (1024**3):.2f} GB")

if __name__ == "__main__":
    main()
