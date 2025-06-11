# mypy: ignore-errors

import os

import psycopg2
from flask import Flask, jsonify
from pgvector.psycopg2 import register_vector

PGHOST = os.getenv("PGHOST", "pg-vector-rw")
PGDATABASE = os.getenv("PGDATABASE", "app_db")
PGUSER = os.getenv("PGUSER", "app")
PGPASSWORD = os.getenv("PGPASSWORD", "password")

app = Flask(__name__)


def _get_conn():
    conn = psycopg2.connect(
        host=PGHOST,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )
    register_vector(conn)
    return conn


@app.route("/")
def root():
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                val = cur.fetchone()[0]
        return jsonify(status="ok", db_result=val)
    except Exception as exc:
        return jsonify(status="error", detail=str(exc)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
