from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import FlightOffer, ScrapeRun


def persist_run(database_path: str | Path, run: ScrapeRun) -> None:
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(connection)
        run_id = _upsert_run(connection, run)
        connection.execute("DELETE FROM segments WHERE run_id = ?", (run_id,))
        connection.execute("DELETE FROM offers WHERE run_id = ?", (run_id,))
        for offer_index, offer in enumerate(run.offers):
            offer_id = _insert_offer(connection, run_id, offer_index, offer)
            for segment_index, segment in enumerate(offer.segments):
                connection.execute(
                    """
                    INSERT INTO segments (
                        offer_id,
                        run_id,
                        segment_index,
                        airline_code,
                        airline_name,
                        flight_number,
                        operating_airline,
                        origin_airport,
                        origin_name,
                        destination_airport,
                        destination_name,
                        departure_time,
                        arrival_time,
                        duration_minutes,
                        aircraft
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        offer_id,
                        run_id,
                        segment_index,
                        segment.airline_code,
                        segment.airline_name,
                        segment.flight_number,
                        segment.operating_airline,
                        segment.origin_airport,
                        segment.origin_name,
                        segment.destination_airport,
                        segment.destination_name,
                        segment.departure_time,
                        segment.arrival_time,
                        segment.duration_minutes,
                        segment.aircraft,
                    ),
                )
        connection.commit()
    finally:
        connection.close()


def list_recent_runs(database_path: str | Path, limit: int = 10) -> list[dict]:
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
                run_key,
                archive_dir,
                requested_mode,
                executed_mode,
                origin,
                destination,
                depart_date,
                return_date,
                captured_at,
                offer_count,
                timings_json,
                notes_json
            FROM runs
            ORDER BY captured_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "run_key": row["run_key"],
                "archive_dir": row["archive_dir"],
                "requested_mode": row["requested_mode"],
                "executed_mode": row["executed_mode"],
                "origin": row["origin"],
                "destination": row["destination"],
                "depart_date": row["depart_date"],
                "return_date": row["return_date"],
                "captured_at": row["captured_at"],
                "offer_count": row["offer_count"],
                "timings": json.loads(row["timings_json"]),
                "notes": json.loads(row["notes_json"]),
            }
            for row in rows
        ]
    finally:
        connection.close()


def list_cheapest_offers(
    database_path: str | Path,
    limit: int = 10,
    origin: str | None = None,
    destination: str | None = None,
    depart_date: str | None = None,
) -> list[dict]:
    predicates: list[str] = ["offers.price IS NOT NULL"]
    params: list[object] = []
    if origin:
        predicates.append("runs.origin = ?")
        params.append(origin)
    if destination:
        predicates.append("runs.destination = ?")
        params.append(destination)
    if depart_date:
        predicates.append("runs.depart_date = ?")
        params.append(depart_date)

    query = f"""
        SELECT
            runs.run_key,
            runs.archive_dir,
            runs.executed_mode,
            runs.origin AS query_origin,
            runs.destination AS query_destination,
            runs.depart_date AS query_depart_date,
            runs.return_date AS query_return_date,
            runs.captured_at,
            offers.offer_index,
            offers.origin_airport,
            offers.destination_airport,
            offers.departure_date,
            offers.arrival_date,
            offers.departure_time,
            offers.arrival_time,
            offers.duration_minutes,
            offers.stops,
            offers.price,
            offers.currency,
            offers.airlines_json,
            offers.flight_numbers_json,
            offers.layovers_json,
            offers.emissions_kg,
            offers.emissions_delta_percent,
            offers.booking_token,
            offers.is_best
        FROM offers
        INNER JOIN runs ON runs.id = offers.run_id
        WHERE {" AND ".join(predicates)}
        ORDER BY offers.price ASC, runs.captured_at DESC, offers.offer_index ASC
        LIMIT ?
    """
    params.append(limit)

    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(query, params).fetchall()
        return [
            {
                "run_key": row["run_key"],
                "archive_dir": row["archive_dir"],
                "executed_mode": row["executed_mode"],
                "query": {
                    "origin": row["query_origin"],
                    "destination": row["query_destination"],
                    "depart_date": row["query_depart_date"],
                    "return_date": row["query_return_date"],
                },
                "captured_at": row["captured_at"],
                "offer_index": row["offer_index"],
                "origin_airport": row["origin_airport"],
                "destination_airport": row["destination_airport"],
                "departure_date": row["departure_date"],
                "arrival_date": row["arrival_date"],
                "departure_time": row["departure_time"],
                "arrival_time": row["arrival_time"],
                "duration_minutes": row["duration_minutes"],
                "stops": row["stops"],
                "price": row["price"],
                "currency": row["currency"],
                "airlines": json.loads(row["airlines_json"]),
                "flight_numbers": json.loads(row["flight_numbers_json"]),
                "layovers": json.loads(row["layovers_json"]),
                "emissions_kg": row["emissions_kg"],
                "emissions_delta_percent": row["emissions_delta_percent"],
                "booking_token": row["booking_token"],
                "is_best": None if row["is_best"] is None else bool(row["is_best"]),
            }
            for row in rows
        ]
    finally:
        connection.close()


def summarize_modes(database_path: str | Path) -> list[dict]:
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
                executed_mode,
                COUNT(*) AS run_count,
                AVG(offer_count) AS avg_offer_count,
                AVG(CAST(json_extract(timings_json, '$.total_seconds') AS REAL)) AS avg_total_seconds,
                MIN(CAST(json_extract(timings_json, '$.total_seconds') AS REAL)) AS min_total_seconds,
                MAX(CAST(json_extract(timings_json, '$.total_seconds') AS REAL)) AS max_total_seconds
            FROM runs
            GROUP BY executed_mode
            ORDER BY run_count DESC, executed_mode ASC
            """
        ).fetchall()
        return [
            {
                "executed_mode": row["executed_mode"],
                "run_count": row["run_count"],
                "avg_offer_count": round(row["avg_offer_count"], 2)
                if row["avg_offer_count"] is not None
                else None,
                "avg_total_seconds": round(row["avg_total_seconds"], 4)
                if row["avg_total_seconds"] is not None
                else None,
                "min_total_seconds": round(row["min_total_seconds"], 4)
                if row["min_total_seconds"] is not None
                else None,
                "max_total_seconds": round(row["max_total_seconds"], 4)
                if row["max_total_seconds"] is not None
                else None,
            }
            for row in rows
        ]
    finally:
        connection.close()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL UNIQUE,
            archive_dir TEXT NOT NULL,
            requested_mode TEXT NOT NULL,
            executed_mode TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            depart_date TEXT NOT NULL,
            return_date TEXT,
            trip_type TEXT NOT NULL,
            passengers INTEGER NOT NULL,
            cabin TEXT NOT NULL,
            max_stops INTEGER,
            final_url TEXT NOT NULL,
            capture_url TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            offer_count INTEGER NOT NULL,
            timings_json TEXT NOT NULL,
            notes_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            offer_index INTEGER NOT NULL,
            origin_airport TEXT,
            destination_airport TEXT,
            departure_date TEXT,
            arrival_date TEXT,
            departure_time TEXT,
            arrival_time TEXT,
            duration_minutes INTEGER,
            stops INTEGER,
            price INTEGER,
            currency TEXT,
            airlines_json TEXT NOT NULL,
            flight_numbers_json TEXT NOT NULL,
            layovers_json TEXT NOT NULL,
            emissions_kg INTEGER,
            emissions_delta_percent INTEGER,
            booking_token TEXT,
            is_best INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            segment_index INTEGER NOT NULL,
            airline_code TEXT,
            airline_name TEXT,
            flight_number TEXT,
            operating_airline TEXT,
            origin_airport TEXT,
            origin_name TEXT,
            destination_airport TEXT,
            destination_name TEXT,
            departure_time TEXT,
            arrival_time TEXT,
            duration_minutes INTEGER,
            aircraft TEXT,
            FOREIGN KEY (offer_id) REFERENCES offers(id) ON DELETE CASCADE,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        """
    )


def _upsert_run(connection: sqlite3.Connection, run: ScrapeRun) -> int:
    connection.execute(
        """
        INSERT INTO runs (
            run_key,
            archive_dir,
            requested_mode,
            executed_mode,
            origin,
            destination,
            depart_date,
            return_date,
            trip_type,
            passengers,
            cabin,
            max_stops,
            final_url,
            capture_url,
            captured_at,
            offer_count,
            timings_json,
            notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_key) DO UPDATE SET
            archive_dir=excluded.archive_dir,
            requested_mode=excluded.requested_mode,
            executed_mode=excluded.executed_mode,
            origin=excluded.origin,
            destination=excluded.destination,
            depart_date=excluded.depart_date,
            return_date=excluded.return_date,
            trip_type=excluded.trip_type,
            passengers=excluded.passengers,
            cabin=excluded.cabin,
            max_stops=excluded.max_stops,
            final_url=excluded.final_url,
            capture_url=excluded.capture_url,
            captured_at=excluded.captured_at,
            offer_count=excluded.offer_count,
            timings_json=excluded.timings_json,
            notes_json=excluded.notes_json
        """,
        (
            str(run.archive_dir),
            str(run.archive_dir),
            run.requested_mode,
            run.executed_mode,
            run.query.origin,
            run.query.destination,
            run.query.depart_date,
            run.query.return_date,
            run.query.trip_type,
            run.query.passengers,
            run.query.cabin,
            run.query.max_stops,
            run.final_url,
            run.capture.url,
            run.capture.captured_at,
            len(run.offers),
            json.dumps(run.timings, sort_keys=True),
            json.dumps(run.notes),
        ),
    )
    row = connection.execute(
        "SELECT id FROM runs WHERE run_key = ?",
        (str(run.archive_dir),),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to persist run metadata.")
    return int(row[0])


def _insert_offer(
    connection: sqlite3.Connection,
    run_id: int,
    offer_index: int,
    offer: FlightOffer,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO offers (
            run_id,
            offer_index,
            origin_airport,
            destination_airport,
            departure_date,
            arrival_date,
            departure_time,
            arrival_time,
            duration_minutes,
            stops,
            price,
            currency,
            airlines_json,
            flight_numbers_json,
            layovers_json,
            emissions_kg,
            emissions_delta_percent,
            booking_token,
            is_best
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            offer_index,
            offer.origin_airport,
            offer.destination_airport,
            offer.departure_date,
            offer.arrival_date,
            offer.departure_time,
            offer.arrival_time,
            offer.duration_minutes,
            offer.stops,
            offer.price,
            offer.currency,
            json.dumps(offer.airlines),
            json.dumps(offer.flight_numbers),
            json.dumps(offer.layovers),
            offer.emissions_kg,
            offer.emissions_delta_percent,
            offer.booking_token,
            1 if offer.is_best else 0 if offer.is_best is not None else None,
        ),
    )
    return int(cursor.lastrowid)
