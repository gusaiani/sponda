dev:
	-lsof -ti :8710 | xargs kill -9 2>/dev/null
	-lsof -ti :3000 | xargs kill -9 2>/dev/null
	cd backend && source .venv/bin/activate && python manage.py runserver 8710 & \
	cd frontend && npx next dev --turbopack & \
	sleep 2 && open http://localhost:3000 & \
	wait

test:
	cd frontend && npm test
	cd backend && pytest -x -q --ignore=tests/test_e2e.py --ignore=tests/test_e2e_browser.py --ignore=tests/test_e2e_favorites.py --ignore=tests/test_e2e_auth.py

test-all:
	cd frontend && npm run build && npm test
	cd backend && pytest -x -q
