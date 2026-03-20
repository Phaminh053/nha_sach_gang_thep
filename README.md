## Local

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python wsgi.py

## Railway

Start command:

```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

Required variables:

```env
FLASK_ENV=production
SECRET_KEY=your-random-secret
JWT_SECRET_KEY=your-other-random-secret
DATABASE_URL=${{MySQL.MYSQL_URL}}
```

The app can also read Railway's built-in `MYSQL_URL` or `MYSQLHOST` / `MYSQLPORT` / `MYSQLUSER` / `MYSQLPASSWORD` / `MYSQLDATABASE` variables directly.
