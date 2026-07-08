# dashboard/app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import ConfigManager
from src.stochastic import StochasticEngine
from src.simulation import run_simulation
from src.analytics import AnalyticsEngine
from src.entities import QualityStatus

st.set_page_config(page_title="Dijital İkiz | OEE Karar Destek", page_icon="🏭", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0B0F19; }
    
    .modern-card {
        background: linear-gradient(145deg, #151A29, #111522);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px; padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        text-align: center; transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .modern-card:hover { transform: translateY(-5px); box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.1); }
    
    .card-title { color: #94A3B8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin-bottom: 10px; }
    .card-value { font-size: 2.5rem; font-weight: 700; background: -webkit-linear-gradient(45deg, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; }
    .card-value-red { background: -webkit-linear-gradient(45deg, #FDA4AF, #E11D48); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .card-value-green { background: -webkit-linear-gradient(45deg, #6EE7B7, #059669); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .card-value-blue { background: -webkit-linear-gradient(45deg, #93C5FD, #2563EB); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .card-subtitle { color: #64748B; font-size: 0.85rem; margin-top: 10px; }

    .stButton>button {
        background: linear-gradient(90deg, #3B82F6 0%, #2563EB 100%) !important; border: none !important; border-radius: 8px !important; color: white !important;
        font-weight: 600 !important; letter-spacing: 1px; padding: 0.5rem 1rem !important; transition: all 0.3s ease; box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.39) !important;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6) !important; }

    .stTabs [data-baseweb="tab-list"] { background-color: transparent; gap: 20px; border-bottom: 1px solid #1E293B; }
    .stTabs [data-baseweb="tab"] { padding: 10px 0; color: #64748B; font-weight: 500; border: none; }
    .stTabs [aria-selected="true"] { color: #38BDF8 !important; border-bottom: 2px solid #38BDF8 !important; background-color: transparent; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-weight: 700; background: -webkit-linear-gradient(45deg, #38BDF8, #3B82F6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>🏭 MES Dijital İkiz & TOC Karar Destek Motoru</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 15px; margin-bottom: 30px;'>Gelişmiş Senaryo Simülasyonu • Kısıtlar Teorisi (TOC) • JIPM OEE Analizi</p>", unsafe_allow_html=True)

    try:
        config = ConfigManager(os.path.join("config", "config.yaml"))
    except Exception as e:
        st.error(f"Konfigürasyon Hatası: {e}")
        return

    with st.form("simulation_form"):
        st.markdown("### 🎛️ Dijital İkiz Senaryo Parametreleri (Tümü Dinamik)")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("<span style='color:#38BDF8; font-weight:600;'>🏗️ Kapasite & İşgücü</span>", unsafe_allow_html=True)
            op_count = st.number_input("Operatör Sayısı", 1, 20, config.resources.get("operator_count", 5))
            cap_kaynak = st.number_input("Kaynak Makine Sayısı", 1, 10, config.resources.get("capacities", {}).get("Kaynak", 1))
            cap_termal = st.number_input("Termal Makine Sayısı", 1, 10, config.resources.get("capacities", {}).get("Termal", 1))

        with col2:
            st.markdown("<span style='color:#38BDF8; font-weight:600;'>⏱️ Çevrim Süreleri (Dk)</span>", unsafe_allow_html=True)
            mu_kaynak = st.number_input("Kaynak İşlem (Ort. Süre)", 1.0, 50.0, float(config.stations.get("Kaynak", {}).get("auto_mu", 15.0)))
            mu_termal = st.number_input("Termal İşlem (Ort. Süre)", 1.0, 50.0, float(config.stations.get("Termal", {}).get("auto_mu", 20.0)))
            target_rho = st.slider("Hedef Sistem Yükü (Rho)", 0.70, 0.99, config.simulation.get("target_utilization", 0.95))

        with col3:
            st.markdown("<span style='color:#38BDF8; font-weight:600;'>🛠️ Arıza & Kalite Kontrol</span>", unsafe_allow_html=True)
            quality_fty = st.slider("NDT FTY (İlk Seferde Doğru) %", 50, 100, int(config.quality.get("ndt_fty_min", 0.85) * 100))
            direct_scrap_rate = st.slider("Hatalı Üründe Direkt Hurda Oranı %", 0, 100, int(config.quality.get("direct_scrap_rate", 0.15) * 100))
            mtbf_kaynak = st.number_input("Kaynak MTBF (Arıza Aralığı Dk)", 50.0, 1000.0, float(config.maintenance.get("Kaynak", {}).get("mtbf", 300.0)))

        with col4:
            st.markdown("<span style='color:#38BDF8; font-weight:600;'>💸 Finans & Kararlılık</span>", unsafe_allow_html=True)
            scrap_c = st.number_input("Birim Hurda (₺)", 100.0, 50000.0, config.financials.get("scrap_cost_per_unit", 8500.0))
            rework_c = st.number_input("Birim Rework (₺)", 100.0, 10000.0, config.financials.get("rework_cost_per_unit", 1200.0))
            replications = st.slider("Monte Carlo Replikasyonu", 1, 20, 5)

        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("🚀 SENARYOYU ÇALIŞTIR VE ANALİZ ET", use_container_width=True)

    if submit_button:
        config.settings["resources"]["operator_count"] = op_count
        config.settings["resources"]["capacities"]["Kaynak"] = cap_kaynak
        config.settings["resources"]["capacities"]["Termal"] = cap_termal
        config.settings["stations"]["Kaynak"]["auto_mu"] = mu_kaynak
        config.settings["stations"]["Termal"]["auto_mu"] = mu_termal
        config.settings["simulation"]["target_utilization"] = target_rho
        config.settings["maintenance"]["Kaynak"]["mtbf"] = mtbf_kaynak
        config.settings["quality"]["ndt_fty_min"] = quality_fty / 100.0
        config.settings["quality"]["ndt_fty_max"] = min(1.0, (quality_fty + 5) / 100.0)
        config.settings["quality"]["direct_scrap_rate"] = direct_scrap_rate / 100.0
        config.settings["financials"]["scrap_cost_per_unit"] = scrap_c
        config.settings["financials"]["rework_cost_per_unit"] = rework_c

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        oee_results, copq_results = [], []
        bottlenecks = {}
        all_states_log, all_parts_log = [], []
        last_df_parts, last_df_states = None, None
        
        for i in range(replications):
            status_text.markdown(f"<span style='color:#38BDF8;'>*( ⏳ ) Olasılık Motoru Çalışıyor... Paralel Evren {i+1} / {replications}*</span>", unsafe_allow_html=True)
            stochastic = StochasticEngine(seed=42 + i)
            df_parts, df_states = run_simulation(config, stochastic)
            analytics = AnalyticsEngine(df_parts, df_states, config)
            
            if analytics.is_valid:
                b_neck = analytics.calculate_bottleneck()
                bottlenecks[b_neck] = bottlenecks.get(b_neck, 0) + 1
                oee_results.append(analytics.calculate_oee(b_neck))
                copq_results.append(analytics.calculate_copq())
                all_states_log.append(df_states)
                all_parts_log.append(df_parts)
                last_df_parts, last_df_states = df_parts, df_states
            
            progress_bar.progress((i + 1) / replications)
            
        status_text.empty()
        progress_bar.empty()

        if not oee_results:
            st.error("Veri üretilemedi. Sistemi çok mu zorladınız? (Hedef Yük oranını düşürmeyi deneyin)")
            return

        st.markdown("<br>", unsafe_allow_html=True)
        primary_bottleneck = max(bottlenecks, key=bottlenecks.get)
        avg_oee = np.mean([res["OEE"] for res in oee_results])
        avg_copq = np.mean([res["Total"] for res in copq_results])

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""
            <div class="modern-card">
                <div class="card-title">🚨 Sistem Kısıtı (Darboğaz)</div>
                <div class="card-value card-value-red">{primary_bottleneck}</div>
                <div class="card-subtitle">Bu istasyonun kapasitesini artırın</div>
            </div>
        """, unsafe_allow_html=True)
        
        c2.markdown(f"""
            <div class="modern-card">
                <div class="card-title">📉 Ortalama Sistem OEE</div>
                <div class="card-value card-value-green">%{avg_oee:.1f}</div>
                <div class="card-subtitle">Dünya Sınıfı Üretim Hedefi: %85</div>
            </div>
        """, unsafe_allow_html=True)

        c3.markdown(f"""
            <div class="modern-card">
                <div class="card-title">💸 Toplam Finansal Zayiat (COPQ)</div>
                <div class="card-value card-value-blue">{avg_copq:,.0f} ₺</div>
                <div class="card-subtitle">Vardiya Başına Hurda, Rework ve Duruş</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["⚙️ OEE & Kısıt Analizi", "🪙 Kalite & Finansal Dağılım", "📁 Olay Günlükleri (Ham Veri)"])

        def apply_modern_layout(fig, title=""):
            fig.update_layout(
                title={'text': title, 'font': {'color': '#F8FAFC', 'size': 18}},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font={'family': 'Inter', 'color': '#94A3B8'}, margin=dict(l=20, r=20, t=50, b=20)
            )
            fig.update_xaxes(showgrid=False, zeroline=False, linecolor='#1E293B')
            fig.update_yaxes(showgrid=True, gridcolor='#1E293B', zeroline=False, linecolor='#1E293B')
            return fig

        with tab1:
            st.markdown("<br><h4 style='color: #F8FAFC; margin-bottom: 20px;'>⚙️ OEE Çarpanları (A x P x Q)</h4>", unsafe_allow_html=True)
            
            avg_a = np.mean([res["Availability"] for res in oee_results])
            avg_p = np.mean([res["Performance"] for res in oee_results])
            avg_q = np.mean([res["Quality"] for res in oee_results])

            col_g1, col_g2, col_g3 = st.columns(3)
            def create_modern_gauge(val, title, color):
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=val, 
                    title={'text': title, 'font': {'size': 14, 'color': '#94A3B8', 'family': 'Inter'}},
                    number={'suffix': "%", 'font': {'color': '#F8FAFC', 'size': 32, 'family': 'Inter', 'weight': 'bold'}},
                    gauge={
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#1E293B"},
                        'bar': {'color': color, 'thickness': 0.2},
                        'bgcolor': "#151A29", 'borderwidth': 0,
                        'steps': [
                            {'range': [0, 60], 'color': "rgba(225, 29, 72, 0.1)"}, 
                            {'range': [60, 85], 'color': "rgba(245, 158, 11, 0.1)"}, 
                            {'range': [85, 100], 'color': "rgba(16, 185, 129, 0.1)"}] 
                    }
                ))
                fig.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)")
                return fig

            col_g1.plotly_chart(create_modern_gauge(avg_a, "Kullanılabilirlik (A)", "#38BDF8"), use_container_width=True)
            col_g2.plotly_chart(create_modern_gauge(avg_p, "Performans (P)", "#FBBF24"), use_container_width=True)
            col_g3.plotly_chart(create_modern_gauge(avg_q, "Kalite (Q)", "#34D399"), use_container_width=True)
            st.markdown("<hr style='border-color: #1E293B; margin: 30px 0;'>", unsafe_allow_html=True)
            
            col_r1, col_r2 = st.columns([1.5, 1])
            with col_r1:
                combined_states = pd.concat(all_states_log)
                state_summary = combined_states.groupby(['station', 'state'])['duration'].sum().reset_index()
                state_summary['duration'] = state_summary['duration'] / replications 
                
                color_map = {
                    "WORKING": "#10B981", "PROCESSING": "#10B981", 
                    "STARVATION": "#334155", "IDLE": "#334155",    
                    "BLOCKED": "#F43F5E",                          
                    "SETUP_CHANGE": "#F59E0B", "SETUP": "#F59E0B", 
                    "BREAKDOWN": "#8B5CF6", "DOWN": "#8B5CF6",     
                    "WAIT_OPERATOR": "#F97316", "WAIT_MAINT": "#F97316"
                }
                fig_states = px.bar(state_summary, x="station", y="duration", color="state", color_discrete_map=color_map)
                fig_states = apply_modern_layout(fig_states, "⏱️ İstasyon Yükü ve Darboğaz Kanıtı (Dk)")
                st.plotly_chart(fig_states, use_container_width=True)

            with col_r2:
                fig_hist = px.histogram(x=[res["OEE"] for res in oee_results], nbins=10, opacity=0.8)
                fig_hist.update_traces(marker_color='#38BDF8')
                fig_hist.add_vline(x=avg_oee, line_dash="dash", line_color="#F43F5E")
                fig_hist = apply_modern_layout(fig_hist, "📉 Sistem Kararlılığı (OEE Sapması)")
                st.plotly_chart(fig_hist, use_container_width=True)

        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            col_p1, col_p2 = st.columns([1, 1.5])
            
            with col_p1:
                combined_parts = pd.concat(all_parts_log)
                unique_parts = combined_parts.drop_duplicates(subset=['part_id'], keep='last')
                
                total_qty = len(unique_parts) / replications
                scrap_qty = len(unique_parts[unique_parts['status'] == QualityStatus.SCRAP.value]) / replications
                rework_qty = len(unique_parts[unique_parts['is_reworked'] == True]) / replications
                good_qty = total_qty - scrap_qty - rework_qty

                fig_funnel = go.Figure(go.Funnel(
                    y=["Üretim", "Sağlam (FTY)", "Yeniden İşlem", "Hurda"],
                    x=[total_qty, good_qty, rework_qty, scrap_qty],
                    textinfo="value+percent initial",
                    marker={"color": ["#38BDF8", "#10B981", "#F59E0B", "#F43F5E"]}
                ))
                fig_funnel = apply_modern_layout(fig_funnel, "📦 Kalite Daralma Hunisi")
                st.plotly_chart(fig_funnel, use_container_width=True)

            with col_p2:
                df_copq = pd.DataFrame({
                    "Kategori": ["Hurda", "Plansız Duruş", "Rework", "Atıl"],
                    "Maliyet": [np.mean([res["Scrap"] for res in copq_results]), 
                                np.mean([res["Downtime"] for res in copq_results]), 
                                np.mean([res["Rework"] for res in copq_results]), 
                                np.mean([res["Idle"] for res in copq_results])]
                }).sort_values(by="Maliyet", ascending=False).reset_index(drop=True)
                
                df_copq["Kümülatif %"] = (df_copq["Maliyet"].cumsum() / df_copq["Maliyet"].sum()) * 100
                
                fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
                fig_pareto.add_trace(go.Bar(x=df_copq["Kategori"], y=df_copq["Maliyet"], marker_color='#6366F1', opacity=0.9), secondary_y=False) 
                fig_pareto.add_trace(go.Scatter(x=df_copq["Kategori"], y=df_copq["Kümülatif %"], line=dict(color='#FCD34D', width=4), marker=dict(size=10)), secondary_y=True)
                fig_pareto = apply_modern_layout(fig_pareto, "🪙 COPQ Pareto Analizi (80/20)")
                fig_pareto.update_yaxes(title_text="Kümülatif %", range=[0, 105], showgrid=False, secondary_y=True)
                fig_pareto.update_layout(showlegend=False)
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab3:
            st.markdown("<br>#### 📝 Sistem Olay Günlükleri (Ham Veri)", unsafe_allow_html=True)
            if last_df_states is not None:
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button("📥 Makine Loglarını İndir (CSV)", data=last_df_states.to_csv(index=False).encode('utf-8'), file_name='makine_log.csv', mime='text/csv')
                    st.dataframe(last_df_states.head(50), use_container_width=True)
                with col_d2:
                    st.download_button("📥 Parça Loglarını İndir (CSV)", data=last_df_parts.to_csv(index=False).encode('utf-8'), file_name='parca_log.csv', mime='text/csv')
                    st.dataframe(last_df_parts.head(50), use_container_width=True)

if __name__ == "__main__":
    main()