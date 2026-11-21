# Overheard

Overheard turns what a traveller hears and sees on a trip into the few moments that touch their bookings, and stays silent about the rest.

## Trip

**Itinerary**:
Every booking for one trip, held together as one thing to protect.
_Avoid_: trip plan, schedule

**Booking**:
One reserved thing on the itinerary with a time and a place: a flight, a hotel stay, a train seat or a timed ticket.
_Avoid_: reservation, leg, segment

**Trip** (subway demo only):
One subway ride from a boarding station to an alighting station.

## Listening

**Input**:
One thing the traveller heard or saw, or one news item found for them: an announcement clip, a photo, a short video, an article.
_Avoid_: signal, event, message

**Itinerary fingerprint**:
The set of yes/no questions that together describe what would matter to this itinerary, each tagged with its booking.
_Avoid_: profile, query set

**Tagged question**:
One fingerprint question, labelled with the booking it protects and its group.

**Learned question**:
A tagged question written after a dismissal; a yes means the input is not about that booking.
_Avoid_: negative example, filter

**Verdict**:
The relevance of one input to each booking, from one Decision 1 call.
_Avoid_: score result, classification

**Radar**:
The sweep of news sources ahead of the trip for anything that could hit a booking.
_Avoid_: monitor, crawler

**Rehearsal**:
The announcements and signs a traveller is likely to meet on each booking, generated and voiced before the trip and run through Overheard.
_Avoid_: simulation, mock trip

## Speaking

**Alert**:
What Overheard says when an input hits a booking: the change, the action, in the traveller's language, with proof.
_Avoid_: notification, warning

**Proof**:
The evidence attached to an alert: the traveller's photo with the line circled, or the quoted sentence from the source.

**Silence receipt**:
The record left by an input Overheard ignored: a gist, its relevance and the nearest booking.
_Avoid_: log entry, skip

**Dismissal**:
The traveller saying an alert was not about them.

**Digest**:
The daily summary of what the radar found, with urgent items first.

**Urgent ping**:
An alert pushed at once because its booking starts within 48 hours.
