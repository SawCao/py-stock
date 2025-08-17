kill $(lsof -t -i:5000) ; nohup flask run -h 0.0.0.0 &
