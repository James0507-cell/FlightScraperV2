from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import HotelOffer, ScrapeRun


def persist_run(database_path: str | Path, run: ScrapeRun) -> None:
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        run_id = _upsert_run(connection, run)
        connection.execute("DELETE FROM room_offers WHERE run_id = ?", (run_id,))
        connection.execute("DELETE FROM hotels WHERE run_id = ?", (run_id,))
        for offer_index, offer in enumerate(run.offers):
            hotel_id = _insert_hotel(connection, run_id, offer_index, offer)
            for room_index, room_offer in enumerate(offer.room_offers):
                connection.execute(
                    """
                    INSERT INTO room_offers (
                        hotel_id,
                        run_id,
                        room_index,
                        room_name,
                        price,
                        currency,
                        taxes_and_fees,
                        cancellation_policy,
                        booking_token
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hotel_id,
                        run_id,
                        room_index,
                        room_offer.room_name,
                        room_offer.price,
                        room_offer.currency,
                        room_offer.taxes_and_fees,
                        room_offer.cancellation_policy,
                        room_offer.booking_token,
                    ),
                )
        connection.commit()
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
            destination TEXT NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            adults INTEGER NOT NULL,
            children INTEGER NOT NULL,
            rooms INTEGER NOT NULL,
            currency TEXT,
            max_price INTEGER,
            final_url TEXT NOT NULL,
            capture_url TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            hotel_count INTEGER NOT NULL,
            timings_json TEXT NOT NULL,
            notes_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            offer_index INTEGER NOT NULL,
            property_id TEXT,
            name TEXT,
            address TEXT,
            neighborhood TEXT,
            review_score REAL,
            review_count INTEGER,
            nightly_price INTEGER,
            total_price INTEGER,
            currency TEXT,
            latitude REAL,
            longitude REAL,
            amenities_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS room_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            room_index INTEGER NOT NULL,
            room_name TEXT,
            price INTEGER,
            currency TEXT,
            taxes_and_fees INTEGER,
            cancellation_policy TEXT,
            booking_token TEXT,
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE,
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
            destination,
            check_in,
            check_out,
            adults,
            children,
            rooms,
            currency,
            max_price,
            final_url,
            capture_url,
            captured_at,
            hotel_count,
            timings_json,
            notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_key) DO UPDATE SET
            archive_dir=excluded.archive_dir,
            requested_mode=excluded.requested_mode,
            executed_mode=excluded.executed_mode,
            destination=excluded.destination,
            check_in=excluded.check_in,
            check_out=excluded.check_out,
            adults=excluded.adults,
            children=excluded.children,
            rooms=excluded.rooms,
            currency=excluded.currency,
            max_price=excluded.max_price,
            final_url=excluded.final_url,
            capture_url=excluded.capture_url,
            captured_at=excluded.captured_at,
            hotel_count=excluded.hotel_count,
            timings_json=excluded.timings_json,
            notes_json=excluded.notes_json
        """,
        (
            str(run.archive_dir),
            str(run.archive_dir),
            run.requested_mode,
            run.executed_mode,
            run.query.destination,
            run.query.check_in,
            run.query.check_out,
            run.query.adults,
            run.query.children,
            run.query.rooms,
            run.query.currency,
            run.query.max_price,
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
        raise RuntimeError("Failed to persist hotel scrape metadata.")
    return int(row[0])


def _insert_hotel(
    connection: sqlite3.Connection,
    run_id: int,
    offer_index: int,
    offer: HotelOffer,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO hotels (
            run_id,
            offer_index,
            property_id,
            name,
            address,
            neighborhood,
            review_score,
            review_count,
            nightly_price,
            total_price,
            currency,
            latitude,
            longitude,
            amenities_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            offer_index,
            offer.property_id,
            offer.name,
            offer.address,
            offer.neighborhood,
            offer.review_score,
            offer.review_count,
            offer.nightly_price,
            offer.total_price,
            offer.currency,
            offer.latitude,
            offer.longitude,
            json.dumps(offer.amenities),
        ),
    )
    return int(cursor.lastrowid)
