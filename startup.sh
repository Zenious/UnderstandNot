#!/bin/sh

tmux new-session -d "redis-server"
tmux split-window -h "rq worker"
tmux split-window -v "sanic-admin webserver.py"
tmux select-layout tiled
tmux -2 attach-session -d