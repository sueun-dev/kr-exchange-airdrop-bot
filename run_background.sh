#!/bin/bash

# 백그라운드에서 프로그램 실행
echo "에어드랍 봇을 백그라운드에서 실행합니다..."
echo "로그는 airdrop_bot.log 파일에 저장됩니다."

# caffeinate로 시스템 절전 방지 + nohup으로 백그라운드 실행
nohup caffeinate -i python3 src/main.py > airdrop_bot.log 2>&1 &

# 프로세스 ID 저장
echo $! > airdrop_bot.pid

echo "프로세스 ID: $(cat airdrop_bot.pid)"
echo "실행 완료! 맥북이 절전 모드로 들어가지 않습니다."
echo ""
echo "로그 확인: tail -f airdrop_bot.log"
echo "프로세스 확인: ps -p $(cat airdrop_bot.pid)"
echo "프로세스 중단: kill $(cat airdrop_bot.pid)"