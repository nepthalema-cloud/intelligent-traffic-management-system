# AI-Powered Smart Traffic Management System

An intelligent traffic management system that uses AI and machine learning to optimize traffic flow, detect congestion, and predict traffic patterns.

## Project Structure

```
AI-Powered Smart Traffic Management System/
├── backend/                 # Django REST API backend
│   ├── apps/               # Django applications
│   │   ├── accounts/      # User authentication and authorization
│   │   ├── roads/         # Road network management
│   │   ├── traffic/       # Traffic data collection and analysis
│   │   └── cameras/       # Camera management and integration
│   ├── config/            # Django project settings
│   │   ├── settings/      # Environment-specific settings
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── requirements/      # Python dependencies
│   │   ├── base.txt
│   │   ├── development.txt
│   │   └── production.txt
│   ├── manage.py
│   ├── Dockerfile
│   └── .env.example
├── frontend/               # React + TypeScript frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   └── utils/         # Utility functions
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
├── ai-services/           # AI microservices
│   ├── common/           # Shared utilities and models
│   ├── vehicle_detection/ # Vehicle detection and classification
│   ├── tracking/         # Vehicle tracking across cameras
│   ├── ocr/              # OCR for license plates and signs
│   ├── face_recognition/ # Face detection and recognition
│   └── prediction/       # Traffic prediction and optimization
├── docs/                  # Documentation
│   ├── api/              # API documentation
│   └── architecture/     # System architecture docs
├── docker/               # Docker-related files
├── docker-compose.yml    # Multi-container orchestration
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Tech Stack

### Backend
- Django 6.0+
- Django REST Framework
- PostgreSQL
- Redis
- Celery (for background tasks)

### Frontend
- React 18+
- TypeScript
- Vite
- Tailwind CSS
- React Router
- Axios

### AI Services
- Python-based microservices
- Machine learning frameworks (to be determined)
- Computer vision (to be determined)
- Real-time processing (to be determined)

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Quick Start with Docker

1. Clone the repository
2. Copy environment files:
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
3. Start all services:
   ```bash
   docker-compose up --build
   ```
4. Access the application:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements/development.txt
python manage.py migrate
python manage.py runserver
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Development Status

This is the initial project setup. No business logic has been implemented yet.

### Completed
- [x] Project structure setup
- [x] Django project initialization (with config package)
- [x] Environment-specific Django settings
- [x] Split requirements files
- [x] React + TypeScript + Vite project initialization
- [x] Tailwind CSS configuration
- [x] React Router and Axios setup
- [x] Docker configuration
- [x] Environment variable templates
- [x] Backend app layout preparation
- [x] AI services structure reorganization

### To Be Implemented
- [ ] Django apps creation (accounts, roads, traffic, cameras)
- [ ] Django models and database migrations
- [ ] REST API endpoints
- [ ] Authentication system
- [ ] Frontend components and pages
- [ ] AI service implementations
- [ ] Testing infrastructure
- [ ] CI/CD pipeline

## Contributing

This project is currently in the initial setup phase. Contributions will be welcome once the core functionality is implemented.

## License

To be determined.
