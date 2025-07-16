@echo off
REM Run the Finance Manager CLI inside the running Docker container

REM Find the container name (default: fm-app-1)
set CONTAINER_NAME=fm-app-1

REM Run the CLI menu inside the container
docker exec -it %CONTAINER_NAME% python menu/main.py