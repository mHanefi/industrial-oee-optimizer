# config/settings.py
import yaml
from pathlib import Path
from typing import Dict, Any, List

class ConfigManager:
    """
    SOLID OCP (Open/Closed) prensibine uygun Statik ve Dinamik Konfigürasyon Yöneticisi.
    Sistem parametrelerini bellek üzerinde izole ederek güvenli erişim sağlar.
    """
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.settings: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """YAML dosyasını güvenli bir şekilde parse eder."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Kritik Konfigürasyon Dosyası Bulunamadı: {self.config_path}")
        
        with open(self.config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    @property
    def simulation(self) -> Dict[str, Any]: return self.settings.get("simulation", {})
    
    @property
    def routing(self) -> List[str]: return self.settings.get("production_routing", [])
    
    @property
    def resources(self) -> Dict[str, Any]: return self.settings.get("resources", {})
    
    @property
    def stations(self) -> Dict[str, Any]: return self.settings.get("stations", {})
    
    @property
    def maintenance(self) -> Dict[str, Any]: return self.settings.get("maintenance", {})
    
    @property
    def quality(self) -> Dict[str, Any]: return self.settings.get("quality", {})
    
    @property
    def financials(self) -> Dict[str, Any]: return self.settings.get("financials", {})