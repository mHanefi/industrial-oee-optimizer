# src/analytics.py
import pandas as pd
from typing import Dict
from config.settings import ConfigManager
from src.entities import QualityStatus, MachineState

class AnalyticsEngine:
    def __init__(self, df_parts: pd.DataFrame, df_states: pd.DataFrame, config: ConfigManager):
        self.df_parts = df_parts
        self.df_states = df_states
        self.config = config
        self.shift_time = self.config.simulation.get("shift_duration_minutes", 480.0)
        self.warmup_fraction = self.config.simulation.get("warmup_fraction", 0.15)
        
        self.is_valid = not self.df_parts.empty and not self.df_states.empty
        if self.is_valid:
            self._apply_warmup_filter()

    def _apply_warmup_filter(self):
        warmup_threshold = self.shift_time * self.warmup_fraction 
        
        # Parçalar için filtreleme
        self.df_parts = self.df_parts[self.df_parts['completion_time'] > warmup_threshold].copy()
        
        # Durumlar için başlangıç ve bitiş zamanı makaslaması (Sızıntı engellendi)
        df_st = self.df_states[self.df_states['end_time'] > warmup_threshold].copy()
        df_st.loc[df_st['start_time'] < warmup_threshold, 'start_time'] = warmup_threshold
        df_st['duration'] = df_st['end_time'] - df_st['start_time']
        self.df_states = df_st[df_st['duration'] > 0].copy()
        
        self.is_valid = not self.df_parts.empty

    def calculate_bottleneck(self) -> str:
        if not self.is_valid: return "Veri Yetersiz"
        active_states = [MachineState.PROCESSING.value]
        df_active = self.df_states[self.df_states['state'].isin(active_states)]
        if df_active.empty: return self.config.routing[0] if self.config.routing else "Bilinmiyor"
        
        station_loads = df_active.groupby('station')['duration'].sum()
        for st_name in station_loads.index:
            cap = self.config.resources.get("capacities", {}).get(st_name, 1)
            station_loads[st_name] = station_loads[st_name] / cap
            
        return station_loads.idxmax()

    def calculate_oee(self, bottleneck_station: str) -> Dict[str, float]:
        # MÜHENDİSLİK DÜZELTMESİ 1: 'routing' kontrolü 'stations' yapıldı. Rework darboğaz olursa OEE %0 dönme hatası giderildi!
        if not self.is_valid or bottleneck_station not in self.config.stations:
            return {"Availability": 0.0, "Performance": 0.0, "Quality": 0.0, "OEE": 0.0}

        cap = self.config.resources.get("capacities", {}).get(bottleneck_station, 1)
        net_time_per_machine = self.shift_time * (1.0 - self.warmup_fraction)
        total_net_time = net_time_per_machine * cap 
        
        df_planned = self.df_states[(self.df_states['station'] == bottleneck_station) & (self.df_states['state'] == MachineState.PLANNED_DOWNTIME.value)]
        planned_downtime = df_planned['duration'].sum() if not df_planned.empty else 0.0
        planned_production_time = max(0.1, total_net_time - planned_downtime)
        
        loss_states = [MachineState.DOWN.value, MachineState.WAIT_MAINTENANCE.value, MachineState.SETUP.value, MachineState.WAIT_OPERATOR.value]
        df_loss = self.df_states[(self.df_states['station'] == bottleneck_station) & (self.df_states['state'].isin(loss_states))]
        unplanned_downtime = df_loss['duration'].sum() if not df_loss.empty else 0.0
        
        operating_time = max(0.1, planned_production_time - unplanned_downtime)
        availability = operating_time / planned_production_time
        
        df_processed = self.df_states[(self.df_states['station'] == bottleneck_station) & (self.df_states['state'] == MachineState.PROCESSING.value)]
        total_processed_by_bottleneck = len(df_processed)
        ideal_cycle = self.config.stations.get(bottleneck_station, {}).get("auto_mu", 5.0)
        
        performance = (total_processed_by_bottleneck * ideal_cycle) / operating_time if operating_time > 0 else 0.0
        performance = min(1.0, performance) 
        
        unique_parts = self.df_parts.drop_duplicates(subset=['part_id'], keep='last')
        total_finished = len(unique_parts)
        defects = unique_parts[(unique_parts['is_reworked'] == True) | (unique_parts['status'] == QualityStatus.SCRAP.value)]
        defect_count = len(defects)
        
        quality = (total_finished - defect_count) / total_finished if total_finished > 0 else 0.0
        oee = availability * performance * quality

        return {
            "Availability": round(availability * 100, 2),
            "Performance": round(performance * 100, 2),
            "Quality": round(quality * 100, 2),
            "OEE": round(oee * 100, 2)
        }

    def calculate_copq(self) -> Dict[str, float]:
        if not self.is_valid:
            return {"Scrap": 0.0, "Rework": 0.0, "Downtime": 0.0, "Idle": 0.0, "Total": 0.0}

        fin = self.config.financials
        unique_parts = self.df_parts.drop_duplicates(subset=['part_id'], keep='last')
        
        scrap_count = len(unique_parts[unique_parts['status'] == QualityStatus.SCRAP.value])
        rework_count = len(unique_parts[unique_parts['is_reworked'] == True])
        
        scrap_cost = scrap_count * fin.get("scrap_cost_per_unit", 8500.0)
        rework_cost = rework_count * fin.get("rework_cost_per_unit", 1200.0)
        
        # Sadece plansız duruşlar sistem maliyetidir.
        down_states = [MachineState.DOWN.value, MachineState.WAIT_MAINTENANCE.value]
        downtime_dur = self.df_states[self.df_states['state'].isin(down_states)]['duration'].sum()
        downtime_cost = downtime_dur * fin.get("downtime_cost_per_minute", 150.0)
        
        # MÜHENDİSLİK DÜZELTMESİ 2 (TOC İhlali Giderildi): 
        # Idle (Boş bekleme) maliyeti SADECE DARBOĞAZ istasyonunda yaşanıyorsa bir kayıptır.
        # Diğer makinelerin boş beklemesi WIP'i (stoğu) önler, cezalandırılamaz!
        b_neck = self.calculate_bottleneck()
        idle_dur = self.df_states[(self.df_states['state'] == MachineState.IDLE.value) & (self.df_states['station'] == b_neck)]['duration'].sum()
        idle_cost = idle_dur * fin.get("idle_cost_per_minute", 45.0)
        
        total = scrap_cost + rework_cost + downtime_cost + idle_cost
        
        return {
            "Scrap": round(scrap_cost, 2),
            "Rework": round(rework_cost, 2),
            "Downtime": round(downtime_cost, 2),
            "Idle": round(idle_cost, 2),
            "Total": round(total, 2)
        }