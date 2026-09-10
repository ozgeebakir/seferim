"""Refahiye–Erzincan döner vardiya algoritması.

A grubu: Pazartesi, Çarşamba, Cuma, Pazar
B grubu: Salı, Perşembe, Cumartesi

Saat mantığı aynı: gruptaki 1. şoför 08:00, 2. 09:00, ... her aktif günde bir dilim kayar.
Boş gün yok — A'nın kapalı gününde B gider.
"""

from __future__ import annotations

from datetime import date, timedelta

GROUP_A_WEEKDAYS = (0, 2, 4, 6)  # Pzt, Çar, Cum, Paz
GROUP_B_WEEKDAYS = (1, 3, 5)  # Sal, Per, Cmt

DEPARTURE_TIMES = [
    "08:00",
    "10:30",
    "13:00",
    "15:30",
    "18:00",
]

SEED_DRIVERS = [
    # A grubu
    {"name": "Ahmet Yılmaz", "phone": "05551000001", "plate": "24 RFH 001", "group": "A"},
    {"name": "Mehmet Kaya", "phone": "05551000002", "plate": "24 RFH 002", "group": "A"},
    {"name": "Ali Demir", "phone": "05551000003", "plate": "24 RFH 003", "group": "A"},
    {"name": "Hasan Çelik", "phone": "05551000004", "plate": "24 RFH 004", "group": "A"},
    {"name": "Hüseyin Şahin", "phone": "05551000005", "plate": "24 RFH 005", "group": "A"},
    # B grubu
    {"name": "Mustafa Aydın", "phone": "05551000006", "plate": "24 RFH 006", "group": "B"},
    {"name": "İbrahim Yıldız", "phone": "05551000007", "plate": "24 RFH 007", "group": "B"},
    {"name": "Osman Arslan", "phone": "05551000008", "plate": "24 RFH 008", "group": "B"},
    {"name": "Yusuf Doğan", "phone": "05551000009", "plate": "24 RFH 009", "group": "B"},
    {"name": "Murat Koç", "phone": "05551000010", "plate": "24 RFH 010", "group": "B"},
]

AUTO_NOTE = "Otomatik vardiya programı"
VEHICLE_TYPE = "14 kişilik minibüs"
DEFAULT_SEATS = 14
DEFAULT_ROUTE = "ilce-merkez"  # Refahiye → Erzincan

DAY_NAMES = [
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
]


def weekdays_for_group(group: str) -> tuple[int, ...]:
    return GROUP_A_WEEKDAYS if group == "A" else GROUP_B_WEEKDAYS


def group_for_day(day: date) -> str:
    return "A" if day.weekday() in GROUP_A_WEEKDAYS else "B"


def drivers_with_group_index(seeds: list[dict] | None = None) -> list[dict]:
    """Her gruba kendi 0..n indeksini verir."""
    seeds = seeds or SEED_DRIVERS
    counters = {"A": 0, "B": 0}
    result = []
    for seed in seeds:
        group = seed["group"]
        item = dict(seed)
        item["group_index"] = counters[group]
        counters[group] += 1
        result.append(item)
    return result


def departure_time_for(group: str, group_index: int, day: date) -> str | None:
    weekdays = weekdays_for_group(group)
    if day.weekday() not in weekdays:
        return None
    slot = weekdays.index(day.weekday())
    n = len(DEPARTURE_TIMES)
    return DEPARTURE_TIMES[(group_index + slot) % n]


def weekly_plan_for(group: str, group_index: int) -> list[tuple[str, str | None]]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    plan = []
    for i, name in enumerate(DAY_NAMES):
        day = monday + timedelta(days=i)
        plan.append((name, departure_time_for(group, group_index, day)))
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
    drivers: group + group_index + id, name, phone, plate, vehicle_type
    """
    if start is None:
        start = date.today()
    trips: list[dict] = []
    for day in iter_schedule_days(start, weeks):
        for driver in drivers:
            depart_time = departure_time_for(
                driver["group"], driver["group_index"], day
            )
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
