"""Labeled synthetic eval set: 24 announcement scripts and 18 poster/board prompts, each labeled per test trip.

Relevance rule: an item is relevant to a trip when it changes service on the trip's line in the trip's direction
between its boarding and alighting stations, or changes the boarding or alighting station itself.
"""

TRIPS = {
    "T1": "Q train, northbound, from Times Sq-42 St to 72 St (2 Av), Manhattan",
    "T2": "F train, Manhattan-bound (northbound), from Jay St-MetroTech (Brooklyn) to 57 St (6 Av), Manhattan",
    "T3": "7 train, Flushing-bound, from Grand Central-42 St to Flushing-Main St, Queens",
}

# (id, lang, text, relevant_trips)
AUDIO = [
    ("a01", "en", "Attention customers. Northbound Q trains are not running between Times Square-42 Street and 72 Street. Please take the N or R train to Lexington Avenue-59 Street and transfer to the 6.", ["T1"]),
    ("a02", "en", "Attention please. Northbound F trains are running with delays of about 20 minutes because of a sick customer at Delancey Street-Essex Street.", ["T2"]),
    ("a03", "en", "Flushing-bound 7 express trains are suspended. 7 local trains are running with delays. Expect waits of up to 15 minutes at Grand Central.", ["T3"]),
    ("a04", "en", "Stand clear of the closing doors, please.", []),
    ("a05", "en", "This is a Brooklyn-bound A train. The next stop is Jay Street-MetroTech.", []),
    ("a06", "en", "Due to track maintenance, L trains are not running between 8 Avenue and Bedford Avenue this weekend.", []),
    ("a07", "en", "Attention customers at Jay Street-MetroTech. Manhattan-bound F trains are running on the A line to West 4 Street. For York Street and East Broadway, take the shuttle bus.", ["T2"]),
    ("a08", "en", "If you have lost an item on the train, please see the station agent or visit the lost and found.", []),
    ("a09", "en", "The next uptown Q train will arrive in 6 minutes.", []),
    ("a10", "en", "Due to an earlier incident, there is no 7 train service between Queensboro Plaza and Flushing-Main Street. Free shuttle buses are available.", ["T3"]),
    ("a11", "en", "N and W trains are delayed because of a train with mechanical problems at Astoria-Ditmars Boulevard.", []),
    ("a12", "en", "Attention passengers. The downtown 1 train is running local from 96 Street to South Ferry.", []),
    ("a13", "en", "Attention customers at Times Square. Uptown Q trains are now boarding on the express track, across the platform, on track 3.", ["T1"]),
    ("a14", "en", "Please do not hold the doors. There is another train directly behind this one.", []),
    ("a15", "en", "Attention F train customers. This weekend Manhattan-bound F trains will skip 57 Street and end at 47-50 Streets-Rockefeller Center.", ["T2"]),
    ("a16", "en", "Manhattan-bound 7 trains are running on schedule. There are delays on the 6 train in the Bronx.", []),
    ("a17", "es", "Atención pasajeros. Los trenes Q en dirección norte no están circulando entre Times Square y la calle 72. Por favor usen los trenes N o R.", ["T1"]),
    ("a18", "es", "Los trenes F hacia Manhattan tienen retrasos de quince minutos por problemas de señales en Jay Street-MetroTech.", ["T2"]),
    ("a19", "es", "Atención. Los trenes 7 expreso hacia Flushing están suspendidos. Los trenes locales circulan con retrasos.", ["T3"]),
    ("a20", "es", "Por favor, apártense de las puertas.", []),
    ("a21", "es", "Los trenes A y C circulan con retrasos debido a un incidente en la calle 59, Columbus Circle.", []),
    ("a22", "es", "Recuerden llevar todas sus pertenencias al salir del tren.", []),
    ("a23", "es", "Este fin de semana no hay servicio del tren L entre Manhattan y Brooklyn.", []),
    ("a24", "es", "Atención. Este fin de semana los trenes F no paran en la calle 57. La última parada es 47-50 Streets-Rockefeller Center.", ["T2"]),
]

_POSTER = ("A realistic smartphone photo of a printed New York City subway service-change poster taped to a tiled "
           "station wall, slightly angled, fluorescent lighting. White poster, bold black sans-serif type, a round "
           "colored subway line bullet at the top left. The poster text reads exactly: ")
_CLOCK = ("A realistic smartphone photo of an LCD subway countdown clock hanging above a New York City subway platform, "
          "black screen with white and amber text and round colored line bullets. The screen shows exactly: ")

# (id, kind, prompt, visible_text, relevant_trips)
IMAGES = [
    ("i01", "poster", _POSTER, "Q (yellow bullet). WEEKEND. No Q trains between 57 St-7 Av and 96 St. Sat and Sun, all day. Take the N to Lexington Av/59 St and transfer to the 6.", ["T1"]),
    ("i02", "poster", _POSTER, "F (orange bullet). WEEKEND. Manhattan-bound F trains run via the A line from Jay St-MetroTech to W 4 St. No F at York St, East Broadway, Delancey St.", ["T2"]),
    ("i03", "poster", _POSTER, "7 (purple bullet). WEEKEND. No 7 trains between 74 St-Broadway and Flushing-Main St. Free shuttle buses provide alternate service.", ["T3"]),
    ("i04", "poster", _POSTER, "L (grey bullet). No L trains between Broadway Junction and Canarsie-Rockaway Pkwy. Take the free shuttle bus.", []),
    ("i05", "poster", _POSTER, "A (blue bullet). Late nights. Uptown A trains skip 50 St. Take the C or the E.", []),
    ("i06", "poster", _POSTER, "1 (red bullet). Downtown 1 trains run express from 96 St to 42 St. Late nights, Mon to Fri.", []),
    ("i07", "clock", _CLOCK, "Q 96 St  DELAYED 14 min | N Astoria-Ditmars Blvd 3 min | R Forest Hills 7 min", ["T1"]),
    ("i08", "clock", _CLOCK, "F Jamaica-179 St 2 min | F Jamaica-179 St 9 min | A Inwood-207 St 4 min", []),
    ("i09", "clock", _CLOCK, "7 Flushing-Main St EXPRESS SUSPENDED | 7 Flushing-Main St local 11 min", ["T3"]),
    ("i10", "poster", _POSTER, "F (orange bullet). FIN DE SEMANA. Los trenes F no paran en 57 St. Usen 47-50 Sts-Rockefeller Ctr.", ["T2"]),
    ("i11", "poster", _POSTER, "6 (green bullet). Los trenes 6 hacia el Bronx circulan como locales. Noches, lunes a viernes.", []),
    ("i12", "poster", _POSTER, "Q (yellow bullet). 72 St station. The 2 Av and 72 St entrance is closed. Use the entrance at 2 Av and 69 St.", ["T1"]),
    ("i13", "poster", _POSTER, "If you see something, say something. Tell a police officer or an MTA employee.", []),
    ("i14", "poster", _POSTER, "G (light green bullet). No G trains between Court Sq and Nassau Av. Take the free shuttle bus.", []),
    ("i15", "poster", _POSTER, "J (brown bullet). Jamaica-bound J trains skip 104 St and 111 St. Weekends.", []),
    ("i16", "poster", _POSTER, "Station sign: Times Sq-42 St. N Q R W 1 2 3 7 S. Uptown and the Bronx.", []),
    ("i17", "poster", _POSTER, "Q (yellow bullet). FIN DE SEMANA. Los trenes Q no paran en la calle 72. Usen 86 St o Lexington Av/63 St.", ["T1"]),
    ("i18", "poster", _POSTER, "M (orange bullet). No M trains between Myrtle Av and Metropolitan Av. Take the J or the free shuttle bus.", []),
]
