# src/factory.py
import simpy
import math
from typing import Dict
from config.settings import ConfigManager

class FactoryEnvironment:
    """
    Fiziksel Üretim Tesisinin Dijital İkiz (In-Memory) Altyapı Mimarı.
    Kaynakları, öncelikli kuyrukları ve ara stok kapasitelerini (Buffer) güvenle yönetir.
    """
    def __init__(self, env: simpy.Environment, config: ConfigManager):
        self.env = env
        self.config = config
        
        # 1. GÜVENLİK (TYPE SAFETY): Operatör sayısı her zaman tam sayı ve en az 1 olmalıdır.
        op_count = max(1, int(self.config.resources.get("operator_count", 5)))
        
        # Operatörler için PriorityResource ZORUNLUDUR (Bakım/Arıza anında öncelik=0 ile araya girerler)
        self.operators = simpy.PriorityResource(env, capacity=op_count)
        
        # Tip tanımlamaları (IDE dostu)
        self.stations: Dict[str, simpy.PriorityResource] = {}
        self.buffers: Dict[str, simpy.Store] = {}
        
        caps = self.config.resources.get("capacities", {})
        station_configs = self.config.stations
        
        for station_name, cfg in station_configs.items():
            # 2. GÜVENLİK (MAKİNE SAYISI): Kapasite kesinlikle integer ve >0 olmalıdır.
            raw_cap = caps.get(station_name, 1)
            capacity = max(1, int(raw_cap))
            
            # Öncelikli Makine Kaynağı (1: Normal Üretim, 0: Acil Arıza Bakımı)
            self.stations[station_name] = simpy.PriorityResource(env, capacity=capacity)
            
            # 3. MİMARİ ESNEKLİK (INFINITE BUFFER): Eğer config 'inf' derse, kapasiteyi sonsuz yap.
            buf_cap_raw = cfg.get("buffer_capacity", 10)
            
            if buf_cap_raw == "inf" or buf_cap_raw == float('inf'):
                buffer_capacity = math.inf
            else:
                buffer_capacity = max(1, int(buf_cap_raw))
                
            self.buffers[station_name] = simpy.Store(env, capacity=buffer_capacity)