"""Расчёт свободных окон с учётом длительности услуг и уже занятых записей."""
from datetime import date, datetime, time, timedelta

import config
import db
from utils import now


def working_dates() -> list[date]:
    """Рабочие дни на DAYS_AHEAD дней вперёд, начиная с сегодня."""
    today = now().date()
    days = (today + timedelta(days=i) for i in range(config.DAYS_AHEAD))
    return [d for d in days if d.weekday() in config.WORK_DAYS]


async def free_slots(day: date, duration: int) -> list[datetime]:
    """Все моменты начала, в которые услуга длительностью duration помещается без пересечений."""
    if day.weekday() not in config.WORK_DAYS:
        return []

    day_start = datetime.combine(day, time(0, 0), tzinfo=config.TZ)
    day_end = day_start + timedelta(days=1)
    busy = await db.bookings_between(int(day_start.timestamp()), int(day_end.timestamp()))
    intervals = [(b["start_ts"], b["start_ts"] + b["duration"] * 60) for b in busy]

    current = now()
    step = timedelta(minutes=config.SLOT_STEP_MIN)
    length = timedelta(minutes=duration)
    t = datetime.combine(day, time(config.WORK_START_HOUR), tzinfo=config.TZ)
    close = datetime.combine(day, time(config.WORK_END_HOUR), tzinfo=config.TZ)

    result = []
    while t + length <= close:
        if t > current:
            s = int(t.timestamp())
            e = s + duration * 60
            # интервалы [s, e) и [bs, be) пересекаются, если s < be и bs < e
            if all(not (s < be and bs < e) for bs, be in intervals):
                result.append(t)
        t += step
    return result


async def is_free(start: datetime, duration: int) -> bool:
    return start in await free_slots(start.date(), duration)
