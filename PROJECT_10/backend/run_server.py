import uvicorn
from app.main import create_app
from app.config import Settings

s = Settings()
app = create_app(s)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010)