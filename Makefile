executor:
	python -m agents.executor.agent

health-supervisor:
	python -m agents.health.supervisor

health-worker:
	python -m agents.health.worker

appointment-supervisor:
	python -m agents.appointment.supervisor

appointment-worker:
	python -m agents.appointment.worker

grocery-supervisor:
	python -m agents.grocery.supervisor

grocery-worker:
	python -m agents.grocery.worker

financial-supervisor:
	python -m agents.financial.supervisor

financial-worker:
	python -m agents.financial.worker

scheduling:
	python -m agents.scheduling.agent

api:
	python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

run-all:
	python -m agents.run_all
