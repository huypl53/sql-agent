import pytz


from datetime import datetime


def get_current_time() -> str:
    """Get the current time in Vietnam timezone (Asia/Ho_Chi_Minh).

    Returns:
        str: Current time in format 'YYYY-MM-DD HH:MM:SS TZ'
        Example: '2024-03-21 14:30:45 ICT'
    """
    # Get the current time in UTC
    utc_now = datetime.now(pytz.UTC)
    # Convert to local timezone (you can change this to any timezone)
    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")  # Default to Vietnam timezone
    local_time = utc_now.astimezone(local_tz)
    return local_time.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_current_date() -> str:
    """Get the current date in Vietnam timezone (Asia/Ho_Chi_Minh) with weekday.

    Returns:
        str: Current date in format 'YYYY-MM-DD (Weekday)'
        Example: '2024-03-21 (Thursday)'
    """
    # Get the current date in UTC
    utc_now = datetime.now(pytz.UTC)
    # Convert to local timezone (you can change this to any timezone)
    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")  # Default to Vietnam timezone
    local_time = utc_now.astimezone(local_tz)
    return local_time.strftime("%Y-%m-%d (%A)")
