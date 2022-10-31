from enum import Enum
# Headers
HEADER_USER_AGENT = "K-Connect/5663 CFNetwork/1390 Darwin/22.0.0"
HEADER_OCP_SUBSCRIPTION_KEY = "6e2ad707ae5249089f9dbf8ed011c38c"

# API Values
API_URL = "https://iot.keurig.com/connected-platform/"
CLIENT_ID = "cbma-v1"

# Brew Temperatures
class Size(Enum):
    Four = 4,
    Six = 6,
    Eight = 8,
    Ten = 10,
    Twelve = 12

class Temperature(Enum):
    TEMPERATURE_WARM=187
    TEMPERATURE_WARMER=191
    TEMPERATURE_HOT=194
    TEMPERATURE_HOTTER=197
    TEMPERATURE_XHOT=200
    TEMPERATURE_MAXHOT=204

# Brew Intensities
class Intensity(Enum):
    BREW_BALANCED=4435
    BREW_RICH=3942
    BREW_ROBUST=3449
    BREW_STRONG=2957
    BREW_INTENSE=2464

# Commands
#Get high altitude setting
COMMAND_NAME_GET_PROP = "get_prop"
# Brew
COMMAND_NAME_BREW = "brew"
# Power on
COMMAND_NAME_ON = "idle"
# Power off
COMMAND_NAME_OFF = "standby"
# Cancel brew
COMMAND_NAME_CANCEL_BREW = "cancel_brew"

#Appliance Statuses
#Status off
STATUS_OFF = "STANDBY"
#Status on
STATUS_ON = "IDLE"
#Status brewing
STATUS_BREWING = "BREW"

#Brewer Statuses
# Brewer ready
BREWER_STATUS_READY = "BREW_READY"
#Brewer not ready
BREWER_STATUS_NOT_READY = "BREW_LOCKED"
# Brewer cancelling
BREWER_STATUS_CANCELLING = "BREW_CANCELING"
# Brewer brewing
BREWER_STATUS_BREWING = "BREW_IN_PROGRESS"
# Brewer complete
BREWER_STATUS_COMPLETE = "BREW_SUCCESSFUL"


#Brewer Not Ready/Cancelled Reasons
# Water resevoir is empty
BREWER_OUT_OF_WATER = "BREW_INSUFFICIENT_WATER"
# Water ran out
BREWER_INSUFFICIENT_WATER = "ADD_WATER"
# No pod loaded
BREWER_POD_NOT_REMOVED = "PM_NOT_CYCLED"
# Lid is open
BREWER_LID_OPEN = "PM_NOT_READY"

#Pod statuses
# No pod loaded
POD_STATUS_EMPTY = "EMPTY"
# Pod loaded
POD_STATUS_LOADED = "POD"
# Punched pod loaded
POD_STATUS_PUNCHED = "PUNCHED"

#Brew type
# Brew hot water
BREW_HOT_WATER = "HOT_WATER"
# Brew coffee
BREW_COFFEE = "NORMAL"
# Brew over ice
BREW_OVER_ICE = "ICED"

#Brew categories
# Hot water
BREW_CATEGORY_WATER = "WATER"
# Favorite brew
BREW_CATEGORY_FAVORITE = "FAVORITE"
# Custom brew
BREW_CATEGORY_CUSTOM = "CUSTOM"
# Iced coffee
BREW_CATEGORY_ICED = "ICED"
# Recommended brew
BREW_CATEGORY_RECOMMENDED = "MASTER"

# Appliance state
NODE_APPLIANCE_STATE = "appl_state"
NODE_BREW_STATE = "brew_state"
NODE_POD_STATE = "lid_recog_result"