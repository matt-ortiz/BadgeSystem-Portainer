from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template
from auth import login_required, requires_roles
from events import get_calendar_events, format_time, get_calendar_service

calendar_sync_blueprint = Blueprint('calendar_sync', __name__)

class CalendarComparer:
    def __init__(self):
        self.master_calendar_id = 'c_188for87jc7sgif2i4cufloqmiljg@resource.calendar.google.com'

    def get_master_events(self, date: str):
        """Fetch events from the master calendar"""
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        events = get_calendar_events(self.master_calendar_id, target_date)
        
        return {
            "date": date,
            "formatted_date": target_date.strftime('%a %b %d, %Y'),
            "events": events if events else []
        }

    def get_all_calendars_events(self, date: str):
        """Get events from all calendars"""
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Using the same calendar IDs from your events.py
        calendar_ids = [
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
        for calendar_id in calendar_ids:
            events = get_calendar_events(calendar_id, target_date)
            if events:
                all_events.extend(events)
        
        return all_events

    def compare_calendars(self, date: str):
        """Compare master calendar with all other calendars"""
        master_events = self.get_master_events(date)['events']
        all_events = self.get_all_calendars_events(date)

        comparison = {
            "date": date,
            "conflicts": [],
            "missing_from_master": [],
            "missing_from_calendars": [],
            "matching_events": []
        }

        self._compare_events(master_events, all_events, comparison)
        return comparison

    def _compare_events(self, master_events, calendar_events, comparison):
        """Compare events and find conflicts"""
        # Find matching and missing events
        for master_event in master_events:
            matching = [e for e in calendar_events 
                       if e['start_time'] == master_event['start_time'] and 
                       e['end_time'] == master_event['end_time'] and
                       e['location'] == master_event['location']]
            
            if matching:
                comparison["matching_events"].append({
                    "master": master_event,
                    "calendar": matching[0]
                })
            else:
                comparison["missing_from_calendars"].append(master_event)

        # Find events in calendars but not in master
        for calendar_event in calendar_events:
            if not any(e['start_time'] == calendar_event['start_time'] and 
                      e['end_time'] == calendar_event['end_time'] and
                      e['location'] == calendar_event['location'] 
                      for e in master_events):
                comparison["missing_from_master"].append(calendar_event)

        # Find conflicts
        sorted_events = sorted(calendar_events, key=lambda x: x['start_time'])
        for i in range(len(sorted_events)-1):
            for j in range(i+1, len(sorted_events)):
                if (sorted_events[i]['location'] == sorted_events[j]['location'] and
                    self._times_overlap(sorted_events[i]['start_time'], 
                                      sorted_events[i]['end_time'],
                                      sorted_events[j]['start_time'], 
                                      sorted_events[j]['end_time'])):
                    comparison["conflicts"].append({
                        "event1": sorted_events[i],
                        "event2": sorted_events[j]
                    })

    def _times_overlap(self, start1, end1, start2, end2):
        """Check if two time periods overlap"""
        if not all([start1, end1, start2, end2]):
            return False
            
        try:
            start1 = datetime.strptime(start1, "%I:%M%p")
            end1 = datetime.strptime(end1, "%I:%M%p")
            start2 = datetime.strptime(start2, "%I:%M%p")
            end2 = datetime.strptime(end2, "%I:%M%p")
            return start1 < end2 and start2 < end1
        except ValueError:
            return False

# Initialize the calendar comparer
calendar_comparer = CalendarComparer()

@calendar_sync_blueprint.route('/api/events_master')
def get_master_events():
    date = request.args.get('date')
    return jsonify(calendar_comparer.get_master_events(date))

@calendar_sync_blueprint.route('/api/calendar_comparison')
def compare_calendars():
    date = request.args.get('date')
    return jsonify(calendar_comparer.compare_calendars(date))

@calendar_sync_blueprint.route('/calendar-sync')
def calendar_sync_dashboard():
    return render_template('calendar_sync.html')
