const calendarColors = {
            'Boardroom Suite A': '#FF6B6B',
            'Boardroom Suite B': '#4ECDC4',
            'Majority Room': '#45B7D1',
            'Senate Boardroom': '#96CEB4',
            'Chairman Office': '#FFEEAD',
            '2nd Floor Conference': '#D4A5A5',
            'John Thune Conference': '#9370DB',
            '3rd Floor Conference A': '#FFB347',
            '3rd Floor Conference B': '#A8E6CF',
            '3rd Floor Conference C': '#3498DB',
            'Studio': '#E056FD',
            'Call Suite 1': '#20B2AA',
            'Call Suite 2': '#FFA07A',
            'Call Suite 3': '#87CEEB',
            'Call Suite 4': '#DDA0DD',
            'Call Suite 5': '#F0E68C',
            'Call Suite 6': '#98FB98',
            'Call Suite 7': '#DEB887'
        };

        document.addEventListener('DOMContentLoaded', function() {
            const calendarEl = document.getElementById('calendar');
            const calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'timeGridDay',
                slotMinTime: '07:00:00',
                slotMaxTime: '21:00:00',
                allDaySlot: false,
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'timeGridDay,timeGridWeek'
                },
                height: '100%',
                events: function(info, successCallback, failureCallback) {
                    fetch(`/api/fullcalendar/events?start=${info.startStr}&end=${info.endStr}`)
                        .then(response => response.json())
                        .then(data => {
                            const events = data.map(event => ({
                                title: event.summary,
                                start: new Date(event.start), // Convert to Date object
                                end: new Date(event.end),     // Convert to Date object
                                backgroundColor: calendarColors[event.calendar] || '#666',
                                extendedProps: {
                                    location: event.location,
                                    description: event.description,
                                    createdBy: event.created_by,
                                    attendees: event.attendees,
                                    calendar: event.calendar
                                }
                            }));
                            successCallback(events);
                        })
                        .catch(error => {
                            console.error('Error fetching events:', error);
                            failureCallback(error);
                        });
                },
                // Also, let's improve the event click handler to show more information
                eventClick: function(info) {
                    const event = info.event;
                    const attendeesList = event.extendedProps.attendees
                        ?.filter(a => a.displayName)
                        ?.map(a => a.displayName)
                        ?.join(', ') || 'No named attendees';
                        
                    alert(`
                Event: ${event.title}
                Time: ${event.start.toLocaleTimeString()} - ${event.end.toLocaleTimeString()}
                Location: ${event.extendedProps.location || 'N/A'}
                Room: ${event.extendedProps.calendar || 'N/A'}
                Created by: ${event.extendedProps.createdBy || 'N/A'}
                Attendees: ${attendeesList}
                `);
                }
            });
            
            calendar.render();
        });