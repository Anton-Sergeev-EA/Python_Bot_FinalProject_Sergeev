from telegram.ext import ConversationHandler
from enum import Enum

class AdCreationStates(Enum):
    TITLE = 1
    DESCRIPTION = 2
    PRICE = 3
    LOCATION = 4
    CONTACT_INFO = 5
    CONFIRM = 6

class AdEditingStates(Enum):
    SELECT_AD = 1
    SELECT_FIELD = 2
    EDIT_VALUE = 3
    CONFIRM = 4

class SearchStates(Enum):
    KEYWORDS = 1
    LOCATION = 2
    PRICE_MIN = 3
    PRICE_MAX = 4
    CATEGORY = 5
    RESULTS = 6

class FeedbackStates(Enum):
    RATING = 1
    COMMENT = 2
    CONFIRM = 3

class ModerationStates(Enum):
    SELECT_AD = 1
    REVIEW = 2
    DECISION = 3
    REJECTION_REASON = 4

# Conversation states as integers for Telegram.
AD_CREATION = [state.value for state in AdCreationStates]
AD_EDITING = [state.value for state in AdEditingStates]
SEARCH = [state.value for state in SearchStates]
FEEDBACK = [state.value for state in FeedbackStates]
MODERATION = [state.value for state in ModerationStates]

# End conversation.
END = ConversationHandler.END
