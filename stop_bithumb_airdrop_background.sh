#!/bin/bash

# 백그라운드 프로세스 중단
if [ -f bithumb_airdrop_bot.pid ]; then
    PID=$(cat bithumb_airdrop_bot.pid)
    if ps -p $PID > /dev/null; then
        echo "빗썸 에어드랍 봇 프로세스(PID: $PID)를 중단합니다..."
        kill $PID
        echo "중단 완료!"
    else
        echo "프로세스가 이미 종료되었습니다."
    fi
    rm -f bithumb_airdrop_bot.pid
else
    echo "실행 중인 프로세스를 찾을 수 없습니다."
fi
