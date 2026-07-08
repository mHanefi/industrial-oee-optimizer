# src/entities.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

class MachineState(Enum):
    IDLE = "STARVATION"               
    PROCESSING = "WORKING"            
    SETUP = "SETUP_CHANGE"            
    BLOCKED = "BLOCKED"               
    DOWN = "BREAKDOWN"                
    WAIT_OPERATOR = "WAIT_OPERATOR"   
    WAIT_MAINTENANCE = "WAIT_MAINT"   
    PLANNED_DOWNTIME = "PLANNED_DOWN" 

class QualityStatus(Enum):
    PENDING = "BEKLIYOR"
    GOOD = "SAĞLAM"
    REWORK = "REWORK"
    SCRAP = "HURDA"

@dataclass
class Part:
    id: str
    creation_time: float
    routing_history: List[str] = field(default_factory=list)
    quality_status: QualityStatus = field(default=QualityStatus.PENDING)
    is_reworked: bool = False  
    rework_return_station: Optional[str] = None 
    completion_time: Optional[float] = None
    lifecycle_logs: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def _get_latest_key(self, station_name: str) -> str:
        """
        AKADEMİK ÇÖZÜM: Rework döngülerinde (Yeniden Giriş) verilerin birbirini ezmesini engeller.
        Örn: NDT -> NDT_2 -> NDT_3 şeklinde anahtar üretir.
        """
        if station_name not in self.lifecycle_logs:
            return station_name
        
        counter = 2
        while f"{station_name}_{counter}" in self.lifecycle_logs:
            counter += 1
            
        # Eğer log_arrival çalışmışsa yeni key'i üretir, 
        # log_process_start/end ise zaten açık olan son key'i kullanır.
        return f"{station_name}_{counter-1}"

    def log_arrival(self, station_name: str, current_time: float):
        # Eğer istasyona daha önce girilmişse yeni bir key yarat
        key = station_name
        if key in self.lifecycle_logs:
            counter = 2
            while f"{station_name}_{counter}" in self.lifecycle_logs:
                counter += 1
            key = f"{station_name}_{counter}"
            
        self.lifecycle_logs[key] = {"queue_entry": round(current_time, 4)}

    def log_process_start(self, station_name: str, current_time: float):
        key = self._get_latest_key(station_name)
        if key in self.lifecycle_logs:
            self.lifecycle_logs[key]["process_start"] = round(current_time, 4)

    def log_process_end(self, station_name: str, current_time: float):
        key = self._get_latest_key(station_name)
        if key in self.lifecycle_logs:
            self.lifecycle_logs[key]["process_end"] = round(current_time, 4)
            self.routing_history.append(station_name)

    def finalize(self, current_time: float, status: QualityStatus):
        self.completion_time = round(current_time, 4)
        self.quality_status = status