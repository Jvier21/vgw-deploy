# SIP env variables 

## Incrementar tiempo de espera

``` json
{
        "name": "SESSION_INACTIVITY_TIMEOUT",
        "value": "15"
},
{
        "name": "FINAL_UTTERANCE_TIMEOUT",
        "value": "10000"
},
{
        "name": "POST_RESPONSE_TIMEOUT",
        "value": "10000"
},
{
        "name": "WATSON_STT_CONNECTION_TIMEOUT",
        "value": "15"
},
{
        "name": "WATSON_TTS_CONNECTION_TIMEOUT",
        "value": "15"
},
{
        "name": "WATSON_CONVERSATION_CONNECTION_TIMEOUT",
        "value": "15"
},
```

## permitir que el bot corte cuando habla alguién más

``` json
{
    "name": "DISABLE_STT_DURING_PLAYBACK",
    "value": "true"
},
```



