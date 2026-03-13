dev:
	cd backend && source .venv/bin/activate && python manage.py runserver 8710 & \
	cd frontend && npm run dev & \
	sleep 2 && open http://localhost:5173 & \
	wait
