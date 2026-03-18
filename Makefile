dev:
	cd backend && source .venv/bin/activate && python manage.py runserver 8710 & \
	cd frontend && npx vite --open & \
	wait
