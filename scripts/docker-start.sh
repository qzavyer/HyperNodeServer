#!/bin/bash

# HyperLiquid Node Parser Docker Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs data config nginx/ssl
    
    # Set permissions
    chmod 755 logs data config
    
    print_success "Directories created"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from example..."
        if [ -f env.example ]; then
            cp env.example .env
            print_success ".env file created from example"
            print_warning "Please update .env file with your configuration"
        else
            print_error "env.example file not found"
            exit 1
        fi
    else
        print_success ".env file found"
    fi
}

# Build and start containers
start_containers() {
    print_status "Building and starting containers..."
    
    # Build the application image
    docker compose build --no-cache
    
    # Start containers
    docker compose up -d
    
    print_success "Containers started"
}

# Wait for application to be ready
wait_for_app() {
    print_status "Waiting for application to be ready..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_success "Application is ready!"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts - waiting for application..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "Application failed to start within expected time"
    return 1
}

# Show container status
show_status() {
    print_status "Container status:"
    docker compose ps
    
    print_status "Application logs:"
    docker compose logs --tail=20 hyperliquid-parser
}

# Show useful URLs
show_urls() {
    echo
    print_success "Application is running!"
    echo
    echo -e "${GREEN}Available URLs:${NC}"
    echo -e "  API: ${BLUE}http://localhost:8000${NC}"
    echo -e "  Health: ${BLUE}http://localhost:8000/health${NC}"
    echo -e "  Documentation: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "  Nginx: ${BLUE}http://localhost:80${NC}"
    echo
    echo -e "${GREEN}Useful commands:${NC}"
    echo -e "  View logs: ${BLUE}docker compose logs -f hyperliquid-parser${NC}"
    echo -e "  Stop: ${BLUE}docker compose down${NC}"
    echo -e "  Restart: ${BLUE}docker compose restart${NC}"
    echo
}

# Main execution
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}HyperLiquid Node Parser Startup${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
    
    check_docker
    create_directories
    check_env_file
    start_containers
    
    if wait_for_app; then
        show_status
        show_urls
    else
        print_error "Failed to start application"
        exit 1
    fi
}

# Run main function
main "$@"
