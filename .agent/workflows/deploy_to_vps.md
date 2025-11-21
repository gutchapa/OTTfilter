---
description: Deploy the refactored OTT Filter App to a VPS
---

Follow these steps to deploy the `refactor/modular-architecture` branch to your VPS.

1.  **Navigate to your project directory**
    ```bash
    cd /path/to/your/project
    ```

2.  **Fetch the new branch**
    ```bash
    git fetch origin
    ```

3.  **Checkout the refactored branch**
    ```bash
    git checkout refactor/modular-architecture
    ```

4.  **Check Python Version (CRITICAL)**
    Ensure you are running Python 3.10 or higher.
    ```bash
    python3 --version
    ```
    If it is older (e.g., 3.6 or 3.8), you **MUST** install Python 3.10+.
    *   **Ubuntu/Debian**: `sudo apt install python3.10 python3.10-venv`
    *   **CentOS/RHEL**: `sudo yum install python3.10` (may require EPEL or IUS repo)

5.  **Update Backend Dependencies**
    ```bash
    cd backend
    # Create virtual environment with Python 3.10
    python3.10 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

6.  **Configure Environment Variables**
    Create or update the `.env` file in the `backend/` directory.
    ```bash
    nano .env
    ```
    Paste your API keys:
    ```
    MONGO_URL="mongodb://localhost:27017"
    TMDB_API_KEY="your_key"
    OMDB_API_KEY="your_key"
    YOUTUBE_API_KEY="your_key"
    OPENAI_API_KEY="your_key"
    ```

6.  **Run the Backend**
    ```bash
    # Run in background or use a process manager like systemd/gunicorn
    nohup python server.py &
    ```

7.  **Update Frontend Dependencies & Build**
    ```bash
    cd ../frontend
    npm install
    npm run build
    ```

8.  **Serve Frontend**
    You can serve the `build` folder using Nginx or a simple server for testing:
    ```bash
    npx serve -s build
    ```
