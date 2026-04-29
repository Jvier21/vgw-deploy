import requests
import time

# Lista de endpoints
endpoints = [
    #"https://tts-azure-ts.nvidiaservices.smartia-ai.com"
    #"http://20.55.240.87:8020/",
    "http://10.0.0.11:8001",
    "http://generic-nlp-adapter.services.smartia-ai.com/dialogflow",
    "http://mrcp-transfer-nlp-adapter.services.smartia-ai.com/user/10103/dialogflow?endreason={endreason}",
    "http://10.0.0.11:8002"
]

# Número de veces que se medirá la latencia para cada endpoint
num_requests = 1000

def measure_latency(url, num_requests):
    latencies = []
    for _ in range(num_requests):
        start_time = time.time()
        response = requests.get(url)
        latency = (time.time() - start_time) * 1000  # Convertir a milisegundos
        latencies.append(latency)
    average_latency = sum(latencies) / len(latencies)
    return average_latency

# Medir y mostrar la latencia promedio para cada endpoint
for endpoint in endpoints:
    avg_latency = measure_latency(endpoint, num_requests)
    print(f"Average Latency for {endpoint}: {avg_latency:.2f} ms")

