# usar el mr paraa ver las peticiones
## peticiones por mins
cat trace-mr.log.0 | grep "2024-09-30" | grep -E "SmartIA 5005 Chile|SmartIA 5005-2 Chile" | grep -E "tts-multitenant-ts.nvidiaservices.smartia-ai.com|tts-multitenant-ts-2.nvidiaservices.smartia-ai.com" | awk '{match($0, /2024-09-30T[0-9]{2}:[0-9]{2}/); print substr($0, RSTART, RLENGTH)}' | sort | uniq -c | awk '{print $2, $1}'
## peticiones por horas
cat trace-mr.log.0 | grep "2024-09-30" | grep -E "SmartIA 5005 Chile|SmartIA 5005-2 Chile" | grep -E "tts-multitenant-ts.nvidiaservices.smartia-ai.com|tts-multitenant-ts-2.nvidiaservices.smartia-ai.com" | awk '{match($0, /2024-09-30T[0-9]{2}/); print substr($0, RSTART, RLENGTH)}' | sort | uniq -c | awk '{print $2, $1}'