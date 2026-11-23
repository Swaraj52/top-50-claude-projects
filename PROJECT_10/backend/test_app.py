from app.main import create_app
from app.config import Settings
s = Settings()
app = create_app(s)
print('App created OK')
print('Routes:')
for r in app.routes:
    if hasattr(r, 'routes'):
        print(f'  Router: {r.name or "unnamed"}')
        for sub in r.routes:
            if hasattr(sub, 'path'):
                print(f'    {sub.path}')
    elif hasattr(r, 'path'):
        print(f'  {r.path}')