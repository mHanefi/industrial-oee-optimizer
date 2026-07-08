# run_sim.py
import os
import sys
import numpy as np

# Proje dizinini sisteme ekle
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from config.settings import ConfigManager
from src.stochastic import StochasticEngine
from src.simulation import run_simulation
from src.analytics import AnalyticsEngine

def main():
    print("🚀 Kurumsal MES Dijital İkiz: MONTE CARLO Simülasyonu Başlatılıyor...")
    
    try:
        config = ConfigManager("config/config.yaml")
        replications = config.simulation.get("monte_carlo_replications", 10)
        print(f"✅ Konfigürasyon Yüklendi. Rota: {config.routing}")
        print(f"🎲 Monte Carlo Vardiya Sayısı: {replications}\n")
        
        oee_results = []
        copq_results = []
        bottlenecks = {}
        
        # Literatürde "Warm-up" süresi simülasyonun başında kesilmelidir.
        # Biz burada AnalyticsEngine içinde bunu zaten yönetiyoruz.
        
        for i in range(replications):
            # AKADEMİK DÜZELTME: Seed yönetimi
            # Law & Kelton'a göre, her replikasyon birbirinden bağımsız (independent) olmalıdır.
            # 42 + i yöntemi yerine, daha geniş bir seed aralığı veya her seferinde farklı bir 
            # başlangıç noktası kullanmak korelasyonu minimize eder.
            current_seed = 1000 + (i * 123) 
            stochastic = StochasticEngine(seed=current_seed)
            
            # Simülasyonu çalıştır
            df_parts, df_states = run_simulation(config, stochastic)
            
            # Analiz motoruna gönder
            analytics = AnalyticsEngine(df_parts, df_states, config)
            
            if analytics.is_valid:
                # Darboğaz tespiti
                b_neck = analytics.calculate_bottleneck()
                bottlenecks[b_neck] = bottlenecks.get(b_neck, 0) + 1
                
                # OEE ve COPQ hesaplamaları
                oee_data = analytics.calculate_oee(b_neck)
                copq_data = analytics.calculate_copq()
                
                oee_results.append(oee_data["OEE"])
                copq_results.append(copq_data["Total"])
            
            # Kullanıcıya geri bildirim (Temiz ve profesyonel)
            sys.stdout.write(f"\rVardiya Analizi: {i+1}/{replications} tamamlandı...")
            sys.stdout.flush()

        # İstatistiksel Özet
        print("\n\n" + "="*50)
        print("📊 İSTATİSTİKSEL ANALİZ ÖZETİ")
        print("="*50)
        
        if oee_results:
            print(f"🏆 Ortalama OEE: %{np.mean(oee_results):.2f} (Std Dev: {np.std(oee_results):.2f})")
            print(f"💰 Ort. Vardiya Maliyeti (COPQ): {np.mean(copq_results):,.2f} ₺")
            
            primary_bottleneck = max(bottlenecks, key=bottlenecks.get)
            b_neck_prob = (bottlenecks[primary_bottleneck] / len(oee_results)) * 100
            print(f"🚨 Ana Kısıt: {primary_bottleneck} (%{b_neck_prob:.1f} olasılıkla)")
        else:
            print("❌ Hata: Analiz edilecek geçerli veri bulunamadı.")
            
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ SİSTEM HATASI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()