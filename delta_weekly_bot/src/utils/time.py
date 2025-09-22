import datetime
import pytz

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
    # This can be adjusted based on the time of day and the strategy's needs.
    if days_until_friday == 0:
        days_until_friday = 7

    return today + datetime.timedelta(days=days_until_friday)

def get_ist_time() -> datetime.datetime:
    """Returns the current time in the 'Asia/Kolkata' timezone."""
    return datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
