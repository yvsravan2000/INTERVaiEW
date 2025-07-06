# INTERVaiEW

Conversational web app built with Python & Streamlit. Features chat UI, API integrations (e.g., currency conversion), DB/data warehouse connections, user authentication, config management, and modern UI with custom fonts/assets. Great for experimenting with chat workflows & APIs.

## Features
- Chat interface for interactive Q&A
- Chat data stored in JSON format
- Custom fonts and static assets for enhanced UI
- Configurable settings via TOML file

## Project Structure
```
app.py                  # Main application entry point
chat.py                 # Chat logic and utilities
requirements.txt        # Python dependencies
chats/                  # Chat data in JSON format
static/                 # Fonts and static assets
streamlit/config.toml   # Streamlit configuration
streamlit/secrets.toml  # Secret keys or configuration (do not share)
```

## Getting Started

### Prerequisites
- Python 3.13
- pip (Python package manager)

### Installation
1. Clone the repository or download the source code.
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configure `streamlit/secrets.toml` and `streamlit/config.toml` as needed.

### Running the Application
To start the app, run:
```powershell
python -m streamlit run app.py
```

## Notes
- Chat data is available in the `chats/` directory.
- Static assets (fonts) are located in the `static/` directory.

