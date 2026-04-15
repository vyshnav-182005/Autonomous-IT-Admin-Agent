"""
OpsPilot AI — Run Admin Panel
Starts the FastAPI admin panel on the configured port.
"""

import uvicorn
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config


def main():
    print("=" * 50)
    print("  ⚡ OpsPilot Admin Panel")
    print(f"  🌐 http://localhost:{config.ADMIN_PANEL_PORT}")
    print("=" * 50)

    uvicorn.run(
        "admin_panel.main:app",
        host="0.0.0.0",
        port=config.ADMIN_PANEL_PORT,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
