import requests
import time

# Lista de endpoints
endpoints = [
    "http://172.16.220.46:3000/",
    "http://172.16.220.46:3001/",
    "http://172.16.220.46:3002/",
    "http://172.16.220.46:3003/"
]

# Número de veces que se medirá la latencia para cada endpoint
num_requests = 100

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

