# src/stochastic.py
import random
import math

class StochasticEngine:
    """
    Law & Kelton standartlarına uygun Stokastik Çekirdek.
    Hata sınırları ve sınır değer (boundary) kontrolleri ile güçlendirilmiştir.
    """
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(self.seed)

    def get_normal_time(self, mu: float, sigma: float, min_val: float = 0.001) -> float:
        """
        Normal dağılım. Mu <= 0 durumunda negatif zaman oluşumunu engeller.
        """
        if mu <= 0: return min_val
        return max(min_val, self.rng.normalvariate(mu, sigma))

    def get_lognormal_time(self, mu: float, sigma: float, min_val: float = 0.001) -> float:
        """
        Gerçek dünya verilerindeki sağa çarpıklık etkisini modeller.
        """
        if mu <= 0: return min_val
        if sigma <= 0: return mu
        
        # Matematiksel Dönüşüm (Parameters to Log-Normal)
        variance = sigma ** 2
        mu_squared = mu ** 2
        mu_log = math.log(mu_squared / math.sqrt(variance + mu_squared))
        sigma_log = math.sqrt(math.log((variance / mu_squared) + 1.0))
        
        return max(min_val, self.rng.lognormvariate(mu_log, sigma_log))

    def get_exponential_time(self, beta: float) -> float:
        """MTBF (Arızalar Arası Süre) için Üstel Dağılım."""
        # Beta = Mean (Ortalama). Lambda = 1/Mean
        if beta <= 0: return 0.001 # Hata durumunda minimum servis süresi
        if beta == float('inf'): return 1e9 # "Asla bozulmaz" durumu için büyük bir sayı
        
        return self.rng.expovariate(1.0 / beta)

    def get_uniform_probability(self, min_val: float, max_val: float) -> float:
        """0.0 ile 1.0 arasında olasılık aralığı üretir."""
        return self.rng.uniform(min_val, max_val)

    def evaluate_chance(self, probability: float) -> bool:
        """Monte Carlo zar atışı."""
        if probability >= 1.0: return True
        if probability <= 0.0: return False
        return self.rng.random() < probability