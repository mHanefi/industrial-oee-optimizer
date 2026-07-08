# src/simulation.py
import simpy
import pandas as pd
from typing import Tuple, List, Dict, Any

from config.settings import ConfigManager
from src.stochastic import StochasticEngine
from src.entities import Part, QualityStatus, MachineState
from src.factory import FactoryEnvironment

class SimulationLogger:
    def __init__(self):
        self.part_logs: List[Dict[str, Any]] = []
        self.state_logs: List[Dict[str, Any]] = []

def run_simulation(config: ConfigManager, stochastic: StochasticEngine) -> Tuple[pd.DataFrame, pd.DataFrame]:
    env = simpy.Environment()
    factory = FactoryEnvironment(env, config)
    logger = SimulationLogger()
    routing = config.routing

    def log_state(station: str, state: str, start_time: float, end_time: float):
        """Veri sızıntısını önleyen yeni nesil loglama mimarisi"""
        dur = end_time - start_time
        if dur > 0:
            logger.state_logs.append({"station": station, "state": state, "start_time": start_time, "end_time": end_time, "duration": dur})

    def break_manager_station(station_name: str, worker_id: int):
        resource = factory.stations[station_name]
        for b in config.simulation.get("breaks", []):
            if b["start_time"] > env.now:
                yield env.timeout(b["start_time"] - env.now)
            start_break = env.now
            with resource.request(priority=-1) as req:
                yield req
                yield env.timeout(b["duration"])
                log_state(station_name, MachineState.PLANNED_DOWNTIME.value, start_break, env.now)

    def breakdown_manager(station_name: str, worker_id: int):
        maint_cfg = config.maintenance.get(station_name)
        if not maint_cfg: return 
        resource = factory.stations[station_name]
        
        while True:
            yield env.timeout(stochastic.get_exponential_time(maint_cfg.get("mtbf", 300.0)))
            start_down = env.now
            with resource.request(priority=0) as req:
                yield req
                start_maint_wait = env.now
                with factory.operators.request(priority=0) as op_req:
                    yield op_req
                    log_state(station_name, MachineState.WAIT_MAINTENANCE.value, start_maint_wait, env.now)
                    
                    start_repair = env.now
                    repair_time = stochastic.get_normal_time(maint_cfg.get("mttr_mu", 30.0), maint_cfg.get("mttr_sigma", 5.0))
                    yield env.timeout(repair_time)
                    log_state(station_name, MachineState.DOWN.value, start_repair, env.now)

    def station_worker(station_name: str, default_next_station: str = None, worker_id: int = 1):
        station_cfg = config.stations.get(station_name, {})
        buffer = factory.buffers[station_name]
        resource = factory.stations[station_name]
        
        while True:
            start_idle = env.now
            part = yield buffer.get()
            log_state(station_name, MachineState.IDLE.value, start_idle, env.now)
            
            part.log_process_start(station_name, env.now)
            
            with resource.request(priority=1) as req:
                yield req
                
                start_setup_wait = env.now
                with factory.operators.request(priority=1) as op_req:
                    yield op_req
                    log_state(station_name, MachineState.WAIT_OPERATOR.value, start_setup_wait, env.now)
                    
                    start_setup = env.now
                    setup_t = stochastic.get_normal_time(station_cfg.get("setup_mu", 1.0), station_cfg.get("setup_sigma", 0.1))
                    yield env.timeout(setup_t)
                    log_state(station_name, MachineState.SETUP.value, start_setup, env.now)

                start_proc = env.now
                proc_t = stochastic.get_lognormal_time(station_cfg.get("auto_mu", 5.0), station_cfg.get("auto_sigma", 1.0))
                yield env.timeout(proc_t)
                part.log_process_end(station_name, env.now)
                log_state(station_name, MachineState.PROCESSING.value, start_proc, env.now)
                
                # KALİTE KONTROL
                is_q_gate = station_cfg.get("is_quality_gate", False)
                if is_q_gate or station_name == routing[-1]:
                    if station_name == "Rework":
                        rec = stochastic.get_uniform_probability(config.quality.get("rework_recovery_min", 0.70), config.quality.get("rework_recovery_max", 0.90))
                        part.quality_status = QualityStatus.GOOD if stochastic.evaluate_chance(rec) else QualityStatus.SCRAP
                    else:
                        fty = stochastic.get_uniform_probability(config.quality.get("ndt_fty_min", 0.75), config.quality.get("ndt_fty_max", 0.88))
                        if stochastic.evaluate_chance(fty): 
                            part.quality_status = QualityStatus.GOOD
                        else: 
                            direct_scrap_rate = config.quality.get("direct_scrap_rate", 0.15)
                            if stochastic.evaluate_chance(direct_scrap_rate): 
                                part.quality_status = QualityStatus.SCRAP
                            else:
                                part.quality_status = QualityStatus.REWORK
                                part.is_reworked = True
            
                # ROTAYA KARAR VERME (ZOMBİ HURDA HATASI GİDERİLDİ)
                if part.quality_status == QualityStatus.SCRAP:
                    next_dest = None # Hurda olan parça derhal sistemi terk eder!
                elif part.quality_status == QualityStatus.REWORK:
                    if part.rework_return_station is None:
                        part.rework_return_station = default_next_station 
                    next_dest = "Rework" if "Rework" in factory.buffers else None
                elif station_name == "Rework":
                    # Rework başarıyla sonuçlandıysa rotasına geri döner
                    next_dest = part.rework_return_station
                else:
                    next_dest = default_next_station
                
                if next_dest:
                    next_buffer = factory.buffers[next_dest]
                    start_block = env.now
                    yield next_buffer.put(part)
                    log_state(station_name, MachineState.BLOCKED.value, start_block, env.now)
                else:
                    part.finalize(env.now, part.quality_status)
                    for s_name, logs in part.lifecycle_logs.items():
                        logger.part_logs.append({
                            "part_id": part.id, "station": s_name,
                            "process_time": logs.get("process_end", env.now) - logs.get("process_start", env.now),
                            "status": part.quality_status.value, "is_reworked": part.is_reworked,
                            "completion_time": part.completion_time
                        })

    def part_generator():
        part_id = 1
        first_station, first_buffer = routing[0], factory.buffers[routing[0]]
        target_rho = config.simulation.get("target_utilization", 0.95)
        
        effective_cycle_times = []
        for s in routing:
            auto = config.stations.get(s, {}).get("auto_mu", 5.0)
            setup = config.stations.get(s, {}).get("setup_mu", 1.0)
            cap = config.resources.get("capacities", {}).get(s, 1)
            
            mtbf = config.maintenance.get(s, {}).get("mtbf", 300.0)
            mttr = config.maintenance.get(s, {}).get("mttr_mu", 30.0)
            availability = mtbf / (mtbf + mttr) if mtbf > 0 else 1.0
            
            true_cycle_time = ((auto + setup) / availability) / cap
            effective_cycle_times.append(true_cycle_time)
            
        bottleneck_cycle_time = max(effective_cycle_times)
        
        while True:
            part = Part(id=f"PRT_{part_id:05d}", creation_time=env.now)
            part.log_arrival(first_station, env.now)
            yield first_buffer.put(part)
            part_id += 1
            yield env.timeout(stochastic.get_exponential_time(bottleneck_cycle_time / target_rho))

    env.process(part_generator())
    
    for i, station in enumerate(routing):
        nxt = routing[i+1] if i + 1 < len(routing) else None
        capacity = config.resources.get("capacities", {}).get(station, 1)
        for w in range(capacity):
            env.process(station_worker(station, nxt, w))
            env.process(breakdown_manager(station, w))
            env.process(break_manager_station(station, w)) 

    if "Rework" in config.stations and "Rework" not in routing:
        rework_cap = config.resources.get("capacities", {}).get("Rework", 1)
        for w in range(rework_cap):
            env.process(station_worker("Rework", None, w))
            env.process(breakdown_manager("Rework", w))
            env.process(break_manager_station("Rework", w))

    env.run(until=config.simulation.get("shift_duration_minutes", 480.0))
    return pd.DataFrame(logger.part_logs), pd.DataFrame(logger.state_logs)