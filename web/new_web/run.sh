kill $(lsof -t -i:5000) ; nohup python /usr/local/bin/flask run -h 0.0.0.0 &
