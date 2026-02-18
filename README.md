# Bluestar Economy Simulator

A comprehensive economic simulation system for modeling and analyzing the Bluestar economy. Built with Streamlit for interactive visualization and analysis.

## Features

- Interactive economic simulation dashboard
- Real-time economy visualization with Plotly
- Configurable economic parameters
- Statistical analysis and reporting

## Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd coin_sim
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application

Start the Streamlit app:
```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`

### Running Tests

Execute the test suite:
```bash
pytest tests/
```

## Project Structure

- `app.py` - Main Streamlit application entry point
- `simulation/` - Core simulation logic and models
- `pages/` - Multi-page Streamlit pages
- `data/defaults/` - Default configuration and data files
- `tests/` - Unit and integration tests
- `.streamlit/` - Streamlit configuration

## Configuration

Streamlit settings are configured in `.streamlit/config.toml`. Key settings include:
- Server port: 8501
- Headless mode enabled for deployment
- Custom theme configuration

## License

MIT License
