# events.py
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        'service-account.json',
        scopes=SCOPES,
        subject='nrscadmin@nrsc.org'
    )
    return build('calendar', 'v3', credentials=credentials)


def format_time(datetime_str):
    if not datetime_str:
        return ""
    dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    eastern = pytz.timezone('America/New_York')
    dt_eastern = dt.astimezone(eastern)
    return dt_eastern.strftime('%-I:%M%p').lower()


def get_calendar_events(calendar_id, target_date):
    service = get_calendar_service()
    eastern = pytz.timezone('America/New_York')
    
    start_time = eastern.localize(datetime.combine(target_date, datetime.min.time())).isoformat()
    end_time = eastern.localize(datetime.combine(target_date, datetime.max.time())).isoformat()
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return [{
            'summary': event.get('summary', 'No Title'),
            'start_time': format_time(event['start'].get('dateTime')),
            'end_time': format_time(event['end'].get('dateTime')),
            'calendar': event.get('organizer', {}).get('displayName', 'Unknown Calendar'),
            'created_by': event.get('creator', {}).get('email', 'Unknown'),
            'location': event.get('location', ''),
            'description': event.get('description', ''),
            'attendees': [{'email': a.get('email', ''), 
                          'displayName': a.get('displayName', '')} 
                         for a in event.get('attendees', [])],
            'conference_data': event.get('conferenceData', {})
        } for event in events_result.get('items', [])]
            
    except Exception as e:
        print(f"Error accessing calendar {calendar_id}: {str(e)}")
        return None


def get_all_events(date_str=None):
    # Get date from string, default to today
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        target_date = datetime.now(pytz.timezone('America/New_York')).date()
    
    calendars = [
            'c_18863bgm0phmiif0k8os19o87hgb8@resource.calendar.google.com',  #NRSC-1-Boardroom Suite A (4)
            'c_1888u94ghequqibin6rslnjckorf8@resource.calendar.google.com',  #NRSC-1-Boardroom Suite B (2)
            'c_1880v02okvj4agt1kn4mb7j2hu32u@resource.calendar.google.com',  #NRSC-1-Majority Room (80)
            'c_188et5rt1alm8ghgkbso0kitm6i9g@resource.calendar.google.com',  #NRSC-1-Senate Boardroom (50)
            'c_1889kg01mgd2ogd8mpcej910ui0jq@resource.calendar.google.com',  #Chairman's Office
            'c_1884gm72dmd2sh42gh2rg0ffqu4ec@resource.calendar.google.com',  #NRSC-2-2nd Floor Conference Room (10)
            'c_1884giitap2dci8on6b6bm09jkdre@resource.calendar.google.com',  #NRSC-2-John Thune Conference Room (8)
            'c_188b7hdp53liciehjeamigaho54q6@resource.calendar.google.com',  #NRSC-3-3rd Floor Conference Room - A (10)
            'c_1889llbfhgiq2hd7m257ko1jkocoa@resource.calendar.google.com',  #NRSC-3-3rd Floor Conference Room - B (10)
            'c_1889llbfhgiq2hd7m257ko1jkocoa@resource.calendar.google.com',  #NRSC-3-3rd Floor Conference Room - C (5)
            'c_18896mg9ssuomjuvk1t0h5htgv3sc@resource.calendar.google.com',  #NRSC-3-Studio (8)
            'c_1884v1gbm5k9uja1gn45og3ve490i@resource.calendar.google.com',  #NRSC-C1-Call Suite 1 (12)
            'c_18863ks7hk6scg71hq2nhkaapno5q@resource.calendar.google.com',  #NRSC-C1-Call Suite 2 (3)
            'c_18822lp908sukh1nmq8p3tsh73olo@resource.calendar.google.com',  #NRSC-C1-Call Suite 3 (3)
            'c_188eog8j7a9t0hvql0859a3m1d4hi@resource.calendar.google.com',  #NRSC-C1-Call Suite 4 (4)
            'c_188dcrv2hh4qgigmln9kjistokekq@resource.calendar.google.com',  #NRSC-C1-Call Suite 5 (5)
            'c_18819kul9gcfgiv8i0ob55la9m02g@resource.calendar.google.com',  #NRSC-C1-Call Suite 6 (6)
            'c_1885vpj43qp9ujm4ik1g1kud1vhk6@resource.calendar.google.com',  #NRSC-C1-Call Suite 7 (6)
        ]
    
    all_events = []
    for calendar_id in calendars:
        events = get_calendar_events(calendar_id, target_date)
        if events:
            all_events.extend(events)
            
    # Sort events by start time
    all_events.sort(key=lambda x: x['start_time'])
    
    return {
        'date': target_date.strftime('%Y-%m-%d'),
        'formatted_date': target_date.strftime('%a %b %d, %Y'),
        'events': all_events
    }


def get_calendar_events_range(calendar_id, start_date, end_date):
    """
    Get events for a specific calendar within a date range.
    Designed to work with FullCalendar's date range requests.
    """
    service = get_calendar_service()
    eastern = pytz.timezone('America/New_York')
    
    # Convert start and end times to RFC3339 timestamps in Eastern time
    start_time = eastern.localize(datetime.combine(start_date, datetime.min.time())).isoformat()
    end_time = eastern.localize(datetime.combine(end_date, datetime.max.time())).isoformat()
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        calendar_events = []
        for event in events_result.get('items', []):
            # Get the event start and end times
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Format for FullCalendar
            calendar_events.append({
                'title': event.get('summary', 'No Title'),
                'start': start,  # FullCalendar expects ISO8601 dates
                'end': end,
                'location': event.get('location', ''),
                'description': event.get('description', ''),
                'extendedProps': {
                    'calendar': event.get('organizer', {}).get('displayName', 'Unknown Calendar'),
                    'created_by': event.get('creator', {}).get('email', 'Unknown'),
                    'attendees': event.get('attendees', []),
                    'conference_data': event.get('conferenceData', {})
                }
            })
            
        return calendar_events
            
    except Exception as e:
        print(f"Error accessing calendar {calendar_id}: {str(e)}")
        return []