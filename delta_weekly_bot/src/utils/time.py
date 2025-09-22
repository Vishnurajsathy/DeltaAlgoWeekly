import datetime
import pytz
import calendar

def get_next_weekly_expiry() -> datetime.date:
    """
    Calculates the next weekly options expiry date.

    This is a simplified implementation assuming weekly options expire on Friday.
    It needs to be verified against Delta Exchange's specific expiry schedule,
    as some exchanges have daily or different weekly schedules.
    """
    today = datetime.date.today()
    # In Python's weekday(), Monday is 0 and Sunday is 6. Friday is 4.
    days_until_friday = (4 - today.weekday() + 7) % 7

    # If today is Friday, we typically want the *next* Friday's expiry, not today's.
    if days_until_friday == 0:
        days_until_friday = 7

    return today + datetime.timedelta(days=days_until_friday)

def get_ist_time() -> datetime.datetime:
    """Returns the current time in the 'Asia/Kolkata' timezone."""
    return datetime.datetime.now(pytz.timezone("Asia/Kolkata"))

def _get_last_friday_of_month(year: int, month: int) -> datetime.date:
    """Helper function to find the last Friday of a given month and year."""
    # Get the number of days in the month
    _, num_days = calendar.monthrange(year, month)

    # Start from the last day and go backwards until we find a Friday (weekday == 4)
    for day in range(num_days, 0, -1):
        date = datetime.date(year, month, day)
        if date.weekday() == 4:  # Friday
            return date
    # This part should be unreachable as every month has a last Friday.
    return None

def get_next_monthly_expiry() -> datetime.date:
    """
    Calculates the next monthly options expiry date.
    This is assumed to be the last Friday of the month.
    """
    today = datetime.date.today()

    # Find the last Friday of the current month
    last_friday_current_month = _get_last_friday_of_month(today.year, today.month)

    if today <= last_friday_current_month:
        # If today is on or before the last Friday, that's our target expiry
        return last_friday_current_month
    else:
        # Otherwise, we need the last Friday of the next month
        next_month = today.month + 1
        next_year = today.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        return _get_last_friday_of_month(next_year, next_month)
