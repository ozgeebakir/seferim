"""Refahiye–Erzincan döner vardiya algoritması.

Aktif günler: Pazartesi, Çarşamba, Cuma, Pazar
Kapalı: Salı, Perşembe, Cumartesi

Ahmet (sıra 0): Pzt 08:00, Çar 09:00, Cum 10:30, Paz 12:00
Mehmet (sıra 1): Pzt 09:00, Çar 10:30, Cum 12:00, ...
Her şoför bir sonraki saat dilimine kayar.
"""

from __future__ import annotations

from datetime import date, timedelta

# Pazartesi=0 ... Pazar=6
ACTIVE_WEEKDAYS = (0, 2, 4, 6)  # Pzt, Çar, Cum, Paz

# Ahmet'in haftalık sırası buradan başlar; diğerleri +1 kayar
DEPARTURE_TIMES = [
    "08:00",
    "09:00",
    "10:30",
    "12:00",
    "13:30",
    "15:00",
    "16:30",
    "18:00",
    "19:30",
    "21:00",
]

SEED_DRIVERS = [
    {"name": "Ahmet Yılmaz", "phone": "05551000001", "plate": "24 RFH 001"},
    {"name": "Mehmet Kaya", "phone": "05551000002", "plate": "24 RFH 002"},
    {"name": "Ali Demir", "phone": "05551000003", "plate": "24 RFH 003"},
    {"name": "Hasan Çelik", "phone": "05551000004", "plate": "24 RFH 004"},
    {"name": "Hüseyin Şahin", "phone": "05551000005", "plate": "24 RFH 005"},
    {"name": "Mustafa Aydın", "phone": "05551000006", "plate": "24 RFH 006"},
    {"name": "İbrahim Yıldız", "phone": "05551000007", "plate": "24 RFH 007"},
    {"name": "Osman Arslan", "phone": "05551000008", "plate": "24 RFH 008"},
    {"name": "Yusuf Doğan", "phone": "05551000009", "plate": "24 RFH 009"},
    {"name": "Murat Koç", "phone": "05551000010", "plate": "24 RFH 010"},
]

AUTO_NOTE = "Otomatik vardiya programı"
VEHICLE_TYPE = "14 kişilik minibüs"
DEFAULT_SEATS = 14
DEFAULT_ROUTE = "ilce-merkez"  # Refahiye → Erzincan


def is_active_day(day: date) -> bool:
    return day.weekday() in ACTIVE_WEEKDAYS


def active_slot_index(day: date) -> int:
    """Haftanın kaçıncı aktif günü (Pzt=0, Çar=1, Cum=2, Paz=3)."""
    return ACTIVE_WEEKDAYS.index(day.weekday())


def departure_time_for(driver_index: int, day: date) -> str | None:
    """Şoför o gün gidiyorsa saatini döner, gitmiyorsa None."""
    if not is_active_day(day):
        return None
    slot = active_slot_index(day)
    n = len(DEPARTURE_TIMES)
    return DEPARTURE_TIMES[(driver_index + slot) % n]


def weekly_plan_for(driver_index: int) -> list[tuple[str, str | None]]:
    """[(gün adı, saat veya None), ...] Pzt→Paz."""
    names = [
        "Pazartesi",
        "Salı",
        "Çarşamba",
        "Perşembe",
        "Cuma",
        "Cumartesi",
        "Pazar",
    ]
    # Referans: bu haftanın pazartesinden itibaren
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    plan = []
    for i, name in enumerate(names):
        day = monday + timedelta(days=i)
        plan.append((name, departure_time_for(driver_index, day)))
    return plan


def iter_schedule_days(start: date, weeks: int = 4):
    for offset in range(weeks * 7):
        yield start + timedelta(days=offset)


def build_auto_trips(
    drivers: list[dict],
    start: date | None = None,
    weeks: int = 4,
    route_code: str = DEFAULT_ROUTE,
) -> list[dict]:
    """
    drivers: sıralı liste; her elemanda id, name, phone, plate, vehicle_type
    Sıra indeksi (0=Ahmet) algoritmayı belirler.
    """
    if start is None:
        start = date.today()
    trips: list[dict] = []
    for day in iter_schedule_days(start, weeks):
        if not is_active_day(day):
            continue
        for index, driver in enumerate(drivers):
            depart_time = departure_time_for(index, day)
            if not depart_time:
                continue
            trips.append(
                {
                    "driver_id": driver["id"],
                    "route_code": route_code,
                    "depart_date": day.isoformat(),
                    "depart_time": depart_time,
                    "seats_total": DEFAULT_SEATS,
                    "driver_name": driver["name"],
                    "driver_phone": driver["phone"],
                    "plate": driver["plate"],
                    "vehicle_type": driver.get("vehicle_type", VEHICLE_TYPE),
                    "note": AUTO_NOTE,
                }
            )
    return trips
