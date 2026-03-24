dev:
	cd backend && source .venv/bin/activate && python manage.py runserver 8710 & \
	cd frontend && npx next dev --turbopack & \
	sleep 2 && open http://localhost:3000 & \
	wait
