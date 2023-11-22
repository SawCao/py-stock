kill $(lsof -t -i:5000) ; nohup /usr/bin/python3 /usr/local/bin/flask run -h 0.0.0.0 &
