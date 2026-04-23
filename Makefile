.PHONY: help setup dev stop logs clean

help:
	@echo "GenericSwarm Development"
	@echo ""
	@echo "  make setup       - Setup (copy .env)"
	@echo "  make dev         - Start all services"
	@echo "  make stop        - Stop services"
	@echo "  make logs        - Tail logs"
	@echo "  make clean       - Clean up"
	@echo ""

setup:
	cp .env.example .env
	@echo "✓ Created .env - edit and add ANTHROPIC_API_KEY"

dev:
	docker-compose up -d
	@echo "✓ Services starting..."
	@echo ""
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"

stop:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	@echo "✓ Cleaned"
