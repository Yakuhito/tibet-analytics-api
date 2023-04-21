#!/bin/bash

TIBET_NETWORK=testnet10 TIBET_LAUNCHER_ID=d63637fea544958c0e9ce7b6cab2e517b5910980da7fc1a7a734ce0f2e236cd2 TIBET_CURRENT_HEIGHT=2420000 uvicorn main:app --host 0.0.0.0 --port 8000 --reload
