"""
ClinicalTrials.gov API v2 Integration Module

Provides functions to search for clinical trials matching a patient's profile
including cancer type, stage, biomarkers, and geographic location.

API Documentation: https://clinicaltrials.gov/data-api/api
"""

import requests
import logging
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger("clinical_trials")

# API Configuration
CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_DISTANCE_MILES = 50
DEFAULT_PAGE_SIZE = 10
MAX_RESULTS = 5           # trials shown to the patient (display cap)
FETCH_PAGE_SIZE = 30      # trials pulled from the API for ranking
CACHE_TTL_MINUTES = 60
REQUEST_TIMEOUT_SECONDS = 15

# Simple in-memory cache (resets between serverless invocations)
_trial_cache: Dict[str, tuple] = {}  # key -> (data, timestamp)

# Zip code prefix to state mapping (first 3 digits)
ZIP_TO_STATE = {
    # Northeast
    "006": "Puerto Rico", "007": "Puerto Rico", "008": "Puerto Rico", "009": "Puerto Rico",
    "010": "Massachusetts", "011": "Massachusetts", "012": "Massachusetts", "013": "Massachusetts",
    "014": "Massachusetts", "015": "Massachusetts", "016": "Massachusetts", "017": "Massachusetts",
    "018": "Massachusetts", "019": "Massachusetts", "020": "Massachusetts", "021": "Massachusetts",
    "022": "Massachusetts", "023": "Massachusetts", "024": "Massachusetts", "025": "Massachusetts",
    "026": "Massachusetts", "027": "Massachusetts",
    "028": "Rhode Island", "029": "Rhode Island",
    "030": "New Hampshire", "031": "New Hampshire", "032": "New Hampshire", "033": "New Hampshire",
    "034": "New Hampshire", "035": "New Hampshire", "036": "New Hampshire", "037": "New Hampshire",
    "038": "New Hampshire",
    "039": "Maine", "040": "Maine", "041": "Maine", "042": "Maine", "043": "Maine", "044": "Maine",
    "045": "Maine", "046": "Maine", "047": "Maine", "048": "Maine", "049": "Maine",
    "050": "Vermont", "051": "Vermont", "052": "Vermont", "053": "Vermont", "054": "Vermont",
    "055": "Vermont", "056": "Vermont", "057": "Vermont", "058": "Vermont", "059": "Vermont",
    "060": "Connecticut", "061": "Connecticut", "062": "Connecticut", "063": "Connecticut",
    "064": "Connecticut", "065": "Connecticut", "066": "Connecticut", "067": "Connecticut", "068": "Connecticut", "069": "Connecticut",
    "070": "New Jersey", "071": "New Jersey", "072": "New Jersey", "073": "New Jersey",
    "074": "New Jersey", "075": "New Jersey", "076": "New Jersey", "077": "New Jersey",
    "078": "New Jersey", "079": "New Jersey", "080": "New Jersey", "081": "New Jersey",
    "082": "New Jersey", "083": "New Jersey", "084": "New Jersey", "085": "New Jersey",
    "086": "New Jersey", "087": "New Jersey", "088": "New Jersey", "089": "New Jersey",
    "100": "New York", "101": "New York", "102": "New York", "103": "New York", "104": "New York",
    "105": "New York", "106": "New York", "107": "New York", "108": "New York", "109": "New York",
    "110": "New York", "111": "New York", "112": "New York", "113": "New York", "114": "New York",
    "115": "New York", "116": "New York", "117": "New York", "118": "New York", "119": "New York",
    "120": "New York", "121": "New York", "122": "New York", "123": "New York", "124": "New York",
    "125": "New York", "126": "New York", "127": "New York", "128": "New York", "129": "New York",
    "130": "New York", "131": "New York", "132": "New York", "133": "New York", "134": "New York",
    "135": "New York", "136": "New York", "137": "New York", "138": "New York", "139": "New York",
    "140": "New York", "141": "New York", "142": "New York", "143": "New York", "144": "New York",
    "145": "New York", "146": "New York", "147": "New York", "148": "New York", "149": "New York",
    "150": "Pennsylvania", "151": "Pennsylvania", "152": "Pennsylvania", "153": "Pennsylvania",
    "154": "Pennsylvania", "155": "Pennsylvania", "156": "Pennsylvania", "157": "Pennsylvania",
    "158": "Pennsylvania", "159": "Pennsylvania", "160": "Pennsylvania", "161": "Pennsylvania",
    "162": "Pennsylvania", "163": "Pennsylvania", "164": "Pennsylvania", "165": "Pennsylvania",
    "166": "Pennsylvania", "167": "Pennsylvania", "168": "Pennsylvania", "169": "Pennsylvania",
    "170": "Pennsylvania", "171": "Pennsylvania", "172": "Pennsylvania", "173": "Pennsylvania",
    "174": "Pennsylvania", "175": "Pennsylvania", "176": "Pennsylvania", "177": "Pennsylvania",
    "178": "Pennsylvania", "179": "Pennsylvania", "180": "Pennsylvania", "181": "Pennsylvania",
    "182": "Pennsylvania", "183": "Pennsylvania", "184": "Pennsylvania", "185": "Pennsylvania",
    "186": "Pennsylvania", "187": "Pennsylvania", "188": "Pennsylvania", "189": "Pennsylvania",
    "190": "Pennsylvania", "191": "Pennsylvania", "192": "Pennsylvania", "193": "Pennsylvania",
    "194": "Pennsylvania", "195": "Pennsylvania", "196": "Pennsylvania",
    # Mid-Atlantic / South
    "197": "Delaware", "198": "Delaware", "199": "Delaware",
    "200": "District of Columbia", "201": "Virginia", "202": "District of Columbia",
    "203": "District of Columbia", "204": "District of Columbia", "205": "District of Columbia",
    "206": "Maryland", "207": "Maryland", "208": "Maryland", "209": "Maryland",
    "210": "Maryland", "211": "Maryland", "212": "Maryland", "214": "Maryland", "215": "Maryland",
    "216": "Maryland", "217": "Maryland", "218": "Maryland", "219": "Maryland",
    "220": "Virginia", "221": "Virginia", "222": "Virginia", "223": "Virginia", "224": "Virginia",
    "225": "Virginia", "226": "Virginia", "227": "Virginia", "228": "Virginia", "229": "Virginia",
    "230": "Virginia", "231": "Virginia", "232": "Virginia", "233": "Virginia", "234": "Virginia",
    "235": "Virginia", "236": "Virginia", "237": "Virginia", "238": "Virginia", "239": "Virginia",
    "240": "Virginia", "241": "Virginia", "242": "Virginia", "243": "Virginia", "244": "Virginia",
    "245": "Virginia", "246": "Virginia",
    "247": "West Virginia", "248": "West Virginia", "249": "West Virginia", "250": "West Virginia",
    "251": "West Virginia", "252": "West Virginia", "253": "West Virginia", "254": "West Virginia",
    "255": "West Virginia", "256": "West Virginia", "257": "West Virginia", "258": "West Virginia",
    "259": "West Virginia", "260": "West Virginia", "261": "West Virginia", "262": "West Virginia",
    "263": "West Virginia", "264": "West Virginia", "265": "West Virginia", "266": "West Virginia",
    "267": "West Virginia", "268": "West Virginia",
    "270": "North Carolina", "271": "North Carolina", "272": "North Carolina", "273": "North Carolina",
    "274": "North Carolina", "275": "North Carolina", "276": "North Carolina", "277": "North Carolina",
    "278": "North Carolina", "279": "North Carolina", "280": "North Carolina", "281": "North Carolina",
    "282": "North Carolina", "283": "North Carolina", "284": "North Carolina", "285": "North Carolina",
    "286": "North Carolina", "287": "North Carolina", "288": "North Carolina", "289": "North Carolina",
    "290": "South Carolina", "291": "South Carolina", "292": "South Carolina", "293": "South Carolina",
    "294": "South Carolina", "295": "South Carolina", "296": "South Carolina", "297": "South Carolina",
    "298": "South Carolina", "299": "South Carolina",
    "300": "Georgia", "301": "Georgia", "302": "Georgia", "303": "Georgia", "304": "Georgia",
    "305": "Georgia", "306": "Georgia", "307": "Georgia", "308": "Georgia", "309": "Georgia",
    "310": "Georgia", "311": "Georgia", "312": "Georgia", "313": "Georgia", "314": "Georgia",
    "315": "Georgia", "316": "Georgia", "317": "Georgia", "318": "Georgia", "319": "Georgia",
    "320": "Florida", "321": "Florida", "322": "Florida", "323": "Florida", "324": "Florida",
    "325": "Florida", "326": "Florida", "327": "Florida", "328": "Florida", "329": "Florida",
    "330": "Florida", "331": "Florida", "332": "Florida", "333": "Florida", "334": "Florida",
    "335": "Florida", "336": "Florida", "337": "Florida", "338": "Florida", "339": "Florida",
    "340": "Florida", "341": "Florida", "342": "Florida", "344": "Florida", "346": "Florida",
    "347": "Florida", "349": "Florida",
    # South / Midwest
    "350": "Alabama", "351": "Alabama", "352": "Alabama", "354": "Alabama", "355": "Alabama",
    "356": "Alabama", "357": "Alabama", "358": "Alabama", "359": "Alabama", "360": "Alabama",
    "361": "Alabama", "362": "Alabama", "363": "Alabama", "364": "Alabama", "365": "Alabama",
    "366": "Alabama", "367": "Alabama", "368": "Alabama", "369": "Alabama",
    "370": "Tennessee", "371": "Tennessee", "372": "Tennessee", "373": "Tennessee", "374": "Tennessee",
    "375": "Tennessee", "376": "Tennessee", "377": "Tennessee", "378": "Tennessee", "379": "Tennessee",
    "380": "Tennessee", "381": "Tennessee", "382": "Tennessee", "383": "Tennessee", "384": "Tennessee",
    "385": "Tennessee",
    "386": "Mississippi", "387": "Mississippi", "388": "Mississippi", "389": "Mississippi",
    "390": "Mississippi", "391": "Mississippi", "392": "Mississippi", "393": "Mississippi",
    "394": "Mississippi", "395": "Mississippi", "396": "Mississippi", "397": "Mississippi",
    "400": "Kentucky", "401": "Kentucky", "402": "Kentucky", "403": "Kentucky", "404": "Kentucky",
    "405": "Kentucky", "406": "Kentucky", "407": "Kentucky", "408": "Kentucky", "409": "Kentucky",
    "410": "Kentucky", "411": "Kentucky", "412": "Kentucky", "413": "Kentucky", "414": "Kentucky",
    "415": "Kentucky", "416": "Kentucky", "417": "Kentucky", "418": "Kentucky",
    "420": "Kentucky", "421": "Kentucky", "422": "Kentucky", "423": "Kentucky", "424": "Kentucky",
    "425": "Kentucky", "426": "Kentucky", "427": "Kentucky",
    "430": "Ohio", "431": "Ohio", "432": "Ohio", "433": "Ohio", "434": "Ohio", "435": "Ohio",
    "436": "Ohio", "437": "Ohio", "438": "Ohio", "439": "Ohio", "440": "Ohio", "441": "Ohio",
    "442": "Ohio", "443": "Ohio", "444": "Ohio", "445": "Ohio", "446": "Ohio", "447": "Ohio",
    "448": "Ohio", "449": "Ohio", "450": "Ohio", "451": "Ohio", "452": "Ohio", "453": "Ohio",
    "454": "Ohio", "455": "Ohio", "456": "Ohio", "457": "Ohio", "458": "Ohio",
    "460": "Indiana", "461": "Indiana", "462": "Indiana", "463": "Indiana", "464": "Indiana",
    "465": "Indiana", "466": "Indiana", "467": "Indiana", "468": "Indiana", "469": "Indiana",
    "470": "Indiana", "471": "Indiana", "472": "Indiana", "473": "Indiana", "474": "Indiana",
    "475": "Indiana", "476": "Indiana", "477": "Indiana", "478": "Indiana", "479": "Indiana",
    "480": "Michigan", "481": "Michigan", "482": "Michigan", "483": "Michigan", "484": "Michigan",
    "485": "Michigan", "486": "Michigan", "487": "Michigan", "488": "Michigan", "489": "Michigan",
    "490": "Michigan", "491": "Michigan", "492": "Michigan", "493": "Michigan", "494": "Michigan",
    "495": "Michigan", "496": "Michigan", "497": "Michigan", "498": "Michigan", "499": "Michigan",
    "500": "Iowa", "501": "Iowa", "502": "Iowa", "503": "Iowa", "504": "Iowa", "505": "Iowa",
    "506": "Iowa", "507": "Iowa", "508": "Iowa", "509": "Iowa", "510": "Iowa", "511": "Iowa",
    "512": "Iowa", "513": "Iowa", "514": "Iowa", "515": "Iowa", "516": "Iowa",
    "520": "Iowa", "521": "Iowa", "522": "Iowa", "523": "Iowa", "524": "Iowa", "525": "Iowa",
    "526": "Iowa", "527": "Iowa", "528": "Iowa",
    "530": "Wisconsin", "531": "Wisconsin", "532": "Wisconsin", "534": "Wisconsin", "535": "Wisconsin",
    "537": "Wisconsin", "538": "Wisconsin", "539": "Wisconsin", "540": "Wisconsin", "541": "Wisconsin",
    "542": "Wisconsin", "543": "Wisconsin", "544": "Wisconsin", "545": "Wisconsin", "546": "Wisconsin",
    "547": "Wisconsin", "548": "Wisconsin", "549": "Wisconsin",
    "550": "Minnesota", "551": "Minnesota", "553": "Minnesota", "554": "Minnesota", "555": "Minnesota",
    "556": "Minnesota", "557": "Minnesota", "558": "Minnesota", "559": "Minnesota", "560": "Minnesota",
    "561": "Minnesota", "562": "Minnesota", "563": "Minnesota", "564": "Minnesota", "565": "Minnesota",
    "566": "Minnesota", "567": "Minnesota",
    "570": "South Dakota", "571": "South Dakota", "572": "South Dakota", "573": "South Dakota",
    "574": "South Dakota", "575": "South Dakota", "576": "South Dakota", "577": "South Dakota",
    "580": "North Dakota", "581": "North Dakota", "582": "North Dakota", "583": "North Dakota",
    "584": "North Dakota", "585": "North Dakota", "586": "North Dakota", "587": "North Dakota",
    "588": "North Dakota",
    "590": "Montana", "591": "Montana", "592": "Montana", "593": "Montana", "594": "Montana",
    "595": "Montana", "596": "Montana", "597": "Montana", "598": "Montana", "599": "Montana",
    "600": "Illinois", "601": "Illinois", "602": "Illinois", "603": "Illinois", "604": "Illinois",
    "605": "Illinois", "606": "Illinois", "607": "Illinois", "608": "Illinois", "609": "Illinois",
    "610": "Illinois", "611": "Illinois", "612": "Illinois", "613": "Illinois", "614": "Illinois",
    "615": "Illinois", "616": "Illinois", "617": "Illinois", "618": "Illinois", "619": "Illinois",
    "620": "Illinois", "622": "Illinois", "623": "Illinois", "624": "Illinois", "625": "Illinois",
    "626": "Illinois", "627": "Illinois", "628": "Illinois", "629": "Illinois",
    "630": "Missouri", "631": "Missouri", "633": "Missouri", "634": "Missouri", "635": "Missouri",
    "636": "Missouri", "637": "Missouri", "638": "Missouri", "639": "Missouri", "640": "Missouri",
    "641": "Missouri", "644": "Missouri", "645": "Missouri", "646": "Missouri", "647": "Missouri",
    "648": "Missouri", "649": "Missouri", "650": "Missouri", "651": "Missouri", "652": "Missouri",
    "653": "Missouri", "654": "Missouri", "655": "Missouri", "656": "Missouri", "657": "Missouri",
    "658": "Missouri",
    "660": "Kansas", "661": "Kansas", "662": "Kansas", "664": "Kansas", "665": "Kansas",
    "666": "Kansas", "667": "Kansas", "668": "Kansas", "669": "Kansas", "670": "Kansas",
    "671": "Kansas", "672": "Kansas", "673": "Kansas", "674": "Kansas", "675": "Kansas",
    "676": "Kansas", "677": "Kansas", "678": "Kansas", "679": "Kansas",
    "680": "Nebraska", "681": "Nebraska", "683": "Nebraska", "684": "Nebraska", "685": "Nebraska",
    "686": "Nebraska", "687": "Nebraska", "688": "Nebraska", "689": "Nebraska", "690": "Nebraska",
    "691": "Nebraska", "692": "Nebraska", "693": "Nebraska",
    # South / Southwest
    "700": "Louisiana", "701": "Louisiana", "703": "Louisiana", "704": "Louisiana", "705": "Louisiana",
    "706": "Louisiana", "707": "Louisiana", "708": "Louisiana", "710": "Louisiana", "711": "Louisiana",
    "712": "Louisiana", "713": "Louisiana", "714": "Louisiana",
    "716": "Arkansas", "717": "Arkansas", "718": "Arkansas", "719": "Arkansas", "720": "Arkansas",
    "721": "Arkansas", "722": "Arkansas", "723": "Arkansas", "724": "Arkansas", "725": "Arkansas",
    "726": "Arkansas", "727": "Arkansas", "728": "Arkansas", "729": "Arkansas",
    "730": "Oklahoma", "731": "Oklahoma", "733": "Oklahoma", "734": "Oklahoma", "735": "Oklahoma",
    "736": "Oklahoma", "737": "Oklahoma", "738": "Oklahoma", "739": "Oklahoma", "740": "Oklahoma",
    "741": "Oklahoma", "743": "Oklahoma", "744": "Oklahoma", "745": "Oklahoma", "746": "Oklahoma",
    "747": "Oklahoma", "748": "Oklahoma", "749": "Oklahoma",
    "750": "Texas", "751": "Texas", "752": "Texas", "753": "Texas", "754": "Texas", "755": "Texas",
    "756": "Texas", "757": "Texas", "758": "Texas", "759": "Texas", "760": "Texas", "761": "Texas",
    "762": "Texas", "763": "Texas", "764": "Texas", "765": "Texas", "766": "Texas", "767": "Texas",
    "768": "Texas", "769": "Texas", "770": "Texas", "771": "Texas", "772": "Texas", "773": "Texas",
    "774": "Texas", "775": "Texas", "776": "Texas", "777": "Texas", "778": "Texas", "779": "Texas",
    "780": "Texas", "781": "Texas", "782": "Texas", "783": "Texas", "784": "Texas", "785": "Texas",
    "786": "Texas", "787": "Texas", "788": "Texas", "789": "Texas", "790": "Texas", "791": "Texas",
    "792": "Texas", "793": "Texas", "794": "Texas", "795": "Texas", "796": "Texas", "797": "Texas",
    "798": "Texas", "799": "Texas",
    # West
    "800": "Colorado", "801": "Colorado", "802": "Colorado", "803": "Colorado", "804": "Colorado",
    "805": "Colorado", "806": "Colorado", "807": "Colorado", "808": "Colorado", "809": "Colorado",
    "810": "Colorado", "811": "Colorado", "812": "Colorado", "813": "Colorado", "814": "Colorado",
    "815": "Colorado", "816": "Colorado",
    "820": "Wyoming", "821": "Wyoming", "822": "Wyoming", "823": "Wyoming", "824": "Wyoming",
    "825": "Wyoming", "826": "Wyoming", "827": "Wyoming", "828": "Wyoming", "829": "Wyoming",
    "830": "Wyoming", "831": "Wyoming",
    "832": "Idaho", "833": "Idaho", "834": "Idaho", "835": "Idaho", "836": "Idaho", "837": "Idaho",
    "838": "Idaho",
    "840": "Utah", "841": "Utah", "842": "Utah", "843": "Utah", "844": "Utah", "845": "Utah",
    "846": "Utah", "847": "Utah",
    "850": "Arizona", "851": "Arizona", "852": "Arizona", "853": "Arizona", "855": "Arizona",
    "856": "Arizona", "857": "Arizona", "859": "Arizona", "860": "Arizona", "863": "Arizona",
    "864": "Arizona", "865": "Arizona",
    "870": "New Mexico", "871": "New Mexico", "872": "New Mexico", "873": "New Mexico",
    "874": "New Mexico", "875": "New Mexico", "877": "New Mexico", "878": "New Mexico",
    "879": "New Mexico", "880": "New Mexico", "881": "New Mexico", "882": "New Mexico",
    "883": "New Mexico", "884": "New Mexico",
    "889": "Nevada", "890": "Nevada", "891": "Nevada", "893": "Nevada", "894": "Nevada",
    "895": "Nevada", "897": "Nevada", "898": "Nevada",
    # Pacific
    "900": "California", "901": "California", "902": "California", "903": "California",
    "904": "California", "905": "California", "906": "California", "907": "California",
    "908": "California", "910": "California", "911": "California", "912": "California",
    "913": "California", "914": "California", "915": "California", "916": "California",
    "917": "California", "918": "California", "919": "California", "920": "California",
    "921": "California", "922": "California", "923": "California", "924": "California",
    "925": "California", "926": "California", "927": "California", "928": "California",
    "930": "California", "931": "California", "932": "California", "933": "California",
    "934": "California", "935": "California", "936": "California", "937": "California",
    "938": "California", "939": "California", "940": "California", "941": "California",
    "942": "California", "943": "California", "944": "California", "945": "California",
    "946": "California", "947": "California", "948": "California", "949": "California",
    "950": "California", "951": "California", "952": "California", "953": "California",
    "954": "California", "955": "California", "956": "California", "957": "California",
    "958": "California", "959": "California", "960": "California", "961": "California",
    "962": "APO/FPO", "963": "APO/FPO", "964": "APO/FPO", "965": "APO/FPO", "966": "APO/FPO",
    "967": "Hawaii", "968": "Hawaii",
    "970": "Oregon", "971": "Oregon", "972": "Oregon", "973": "Oregon", "974": "Oregon",
    "975": "Oregon", "976": "Oregon", "977": "Oregon", "978": "Oregon", "979": "Oregon",
    "980": "Washington", "981": "Washington", "982": "Washington", "983": "Washington",
    "984": "Washington", "985": "Washington", "986": "Washington", "988": "Washington",
    "989": "Washington", "990": "Washington", "991": "Washington", "992": "Washington",
    "993": "Washington", "994": "Washington",
    "995": "Alaska", "996": "Alaska", "997": "Alaska", "998": "Alaska", "999": "Alaska",
}


# =============================================================================
# ZIP CODE COORDINATES AND DISTANCE CALCULATION
# =============================================================================

import math
from typing import Tuple

# ZIP code prefix to approximate coordinates (latitude, longitude)
# Covers major metropolitan areas for distance estimation
ZIP_COORDINATES = {
    # Northeast
    "100": (40.7128, -74.0060),   # New York, NY
    "101": (40.7128, -74.0060),   # New York, NY
    "102": (40.7128, -74.0060),   # New York, NY
    "103": (40.5795, -74.1502),   # Staten Island, NY
    "104": (40.8448, -73.8648),   # Bronx, NY
    "110": (40.7282, -73.7949),   # Queens, NY
    "111": (40.6501, -73.9496),   # Brooklyn, NY
    "112": (40.6501, -73.9496),   # Brooklyn, NY
    "021": (42.3601, -71.0589),   # Boston, MA
    "022": (42.3601, -71.0589),   # Boston, MA
    "191": (39.9526, -75.1652),   # Philadelphia, PA
    "192": (39.9526, -75.1652),   # Philadelphia, PA
    "200": (38.9072, -77.0369),   # Washington, DC
    "201": (38.9072, -77.0369),   # Washington, DC
    "070": (40.7357, -74.1724),   # Newark, NJ
    "071": (40.7357, -74.1724),   # Newark, NJ
    # Southeast
    "303": (33.7490, -84.3880),   # Atlanta, GA
    "304": (33.7490, -84.3880),   # Atlanta, GA
    "331": (25.7617, -80.1918),   # Miami, FL
    "332": (25.7617, -80.1918),   # Miami, FL
    "333": (26.1224, -80.1373),   # Fort Lauderdale, FL
    "346": (27.9506, -82.4572),   # Tampa, FL
    "347": (28.5383, -81.3792),   # Orlando, FL
    "272": (35.7796, -78.6382),   # Raleigh, NC
    "282": (35.2271, -80.8431),   # Charlotte, NC
    # Midwest
    "606": (41.8781, -87.6298),   # Chicago, IL
    "607": (41.8781, -87.6298),   # Chicago, IL
    "608": (41.8781, -87.6298),   # Chicago, IL
    "481": (42.3314, -83.0458),   # Detroit, MI
    "482": (42.3314, -83.0458),   # Detroit, MI
    "432": (39.9612, -82.9988),   # Columbus, OH
    "441": (41.4993, -81.6944),   # Cleveland, OH
    "551": (44.9778, -93.2650),   # Minneapolis, MN
    "631": (38.6270, -90.1994),   # St. Louis, MO
    # Southwest
    "770": (29.7604, -95.3698),   # Houston, TX
    "771": (29.7604, -95.3698),   # Houston, TX
    "772": (29.7604, -95.3698),   # Houston, TX
    "750": (32.7767, -96.7970),   # Dallas, TX
    "751": (32.7767, -96.7970),   # Dallas, TX
    "752": (32.8998, -97.0403),   # Fort Worth, TX
    "782": (29.4241, -98.4936),   # San Antonio, TX
    "852": (33.4484, -112.0740),  # Phoenix, AZ
    "853": (33.4484, -112.0740),  # Phoenix, AZ
    "871": (35.0844, -106.6504),  # Albuquerque, NM
    "802": (39.7392, -104.9903),  # Denver, CO
    "803": (39.7392, -104.9903),  # Denver, CO
    # West Coast
    "900": (34.0522, -118.2437),  # Los Angeles, CA
    "901": (34.0522, -118.2437),  # Los Angeles, CA
    "902": (33.9425, -118.4081),  # Inglewood, CA
    "906": (34.1478, -118.1445),  # Pasadena, CA
    "917": (34.1478, -118.1445),  # Burbank/Glendale, CA
    "920": (32.7157, -117.1611),  # San Diego, CA
    "921": (32.7157, -117.1611),  # San Diego, CA
    "941": (37.7749, -122.4194),  # San Francisco, CA
    "942": (37.7749, -122.4194),  # San Francisco, CA
    "943": (37.5485, -122.0590),  # Palo Alto, CA
    "945": (37.8044, -122.2712),  # Oakland, CA
    "946": (37.8044, -122.2712),  # Oakland, CA
    "950": (37.3382, -121.8863),  # San Jose, CA
    "951": (37.3382, -121.8863),  # San Jose, CA
    "981": (47.6062, -122.3321),  # Seattle, WA
    "980": (47.6062, -122.3321),  # Seattle, WA
    "972": (45.5152, -122.6784),  # Portland, OR
    "891": (36.1699, -115.1398),  # Las Vegas, NV
}

# State centroids as fallback for locations without ZIP coordinates
STATE_CENTROIDS = {
    "Alabama": (32.806671, -86.791130),
    "Alaska": (61.370716, -152.404419),
    "Arizona": (33.729759, -111.431221),
    "Arkansas": (34.969704, -92.373123),
    "California": (36.116203, -119.681564),
    "Colorado": (39.059811, -105.311104),
    "Connecticut": (41.597782, -72.755371),
    "Delaware": (39.318523, -75.507141),
    "Florida": (27.766279, -81.686783),
    "Georgia": (33.040619, -83.643074),
    "Hawaii": (21.094318, -157.498337),
    "Idaho": (44.240459, -114.478828),
    "Illinois": (40.349457, -88.986137),
    "Indiana": (39.849426, -86.258278),
    "Iowa": (42.011539, -93.210526),
    "Kansas": (38.526600, -96.726486),
    "Kentucky": (37.668140, -84.670067),
    "Louisiana": (31.169546, -91.867805),
    "Maine": (44.693947, -69.381927),
    "Maryland": (39.063946, -76.802101),
    "Massachusetts": (42.230171, -71.530106),
    "Michigan": (43.326618, -84.536095),
    "Minnesota": (45.694454, -93.900192),
    "Mississippi": (32.741646, -89.678696),
    "Missouri": (38.456085, -92.288368),
    "Montana": (46.921925, -110.454353),
    "Nebraska": (41.125370, -98.268082),
    "Nevada": (38.313515, -117.055374),
    "New Hampshire": (43.452492, -71.563896),
    "New Jersey": (40.298904, -74.521011),
    "New Mexico": (34.840515, -106.248482),
    "New York": (42.165726, -74.948051),
    "North Carolina": (35.630066, -79.806419),
    "North Dakota": (47.528912, -99.784012),
    "Ohio": (40.388783, -82.764915),
    "Oklahoma": (35.565342, -96.928917),
    "Oregon": (44.572021, -122.070938),
    "Pennsylvania": (40.590752, -77.209755),
    "Rhode Island": (41.680893, -71.511780),
    "South Carolina": (33.856892, -80.945007),
    "South Dakota": (44.299782, -99.438828),
    "Tennessee": (35.747845, -86.692345),
    "Texas": (31.054487, -97.563461),
    "Utah": (40.150032, -111.862434),
    "Vermont": (44.045876, -72.710686),
    "Virginia": (37.769337, -78.169968),
    "Washington": (47.400902, -121.490494),
    "West Virginia": (38.491226, -80.954453),
    "Wisconsin": (44.268543, -89.616508),
    "Wyoming": (42.755966, -107.302490),
    "District of Columbia": (38.9072, -77.0369),
    "Puerto Rico": (18.2208, -66.5901),
}


def get_zip_coordinates(zip_code: str) -> Optional[Tuple[float, float]]:
    """
    Get approximate coordinates for a ZIP code.
    Uses 3-digit prefix for approximate location.

    Args:
        zip_code: 5-digit ZIP code string

    Returns:
        (latitude, longitude) tuple or None if not found
    """
    if not zip_code or len(zip_code) < 3:
        return None

    prefix = zip_code[:3]

    # Try exact prefix match
    if prefix in ZIP_COORDINATES:
        return ZIP_COORDINATES[prefix]

    # Fallback to state centroid
    state = ZIP_TO_STATE.get(prefix)
    if state and state in STATE_CENTROIDS:
        return STATE_CENTROIDS[state]

    return None


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        coord1: (latitude, longitude) of first point
        coord2: (latitude, longitude) of second point

    Returns:
        Distance in miles
    """
    R = 3958.8  # Earth's radius in miles

    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def calculate_trial_distance(patient_zip: str, trial_location: Dict[str, Any]) -> Optional[float]:
    """
    Calculate distance from patient to trial location.

    Args:
        patient_zip: Patient's ZIP code
        trial_location: Dict with city, state, zip keys

    Returns:
        Distance in miles (rounded to nearest integer) or None if cannot calculate
    """
    if not patient_zip or len(patient_zip) < 3:
        return None

    patient_prefix = patient_zip[:3]

    # Get patient coordinates - prefer specific ZIP, fallback to state
    patient_coords = ZIP_COORDINATES.get(patient_prefix)
    patient_used_state_fallback = False
    if not patient_coords:
        patient_state = ZIP_TO_STATE.get(patient_prefix)
        if patient_state and patient_state in STATE_CENTROIDS:
            patient_coords = STATE_CENTROIDS[patient_state]
            patient_used_state_fallback = True

    if not patient_coords:
        return None

    # Try to get trial coordinates from ZIP
    trial_zip = trial_location.get('zip', '')
    trial_coords = None
    trial_used_state_fallback = False

    if trial_zip and len(trial_zip) >= 3:
        trial_prefix = trial_zip[:3]
        trial_coords = ZIP_COORDINATES.get(trial_prefix)

    # Fallback: use state centroid for trial
    if not trial_coords:
        trial_state = trial_location.get('state', '')
        # Handle state abbreviations
        state_abbrev_to_name = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico"
        }
        state_name = state_abbrev_to_name.get(trial_state, trial_state)
        trial_coords = STATE_CENTROIDS.get(state_name)
        if trial_coords:
            trial_used_state_fallback = True

    if not trial_coords:
        return None

    # If both fell back to state centroids and coords are identical, return None
    # (would show misleading 0 miles)
    if patient_coords == trial_coords:
        return None

    distance = haversine_distance(patient_coords, trial_coords)
    # Return None for very small distances that might be artifacts of imprecise lookup
    if distance < 1:
        return None
    return round(distance)


def zip_to_state(zip_code: str) -> Optional[str]:
    """
    Convert a US zip code to its state name.

    Args:
        zip_code: 5-digit zip code string

    Returns:
        State name or None if not found
    """
    if not zip_code or len(zip_code) < 3:
        return None
    prefix = zip_code[:3]
    return ZIP_TO_STATE.get(prefix)


# Whole-module field projection requested from the API. Requesting whole
# modules (not individual leaves) means a missing leaf never silently drops a
# field, and guarantees `fields` is a superset of everything parse_trial_result
# reads. Keeps payloads small vs. the full study record.
TRIAL_FIELDS = ",".join([
    "protocolSection.identificationModule",
    "protocolSection.statusModule",
    "protocolSection.descriptionModule",
    "protocolSection.conditionsModule",
    "protocolSection.armsInterventionsModule",
    "protocolSection.designModule",
    "protocolSection.eligibilityModule",
    "protocolSection.contactsLocationsModule",
])


def build_search_query(patient_context: Dict[str, Any],
                       page_size: int = FETCH_PAGE_SIZE,
                       radius_miles: Optional[int] = 100) -> Dict[str, str]:
    """
    Build ClinicalTrials.gov API v2 query parameters from a patient profile.

    Hard filters (all AND-ed by the API):
    - overallStatus: RECRUITING + NOT_YET_RECRUITING only (actionable trials
      accepting, or about to accept, new patients).
    - StudyType: INTERVENTIONAL only (treatment trials, not observational).
    - geo: within `radius_miles` of the patient's ZIP (great-circle), unless
      `radius_miles is None` (nationwide) or the ZIP can't be geocoded.
    - condition: per-cancer synonyms (+ stage terms) from cancer config.

    Biomarker / treatment-line signals are deliberately NOT hard filters — they
    rank the broad result set in score_trial_relevance() instead.

    Args:
        patient_context: Extracted patient context from profile_utils
        page_size: Number of studies to fetch for ranking
        radius_miles: Geo radius in miles (25/50/100), or None for nationwide

    Returns:
        Dict of query parameters for the API
    """
    params = {
        "format": "json",
        "pageSize": str(page_size),
        "countTotal": "true",
        "filter.overallStatus": "RECRUITING,NOT_YET_RECRUITING",
        "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
        "fields": TRIAL_FIELDS,
    }

    # Build condition query — look up the per-cancer ClinicalTrials.gov
    # synonyms from config/cancers/<slug>/trial_synonyms.yaml (or fall back
    # to cancer.yaml.clinicaltrials_conditions). Fixes the previous bug
    # that unconditionally appended "colorectal cancer" for every cancer.
    cancer_slug = patient_context.get("cancer_slug")
    if not cancer_slug:
        # Legacy fallback: derive from the raw cancer_type string
        try:
            from lib.cancer_registry import resolve_slug
            cancer_slug = resolve_slug(patient_context.get("cancer_type") or "")
        except Exception:
            cancer_slug = "colorectal"

    try:
        from lib.cancer_registry import load_trial_synonyms
        synonyms = load_trial_synonyms(cancer_slug) or {}
    except Exception:
        synonyms = {}

    conditions = list(synonyms.get("conditions") or [])
    if not conditions:
        conditions = ["cancer"]

    # Stage-specific terms — from per-cancer config when present
    stage = patient_context.get("stage") or ""
    stage_upper = stage.upper()
    stage_specific = synonyms.get("stage_specific") or {}
    if "IV" in stage_upper or "4" in stage:
        conditions.extend(stage_specific.get("IV") or [])
    elif "III" in stage_upper or "3" in stage:
        conditions.extend(stage_specific.get("III") or [])
    elif "II" in stage_upper or "2" in stage:
        conditions.extend(stage_specific.get("II") or [])
    elif "I" in stage_upper or "1" in stage:
        conditions.extend(stage_specific.get("I") or [])

    params["query.cond"] = " OR ".join(conditions)

    # Geo radius — filter to trials with a location within `radius_miles` of the
    # patient's ZIP. Uses the API's server-side great-circle distance filter, so
    # border-town patients see nearby out-of-state trials (unlike the old
    # state-name match). Omitted for nationwide or an un-geocodable ZIP.
    zip_code = patient_context.get("zip_code")
    if radius_miles is not None and zip_code and zip_code != "unspecified" and zip_code.strip():
        coords = get_zip_coordinates(zip_code.strip())
        if coords:
            lat, lon = coords
            params["filter.geo"] = f"distance({lat},{lon},{radius_miles}mi)"

    return params


def fetch_clinical_trials(params: Dict[str, str],
                          use_cache: bool = True) -> Dict[str, Any]:
    """
    Fetch clinical trials from ClinicalTrials.gov API v2.

    Args:
        params: Query parameters
        use_cache: Whether to use cached results

    Returns:
        API response with trials data
    """
    # Generate cache key
    cache_key = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

    # Check cache
    if use_cache and cache_key in _trial_cache:
        data, timestamp = _trial_cache[cache_key]
        if datetime.now() - timestamp < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info("Cache hit for clinical trials query")
            return data

    try:
        logger.info(f"Fetching clinical trials with params: {params}")
        response = requests.get(
            CLINICAL_TRIALS_BASE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={
                "User-Agent": "WondrLink-Colon-Cancer-Chatbot/1.0",
                "Accept": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()

        # Cache result
        _trial_cache[cache_key] = (data, datetime.now())

        return data

    except requests.exceptions.Timeout:
        logger.error("ClinicalTrials.gov API timeout")
        return {"error": "timeout", "studies": []}
    except requests.exceptions.RequestException as e:
        logger.error(f"ClinicalTrials.gov API error: {e}")
        return {"error": str(e), "studies": []}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ClinicalTrials.gov response: {e}")
        return {"error": "invalid_response", "studies": []}


_STATUS_LABELS = {
    "RECRUITING": "Recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "NOT_YET_RECRUITING": "Not yet recruiting",
    "COMPLETED": "Completed",
    "SUSPENDED": "Suspended",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "AVAILABLE": "Available",
    "NO_LONGER_AVAILABLE": "No longer available",
    "TEMPORARILY_NOT_AVAILABLE": "Temporarily not available",
    "APPROVED_FOR_MARKETING": "Approved for marketing",
    "WITHHELD": "Withheld",
    "UNKNOWN": "Unknown status",
}

_PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "Not applicable",
}


def _humanize_status(raw: str) -> str:
    """Turn a raw ClinicalTrials.gov overallStatus enum into a display label."""
    if not raw:
        return "Unknown status"
    key = raw.strip().upper()
    return _STATUS_LABELS.get(key, raw.replace("_", " ").capitalize())


def _humanize_phase(phases: list) -> str:
    """Turn the raw phases list into a display label, e.g. ['PHASE1','PHASE2'] -> 'Phase 1/2'."""
    if not phases:
        return "Not specified"
    labels = [
        _PHASE_LABELS.get(str(p).strip().upper(), str(p).replace("_", " ").title())
        for p in phases
    ]
    # Collapse consecutive numbered phases: "Phase 1" + "Phase 2" -> "Phase 1/2"
    if len(labels) > 1 and all(l.startswith("Phase ") for l in labels):
        return "Phase " + "/".join(l.replace("Phase ", "") for l in labels)
    return " / ".join(labels)


def calculate_trial_distance_geo(patient_coords: Optional[Tuple[float, float]],
                                 patient_zip: Optional[str],
                                 loc: Dict[str, Any]) -> Optional[float]:
    """Distance in miles (rounded) from the patient to a trial location.

    Prefers the location's exact geoPoint (from the API) via haversine; falls
    back to the ZIP/state-centroid estimate when geoPoint is absent.
    """
    if patient_coords and loc.get("lat") is not None and loc.get("lon") is not None:
        return round(haversine_distance(patient_coords, (loc["lat"], loc["lon"])))
    if patient_zip:
        return calculate_trial_distance(patient_zip, loc)
    return None


def _prettify_condition(cond: str) -> str:
    """Lightly de-jargon a condition label for patients (MeSH -> plain)."""
    if not cond:
        return ""
    return cond.replace("Neoplasms", "Cancer").replace("Neoplasm", "Cancer")


def _plain_summary(phase: str, study_purpose: str,
                   interventions: List[Dict[str, Any]],
                   conditions: List[str]) -> str:
    """One-line, non-technical description built from structured fields.

    e.g. "Phase 2 trial testing Botensilimab and Balstilimab as a treatment
    for Colorectal Cancer." — avoids the dense scientific brief summary.
    """
    drugs = [i.get("name", "") for i in (interventions or []) if i.get("name")]
    cond = _prettify_condition((conditions or [""])[0])
    phase_l = phase if phase and phase.lower() not in ("not specified", "") else ""
    purpose_l = (study_purpose or "").lower()

    lead = (phase_l + " ") if phase_l else ""
    if drugs:
        if len(drugs) == 1:
            drug_str = drugs[0]
        elif len(drugs) == 2:
            drug_str = f"{drugs[0]} and {drugs[1]}"
        else:
            drug_str = f"{drugs[0]}, {drugs[1]}, and others"
        if purpose_l == "treatment":
            body = f"trial testing {drug_str} as a treatment"
        elif purpose_l:
            body = f"{purpose_l} study of {drug_str}"
        else:
            body = f"trial of {drug_str}"
    else:
        body = "treatment trial" if purpose_l == "treatment" else (
            f"{purpose_l} study" if purpose_l else "clinical trial")

    text = (lead + body).strip()
    text = (text[0].upper() + text[1:]) if text else "Clinical trial"
    if cond:
        text += f" for {cond}"
    return text + "."


def parse_trial_result(study: Dict[str, Any], preferred_state: Optional[str] = None,
                       patient_zip: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a single study result into a display-friendly format.

    Args:
        study: Raw study data from API
        preferred_state: State name to prioritize when listing locations
        patient_zip: Patient's ZIP code for distance calculation

    Returns:
        Dict with the display fields (nct_id, title, phase, status, band-ready
        relevance, locations w/ distance, and the enriched interventions,
        conditions, study_purpose, enrollment, eligibility, central_contact).
    """
    protocol = study.get("protocolSection", {})
    id_module = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    desc_module = protocol.get("descriptionModule", {})
    design_module = protocol.get("designModule", {})
    contacts_module = protocol.get("contactsLocationsModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    arms_module = protocol.get("armsInterventionsModule", {})

    nct_id = id_module.get("nctId", "")

    # Get locations - prioritize the patient's state. Capture each location's
    # geoPoint (lat/lon) when present for accurate distance.
    all_us_locations = []
    preferred_locations = []

    for loc in contacts_module.get("locations", []):
        if loc.get("country", "").lower() in ["united states", "usa", "us"]:
            geo = loc.get("geoPoint") or {}
            loc_info = {
                "facility": loc.get("facility", ""),
                "city": loc.get("city", ""),
                "state": loc.get("state", ""),
                "zip": loc.get("zip", ""),
                "status": loc.get("status", ""),
                "lat": geo.get("lat"),
                "lon": geo.get("lon"),
            }
            # Check if this location is in the preferred state
            if preferred_state and loc.get("state", "").lower() == preferred_state.lower():
                preferred_locations.append(loc_info)
            else:
                all_us_locations.append(loc_info)

    # Combine: preferred state locations first, then others (limit to 3 total)
    locations = (preferred_locations + all_us_locations)[:3]

    # Distance per location — geoPoint-accurate, ZIP/centroid fallback.
    patient_coords = get_zip_coordinates(patient_zip) if patient_zip else None
    if patient_zip:
        for loc in locations:
            loc['distance_miles'] = calculate_trial_distance_geo(patient_coords, patient_zip, loc)

        # Sort locations by distance (nearest first), putting None distances last
        locations_with_distance = [l for l in locations if l.get('distance_miles') is not None]
        locations_without_distance = [l for l in locations if l.get('distance_miles') is None]
        locations_with_distance.sort(key=lambda x: x['distance_miles'])
        locations = locations_with_distance + locations_without_distance

    # Determine nearest distance
    nearest_distance = None
    if locations and locations[0].get('distance_miles') is not None:
        nearest_distance = locations[0]['distance_miles']

    # Get phases (humanized: "PHASE2" -> "Phase 2", ["PHASE1","PHASE2"] -> "Phase 1/2", [] -> "Not specified")
    phase_str = _humanize_phase(design_module.get("phases", []))

    # Get brief summary (truncate if too long)
    brief_summary = desc_module.get("briefSummary", "")
    if len(brief_summary) > 400:
        brief_summary = brief_summary[:397] + "..."

    # Interventions as {name, type} objects (DRUG / BIOLOGICAL / PROCEDURE ...)
    interventions = [
        {"name": i.get("name", ""), "type": i.get("type", "")}
        for i in (arms_module.get("interventions") or [])
        if i.get("name")
    ]

    # Primary purpose, humanized (TREATMENT -> "Treatment", SUPPORTIVE_CARE -> "Supportive Care")
    raw_purpose = (design_module.get("designInfo", {}) or {}).get("primaryPurpose", "") or ""
    study_purpose = raw_purpose.replace("_", " ").title()

    # Central contact (first listed), if any
    central_contacts = contacts_module.get("centralContacts") or []
    central_contact = None
    if central_contacts:
        cc = central_contacts[0]
        central_contact = {
            "name": cc.get("name", ""),
            "phone": cc.get("phone", ""),
            "email": cc.get("email", ""),
        }

    min_age = eligibility_module.get("minimumAge", "")
    max_age = eligibility_module.get("maximumAge", "")
    sex = eligibility_module.get("sex", "All")
    healthy_volunteers = eligibility_module.get("healthyVolunteers")

    # Plain-language, patient-friendly one-liner (replaces the dense scientific
    # brief summary on the card; brief_summary is still returned for reference).
    plain_summary = _plain_summary(
        phase_str, study_purpose, interventions, conditions_module.get("conditions", []) or []
    )

    return {
        "nct_id": nct_id,
        "title": id_module.get("briefTitle", "Untitled Study"),
        "official_title": id_module.get("officialTitle", ""),
        "phase": phase_str,
        "status": _humanize_status(status_module.get("overallStatus", "")),
        "raw_status": status_module.get("overallStatus", ""),
        "plain_summary": plain_summary,
        "brief_summary": brief_summary,
        "start_date": status_module.get("startDateStruct", {}).get("date", ""),
        "conditions": conditions_module.get("conditions", []) or [],
        "interventions": interventions,
        "study_type": design_module.get("studyType", ""),
        "study_purpose": study_purpose,
        "enrollment_count": (design_module.get("enrollmentInfo", {}) or {}).get("count"),
        "eligibility_criteria": eligibility_module.get("eligibilityCriteria", ""),
        "healthy_volunteers": healthy_volunteers,
        "central_contact": central_contact,
        "locations": locations,
        "nearest_distance_miles": nearest_distance,
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        # Flat eligibility (score_trial_relevance reads these) ...
        "min_age": min_age,
        "max_age": max_age,
        "sex": sex,
        # ... plus nested for the frontend.
        "eligibility": {
            "min_age": min_age,
            "max_age": max_age,
            "sex": sex,
            "healthy_volunteers": healthy_volunteers,
        },
    }


def _parse_age(age_str: str) -> Optional[int]:
    """
    Parse age string from ClinicalTrials.gov format (e.g., '18 Years', '65 Years').

    Returns:
        Integer age or None if cannot parse
    """
    if not age_str:
        return None
    import re
    match = re.search(r'(\d+)', str(age_str))
    if match:
        return int(match.group(1))
    return None


def score_trial_relevance(trial: Dict[str, Any],
                          patient_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a clinical trial's relevance to the patient profile.

    Checks age eligibility, sex eligibility, biomarker alignment,
    treatment line alignment, and distance.

    Args:
        trial: Parsed trial dict from parse_trial_result()
        patient_context: Patient context from extract_patient_context_complex()

    Returns:
        Dict with: score (0-100), reasons (list), warnings (list), eligible (bool)
    """
    score = 50  # Base score
    reasons = []
    warnings = []
    eligible = True

    intervention_names = " ".join(
        i.get("name", "") for i in (trial.get("interventions") or [])
    )
    condition_names = " ".join(trial.get("conditions") or [])
    trial_text = (
        (trial.get("title") or "") + " " +
        (trial.get("official_title") or "") + " " +
        (trial.get("brief_summary") or "") + " " +
        intervention_names + " " +
        condition_names
    ).lower()

    # --- 1. Age eligibility ---
    patient_age = patient_context.get("age")
    if patient_age:
        try:
            patient_age = int(patient_age)
        except (ValueError, TypeError):
            patient_age = None

    if patient_age:
        min_age = _parse_age(trial.get("min_age", ""))
        max_age = _parse_age(trial.get("max_age", ""))

        if min_age and patient_age < min_age:
            eligible = False
            warnings.append(f"Minimum age is {min_age}, patient is {patient_age}")
        elif max_age and patient_age > max_age:
            eligible = False
            warnings.append(f"Maximum age is {max_age}, patient is {patient_age}")
        else:
            if min_age or max_age:
                # Age eligibility is already shown on the card — don't echo it
                # back as a match "reason" (keep the score nudge though).
                score += 5

    # --- 2. Sex eligibility ---
    trial_sex = (trial.get("sex") or "All").lower()
    patient_gender = (patient_context.get("gender") or "").lower()

    if trial_sex != "all" and patient_gender and patient_gender != "unspecified":
        if trial_sex == "female" and patient_gender in ("male", "m"):
            eligible = False
            warnings.append("Trial is for female patients only")
        elif trial_sex == "male" and patient_gender in ("female", "f"):
            eligible = False
            warnings.append("Trial is for male patients only")
        else:
            # Sex eligibility is shown on the card too — score nudge only.
            score += 5

    # --- 3. Biomarker alignment ---
    biomarkers = (patient_context.get("biomarkers") or "").upper()

    if biomarkers and biomarkers not in ("UNSPECIFIED", "PENDING/UNSPECIFIED"):
        # MSI-H alignment
        if "MSI-H" in biomarkers or "MSI-HIGH" in biomarkers or "UNSTABLE" in biomarkers:
            if "msi" in trial_text or "immunotherapy" in trial_text or "pembrolizumab" in trial_text or "checkpoint" in trial_text:
                reasons.append("MSI-H status aligns with immunotherapy trial")
                score += 15
        elif "MSS" in biomarkers or "STABLE" in biomarkers:
            if "msi-h" in trial_text and "msi-h required" in trial_text:
                warnings.append("Trial may require MSI-H; patient is MSS")

        # KRAS alignment
        if "KRAS" in biomarkers:
            if "mutation" in biomarkers.lower() or "mutant" in biomarkers.lower() or "g12" in biomarkers.lower():
                if "kras" in trial_text:
                    reasons.append("KRAS mutation relevant to this trial")
                    score += 10
                if "cetuximab" in trial_text or "panitumumab" in trial_text:
                    warnings.append("EGFR inhibitors in trial may not be effective with KRAS mutation")

        # BRAF alignment
        if "BRAF" in biomarkers and ("V600E" in biomarkers or "MUTATION" in biomarkers):
            if "braf" in trial_text or "encorafenib" in trial_text:
                reasons.append("BRAF V600E relevant to this trial")
                score += 10

        # HER2 alignment
        if "HER2" in biomarkers and ("POSITIVE" in biomarkers or "AMPLIFIED" in biomarkers or "3+" in biomarkers):
            if "her2" in trial_text or "trastuzumab" in trial_text:
                reasons.append("HER2+ status relevant to this trial")
                score += 10

    # --- 4. Treatment line alignment ---
    treatment_line = (patient_context.get("treatment_line") or "").lower()
    if treatment_line:
        if "first" in treatment_line or "1st" in treatment_line or "adjuvant" in treatment_line:
            if "first-line" in trial_text or "first line" in trial_text or "adjuvant" in trial_text:
                reasons.append("Matches first-line/adjuvant treatment setting")
                score += 10
        elif "second" in treatment_line or "2nd" in treatment_line:
            if "second-line" in trial_text or "second line" in trial_text:
                reasons.append("Matches second-line treatment setting")
                score += 10
        elif "third" in treatment_line or "3rd" in treatment_line:
            if "third-line" in trial_text or "third line" in trial_text or "refractory" in trial_text:
                reasons.append("Matches third-line/refractory setting")
                score += 10

    # --- 5. Distance bonus (geoPoint-accurate when available) ---
    nearest_distance = trial.get("nearest_distance_miles")
    if nearest_distance is not None:
        if nearest_distance <= 25:
            reasons.append(f"Close to you (~{nearest_distance} mi)")
            score += 10
        elif nearest_distance <= 50:
            reasons.append(f"Within 50 miles (~{nearest_distance} mi)")
            score += 5
        elif nearest_distance <= 100:
            reasons.append(f"Within 100 miles (~{nearest_distance} mi)")
            score += 2

    # --- 6. Treatment-purpose boost ---
    # The query is interventional-only; this separates treatment trials from
    # prevention / diagnostic / supportive-care interventional studies.
    if (trial.get("study_purpose") or "").lower() == "treatment":
        reasons.append("Treatment-focused")
        score += 5

    # Clamp score to 0-100
    score = max(0, min(100, score))

    return {
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
        "eligible": eligible
    }


def validate_trial_search_readiness(patient_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check whether the patient profile has enough data for a meaningful trial search.

    Critical fields (blocks search if missing): zip_code, stage
    Helpful fields (warns if missing): biomarkers, treatment_line, age

    Returns:
        Dict with: ready (bool), missing_critical (list), missing_helpful (list),
                   prompt_message (str or None)
    """
    if not patient_context:
        return {
            "ready": False,
            "missing_critical": ["zip_code", "stage"],
            "missing_helpful": ["biomarkers", "treatment_line", "age"],
            "prompt_message": (
                "I don't have enough information to search for clinical trials yet. "
                "Please update your profile with at least your **zip code** and **cancer stage** "
                "so I can find relevant trials near you."
            )
        }

    missing_critical = []
    missing_helpful = []

    # Critical fields
    zip_code = patient_context.get("zip_code")
    if not zip_code or zip_code == "unspecified":
        missing_critical.append("zip_code")

    stage = patient_context.get("stage")
    if not stage or stage == "unspecified":
        missing_critical.append("stage")

    # Helpful fields
    biomarkers = patient_context.get("biomarkers")
    if not biomarkers or biomarkers == "unspecified" or biomarkers == "pending/unspecified":
        missing_helpful.append("biomarkers")

    treatment_line = patient_context.get("treatment_line")
    if not treatment_line:
        missing_helpful.append("treatment_line")

    age = patient_context.get("age")
    if not age:
        missing_helpful.append("age")

    gender = patient_context.get("gender")
    if not gender or gender == "unspecified":
        missing_helpful.append("gender")

    # Build prompt message
    if missing_critical:
        field_names = {
            "zip_code": "zip code",
            "stage": "cancer stage"
        }
        missing_names = [field_names.get(f, f) for f in missing_critical]
        prompt_message = (
            f"Before I can search for clinical trials, I need your "
            f"**{' and '.join(missing_names)}**. "
            f"Please update your profile with this information so I can find the most relevant trials for you."
        )
        return {
            "ready": False,
            "missing_critical": missing_critical,
            "missing_helpful": missing_helpful,
            "prompt_message": prompt_message
        }

    # Ready but with helpful fields missing
    prompt_message = None
    if missing_helpful:
        field_names = {
            "biomarkers": "biomarker results",
            "treatment_line": "current treatment line",
            "age": "age",
            "gender": "gender"
        }
        missing_names = [field_names.get(f, f) for f in missing_helpful]
        prompt_message = (
            f"Tip: Adding your {', '.join(missing_names)} to your profile "
            f"would help me find even more relevant trials for you."
        )

    return {
        "ready": True,
        "missing_critical": [],
        "missing_helpful": missing_helpful,
        "prompt_message": prompt_message
    }


def search_trials_for_patient(patient_context: Dict[str, Any],
                               max_results: int = MAX_RESULTS,
                               radius_miles: Optional[int] = 100) -> Dict[str, Any]:
    """
    Search for clinical trials matching patient profile.

    Args:
        patient_context: From extract_patient_context_complex()
        max_results: Maximum trials to return
        radius_miles: Geo search radius in miles (25/50/100), or None nationwide

    Returns:
        Dict with: trials (list), total_found, search_criteria, error (if any)
    """
    # Validate required fields
    zip_code = patient_context.get("zip_code")
    if not zip_code or zip_code == "unspecified":
        return {
            "trials": [],
            "total_found": 0,
            "search_criteria": {},
            "error": "no_zip_code",
            "error_message": "Please add your zip code to your profile to search for local clinical trials."
        }

    # Get the state for location prioritization
    patient_state = zip_to_state(zip_code)

    # Build query (recruiting + interventional, within radius; large page for ranking)
    params = build_search_query(patient_context, radius_miles=radius_miles)

    # Fetch results
    response = fetch_clinical_trials(params)

    if response.get("error"):
        error_type = response["error"]
        error_messages = {
            "timeout": "The clinical trials database is taking longer than expected. Please try again in a moment.",
            "invalid_response": "Unable to process clinical trials data. Please try again.",
        }
        return {
            "trials": [],
            "total_found": 0,
            "search_criteria": params,
            "error": error_type,
            "error_message": error_messages.get(error_type, f"Error searching for trials: {error_type}")
        }

    studies = response.get("studies", [])

    # National fallback: if the geo-radius search returned nothing, retry
    # nationwide so we still surface trials. Distance is still computed
    # per-trial during ranking below, so nearby ones still float to the top.
    relaxed_location = False
    if not studies and radius_miles is not None:
        relaxed_location = True
        params = build_search_query(patient_context, radius_miles=None)
        response = fetch_clinical_trials(params)
        if response.get("error"):
            return {
                "trials": [], "total_found": 0, "search_criteria": params,
                "error": response["error"],
                "error_message": f"Error searching for trials: {response['error']}",
            }
        studies = response.get("studies", [])

    # Parse and score the FULL fetched set, then rank and keep the top N.
    trials = [parse_trial_result(s, preferred_state=patient_state, patient_zip=zip_code) for s in studies]
    for trial in trials:
        relevance = score_trial_relevance(trial, patient_context)
        score = relevance["score"]
        trial["relevance_score"] = score
        trial["relevance_reasons"] = relevance["reasons"]
        trial["relevance_warnings"] = relevance["warnings"]
        trial["likely_eligible"] = relevance["eligible"]
        # Nested object the frontend renders as a Strong/Moderate/General badge.
        # (Thresholds match format_trials_for_chat: >=70 strong, >=55 moderate.)
        trial["relevance"] = {
            "score": score,
            "band": "strong" if score >= 70 else "moderate" if score >= 55 else "general",
            "reasons": relevance["reasons"],
            "warnings": relevance["warnings"],
        }

    # Sort trials by relevance score (highest first), then keep the display cap
    trials.sort(key=lambda t: t.get("relevance_score", 0), reverse=True)
    trials = trials[:max_results]

    return {
        "trials": trials,
        "total_found": response.get("totalCount", len(studies)),
        "search_criteria": params,
        "radius_miles": None if relaxed_location else radius_miles,
        "relaxed_location": relaxed_location,
        "error": None,
        "error_message": None
    }


def count_trials_for_radii(patient_context: Dict[str, Any],
                           radii=(25, 50, 100, None)) -> Dict[str, Any]:
    """Total recruiting + interventional trial counts at each radius.

    Powers the reassuring "N recruiting trials within X miles" summary line.
    Cheap: pageSize=1, reads only totalCount, and fetch_clinical_trials caches
    each params combo — so repeat loads don't re-hit the API.
    """
    counts: Dict[str, Any] = {}
    for r in radii:
        key = "nationwide" if r is None else str(r)
        try:
            params = build_search_query(patient_context, page_size=1, radius_miles=r)
            resp = fetch_clinical_trials(params)
            counts[key] = resp.get("totalCount") if not resp.get("error") else None
        except Exception:
            counts[key] = None
    return counts


def format_trials_for_chat(trials_data: Dict[str, Any]) -> str:
    """
    Format clinical trials results for chat display.

    Args:
        trials_data: Result from search_trials_for_patient()

    Returns:
        Formatted markdown string for chat display
    """
    # Handle errors
    if trials_data.get("error"):
        if trials_data["error"] == "no_zip_code":
            return trials_data.get("error_message", "Please add your zip code to search for trials.")
        return trials_data.get("error_message", "Unable to search for clinical trials right now. Please try again later or visit [ClinicalTrials.gov](https://clinicaltrials.gov) directly.")

    trials = trials_data.get("trials", [])
    total_found = trials_data.get("total_found", 0)

    if not trials:
        return """I searched ClinicalTrials.gov but didn't find recruiting trials that closely match your specific profile criteria in your area. This doesn't mean there aren't options for you:

**Next Steps:**
- **Expand your search** at [ClinicalTrials.gov](https://clinicaltrials.gov/search?cond=colorectal+cancer&aggFilters=status:rec)
- **Try CCA Trial Finder** at [colorectalcancer.org](https://colorectalcancer.org/treatment/types-treatment/clinical-trials/clinical-trial-finder) for a guided search
- **NCI Trial Search** at [cancer.gov](https://www.cancer.gov/research/participate/clinical-trials-search)
- **Ask your oncologist** about trials at nearby academic cancer centers
- **Contact NCI** at 1-800-4-CANCER for personalized trial matching assistance

Your oncology team may also know of trials not yet listed or trials at partner institutions that could be a good fit for you."""

    # Format trials
    output = f"I found **{total_found}** recruiting clinical trial{'s' if total_found != 1 else ''} that may be relevant to your profile:\n\n"

    for i, t in enumerate(trials, 1):
        output += f"### {i}. {t['title']}\n"
        output += f"**NCT ID:** [{t['nct_id']}]({t['url']})\n"
        output += f"**Phase:** {t['phase']} | **Status:** {t['status']}\n"

        if t.get("locations"):
            loc = t["locations"][0]
            facility = loc.get("facility", "")
            city = loc.get("city", "")
            state = loc.get("state", "")
            distance = loc.get("distance_miles")
            location_str = ", ".join(filter(None, [facility, city, state]))
            if location_str:
                if distance is not None:
                    output += f"**Location:** {location_str} (~{distance} miles away)\n"
                else:
                    output += f"**Location:** {location_str}\n"

        # Show relevance match strength
        relevance_score = t.get("relevance_score", 50)
        if relevance_score >= 70:
            output += "**Match:** Strong match for your profile\n"
        elif relevance_score >= 55:
            output += "**Match:** Moderate match for your profile\n"
        else:
            output += "**Match:** General match\n"

        # Show relevance reasons (top 3)
        reasons = t.get("relevance_reasons", [])
        if reasons:
            output += "**Why it may fit:** " + "; ".join(reasons[:3]) + "\n"

        # Show warnings (top 2)
        warnings = t.get("relevance_warnings", [])
        if warnings:
            output += "**Note:** " + "; ".join(warnings[:2]) + "\n"

        # Eligibility flag
        if t.get("likely_eligible") is False:
            output += "**Eligibility concern:** Based on your profile, you may not meet some eligibility criteria. Discuss with your oncologist.\n"

        if t.get("brief_summary"):
            # Show first 200 chars of summary
            summary = t["brief_summary"][:200]
            if len(t["brief_summary"]) > 200:
                summary += "..."
            output += f"\n_{summary}_\n"

        output += f"\n[View Full Trial Details]({t['url']})\n\n---\n\n"

    output += """**Important Reminders:**
- Clinical trial information changes frequently — always verify availability directly with the trial site
- Eligibility depends on many factors beyond what we can assess here — your oncologist can review these with you
- Many trials cover the cost of the experimental treatment; standard-of-care costs are typically billed to insurance
- Ask the trial coordinator about financial assistance programs and travel grants

**Find More Trials:**
- [ClinicalTrials.gov](https://clinicaltrials.gov/search?cond=colorectal+cancer&aggFilters=status:rec)
- [CCA Trial Finder](https://colorectalcancer.org/treatment/types-treatment/clinical-trials/clinical-trial-finder)
- [NCI Trial Search](https://www.cancer.gov/research/participate/clinical-trials-search)"""

    return output


def is_clinical_trial_query(message: str) -> bool:
    """
    Detect if user is asking about clinical trials.

    Args:
        message: User's chat message

    Returns:
        True if message appears to be about clinical trials
    """
    message_lower = message.lower()

    # Direct trial keywords
    trial_keywords = [
        'clinical trial', 'clinical trials',
        'research study', 'research studies',
        'clinical study', 'clinical studies',
        'experimental treatment', 'experimental therapy',
        'investigational', 'trial eligibility',
        'enroll in a trial', 'participate in research',
        'find trials', 'search trials', 'trial options',
        'new treatments being tested', 'trials near me',
        'trial for my cancer', 'trials for colon cancer',
        'trials for colorectal',
        # Implicit trial interest indicators
        'new treatment options', 'new treatments available',
        'any new drugs', 'latest treatments', 'cutting edge',
        'novel therapy', 'novel treatment',
        'what else is out there', 'other options besides',
        'ran out of options', 'no more options',
        'anything else i can try', 'something new to try',
        'phase 1', 'phase 2', 'phase 3', 'phase i', 'phase ii', 'phase iii',
        'after standard treatment', 'beyond standard care',
        'research opportunities', 'studies near me'
    ]

    # Check for direct matches
    for keyword in trial_keywords:
        if keyword in message_lower:
            return True

    # Check for question patterns about trials
    trial_question_patterns = [
        ('trial', 'qualify'),
        ('trial', 'eligible'),
        ('trial', 'available'),
        ('trial', 'options'),
        ('study', 'participate'),
        ('study', 'enroll'),
    ]

    for pattern in trial_question_patterns:
        if all(word in message_lower for word in pattern):
            return True

    return False
